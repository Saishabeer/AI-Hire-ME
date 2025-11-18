"""
AI Conversational Interview Views
Handles AI-powered conversational interviews
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from typing import List, Dict
from django.http import JsonResponse, HttpRequest, HttpResponseBadRequest
from django.views.decorators.http import require_http_methods, require_POST
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
import os
from .models import Interview, InterviewResponse, Answer, Question
from ai_engine.interview_session import InterviewSession
from .prompts import SYSTEM_PROMPT
from . import openai_client as oc
from .interview_session import new_session, get_session, add_turn
import json
import requests

# Store active sessions (in production, use Redis or database)
active_sessions = {}


def _tts_for_question(q: Question) -> str:
    """Build a spoken prompt for a question, including options for multiple choice."""
    base = q.question_text
    if q.question_type == 'multiple_choice':
        try:
            opts = [o.option_text for o in q.options.all()]
        except Exception:
            opts = []
        if opts:
            base += " Options are: " + "; ".join(opts)
    return base


def ai_interview_start(request, pk):
    """Start an AI conversational interview"""
    interview = get_object_or_404(Interview, pk=pk, is_active=True)
    # Render a simple form-based interview (no voice, no API key requirement)
    context = {
        'interview': interview,
    }
    return render(request, 'interviews/ai_voice_interview.html', context)


def ai_interview_info(request, pk):
    """Information page to collect candidate name and email before live interview."""
    interview = get_object_or_404(Interview, pk=pk, is_active=True)
    return render(request, 'interviews/ai_voice_info.html', { 'interview': interview })


@require_http_methods(["POST"])
@csrf_exempt
def ai_interview_init(request, pk):
    """Initialize AI interview session"""
    try:
        interview = get_object_or_404(Interview, pk=pk, is_active=True)
        
        # Create new session
        session = InterviewSession(interview)
        session_id = str(id(session))
        active_sessions[session_id] = session
        
        # Start interview
        result = session.start_interview()
        
        return JsonResponse({
            'success': True,
            'session_id': session_id,
            'message': result['message'],
            'total_questions': result['total_questions']
        })
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_http_methods(["POST"])
@csrf_exempt
def ai_interview_respond(request, pk):
    """Process candidate response in AI interview"""
    try:
        data = json.loads(request.body)
        session_id = data.get('session_id')
        user_message = data.get('message')
        
        if not session_id or session_id not in active_sessions:
            return JsonResponse({
                'success': False,
                'error': 'Invalid session'
            }, status=400)
        
        session = active_sessions[session_id]
        
        # Check if this is the first message (candidate ready to start)
        if data.get('ready_to_start'):
            result = session.ask_next_question()
        else:
            # Process the answer
            result = session.process_answer(user_message)
            
            # Use the answered_question_id from session for form updates
            if result.get('answer_saved') and result.get('answered_question_id'):
                result['question_id'] = result.pop('answered_question_id')
        
        return JsonResponse(result)
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_http_methods(["POST"])
@csrf_exempt
def ai_interview_transcribe(request, pk):
    """Transcribe audio to text using Whisper"""
    try:
        if 'audio' not in request.FILES:
            return JsonResponse({
                'success': False,
                'error': 'No audio file provided'
            }, status=400)
        
        audio_file = request.FILES['audio']
        session_id = request.POST.get('session_id')
        
        if not session_id or session_id not in active_sessions:
            return JsonResponse({
                'success': False,
                'error': 'Invalid session'
            }, status=400)
        
        session = active_sessions[session_id]
        
        # Transcribe audio
        result = session.ai_client.transcribe_audio(audio_file)
        
        if result['success']:
            return JsonResponse({
                'success': True,
                'text': result['text']
            })
        else:
            return JsonResponse({
                'success': False,
                'error': result.get('message', 'Transcription failed')
            }, status=500)
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_http_methods(["POST"])
@csrf_exempt
def ai_interview_submit(request, pk):
    """Submit completed AI interview"""
    try:
        data = json.loads(request.body)
        session_id = data.get('session_id')
        candidate_name = data.get('candidate_name')
        candidate_email = data.get('candidate_email')
        
        if not session_id or session_id not in active_sessions:
            return JsonResponse({
                'success': False,
                'error': 'Invalid session'
            }, status=400)
        
        session = active_sessions[session_id]
        interview = session.interview
        
        # Create interview response
        response = InterviewResponse.objects.create(
            interview=interview,
            candidate_name=candidate_name,
            candidate_email=candidate_email
        )
        
        # Save all answers
        answers_data = session.get_formatted_answers()
        for answer_data in answers_data:
            question = Question.objects.get(id=answer_data['question_id'])
            answer = Answer.objects.create(
                response=response,
                question=question,
                answer_text=answer_data['answer']
            )
        
        # Clean up session
        del active_sessions[session_id]
        
        return JsonResponse({
            'success': True,
            'message': 'Interview submitted successfully!',
            'response_id': response.id
        })
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_http_methods(["GET"])
def ai_interview_status(request, pk):
    """Get current interview session status"""
    try:
        session_id = request.GET.get('session_id')
        
        if not session_id or session_id not in active_sessions:
            return JsonResponse({
                'success': False,
                'error': 'Invalid session'
            }, status=400)
        
        session = active_sessions[session_id]
        session_data = session.get_session_data()
        
        return JsonResponse({
            'success': True,
            'data': session_data
        })
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_http_methods(["POST"])
@csrf_exempt
def ai_interview_speak(request, pk):
    """Convert AI text to speech"""
    try:
        data = json.loads(request.body)
        text = data.get('text')
        session_id = data.get('session_id')
        
        if not text:
            return JsonResponse({
                'success': False,
                'error': 'No text provided'
            }, status=400)
        
        if not session_id or session_id not in active_sessions:
            return JsonResponse({
                'success': False,
                'error': 'Invalid session'
            }, status=400)
        
        session = active_sessions[session_id]
        
        # Generate speech
        result = session.ai_client.text_to_speech(text)
        
        if result['success']:
            # Convert audio bytes to base64 for JSON response
            import base64
            audio_base64 = base64.b64encode(result['audio']).decode('utf-8')
            
            return JsonResponse({
                'success': True,
                'audio': audio_base64
            })
        else:
            return JsonResponse({
                'success': False,
                'error': result.get('error', 'TTS failed')
            }, status=500)
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@csrf_exempt
@require_POST
def init_session(request: HttpRequest) -> JsonResponse:
    """
    POST /ai-interview/init/ {name, email, interview_id}
    Creates a session tied to an Interview and returns greeting + first question with TTS audio.
    """
    name = (request.POST.get("name") or "").strip()
    email = (request.POST.get("email") or "").strip()
    try:
        interview_id = int(request.POST.get("interview_id") or 0)
    except Exception:
        interview_id = 0

    # Allow defaults so the session can auto-start without user input
    if not name:
        name = "Guest"
    if not email:
        email = "guest@example.com"
    if not interview_id:
        return HttpResponseBadRequest("Missing interview_id")

    interview = get_object_or_404(Interview, pk=interview_id, is_active=True)

    # Create session bound to this interview
    sess = new_session(name, email, interview_id=interview.id)

    # Compose greeting + first question from DB
    qs = list(interview.questions.all())
    if not qs:
        assistant_text = f"Hello {name}, there are no questions configured for this interview yet."
        add_turn(sess.session_id, "assistant", assistant_text)
        audio_b64 = None
        try:
            audio_b64 = oc.text_to_speech_base64(assistant_text)
        except Exception:
            # Allow flow to continue even if TTS is unavailable
            audio_b64 = None
        return JsonResponse(
            {
                "session_id": sess.session_id,
                "assistant_text": assistant_text,
                "audio_base64": audio_b64,
                "done": True,
            },
            status=200,
        )

    first_q = qs[0]
    first_q_tts = _tts_for_question(first_q)
    assistant_text = (
        f"Hello {name}. Welcome to the interview for {interview.title}. "
        f"Let's begin. First question: {first_q_tts}"
    )
    add_turn(sess.session_id, "assistant", assistant_text)
    audio_b64 = None
    try:
        audio_b64 = oc.text_to_speech_base64(assistant_text)
    except Exception:
        # If TTS fails (e.g., missing/invalid API key), continue with text only.
        audio_b64 = None

    return JsonResponse(
        {
            "session_id": sess.session_id,
            "assistant_text": assistant_text,
            "audio_base64": audio_b64,
        },
        status=200,
    )

@csrf_exempt
@require_POST
def transcribe(request: HttpRequest) -> JsonResponse:
    """
    POST /ai-interview/transcribe/ multipart/form-data with 'audio' field.
    Returns {text}.
    """
    f = request.FILES.get("audio")
    if not f:
        return HttpResponseBadRequest("Missing 'audio' file")
    data = f.read()
    text = oc.transcribe_audio(data, filename=f.name or "audio.webm")
    return JsonResponse({"text": text}, status=200)

@csrf_exempt
@require_POST
def respond(request: HttpRequest) -> JsonResponse:
    """
    POST /ai-interview/respond/ {session_id, text}
    Records the user's answer to the current DB question, then returns the next question via TTS.
    When all questions are answered, saves InterviewResponse + Answers and returns a closing message.
    """
    session_id = (request.POST.get("session_id") or "").strip()
    text = (request.POST.get("text") or "").strip()
    sess = get_session(session_id)
    if not sess:
        return HttpResponseBadRequest("Invalid session_id")
    if not text:
        return HttpResponseBadRequest("Missing text")

    interview = get_object_or_404(Interview, pk=sess.interview_id, is_active=True)
    qs = list(interview.questions.all())
    total = len(qs)

    # Save answer for current question
    if 0 <= sess.current_index < total:
        current_q = qs[sess.current_index]
        sess.answers[current_q.id] = text
        add_turn(session_id, "user", text)
        sess.current_index += 1

    # Next question or finish
    if sess.current_index < total:
        next_q = qs[sess.current_index]
        next_q_tts = _tts_for_question(next_q)
        assistant_text = f"Thank you. Next question: {next_q_tts}"
        add_turn(session_id, "assistant", assistant_text)
        try:
            audio_b64 = oc.text_to_speech_base64(assistant_text)
        except Exception:
            audio_b64 = None
        return JsonResponse({"assistant_text": assistant_text, "audio_base64": audio_b64, "done": False}, status=200)
    else:
        # Persist to DB
        response = InterviewResponse.objects.create(
            interview=interview,
            candidate_name=sess.candidate_name or "",
            candidate_email=sess.candidate_email or "",
        )
        for q in qs:
            ans_text = sess.answers.get(q.id, "")
            Answer.objects.create(response=response, question=q, answer_text=ans_text)

        closing = "Thank you. This concludes the interview. Have a great day!"
        add_turn(session_id, "assistant", closing)
        try:
            audio_b64 = oc.text_to_speech_base64(closing)
        except Exception:
            audio_b64 = None
        return JsonResponse({"assistant_text": closing, "audio_base64": audio_b64, "done": True, "response_id": response.id}, status=200)

@csrf_exempt
@require_POST
def speak(request: HttpRequest) -> JsonResponse:
    """
    POST /ai-interview/speak/ {text}
    Helper to TTS any text (returns base64 MP3).
    """
    try:
        # Accept both form-encoded and JSON bodies
        text = (request.POST.get("text") or "").strip()
        if not text:
            try:
                body = json.loads(request.body or b"{}")
                text = (body.get("text") or "").strip()
            except Exception:
                text = ""

        if not text:
            return HttpResponseBadRequest("Missing 'text'")

        audio_b64 = oc.text_to_speech_base64(text)
        return JsonResponse({"audio_base64": audio_b64}, status=200)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
@require_POST
def realtime_session(request: HttpRequest) -> JsonResponse:
    """
    POST /ai-interview/realtime/session/
    Mints an ephemeral OpenAI Realtime session token for browser-side WebRTC.
    Optionally accepts {session_id, name, email, interview_id} to craft instructions.
    """
    try:
        api_key = getattr(settings, "OPENAI_API_KEY", os.environ.get("OPENAI_API_KEY", ""))
        if not api_key:
            return JsonResponse({"error": "OPENAI_API_KEY is not configured"}, status=500)

        # Gather optional context to personalize instructions
        session_id = (request.POST.get("session_id") or "").strip()
        name = (request.POST.get("name") or "").strip()
        email = (request.POST.get("email") or "").strip()
        try:
            interview_id = int(request.POST.get("interview_id") or 0)
        except Exception:
            interview_id = 0

        if session_id and not interview_id:
            sess = get_session(session_id)
            if sess:
                name = name or (sess.candidate_name or "")
                email = email or (sess.candidate_email or "")
                interview_id = interview_id or (sess.interview_id or 0)

        instructions = ""
        questions_array = []
        closing_line = "Thank you. This concludes the interview. Have a great day!"
        if interview_id:
            try:
                interview = Interview.objects.get(pk=interview_id, is_active=True)
                # Build a strict question list from the HR-configured form
                try:
                    qs = list(interview.questions.all())
                except Exception:
                    qs = []

                q_lines = []
                questions_array = []
                for i, q in enumerate(qs, start=1):
                    # Plain question text used for deterministic prompting
                    q_text = f"{q.question_text}".strip()
                    try:
                        if getattr(q, 'question_type', '') == 'multiple_choice':
                            opts = []
                            try:
                                opts = [o.option_text for o in q.options.all()]
                            except Exception:
                                opts = []
                            if opts:
                                q_text = (q_text + " Options: " + "; ".join(opts)).strip()
                    except Exception:
                        pass
                    questions_array.append(q_text)
                    # For human-readable instruction block with numbering
                    line = f"{i}. {q_text}"
                    q_lines.append(line)

                questions_block = "\n".join(q_lines) if q_lines else "(No questions configured)"

                greet_name = f" {name}" if name else ""
                instructions = (
                    f"You are an AI interviewer for '{interview.title}'. Address the candidate{greet_name}.\n"
                    "Ask ONLY the questions listed below, in the exact order, ONE at a time.\n"
                    "Use the EXACT wording of each question VERBATIM.\n"
                    "After each candidate response, briefly acknowledge and immediately ask the next question.\n"
                    "Do NOT invent, add, or skip questions. Do NOT change their meaning. Keep responses concise and professional.\n"
                    "When the last question is answered, speak this exact closing line and stop:\n"
                    f"\"{closing_line}\"\n\n"
                    f"Questions to ask (strict order):\n{questions_block}"
                )
            except Interview.DoesNotExist:
                instructions = (
                    f"You are an AI interviewer. Address the candidate{(' ' + name) if name else ''}. "
                    "No questions are configured; politely inform the candidate and end the call."
                )
        else:
            instructions = (
                f"You are an AI interviewer. Address the candidate{(' ' + name) if name else ''}. "
                "No interview was specified; politely inform the candidate and end the call."
            )

        model = getattr(settings, "OPENAI_REALTIME_MODEL", "gpt-4o-realtime-preview-2024-12-17")
        voice = getattr(settings, "OPENAI_TTS_VOICE", "alloy")

        url = "https://api.openai.com/v1/realtime/sessions"
        payload = {
            "model": model,
            "voice": voice,
            # OpenAI sessions requires either ["text"] or ["audio","text"].
            # We want live audio back-and-forth, so include both.
            "modalities": ["audio", "text"],
            "instructions": instructions,
            # Enable server-side VAD so the model responds when you finish speaking
            "turn_detection": {"type": "server_vad", "threshold": 0.5},
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "OpenAI-Beta": "realtime=v1",
        }

        r = requests.post(url, json=payload, headers=headers, timeout=20)
        r.raise_for_status()
        js = r.json()
        token = (js.get("client_secret") or {}).get("value")
        if not token:
            return JsonResponse({"error": "Failed to create ephemeral token"}, status=500)

        return JsonResponse({
            "token": token,
            "expires_at": (js.get("client_secret") or {}).get("expires_at"),
            "model": js.get("model", model),
            # Echo back the exact instructions we constructed so the frontend can reinforce them
            "instructions": instructions,
            "voice": voice,
            # Provide deterministic question list and closing line for client-side orchestration
            "questions": questions_array,
            "closing": closing_line,
        })
    except requests.HTTPError as e:
        try:
            return JsonResponse({"error": e.response.text}, status=e.response.status_code)
        except Exception:
            return JsonResponse({"error": str(e)}, status=500)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
@require_POST
def submit(request: HttpRequest) -> JsonResponse:
    """
    POST /ai-interview/submit/ {session_id, name, email}
    Lightweight submit endpoint to finalize a session.
    For now, this acknowledges completion. Persisting to DB can be added later.
    """
    try:
        session_id = (request.POST.get("session_id") or "").strip()
        name = (request.POST.get("name") or request.POST.get("candidate_name") or "").strip()
        email = (request.POST.get("email") or request.POST.get("candidate_email") or "").strip()

        # Ensure session exists (optional)
        sess = get_session(session_id)
        if not sess:
            return HttpResponseBadRequest("Invalid session_id")

        # Optionally, here you could persist to DB or trigger async processing.
        # For simplicity, just acknowledge and let frontend redirect.
        return JsonResponse({"ok": True, "session_id": session_id, "candidate_name": name, "candidate_email": email}, status=200)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
