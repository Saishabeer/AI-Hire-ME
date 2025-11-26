from typing import List


def _questions_block_for_interview(interview) -> str:
    """
    Build a human-readable questions block grouped by sections, in strict order.
    """
    lines: List[str] = []
    idx = 1
    try:
        sections = list(interview.sections.all().order_by("order", "id"))
    except Exception:
        sections = []
    for s in sections:
        lines.append(f"Section: {s.title}")
        try:
            qtexts = list(
                s.questions.all().order_by("order", "id").values_list("question_text", flat=True)
            )
        except Exception:
            qtexts = []
        if qtexts:
            for q in qtexts:
                lines.append(f"{idx}. {q}")
                idx += 1
        else:
            lines.append(f"{idx}. (no questions)")
            idx += 1
    return "\n".join(lines) if lines else "(No questions configured)"


def build_realtime_instructions(interview=None) -> str:
    """
    Strict, reusable instructions for the OpenAI Realtime session.
    When an Interview is passed, the model is constrained to ONLY those questions in the provided order.
    """
    if interview is not None:
        qb = _questions_block_for_interview(interview)
        return (
            f"You are conducting a strictly scripted interview for '{interview.title}'. "
            "Follow these hard rules:\n"
            "0) Do not speak or produce any output unless explicitly requested via a response.create event.\n"
            "1) Speak ONLY in English.\n"
            "2) Speak ONLY the exact question text provided by HR, in the configured order.\n"
            "3) Ask EXACTLY one question per turn and output nothing except the question text.\n"
            "4) Do NOT add greetings, acknowledgements, summaries, follow-ups, or filler words.\n"
            "5) Never rephrase, paraphrase, translate, or invent new questions.\n"
            "6) If no next question is provided, remain silent.\n"
            "7) Conclude only after the final question has been asked.\n\n"
            "Questions (by section):\n"
            f"{qb}"
        )

    # Generic fallback when no specific interview is provided
    return (
        "You are a professional interviewer. Follow these hard rules:\n"
        "0) Do not speak or produce any output unless explicitly requested via a response.create event.\n"
        "1) Speak ONLY in English.\n"
        "2) When prompted, ask the first question exactly as written, with no greeting or preamble.\n"
        "3) Ask EXACTLY one question per turn and output nothing except the question text.\n"
        "4) Do NOT add acknowledgements, summaries, or follow-ups.\n"
        "5) Never rephrase, paraphrase, translate, or invent new questions.\n"
        "6) Conclude only after the final question has been asked."
    )


def verbatim_question_template() -> str:
    """
    Template used client-side to force the model to speak only the exact question text.
    ${Q} will be replaced with the exact question string on the JS side.
    """
    return 'Say exactly: "${Q}". Speak ONLY in English. Output only that question and nothing else. Do not add any words, prefixes, postfixes, or extra punctuation.'


def first_utterance_template() -> str:
    """
    Template for the very first model utterance.
    ${Q} will be replaced with the exact first question string on the JS side.
    The first utterance MUST start with a brief English greeting and then ask the first question verbatim.
    """
    return 'Start with a brief English greeting (e.g., "Hello, let\'s begin.") then ask exactly: "${Q}". Speak ONLY in English. Do not add anything else after the question. Ask ONE question per turn only.'


__all__ = [
    "build_realtime_instructions",
    "verbatim_question_template",
    "first_utterance_template",
]
