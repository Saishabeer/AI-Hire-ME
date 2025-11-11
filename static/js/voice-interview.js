/* Minimal Voice Interview Client
 * - WebRTC recording via MediaRecorder
 * - Whisper transcription via /interviews/ai-interview/transcribe/
 * - GPT conversation via /interviews/ai-interview/respond/
 * - TTS playback via audio_base64 from server
 *
 * HTML element IDs expected (see templates/interviews/ai_voice_interview.html):
 *  - #name, #email, #startBtn
 *  - #holdToTalk (press-and-hold to answer)
 *  - #player (HTMLAudioElement)
 *  - #log (container for messages)
 */

(function () {
  const $ = (id) => document.getElementById(id);

  // Elements
  const nameEl = $('name');
  const emailEl = $('email');
  const interviewIdEl = $('interviewId');
  const startBtn = $('startBtn');
  const talkBtn = $('holdToTalk');
  const player = $('player');
  const logEl = $('log');

  // State
  let sessionId = null;
  let mediaRecorder = null;
  let chunks = [];
  let recording = false;
  let speaking = false;

  function log(role, text) {
    const p = document.createElement('p');
    p.className = role === 'user' ? 'user' : 'assistant';
    p.textContent = (role === 'user' ? 'You: ' : 'AI: ') + text;
    logEl.appendChild(p);
    logEl.scrollTop = logEl.scrollHeight;
  }

  function playBase64(b64) {
    try {
      const src = `data:audio/mp3;base64,${b64}`;
      player.src = src;
      const p = player.play();
      if (p && typeof p.catch === 'function') {
        p.catch(() => new Audio(src).play().catch(() => {}));
      }
    } catch (e) {
      try { new Audio(`data:audio/mp3;base64,${b64}`).play().catch(() => {}); } catch (_) {}
    }
  }

  async function startInterview() {
    const name = (nameEl.value || '').trim();
    const email = (emailEl.value || '').trim();
    const interviewId = (interviewIdEl && interviewIdEl.value) ? interviewIdEl.value.trim() : '';
    if (!name || !email) {
      alert('Enter your name and email');
      return;
    }
    if (!interviewId) {
      alert('Missing interview id. Reload the page.');
      return;
    }

    // Pre-request mic permission to avoid browser block later
    try {
      const s = await navigator.mediaDevices.getUserMedia({ audio: true });
      s.getTracks().forEach((t) => t.stop());
    } catch (e) {
      alert('Microphone permission is required.');
      return;
    }

    startBtn.disabled = true;
    startBtn.textContent = 'Starting...';

    const fd = new FormData();
    fd.append('name', name);
    fd.append('email', email);
    fd.append('interview_id', interviewId);

    const res = await fetch('/interviews/ai-interview/init/', { method: 'POST', body: fd });
    const data = await res.json();
    if (!res.ok) {
      alert(data.error || 'Failed to start');
      startBtn.disabled = false;
      startBtn.textContent = 'Start Interview';
      return;
    }

    sessionId = data.session_id;
    if (data.assistant_text) log('assistant', data.assistant_text);
    if (data.audio_base64) playBase64(data.audio_base64);

    if (data.done) {
      startBtn.textContent = 'Completed';
      talkBtn.disabled = true;
    } else {
      talkBtn.disabled = false;
      startBtn.textContent = 'Started';
    }
  }

  async function beginRecord() {
    if (recording || speaking || !sessionId) return;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, sampleRate: 16000 },
      });
      chunks = [];
      mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm;codecs=opus' });
      mediaRecorder.ondataavailable = (e) => e.data && chunks.push(e.data);
      mediaRecorder.onstop = async () => {
        try {
          const blob = new Blob(chunks, { type: 'audio/webm' });
          if (blob.size < 1000) return; // Too short
          await handleRecordedBlob(blob);
        } finally {
          stream.getTracks().forEach((t) => t.stop());
        }
      };
      mediaRecorder.start();
      recording = true;
      talkBtn.textContent = 'Recording...';
    } catch (e) {
      alert('Mic error: ' + (e?.message || e));
    }
  }

  function endRecord() {
    if (!recording || !mediaRecorder) return;
    recording = false;
    talkBtn.textContent = 'Hold to Answer';
    mediaRecorder.stop();
  }

  async function handleRecordedBlob(blob) {
    // 1) Transcribe
    const fd = new FormData();
    fd.append('audio', blob, 'answer.webm');
    fd.append('session_id', sessionId);
    const tr = await fetch('/interviews/ai-interview/transcribe/', { method: 'POST', body: fd });
    const tj = await tr.json();
    if (!tr.ok) {
      alert(tj.error || 'Transcription failed');
      return;
    }
    const text = (tj.text || '').trim();
    if (!text) return;
    log('user', text);

    // 2) Respond
    const fd2 = new FormData();
    fd2.append('session_id', sessionId);
    fd2.append('text', text);
    const rr = await fetch('/interviews/ai-interview/respond/', { method: 'POST', body: fd2 });
    const rj = await rr.json();
    if (!rr.ok) {
      alert(rj.error || 'AI failed');
      return;
    }
    if (rj.assistant_text) log('assistant', rj.assistant_text);
    if (rj.audio_base64) {
      speaking = true;
      try { playBase64(rj.audio_base64); } finally { speaking = false; }
    }
    if (rj.done) {
      talkBtn.disabled = true;
      talkBtn.textContent = 'Interview Completed';
    }
  }

  // Wire events
  startBtn?.addEventListener('click', startInterview);
  talkBtn?.addEventListener('mousedown', (e) => { e.preventDefault(); beginRecord(); });
  talkBtn?.addEventListener('mouseup', (e) => { e.preventDefault(); endRecord(); });
  talkBtn?.addEventListener('mouseleave', (e) => { if (recording) endRecord(); });
  talkBtn?.addEventListener('touchstart', (e) => { e.preventDefault(); beginRecord(); });
  talkBtn?.addEventListener('touchend', (e) => { e.preventDefault(); endRecord(); });
})();
