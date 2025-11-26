/**
 * Live AI Interview UI + WebRTC client
 * - Two-panel layout: Collected Info (left) + Voice Chat transcript (right)
 * - Section tabs at top with answered/total counts
 * - Autostarts the realtime session; Pause/End controls available
 *
 * Reads config from #ai-interview-root data attributes:
 *   - data-session-url: Django endpoint that mints the ephemeral token
 *   - data-interview-id: numeric interview id
 */
(() => {
  const root = document.getElementById('ai-interview-root');
  if (!root) return;

  // --- DOM Elements ---
  const micStateEl = document.getElementById('mic-state');
  const connStateEl = document.getElementById('conn-state');
  const aiStateEl = document.getElementById('ai-state');
  const logsEl = null; // logs removed from UI

  const transcriptListEl = document.getElementById('transcript-list');
  const collectedInfoEl = document.getElementById('collected-info');
  const tabsEl = document.getElementById('section-tabs');
  const statusPill = document.getElementById('status-pill');

  const connectBtn = document.getElementById('connect-interview');
  const pauseBtn = document.getElementById('pause-interview');
  const endBtn = document.getElementById('end-interview');

  // --- Config ---
  const sessionUrl = root.dataset.sessionUrl || '';
  const interviewId = Number(root.dataset.interviewId || 0);
  const submitUrl = root.dataset.submitUrl || '';
  const responsesUrl = root.dataset.responsesUrl || '';
  const candidateName = root.dataset.candidateName || '';
  const candidateEmail = root.dataset.candidateEmail || '';
  // Centralized prompt templates provided by server (fallbacks included)
  const firstUttTpl = root.dataset.firstUttTemplate || 'Your first utterance must be exactly: "${Q}". Output nothing else. Ask ONE question per turn only.';
  const verbatimTpl = root.dataset.verbatimTemplate || 'Say exactly: "${Q}". Output only that question and nothing else. Do not add any words, prefixes, postfixes, or extra punctuation.';
  // (templates defined above)

  // --- State ---
  let pc = null;
  let dc = null;
  let localStream = null;
  let remoteStream = null;
  let modelInUse = null;

  let paused = false;
  let submitted = false;
  let isAsking = false;
  let lastTranscript = "";
  let expectedQ = "";
  let allowGreeting = false;
  let aiAccum = "";

  // Ordered list of QA DOM nodes across all sections
  const QA_NODES = Array.from(document.querySelectorAll('#collected-info .qa'));
  const SECTION_TABS = Array.from(document.querySelectorAll('.section-tab'));

  // Pointer to the "current" question index in QA_NODES
  let currentIdx = 0;

  // Accumulator for AI streaming text
  let aiStreamingEl = null;
  let lastAIDelta = "";

  // --- Utilities ---
  function log(line, obj) {
    try {
      // UI logs removed; keep quiet console debug for developers
      if (obj !== undefined) {
        console.debug('[AI Interview]', line, obj);
      } else {
        console.debug('[AI Interview]', line);
      }
    } catch (_) {}
  }



  // Replace ${Q} in a template with the exact question text
  function fillTpl(tpl, q) {
    try {
      return String(tpl || '').replaceAll('${Q}', String(q || ''));
    } catch (_) {
      return String(tpl || '');
    }
  }

  function setPill(state) {
    // states: disconnected, connecting, connected, paused, error
    if (!statusPill) return;
    statusPill.classList.remove('pill-red', 'pill-green', 'pill-yellow');
    let text = 'Disconnected';
    if (state === 'connecting')      { statusPill.classList.add('pill-yellow'); text = 'Connecting'; }
    else if (state === 'connected')  { statusPill.classList.add('pill-green');  text = 'Connected'; }
    else if (state === 'paused')     { statusPill.classList.add('pill-yellow'); text = 'Paused'; }
    else if (state === 'error')      { statusPill.classList.add('pill-red');    text = 'Error'; }
    else                             { statusPill.classList.add('pill-red');    text = 'Disconnected'; }
    statusPill.textContent = text;
  }

  function scrollToBottom(el) {
    try {
      el.scrollTop = el.scrollHeight;
    } catch (_) {}
  }

  function textFromAny(obj) {
    // Attempt to extract meaningful text from various realtime event payloads
    if (!obj) return '';
    if (typeof obj === 'string') return obj;
    if (obj.text) return String(obj.text);
    if (obj.transcript) return String(obj.transcript);
    if (obj.delta) return String(obj.delta);
    if (obj.value && typeof obj.value.text === 'string') return obj.value.text;
    if (Array.isArray(obj.output_text) && obj.output_text.length) return obj.output_text.join('');
    if (obj.output && typeof obj.output.text === 'string') return obj.output.text;
    try {
      return JSON.stringify(obj);
    } catch {
      return String(obj);
    }
  }

  function addChatBubble(role, initialText = '') {
    // role: 'ai' | 'user'
    if (!transcriptListEl) return null;
    const row = document.createElement('div');
    row.className = role === 'ai' ? 'bubble bubble-ai align-left' : 'bubble bubble-user align-right';
    const label = role === 'ai' ? 'AI: ' : 'You: ';
    row.textContent = label + (initialText || '');
    transcriptListEl.appendChild(row);
    scrollToBottom(transcriptListEl);
    return row;
  }

// Toggle microphone tracks
function setMicEnabled(enabled) {
  try {
    const tracks = (localStream && localStream.getAudioTracks && localStream.getAudioTracks()) || [];
    tracks.forEach(t => t.enabled = !!enabled);
    if (micStateEl) micStateEl.textContent = enabled ? 'on' : 'muted';
  } catch (_) {}
}

// Normalize text for echo checks
function normalizeText(s) {
  try {
    return String(s || '')
      .toLowerCase()
      .replace(/[^a-z0-9\\s]/g, '')
      .replace(/\\s+/g, ' ')
      .trim();
  } catch (_) { return String(s || ''); }
}
  // Toggle microphone tracks
  function setMicEnabled(enabled) {
    try {
      const tracks = (localStream && localStream.getAudioTracks && localStream.getAudioTracks()) || [];
      tracks.forEach(t => t.enabled = !!enabled);
      if (micStateEl) micStateEl.textContent = enabled ? 'on' : 'muted';
    } catch (_) {}
  }

  // Normalize text for echo checks
  function normalizeText(s) {
    try {
      return String(s || '')
        .toLowerCase()
        .replace(/[^a-z0-9\s]/g, '')
        .replace(/\s+/g, ' ')
        .trim();
    } catch (_) { return String(s || ''); }
  }

  // Toggle microphone tracks
  function setMicEnabled(enabled) {
    try {
      const tracks = (localStream && localStream.getAudioTracks && localStream.getAudioTracks()) || [];
      tracks.forEach(t => t.enabled = !!enabled);
      if (micStateEl) micStateEl.textContent = enabled ? 'on' : 'muted';
    } catch (_) {}
  }

  // Normalize text for echo checks
  function normalizeText(s) {
    try {
      return String(s || '')
        .toLowerCase()
        .replace(/[^a-z0-9\s]/g, '')
        .replace(/\s+/g, ' ')
        .trim();
    } catch (_) { return String(s || ''); }
  }

  // Local English TTS for greeting + verbatim HR questions (mutes mic during TTS)
  function speakText(text, onend) {
    try {
      setMicEnabled(false);
      const utter = new SpeechSynthesisUtterance(String(text || ''));
      utter.lang = 'en-US';
      utter.rate = 1.0;
      utter.pitch = 1.0;
      const voices = (window.speechSynthesis && window.speechSynthesis.getVoices && window.speechSynthesis.getVoices()) || [];
      const enVoice = voices.find(v => (v.lang || '').toLowerCase().startsWith('en')) || voices[0] || null;
      if (enVoice) utter.voice = enVoice;
      utter.onend = () => {
        try {
          setMicEnabled(true);
          if (typeof onend === 'function') onend();
        } catch (_) {}
      };
      window.speechSynthesis.speak(utter);
    } catch (e) {
      console.error('Local TTS error', e);
      try { setMicEnabled(true); if (typeof onend === 'function') onend(); } catch (_) {}
    }
  }

  function updateActiveQuestionHighlight() {
    QA_NODES.forEach(n => n.classList.remove('active'));
    const node = QA_NODES[currentIdx];
    if (node) {
      node.classList.add('active');
      node.scrollIntoView({ block: 'center', behavior: 'smooth' });
    }
    // Update active section tab
    const secId = node ? String(node.dataset.sectionId || '') : '';
    SECTION_TABS.forEach(tab => tab.classList.toggle('active', String(tab.dataset.sectionId) === secId));
  }

  function updateTabCounts() {
    SECTION_TABS.forEach(tab => {
      const secId = String(tab.dataset.sectionId);
      const total = Number(tab.dataset.total || 0);
      let answered = 0;
      QA_NODES.forEach(qa => {
        if (String(qa.dataset.sectionId) === secId) {
          const ans = qa.querySelector('.answer');
          if (ans && String(ans.textContent || '').trim().length > 0) answered += 1;
        }
      });
      const answeredEl = tab.querySelector('.answered');
      if (answeredEl) answeredEl.textContent = String(answered);
      tab.dataset.answered = String(answered);
      tab.classList.toggle('done', answered >= total && total > 0);
    });
  }

  function acceptUserAnswerAndAdvance(text) {
    // Write transcript to current QA answer and move pointer
    const qa = QA_NODES[currentIdx];
    if (qa) {
      const ansEl = qa.querySelector('.answer');
      if (ansEl) ansEl.textContent = text;
    }
    updateTabCounts();
    currentIdx = Math.min(currentIdx + 1, Math.max(0, QA_NODES.length - 1));
    updateActiveQuestionHighlight();
  }

  // Collect answers from the on-page QA list into a compact JSON structure
  function collectAnswersFromDom() {
    const out = [];
    QA_NODES.forEach((qa) => {
      const qid = Number(qa.dataset.questionId || qa.getAttribute('data-question-id') || 0);
      const ansEl = qa.querySelector('.answer');
      const text = String((ansEl && ansEl.textContent) || '').trim();
      if (qid > 0) {
        out.push({ question: qid, text, option_values: [] });
      }
    });
    return out;
  }

  // Build a simple transcript string from the chat bubbles
  function collectTranscriptText() {
    const rows = Array.from(document.querySelectorAll('#transcript-list .bubble'));
    return rows.map(r => String(r.textContent || '').trim()).filter(Boolean).join('\n');
  }

  async function submitPayload(source = 'realtime') {
    if (!submitUrl || submitted) return;
    const payload = {
      candidate_name: candidateName || 'Anonymous',
      candidate_email: candidateEmail || 'anonymous@example.com',
      answers: collectAnswersFromDom(),
      transcript: collectTranscriptText(),
      source
    };
    try {
      const resp = await fetch(submitUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!resp.ok) {
        const t = await resp.text().catch(() => '');
        console.error('Failed to submit interview JSON', t);
        return;
      }
      let data = null;
      try {
        data = await resp.json();
      } catch (_) {
        data = null;
      }
      submitted = true;
      const nextUrl = (data && data.receipt_url) ? data.receipt_url : (responsesUrl || '');
      if (nextUrl) {
        window.location.href = nextUrl;
      }
    } catch (e) {
      console.error('Submit error', e);
    }
  }

  // --- RTC / Realtime ---
  async function createSession() {
    const resp = await fetch(sessionUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }, // CSRF exempt server-side for this endpoint
      body: JSON.stringify({ interview_id: interviewId }),
    });
    if (!resp.ok) {
      const t = await resp.text().catch(() => '');
      throw new Error('Failed to create realtime session: ' + t);
    }
    return resp.json();
  }

  async function startRealtimeInterview() {
    try {
      setPill('connecting');
      if (connectBtn) { connectBtn.disabled = true; connectBtn.innerHTML = '<i class="fas fa-play"></i> Connecting…'; }
      if (connStateEl) connStateEl.textContent = 'creating-session';

      const session = await createSession();
      const ephemeralKey = (session.client_secret && session.client_secret.value) || session.client_secret;
      modelInUse = session.model || 'gpt-4o-realtime-preview-2024-12-17';
      log('Ephemeral session created', { model: modelInUse });

      // Get mic once
      localStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: false,
          channelCount: 1,
          sampleRate: 16000,
          sampleSize: 16,
        }
      });
      if (micStateEl) micStateEl.textContent = 'on';

      // Peer connection
      pc = new RTCPeerConnection({ iceServers: [{ urls: ['stun:stun.l.google.com:19302'] }] });
      pc.onconnectionstatechange = () => {
        if (connStateEl) connStateEl.textContent = pc.connectionState;
        log('RTCPeerConnection state', { state: pc.connectionState });
        if (pc.connectionState === 'connected') setPill('connected');
        if (pc.connectionState === 'failed' || pc.connectionState === 'disconnected') setPill('error');
      };

      // Remote audio
      remoteStream = new MediaStream();
      const audioEl = document.getElementById('ai-remote-audio');
      if (audioEl) audioEl.srcObject = remoteStream;

      pc.ontrack = (e) => {
        if (aiStateEl) aiStateEl.textContent = 'speaking';
        remoteStream.addTrack(e.track);
        e.track.onended = () => {
          if (aiStateEl) aiStateEl.textContent = 'idle';
        };
      };

      // Attach local mic
      localStream.getTracks().forEach((t) => pc.addTrack(t, localStream));

      // Data channel for control + event streaming
      dc = pc.createDataChannel('oai-events');
      dc.onopen = () => {
        log('Data channel open.');
        // Determine exact first question from UI
        const firstQA = QA_NODES[0] || null;
        const firstQText = firstQA ? String(firstQA.querySelector('.bubble-q')?.textContent || '').trim() : '';
        const prompt = firstQText
          ? `Ask exactly this question with no greeting, no preamble, no paraphrasing, and do not chain multiple questions: "${firstQText}". Respond only with that question.`
          : 'Ask the first question from the provided list exactly as written. Respond only with that question.';


        // 0) Set first-utterance hard rule on session (defensive)
        try {
          const sys = firstQText
            ? fillTpl(firstUttTpl, firstQText)
            : 'Your first utterance must be the first question exactly as written. Output nothing else. Ask ONE question per turn only.';
          dc.send(JSON.stringify({ type: 'session.update', session: { instructions: sys } }));
        } catch (_) {}

        // 1) Cancel any pending/implicit responses
        try { dc.send(JSON.stringify({ type: 'response.cancel' })); } catch (_) {}

        // 3) Speak immediately (no delay) for natural turn-taking
        try {
          const greeting = "Hello, let's begin.";
          expectedQ = firstQText || '';
          allowGreeting = true;
          const display = expectedQ ? (greeting + ' ' + expectedQ) : greeting;
          addChatBubble('ai', display);
          isAsking = true;
          speakText(display, () => { isAsking = false; });
        } catch (e) {
          log('Failed to start local TTS', { error: String(e) });
        }
      };

      dc.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data);
          handleRealtimeEvent(msg);
        } catch {
          log('Non-JSON message from model', { data: ev.data });
        }
      };

      dc.onclose = () => log('Data channel closed.');

      // SDP offer/answer with OpenAI Realtime
      const offer = await pc.createOffer({ offerToReceiveAudio: true, offerToReceiveVideo: false });
      await pc.setLocalDescription(offer);

      const sdpResp = await fetch(`https://api.openai.com/v1/realtime?model=${encodeURIComponent(modelInUse)}`, {
        method: 'POST',
        body: offer.sdp,
        headers: {
          Authorization: `Bearer ${ephemeralKey}`,
          'Content-Type': 'application/sdp',
        },
      });
      if (!sdpResp.ok) throw new Error(await sdpResp.text());
      const answer = await sdpResp.text();
      await pc.setRemoteDescription({ type: 'answer', sdp: answer });

      window.__aiInterviewEnd__ = endRealtimeInterview;
      if (connStateEl) connStateEl.textContent = 'connected';
      setPill('connected');
      if (connectBtn) { connectBtn.disabled = true; connectBtn.innerHTML = '<i class="fas fa-check"></i> Connected'; }
      if (pauseBtn) pauseBtn.disabled = false;
      if (endBtn) endBtn.disabled = false;
      log('Interview connected.');

      // Initialize UI pointers
      updateTabCounts();
      updateActiveQuestionHighlight();
    } catch (e) {
      console.error('Realtime interview failed to start:', e);
      // No alerts; reflect error in status pill and connection text
      if (connStateEl) connStateEl.textContent = 'error';
      setPill('error');
      if (connectBtn) { connectBtn.disabled = false; connectBtn.innerHTML = '<i class="fas fa-play"></i> Connect'; }
      if (pauseBtn) pauseBtn.disabled = true;
      if (endBtn) endBtn.disabled = true;
      log('Error', { error: (e && e.message) || String(e) });
    }
  }

  async function endRealtimeInterview() {
    // Attempt to submit transcript + answers JSON before tearing down UI
    try { await submitPayload('realtime'); } catch (e) { console.error('Submit during end failed', e); }
    try {
      if (dc && dc.readyState === 'open') dc.close();
    } catch {}
    try {
      if (pc) pc.close();
    } catch {}
    try {
      if (localStream) localStream.getTracks().forEach((t) => t.stop());
    } catch {}
    pc = null;
    dc = null;
    localStream = null;
    remoteStream = null;
    if (micStateEl) micStateEl.textContent = 'off';
    if (aiStateEl) aiStateEl.textContent = 'idle';
    if (connStateEl) connStateEl.textContent = 'closed';
    setPill('disconnected');
    if (connectBtn) { connectBtn.disabled = false; connectBtn.innerHTML = '<i class="fas fa-play"></i> Connect'; }
    if (pauseBtn) { pauseBtn.disabled = true; pauseBtn.innerHTML = '<i class="fas fa-pause"></i> Pause'; }
    if (endBtn) endBtn.disabled = true;
    log('Interview ended.');
  }

  function handleRealtimeEvent(msg) {
    // Generic handler robust to minor schema changes
    // Common events (names may differ across previews):
    // - response.output_text.delta { delta: "..." }
    // - response.delta { delta: "..." }
    // - response.completed
    // - input_audio_transcription.completed { text: "..." } (server-side whisper)
    // - conversation.item.input_audio_transcription.completed { transcript: "..." }
    try {
      const t = (msg.type || '').toLowerCase();
      // Barge-in: if user transcription deltas arrive while AI is speaking, cancel local TTS immediately
      if (t.includes('transcription') && t.includes('delta')) {
        if (isAsking) {
          try { window.speechSynthesis.cancel(); } catch (_) {}
          isAsking = false;
          setMicEnabled(true);
        }
        // Ignore delta rendering; we wait for 'transcription.completed'
        return;
      }
      // Ignore any model-generated text deltas; client controls AI transcript output
      if (t.includes('response') && t.includes('delta')) {
        return;
      }

      // AI streaming text (delta-based)
      if (t.includes('response') && t.includes('delta')) {
        // Ignore model deltas completely; client controls transcript output
        return;
      }

      // AI response completed
      if (t.includes('response') && t.includes('completed')) {
        aiStreamingEl = null;
        lastAIDelta = "";
        isAsking = false;
        if (aiStateEl) aiStateEl.textContent = 'idle';
        return;
      }

      // User transcription completed (server-side VAD + whisper)
      if (t.includes('transcription') && t.includes('completed')) {
        const text = textFromAny(msg);
        if (text) {
          // Ignore while AI is speaking (prevents echo of our own TTS)
          if (isAsking) return;
          // Deduplicate repeated transcripts
          if (text === lastTranscript) return;
          // Ignore echo of AI question (e.g., mic captured speaker output)
          const nText = normalizeText(text);
          const nExpected = normalizeText(expectedQ);
          if (nExpected && (nText === nExpected || nText.includes(nExpected))) {
            return;
          }
          lastTranscript = text;
          // Record candidate answer and advance pointer
          addChatBubble('user', text);
          acceptUserAnswerAndAdvance(text);

          // Determine the next unanswered question (avoid repeating last question)
          const nextUnanswered = QA_NODES.find(qa => {
            const ans = qa.querySelector('.answer');
            return !ans || String(ans.textContent || '').trim().length === 0;
          }) || null;

          // If no questions remain unanswered, end and submit
          if (!nextUnanswered) {
            endRealtimeInterview();
            return;
          }

          // Move pointer to first unanswered and ask it verbatim
          currentIdx = Math.max(0, QA_NODES.indexOf(nextUnanswered));
          updateActiveQuestionHighlight();

          const nextQText = String(nextUnanswered.querySelector('.bubble-q')?.textContent || '').trim();
          if (nextQText && dc && dc.readyState === 'open' && !isAsking) {
            // Cancel any pending output
            try { dc.send(JSON.stringify({ type: 'response.cancel' })); } catch (_) {}

            // Create a response that speaks the exact next question and nothing else
            try {
              expectedQ = nextQText;
              const display = expectedQ;
              addChatBubble('ai', display);
              isAsking = true;
              speakText(display, () => { isAsking = false; });
            } catch (e) {
              log('Failed to start local TTS for next question', { error: String(e) });
            }
          }
        }
        return;
      }

    } catch (err) {
      log('handleRealtimeEvent error', { error: String(err) });
    }
  }

  // --- Controls ---
  function togglePause() {
    paused = !paused;
    const tracks = (localStream && localStream.getAudioTracks && localStream.getAudioTracks()) || [];
    tracks.forEach(t => t.enabled = !paused);
    if (micStateEl) micStateEl.textContent = paused ? 'paused' : 'on';
    if (pauseBtn) pauseBtn.innerHTML = paused
      ? '<i class="fas fa-play"></i> Resume'
      : '<i class="fas fa-pause"></i> Pause';
    setPill(paused ? 'paused' : 'connected');
  }

  function wire() {
    if (connectBtn) connectBtn.addEventListener('click', startRealtimeInterview);
    if (pauseBtn) pauseBtn.addEventListener('click', togglePause);
    if (endBtn) endBtn.addEventListener('click', endRealtimeInterview);

    // Clicking a section tab scrolls to its first unanswered question
    if (tabsEl) {
      tabsEl.addEventListener('click', (e) => {
        const tab = e.target.closest('.section-tab');
        if (!tab) return;
        const secId = String(tab.dataset.sectionId);
        // Find first unanswered QA in this section
        const firstUnanswered = QA_NODES.find(qa => String(qa.dataset.sectionId) === secId && String(qa.querySelector('.answer')?.textContent || '').trim().length === 0);
        const target = firstUnanswered || QA_NODES.find(qa => String(qa.dataset.sectionId) === secId) || null;
        if (!target) return;
        currentIdx = Math.max(0, QA_NODES.indexOf(target));
        updateActiveQuestionHighlight();
      });
    }

    // No autostart; wait for explicit Connect
    setPill('disconnected');
    if (connStateEl) connStateEl.textContent = 'idle';

    // Guard: no questions configured
    if (QA_NODES.length === 0) {
      addChatBubble('ai', 'No questions are configured for this interview.');
      if (connectBtn) connectBtn.disabled = true;
      if (connStateEl) connStateEl.textContent = 'no-questions';
      return;
    }

    // Attempt to auto-start immediately so AI initiates the first question
    // If the browser blocks mic without user gesture, the Connect button remains available as fallback.
    try {
      if (connectBtn && !connectBtn.disabled) {
        startRealtimeInterview();
      }
    } catch (_) {}
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', wire, { once: true });
  } else {
    wire();
  }
})();
