import base64
import os
from typing import List, Dict, Optional

# Import requests lazily-safe to avoid crashing Django at import time
try:
    import requests  # type: ignore
except Exception:
    requests = None  # Will be validated at call-time

# Read from .env via python-decouple if available; fallback to environment
try:
    from decouple import config as _config  # type: ignore
    OPENAI_API_KEY = _config("OPENAI_API_KEY", default=os.environ.get("OPENAI_API_KEY", ""))
except Exception:
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

OPENAI_API_BASE = os.environ.get("OPENAI_API_BASE", "https://api.openai.com/v1")
CHAT_MODEL = os.environ.get("OPENAI_CHAT_MODEL", "gpt-4o-mini")
TRANSCRIBE_MODEL = os.environ.get("OPENAI_TRANSCRIBE_MODEL", "whisper-1")
TTS_MODEL = os.environ.get("OPENAI_TTS_MODEL", "tts-1")
TTS_VOICE = os.environ.get("OPENAI_TTS_VOICE", "alloy")


def _require_requests():
    if requests is None:
        raise RuntimeError("Missing dependency: 'requests'. Install it with: pip install requests")


def _require_api_key():
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not configured. Set it in your .env or environment")


def _auth_headers(extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    _require_api_key()
    h = {"Authorization": f"Bearer {OPENAI_API_KEY}"}
    if extra:
        h.update(extra)
    return h


def transcribe_audio(file_bytes: bytes, filename: str = "audio.webm") -> str:
    _require_requests()
    _require_api_key()
    url = f"{OPENAI_API_BASE}/audio/transcriptions"
    files = {"file": (filename, file_bytes, "application/octet-stream")}
    data = {"model": TRANSCRIBE_MODEL}
    resp = requests.post(url, headers=_auth_headers(), files=files, data=data, timeout=60)  # type: ignore
    resp.raise_for_status()
    js = resp.json()
    return (js.get("text") or "").strip()


def chat_complete(messages: List[Dict[str, str]], system_prompt: str) -> str:
    _require_requests()
    _require_api_key()
    url = f"{OPENAI_API_BASE}/chat/completions"
    payload = {
        "model": CHAT_MODEL,
        "messages": [{"role": "system", "content": system_prompt}] + messages,
        "temperature": 0.7,
    }
    resp = requests.post(  # type: ignore
        url,
        headers={**_auth_headers(), "Content-Type": "application/json"},
        json=payload,
        timeout=60,
    )
    resp.raise_for_status()
    js = resp.json()
    return js["choices"][0]["message"]["content"].strip()


def text_to_speech_bytes(text: str, voice: Optional[str] = None) -> bytes:
    _require_requests()
    _require_api_key()
    voice = voice or TTS_VOICE
    url = f"{OPENAI_API_BASE}/audio/speech"
    payload = {"model": TTS_MODEL, "voice": voice, "input": text, "format": "mp3"}
    resp = requests.post(  # type: ignore
        url, headers={**_auth_headers({"Content-Type": "application/json"})}, json=payload, timeout=60
    )
    resp.raise_for_status()
    return resp.content


def text_to_speech_base64(text: str, voice: Optional[str] = None) -> str:
    audio = text_to_speech_bytes(text, voice)
    return base64.b64encode(audio).decode("ascii")


def create_realtime_ephemeral_session(model: str, voice: str = "verse") -> Dict[str, str]:
    """
    Create an ephemeral Realtime session with OpenAI and return {'token': ..., 'expires_at': ...}.
    """
    _require_requests()
    _require_api_key()
    url = f"{OPENAI_API_BASE}/realtime/sessions"
    resp = requests.post(  # type: ignore
        url,
        headers={
            **_auth_headers({"Content-Type": "application/json"}),
            "OpenAI-Beta": "realtime=v1",
        },
        json={
            "model": model,
            "voice": voice,
            "modalities": ["audio", "text"],
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    client_secret = (data.get("client_secret") or {}).get("value")
    if not client_secret:
        raise RuntimeError("OpenAI Realtime: missing client_secret in response")
    return {"token": client_secret, "expires_at": data.get("expires_at")}