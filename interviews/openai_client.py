import base64
import os
from typing import List, Dict, Any, Optional

import requests
from django.conf import settings

# Load API key from Django settings or environment
OPENAI_API_KEY = getattr(settings, "OPENAI_API_KEY", None) or os.environ.get("OPENAI_API_KEY", "")

OPENAI_API_BASE = getattr(settings, "OPENAI_API_BASE", "https://api.openai.com/v1")
CHAT_MODEL = getattr(settings, "OPENAI_CHAT_MODEL", "gpt-4o-mini")
TRANSCRIBE_MODEL = getattr(settings, "OPENAI_TRANSCRIBE_MODEL", "whisper-1")  # or gpt-4o-mini-transcribe
TTS_MODEL = getattr(settings, "OPENAI_TTS_MODEL", "tts-1")
TTS_VOICE = getattr(settings, "OPENAI_TTS_VOICE", "alloy")


def _assert_api_key():
    if not OPENAI_API_KEY:
        raise RuntimeError(
            "OPENAI_API_KEY is not configured. Set it in your .env file or environment."
        )


def _auth_headers(extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    _assert_api_key()
    h = {"Authorization": f"Bearer {OPENAI_API_KEY}"}
    if extra:
        h.update(extra)
    return h


def transcribe_audio(file_bytes: bytes, filename: str = "audio.webm") -> str:
    """
    Send audio bytes to OpenAI transcription API and return text.
    """
    _assert_api_key()
    url = f"{OPENAI_API_BASE}/audio/transcriptions"
    files = {
        "file": (filename, file_bytes, "application/octet-stream"),
    }
    data = {"model": TRANSCRIBE_MODEL}
    resp = requests.post(url, headers=_auth_headers(), files=files, data=data, timeout=60)
    resp.raise_for_status()
    js = resp.json()
    return js.get("text", "").strip()


def chat_complete(messages: List[Dict[str, str]], system_prompt: str) -> str:
    """
    Send chat messages with a system prompt; return assistant text.
    messages = [{"role":"user","content":"..."}...]
    """
    _assert_api_key()
    url = f"{OPENAI_API_BASE}/chat/completions"
    payload = {
        "model": CHAT_MODEL,
        "messages": [{"role": "system", "content": system_prompt}] + messages,
        "temperature": 0.7,
    }
    resp = requests.post(url, headers={**_auth_headers(), "Content-Type": "application/json"}, json=payload, timeout=60)
    resp.raise_for_status()
    js = resp.json()
    return js["choices"][0]["message"]["content"].strip()


def text_to_speech_bytes(text: str, voice: Optional[str] = None) -> bytes:
    """
    Convert text to speech and return audio bytes (MP3).
    """
    _assert_api_key()
    voice = voice or TTS_VOICE
    url = f"{OPENAI_API_BASE}/audio/speech"
    payload = {
        "model": TTS_MODEL,
        "voice": voice,
        "input": text,
        "format": "mp3",
    }
    resp = requests.post(url, headers={**_auth_headers({"Content-Type": "application/json"}),}, json=payload, timeout=60)
    resp.raise_for_status()
    return resp.content


def text_to_speech_base64(text: str, voice: Optional[str] = None) -> str:
    audio = text_to_speech_bytes(text, voice)
    return base64.b64encode(audio).decode("ascii")