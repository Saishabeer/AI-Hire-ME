from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import List, Dict


@dataclass
class InterviewTurn:
    role: str  # "user" or "assistant"
    content: str


@dataclass
class InterviewSession:
    session_id: str
    candidate_name: str = ""
    candidate_email: str = ""
    interview_id: int | None = None
    current_index: int = 0  # index of next question to ask
    turns: List[InterviewTurn] = field(default_factory=list)
    # Map question_id -> answer_text
    answers: Dict[int, str] = field(default_factory=dict)


# Simple in-memory store (replace with DB if needed)
_SESSIONS: Dict[str, InterviewSession] = {}


def new_session(candidate_name: str, candidate_email: str, interview_id: int | None = None) -> InterviewSession:
    sid = str(uuid.uuid4())
    sess = InterviewSession(
        session_id=sid,
        candidate_name=candidate_name,
        candidate_email=candidate_email,
        interview_id=interview_id,
    )
    _SESSIONS[sid] = sess
    return sess


def get_session(session_id: str) -> InterviewSession | None:
    return _SESSIONS.get(session_id)


def add_turn(session_id: str, role: str, content: str) -> None:
    sess = _SESSIONS.get(session_id)
    if not sess:
        return
    sess.turns.append(InterviewTurn(role=role, content=content))