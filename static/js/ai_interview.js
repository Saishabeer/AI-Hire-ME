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

  // --- State ---
  let pc = null;
  let dc = null;
  let localStream = null;
  let remoteStream = null;
  let modelInUse = null;

  let paused = false;

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
    row.textContent = initialText || '';
    transcriptListEl.appendChild(row);
    scrollToBottom(transcriptListEl);
    return row;
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
      localStream = await navigator.mediaDevices.getUserMedia({ audio: true });
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
        // Start immediately; the strict question list is already in the server-side session instructions
        const startEvent = {
          type: 'response.create',
          response: {
            instructions: 'Start the interview now with question 1.',
            modalities: ['text', 'audio'],
          },
        };
        try {
          dc.send(JSON.stringify(startEvent));
        } catch (e) {
          log('Failed to send start event', { error: String(e) });
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

  function endRealtimeInterview() {
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

      // AI streaming text (delta-based)
      if (t.includes('response') && t.includes('delta')) {
        const chunk = textFromAny(msg);
        if (chunk && chunk !== lastAIDelta) {
          if (!aiStreamingEl) aiStreamingEl = addChatBubble('ai', '');
          if (aiStreamingEl) aiStreamingEl.textContent += chunk;
          lastAIDelta = chunk;
          if (aiStateEl) aiStateEl.textContent = 'speaking';
          scrollToBottom(transcriptListEl);
        }
        return;
      }

      // AI response completed
      if (t.includes('response') && t.includes('completed')) {
        aiStreamingEl = null;
        lastAIDelta = "";
        if (aiStateEl) aiStateEl.textContent = 'idle';
        return;
      }

      // User transcription completed (server-side VAD + whisper)
      if (t.includes('transcription') && t.includes('completed')) {
        const text = textFromAny(msg);
        if (text) {
          addChatBubble('user', text);
          acceptUserAnswerAndAdvance(text);
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
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', wire, { once: true });
  } else {
    wire();
  }
})();