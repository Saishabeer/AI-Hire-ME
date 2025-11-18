// AI Interview – Stable HTTP-based flow with optional local ASR/TTS fallback
(function () {
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init, { once: true });
  } else {
    init();
  }

  function init() {
    const $ = (id) => document.getElementById(id);

    // Elements
    const interviewIdEl = $('interviewId');
    const aiAudio = $('aiAudio');
    const statusEl = $('status');
    const userTranscript = $('userTranscript');
    const aiTranscript = $('aiTranscript');
    const startBtn = $('startInterviewBtn');
    const sendBtn = $('sendAnswerBtn');
    const answerInput = $('answerInput');
    const speakBtn = $('speakBtn');

    if (!statusEl || !userTranscript || !aiTranscript) {
      console.warn('[AI Interview] Missing required DOM elements.');
      return;
    }

    // State
    let sessionId = null;
    let recognizing = false;
    let recog = null;

    // Utilities
    function setStatus(t) {
      try { statusEl.textContent = t; } catch (_) {}
    }

    function append(el, t) {
      if (!el) return;
      el.textContent += String(t ?? '');
      try { el.scrollTop = el.scrollHeight; } catch (_) {}
    }

    function appendLine(el, t) {
      append(el, (t || '') + '\n');
    }

    function setLastLine(el, text) {
      if (!el) return;
      const lines = (el.textContent || '').split('\n');
      const hadNewline = (el.textContent || '').endsWith('\n');
      if (hadNewline) {
        lines.pop();
        lines.push(String(text));
        el.textContent = lines.join('\n') + '\n';
      } else {
        if (lines.length === 0) {
          el.textContent = String(text);
        } else {
          lines[lines.length - 1] = String(text);
          el.textContent = lines.join('\n');
        }
      }
      try { el.scrollTop = el.scrollHeight; } catch (_) {}
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

    function getInterviewId() {
      const byInput = (interviewIdEl && interviewIdEl.value) ? interviewIdEl.value.trim() : '';
      if (byInput) return byInput;
      try {
        const m = (location.pathname || '').match(/interviews\/(\d+)\//);
        if (m && m[1]) return m[1];
      } catch (_) {}
      return '';
    }

    // Local TTS fallback using Web Speech API
    function speakLocal(text) {
      try {
        if (!text || !window.speechSynthesis) return;
        window.speechSynthesis.cancel();
        const u = new SpeechSynthesisUtterance(text);
        u.lang = navigator.language || 'en-US';
        u.rate = 1.0;
        u.pitch = 1.0;
        window.speechSynthesis.speak(u);
      } catch (e) {
        console.warn('[AI Interview] Local TTS failed:', e);
      }
    }

    function playBase64Audio(b64) {
      if (!b64) return false;
      try {
        if (aiAudio) {
          aiAudio.src = `data:audio/mpeg;base64,${b64}`;
          aiAudio.play?.().catch(() => {});
          return true;
        } else {
          const a = new Audio(`data:audio/mpeg;base64,${b64}`);
          a.play?.().catch(() => {});
          return true;
        }
      } catch (_) {
        return false;
      }
    }

    // Start interview session
    async function startInterview() {
      if (sessionId) return;

      const interviewId = getInterviewId();
      if (!interviewId) {
        alert('Missing interview id. Reload the page.');
        return;
      }

      const name = getQueryParam('name') || 'Guest';
      const email = getQueryParam('email') || 'guest@example.com';

      setStatus('Initializing…');

      const fd = new FormData();
      fd.append('name', name);
      fd.append('email', email);
      fd.append('interview_id', interviewId);

      const res = await fetch('/interviews/ai-interview/init/', { method: 'POST', body: fd });
      const data = await safeJson(res);
      if (!res.ok) {
        console.warn('[AI Interview] init error:', res.status, data && data.error);
        setStatus('Failed to start session.');
        alert(data.error || 'Failed to start');
        return;
      }

      sessionId = data.session_id;
      const assistantText = (data.assistant_text || '').trim();
      if (assistantText) {
        appendLine(aiTranscript, assistantText);
        if (!playBase64Audio(data.audio_base64)) {
          speakLocal(assistantText);
        }
      }

      setStatus('Session ready. You can speak or type your answer.');
    }

    // Send a typed or recognized answer to server
    async function sendAnswer(text) {
      const msg = (text || '').trim();
      if (!msg) return;
      if (!sessionId) {
        setStatus('Session not started.');
        return;
      }

      appendLine(userTranscript, msg);

      const fd = new FormData();
      fd.append('session_id', sessionId);
      fd.append('text', msg);

      setStatus('Sending answer…');
      const res = await fetch('/interviews/ai-interview/respond/', { method: 'POST', body: fd });
      const data = await safeJson(res);
      if (!res.ok) {
        setStatus('Error while responding.');
        console.warn('[AI Interview] respond error:', res.status, data && data.error);
        return;
      }

      const assistantText = (data.assistant_text || '').trim();
      if (assistantText) {
        appendLine(aiTranscript, assistantText);
        if (!playBase64Audio(data.audio_base64)) {
          speakLocal(assistantText);
        }
      }

      if (data.done) {
        setStatus('Interview completed. Thank you!');
        if (answerInput) answerInput.disabled = true;
        if (sendBtn) sendBtn.disabled = true;
        if (speakBtn) speakBtn.disabled = true;
      } else {
        setStatus('Awaiting your answer…');
      }
    }

    // Browser speech recognition (optional)
    function getSpeechRecognizer() {
      return window.SpeechRecognition || window.webkitSpeechRecognition || null;
    }

    function startASR() {
      if (recognizing) return;
      const SR = getSpeechRecognizer();
      if (!SR) {
        setStatus('Speech recognition not supported in this browser.');
        return;
      }
      recog = new SR();
      recog.lang = navigator.language || 'en-US';
      recog.continuous = true;
      recog.interimResults = true;

      recognizing = true;
      if (speakBtn) speakBtn.textContent = 'Stop Speaking';
      setStatus('Listening…');

      let interim = '';
      recog.onresult = (ev) => {
        interim = '';
        for (let i = ev.resultIndex; i < ev.results.length; i++) {
          const res = ev.results[i];
          const txt = (res[0] && res[0].transcript) ? res[0].transcript : '';
          if (res.isFinal) {
            const finalText = txt.trim();
            if (finalText) {
              if (userTranscript && (userTranscript.textContent || '').endsWith('\n')) {
              } else {
                appendLine(userTranscript, '');
              }
              setLastLine(userTranscript, finalText);
              appendLine(userTranscript, '');
              sendAnswer(finalText);
            }
          } else {
            interim += txt;
          }
        }
        if (interim) {
          if (userTranscript && (userTranscript.textContent || '').endsWith('\n')) {
          } else {
            appendLine(userTranscript, '');
          }
          setLastLine(userTranscript, interim);
        }
      };

      recog.onerror = (e) => {
        console.warn('[AI Interview] ASR error:', e);
        setStatus('Speech recognition error.');
      };

      recog.onend = () => {
        recognizing = false;
        if (speakBtn) speakBtn.textContent = 'Speak';
        setStatus(sessionId ? 'Session ready.' : 'Idle');
      };

      try {
        recog.start();
      } catch (e) {
        console.warn('[AI Interview] ASR start failed:', e);
        recognizing = false;
        if (speakBtn) speakBtn.textContent = 'Speak';
        setStatus('Unable to start speech recognition.');
      }
    }

    function stopASR() {
      recognizing = false;
      try { recog && recog.stop(); } catch (_) {}
      if (speakBtn) speakBtn.textContent = 'Speak';
      setStatus(sessionId ? 'Session ready.' : 'Idle');
    }

    // Wire events
    if (startBtn) {
      startBtn.addEventListener('click', async (e) => {
        e.preventDefault();
        try { await startInterview(); } catch (_) {}
      });
    } else {
      const iid = getInterviewId();
      if (iid) {
        setTimeout(() => { startInterview().catch(() => {}); }, 200);
      }
    }

    if (sendBtn && answerInput) {
      sendBtn.addEventListener('click', async (e) => {
        e.preventDefault();
        await sendAnswer(answerInput.value || '');
        answerInput.value = '';
        answerInput.focus();
      });
      answerInput.addEventListener('keydown', async (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault();
          await sendAnswer(answerInput.value || '');
          answerInput.value = '';
        }
      });
    }

    if (speakBtn) {
      speakBtn.addEventListener('click', (e) => {
        e.preventDefault();
        if (recognizing) {
          stopASR();
        } else {
          if (!sessionId) {
            startInterview().then(startASR).catch(() => {});
          } else {
            startASR();
          }
        }
      });
    }

    setStatus('Idle');
  }
})();
