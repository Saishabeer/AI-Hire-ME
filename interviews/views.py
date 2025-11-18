from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from .models import Interview, Question, QuestionOption, InterviewResponse, Answer
import json

# Added imports for realtime session minting
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
import os
import urllib.request
import urllib.error
import urllib.parse


@require_http_methods(["GET"])
def interview_list(request):
    """List all interviews"""
    interviews = Interview.objects.filter(is_active=True)
    user_interviews = Interview.objects.filter(created_by=request.user) if request.user.is_authenticated else None
    context = {'interviews': interviews, 'user_interviews': user_interviews}
    return render(request, 'interviews/list.html', context)


@login_required
@require_http_methods(["GET", "POST"])
def interview_create(request):
    """Create a new interview form"""
    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description', '').strip()
        if not title:
            messages.error(request, 'Interview title is required')
            return redirect('interviews:create')

        interview = Interview.objects.create(
            title=title.strip(),
            description=description,
            created_by=request.user
        )
        messages.success(request, 'Interview created successfully!')
        return redirect('interviews:edit', pk=interview.pk)

    return render(request, 'interviews/create.html')


@login_required
@require_http_methods(["GET", "POST"])
def interview_edit(request, pk):
    """Edit interview form with Google Forms-like interface"""
    interview = get_object_or_404(Interview, pk=pk, created_by=request.user)

    if request.method == 'POST':
        # Update interview details (standard form submit)
        interview.title = request.POST.get('title', interview.title).strip()
        interview.description = request.POST.get('description', interview.description).strip()
        interview.save()

        # Handle questions via AJAX JSON
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            try:
                data = json.loads(request.body or '{}')
            except Exception:
                return JsonResponse({'success': False, 'error': 'Invalid JSON payload'}, status=400)

            action = data.get('action')

            if action == 'add_question':
                question = Question.objects.create(
                    interview=interview,
                    question_text=data.get('question_text', 'Untitled Question'),
                    question_type=data.get('question_type', 'text'),
                    is_required=bool(data.get('is_required', True)),
                    order=interview.questions.count(),
                )
                return JsonResponse({'success': True, 'question_id': question.id})

            elif action == 'update_question':
                question = get_object_or_404(Question, pk=data.get('question_id'), interview=interview)
                question.question_text = data.get('question_text', question.question_text)
                question.question_type = data.get('question_type', question.question_type)
                question.is_required = bool(data.get('is_required', question.is_required))
                question.save()
                return JsonResponse({'success': True})

            elif action == 'delete_question':
                question = get_object_or_404(Question, pk=data.get('question_id'), interview=interview)
                question.delete()
                return JsonResponse({'success': True})

            elif action == 'add_option':
                question = get_object_or_404(Question, pk=data.get('question_id'), interview=interview)
                option = QuestionOption.objects.create(
                    question=question,
                    option_text=data.get('option_text', 'Option'),
                    order=question.options.count(),
                )
                return JsonResponse({'success': True, 'option_id': option.id})

            elif action == 'delete_option':
                # Hardened: ensure the option belongs to the current interview
                option = get_object_or_404(
                    QuestionOption,
                    pk=data.get('option_id'),
                    question__interview=interview
                )
                option.delete()
                return JsonResponse({'success': True})

        messages.success(request, 'Interview updated successfully!')
        return redirect('interviews:edit', pk=pk)

    context = {'interview': interview, 'questions': interview.questions.all()}
    return render(request, 'interviews/edit.html', context)


@require_http_methods(["GET"])
def interview_detail(request, pk):
    """View interview details"""
    interview = get_object_or_404(Interview, pk=pk)
    return render(request, 'interviews/detail.html', {'interview': interview})


@login_required
@require_http_methods(["GET"])
def interview_preview(request, pk):
    """Preview the interview form"""
    interview = get_object_or_404(Interview, pk=pk, created_by=request.user)
    return render(request, 'interviews/preview.html', {'interview': interview, 'preview_mode': True})


@login_required
@require_http_methods(["GET", "POST"])
def interview_delete(request, pk):
    """Delete an interview"""
    interview = get_object_or_404(Interview, pk=pk, created_by=request.user)

    if request.method == 'POST':
        interview.delete()
        messages.success(request, 'Interview deleted successfully!')
        return redirect('interviews:list')

    return render(request, 'interviews/delete.html', {'interview': interview})


