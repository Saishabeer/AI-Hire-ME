(function bootstrap() {
  // If DOM not ready yet, wait for it
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bootstrap, { once: true });
    return;
  }

  // Simplified: realtime-only, no text mode

  const $ = (id) => document.getElementById(id);

  // Elements
  const interviewIdEl = $('interviewId');
  const aiAudio = $('aiAudio'); // Realtime audio via WebRTC
  const statusEl = $('status');
  const userTranscript = $('userTranscript');
  const aiTranscript = $('aiTranscript');
  // Minimal UI; no extra controls

  if (!aiAudio || !statusEl || !userTranscript || !aiTranscript) {
    // If critical elements are missing, do not continue
    console.warn('AI interview: required DOM elements not found');
    return;
  }

  // State
  let sessionId = null;
  let pc = null;
  let localStream = null;
  let remoteStream = null;
  let connected = false;
  let eventsChannel = null;
  let turnIndex = 0; // transcript turns
  let started = false;

  async function ensureMic() {
    // Ask for microphone permission early and cache the stream
    if (localStream) return localStream;
    try {
      localStream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true }
      });
      return localStream;
    } catch (e) {
      throw new Error('Microphone permission denied or unavailable');
    }
  }

  // No separate log; transcripts show text

  function setStatus(t) {
    try { if (statusEl) statusEl.textContent = t; } catch (_) {}
  }

  function append(el, t) {
    if (!el) return;
    try { el.textContent += t; el.scrollTop = el.scrollHeight; } catch (_) {}
  }
  function appendLine(el, t) { append(el, (t || '') + '\n'); }

  // Ensure AI audio element is ready for autoplay
  try {
    aiAudio.autoplay = true;
    aiAudio.playsInline = true;
    aiAudio.muted = false;
    aiAudio.volume = 1.0;
  } catch (_) {}

  function getInterviewIdFallback() {
    // 1) Hidden input
    const byInput = (interviewIdEl && interviewIdEl.value) ? interviewIdEl.value.trim() : '';
    if (byInput) return byInput;
    // 2) URL path like /interviews/123/ai-interview/
    try {
      const m = (location.pathname || '').match(/interviews\/(\d+)\//);
      if (m && m[1]) return m[1];
    } catch (_) {}
    return '';
  }

  async function safeJson(res) {
    try { return await res.json(); } catch { return {}; }
  }

  function getQueryParam(key) {
    try {
      const params = new URLSearchParams(window.location.search || '');
      return (params.get(key) || '').trim();
    } catch (_) { return ''; }
  }

  async function startInterview() {
    if (started) return;
    // Pre-warm audio element to reduce autoplay issues
    try { await aiAudio.play().catch(() => {}); } catch (_) {}

    const name = getQueryParam('name');
    const email = getQueryParam('email');
    const interviewId = getInterviewIdFallback();

    if (!interviewId) {
      alert('Missing interview id. Reload the page.');
      return;
    }

    setStatus('Initializing…');
    started = true;

    const fd = new FormData();
    fd.append('name', name);
    fd.append('email', email);
    fd.append('interview_id', interviewId);
    // POST session init

    // Mic is required for realtime
    try {
      await ensureMic();
    } catch (e) {
      setStatus('Microphone permission denied.');
      started = false;
      return;
    }

    // 1) Initialize session and play first question TTS from server
    const res = await fetch('/interviews/ai-interview/init/', { method: 'POST', body: fd });
    const data = await safeJson(res);
    if (!res.ok) {
      alert(data.error || 'Failed to start');
      started = false;
      return;
    }

    sessionId = data.session_id;
    if (data.assistant_text) { appendLine(aiTranscript, data.assistant_text); }

    // 2) Mint ephemeral realtime token to enable live audio
    const fd2 = new FormData();
    fd2.append('session_id', sessionId);
    fd2.append('name', name);
    fd2.append('email', email);
    fd2.append('interview_id', interviewId);

    setStatus('Creating realtime session…');
    const tokRes = await fetch('/interviews/ai-interview/realtime/session/', { method: 'POST', body: fd2 });
    const tok = await safeJson(tokRes);
    if (!tokRes.ok) {
      const msg = tok?.error || 'Failed to create realtime session';
      try { console.warn('[AI Interview] Realtime token error', tokRes.status, msg); } catch (_) {}
      setStatus('Realtime error: ' + msg);
      started = false;
      return;
    }

    try {
      await connectRealtime(tok.token, tok.model, tok.instructions, tok.voice);
      setStatus('Live. Speak to your mic.');
    } catch (e) {
      try { console.warn('[AI Interview] Realtime connection failed', e); } catch (_) {}
      cleanupPeer();
      setStatus('Realtime connection failed.');
      started = false;
    }
  }

  function autoStartIfReady() {
    const iid = getInterviewIdFallback();
    if (iid) startInterview();
  }

  async function connectRealtime(ephemeralToken, model, sessionInstructions, sessionVoice) {
    // Get or reuse mic stream
    if (!localStream) {
      localStream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true }
      });
    }

    // Prepare peer connection
    pc = new RTCPeerConnection({
      iceServers: [{ urls: 'stun:stun.l.google.com:19302' }]
    });

    // Data channel to instruct the model and receive events/text
    pc.ondatachannel = (event) => {
      try {
        const ch = event.channel;
        if (ch && ch.label === 'oai-events') attachEventsChannel(ch, sessionInstructions, sessionVoice);
      } catch (_) {}
    };
    const proactive = pc.createDataChannel('oai-events');
    attachEventsChannel(proactive, sessionInstructions, sessionVoice);

    // Attach mic (sendonly) and request a recvonly m-line for remote audio
    const audioTrack = localStream.getAudioTracks()[0];
    if (audioTrack) {
      try { audioTrack.contentHint = 'speech'; } catch (_) {}
      const tx = pc.addTransceiver('audio', { direction: 'sendonly' });
      try { await tx.sender.replaceTrack(audioTrack); } catch (_) { /* fallback below */ }
      if (!tx.sender.track) {
        try { pc.addTrack(audioTrack, localStream); } catch (_) {}
      }
    }
    try { pc.addTransceiver('audio', { direction: 'recvonly' }); } catch (_) {}

    // Receive AI audio
    remoteStream = new MediaStream();
    try { aiAudio.srcObject = remoteStream; } catch (e) { console.warn('set srcObject failed', e); }
    pc.addEventListener('track', (event) => {
      try {
        if (event.track && event.track.kind === 'audio') {
          remoteStream.addTrack(event.track);
        }
        if (event.streams && event.streams[0]) {
          event.streams[0].getAudioTracks().forEach((track) => {
            if (!remoteStream.getTracks().includes(track)) {
              remoteStream.addTrack(track);
            }
          });
        }
        try { aiAudio.play().catch((e) => console.warn('aiAudio.play failed', e)); } catch (err) { console.warn('aiAudio.play threw', err); }
      } catch (e) { console.warn('ontrack error', e); }
    });

    pc.onconnectionstatechange = () => {
      if (pc.connectionState === 'failed' || pc.connectionState === 'disconnected' || pc.connectionState === 'closed') {
        cleanupPeer();
        setStatus('Disconnected.');
      }
    };
    pc.oniceconnectionstatechange = () => { try { console.log('ICE state:', pc.iceConnectionState); } catch (_) {} };

    // Create SDP offer and wait for ICE gathering complete (non-trickle)
    const offer = await pc.createOffer();
    await pc.setLocalDescription(offer);
    await new Promise((resolve) => {
      if (pc.iceGatheringState === 'complete') return resolve();
      const check = () => {
        if (pc.iceGatheringState === 'complete') {
          pc.removeEventListener('icegatheringstatechange', check);
          resolve();
        }
      };
      pc.addEventListener('icegatheringstatechange', check);
      // Give ICE more time to gather for reliability on some networks
      setTimeout(resolve, 10000);
    });

    // Exchange SDP with OpenAI Realtime
    const resp = await fetch(`https://api.openai.com/v1/realtime?model=${encodeURIComponent(model || 'gpt-4o-realtime-preview-2024-12-17')}`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${ephemeralToken}`,
        'Content-Type': 'application/sdp',
        'Accept': 'application/sdp',
        'OpenAI-Beta': 'realtime=v1'
      },
      body: pc.localDescription.sdp
    });
    if (!resp.ok) {
      const errText = await resp.text();
      throw new Error('SDP exchange failed: ' + errText);
    }
    const answerSDP = await resp.text();
    await pc.setRemoteDescription({ type: 'answer', sdp: answerSDP });
    connected = true;
    console.log('WebRTC connected');
  }

  function attachEventsChannel(ch, sessionInstructions, sessionVoice) {
    eventsChannel = ch;
    eventsChannel.onopen = () => {
      setStatus('Connected.');
      try {
        const reinforce = ' Then ASK ONLY THE FIRST QUESTION from the HR-provided list (in strict order). Do not invent or reword any question.';
        const instr = ((sessionInstructions || '') + ' ' + reinforce).trim();
        eventsChannel.send(JSON.stringify({
          type: 'response.create',
          response: {
            conversation: 'default',
            instructions: instr,
            modalities: ['audio', 'text'],
            audio: { voice: (sessionVoice || 'alloy') }
          }
        }));
      } catch (e) { console.warn('oai-events send failed', e); }
    };
    eventsChannel.onmessage = (e) => {
      try {
        const evt = JSON.parse(e.data);
        handleRealtimeEvent(evt);
      } catch (_) {}
    };
    eventsChannel.onerror = (e) => { try { console.error('oai-events error', e); } catch (_) {} };
  }

  function handleRealtimeEvent(evt) {
    const t = (evt && evt.type) || '';
    // Live user transcription
    if (t.indexOf('transcription.delta') !== -1) {
      const textU = extractText(evt);
      if (textU) append(userTranscript, textU);
      return;
    }
    if (t.indexOf('transcription.completed') !== -1) {
      appendLine(userTranscript, '');
      turnIndex += 1;
      return;
    }
    // Assistant text
    if (t === 'response.output_text.delta' || (t.indexOf('response.') === 0 && t.indexOf('.delta') === t.length - 6)) {
      const textA = extractText(evt);
      if (textA) append(aiTranscript, textA);
      return;
    }
    if (t === 'response.output_text.done' || t === 'response.completed') {
      appendLine(aiTranscript, '');
      turnIndex += 1;
      return;
    }
  }

  function extractText(evt) {
    if (!evt || typeof evt !== 'object') return null;
    if (typeof evt.delta === 'string') return evt.delta;
    if (evt.delta && typeof evt.delta.text === 'string') return evt.delta.text;
    if (typeof evt.text === 'string') return evt.text;
    if (typeof evt.transcript === 'string') return evt.transcript;
    if (evt.output_text && Array.isArray(evt.output_text)) return evt.output_text.join('');
    return null;
  }

  function cleanupPeer() {
    connected = false;
    try { if (pc) pc.onconnectionstatechange = null; } catch (_) {}
    try { if (pc) pc.close(); } catch (_) {}
    pc = null;
    try { if (eventsChannel) eventsChannel.close(); } catch (_) {}
    eventsChannel = null;
    try { if (localStream) localStream.getTracks().forEach(t => t.stop()); } catch (_) {}
    localStream = null;
    try {
      if (remoteStream) {
        remoteStream.getTracks().forEach((t) => t.stop());
      }
    } catch (_) {}
    remoteStream = null;
    try { if (aiAudio) aiAudio.srcObject = null; } catch (_) {}
    setStatus('Idle');
  }
  // Auto-start immediately
  try { autoStartIfReady(); } catch (_) {}
})();