@require_http_methods(["GET", "POST"])
def interview_take(request, pk):
    """Take the interview (for candidates)"""
    interview = get_object_or_404(Interview, pk=pk, is_active=True)

    if request.method == 'POST':
        candidate_name = (request.POST.get('candidate_name') or '').strip()
        candidate_email = (request.POST.get('candidate_email') or '').strip()

        if not candidate_name or not candidate_email:
            messages.error(request, 'Name and email are required')
            # Redirect back to AI interview info page
            return redirect('interviews:ai_interview', pk=pk)

        # Create response
        response = InterviewResponse.objects.create(
            interview=interview,
            candidate_name=candidate_name,
            candidate_email=candidate_email
        )

        # Save answers
        for question in interview.questions.all():
            answer = Answer.objects.create(response=response, question=question)

            if question.question_type in ['text', 'textarea']:
                answer.answer_text = request.POST.get(f'question_{question.id}', '') or ''
                answer.save()

            elif question.question_type == 'multiple_choice':
                option_id = request.POST.get(f'question_{question.id}')
                if option_id:
                    try:
                        opt_id_int = int(option_id)
                        option = QuestionOption.objects.get(pk=opt_id_int, question=question)
                        answer.selected_options.add(option)
                    except (QuestionOption.DoesNotExist, ValueError, TypeError):
                        # Ignore invalid option values
                        pass

        messages.success(request, 'Interview submitted successfully!')
        return redirect('interviews:list')

    return render(request, 'interviews/ai_voice_interview.html', {'interview': interview})


@login_required
@require_http_methods(["GET"])
def interview_responses(request, pk):
    """View responses for an interview"""
    interview = get_object_or_404(Interview, pk=pk, created_by=request.user)
    responses = interview.responses.all()
    return render(request, 'interviews/responses.html', {'interview': interview, 'responses': responses})


# === Realtime AI Interview: Mint ephemeral OpenAI Realtime session token ===
@csrf_exempt
@require_http_methods(["POST"])
def realtime_session(request):
    """
    Returns an ephemeral OpenAI Realtime session token configured with server-side VAD.
    If an interview_id is provided in the POST body, the session is constrained to ONLY ask
    that interview's questions in order and never invent new questions.
    """
    api_key = getattr(settings, "OPENAI_API_KEY", os.getenv("OPENAI_API_KEY"))
    if not api_key:
        return JsonResponse({"error": "OPENAI_API_KEY is not configured on the server."}, status=500)

    # Try to read interview_id from request to build strict instructions
    interview = None
    try:
        raw = request.body.decode("utf-8") if request.body else "{}"
        body_json = json.loads(raw or "{}")
        interview_id = body_json.get("interview_id") or body_json.get("pk")
        if interview_id:
            try:
                interview = Interview.objects.get(pk=interview_id, is_active=True)
            except Interview.DoesNotExist:
                return JsonResponse({"error": "Interview not found or inactive."}, status=404)
    except Exception:
        # If body can't be parsed, continue with generic behavior
        interview = None

    model = "gpt-4o-realtime-preview-2024-12-17"

    # Build strict instructions when an interview is provided
    if interview:
        questions = list(
            interview.questions.all().order_by("order", "id").values_list("question_text", flat=True)
        )
        enumerated = "\n".join([f"{i+1}. {q}" for i, q in enumerate(questions)]) or "1. (no questions defined)"
        instructions = (
            f"You are interviewing a candidate for '{interview.title}'. "
            "Ask ONLY the following questions in EXACTLY this order, one at a time. "
            "Do NOT add, invent, or substitute any other questions. "
            "After each answer, briefly acknowledge and move on to the next question. "
            "If the candidate has already answered a question implicitly, briefly confirm and proceed. "
            "If interrupted, stop speaking and listen (barge-in). "
            "Conclude politely after the final question.\n\n"
            "Questions:\n"
            f"{enumerated}"
        )
    else:
        # Generic fallback (less strict if no interview provided)
        instructions = (
            "You are a professional interviewer. Start immediately by greeting the candidate and asking the first question. "
            "Continue asking one question at a time automatically. If the candidate interrupts, stop speaking and listen (barge-in). "
            "Keep responses concise and conversational. Conclude politely when the interview is complete."
        )

    payload = {
        "model": model,
        "voice": "verse",
        "modalities": ["text", "audio"],
        "turn_detection": {
            "type": "server_vad",
            "threshold": 0.5,
            "prefix_padding_ms": 300,
            "silence_duration_ms": 400,
        },
        "instructions": instructions,
    }

    try:
        req = urllib.request.Request(
            "https://api.openai.com/v1/realtime/sessions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read().decode("utf-8")
            data = json.loads(body)
            # Return only what's needed by the browser
            return JsonResponse(
                {"client_secret": data.get("client_secret"), "id": data.get("id"), "model": data.get("model")}
            )
    except urllib.error.HTTPError as e:
        try:
            err_body = e.read().decode("utf-8")
        except Exception:
            err_body = ""
        return JsonResponse({"error": "Failed to create session", "details": err_body}, status=e.code)
    except Exception as e:
        return JsonResponse({"error": "Internal server error", "details": str(e)}, status=500)
