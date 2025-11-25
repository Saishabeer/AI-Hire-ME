from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from .models import Interview, Section, Question, QuestionOption, InterviewResponse, Answer, Candidate
from .serializers import SubmitResponseSerializer
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.urls import reverse
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
                # Optional section assignment on create
                sec = None
                sid = data.get('section_id')
                if sid not in (None, '', 'null'):
                    try:
                        sec = Section.objects.get(pk=sid, interview=interview)
                    except Section.DoesNotExist:
                        sec = None
                # Always default to first section when none resolved (enforce all questions belong to a section)
                if sec is None:
                    try:
                        sec = interview.sections.order_by("order", "id").first()
                    except Exception:
                        sec = None

                question = Question.objects.create(
                    interview=interview,
                    section=sec,
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

            elif action == 'update_option':
                # Update option text (ensure option belongs to this interview)
                option = get_object_or_404(
                    QuestionOption,
                    pk=data.get('option_id'),
                    question__interview=interview
                )
                option.option_text = data.get('option_text', option.option_text)
                option.save()
                return JsonResponse({'success': True})
            
            elif action == 'delete_option':
                # Hardened: ensure the option belongs to the current interview
                option = get_object_or_404(
                    QuestionOption,
                    pk=data.get('option_id'),
                    question__interview=interview
                )
                option.delete()
                return JsonResponse({'success': True})

            elif action == 'add_section':
                title = (data.get('title') or 'Untitled Section').strip()
                description = (data.get('description') or '').strip()
                section = Section.objects.create(
                    interview=interview,
                    title=title or 'Untitled Section',
                    description=description,
                    order=interview.sections.count()
                )
                return JsonResponse({'success': True, 'section_id': section.id})

            elif action == 'update_section':
                section = get_object_or_404(Section, pk=data.get('section_id'), interview=interview)
                if 'title' in data:
                    section.title = (data.get('title') or '').strip() or section.title
                if 'description' in data:
                    section.description = (data.get('description') or '').strip()
                if 'order' in data and isinstance(data.get('order'), int):
                    section.order = data.get('order')
                section.save()
                return JsonResponse({'success': True})

            elif action == 'delete_section':
                section = get_object_or_404(Section, pk=data.get('section_id'), interview=interview)
                # Reassign questions from this section to a fallback section (no 'General' bucket)
                others = interview.sections.exclude(pk=section.pk).order_by("order", "id")
                if others.exists():
                    fallback = others.first()
                else:
                    # Create a new section if none remain
                    fallback = Section.objects.create(interview=interview, title="Section 1", order=0)
                Question.objects.filter(interview=interview, section=section).update(section=fallback)
                section.delete()
                return JsonResponse({'success': True, 'fallback_section_id': fallback.id})

            elif action == 'move_question':
                question = get_object_or_404(Question, pk=data.get('question_id'), interview=interview)
                section_id = data.get('section_id')
                if section_id in (None, '', 'null'):
                    # Keep current section or fallback to the first available section (no unsectioned state)
                    fallback = question.section or interview.sections.order_by("order", "id").first()
                    if fallback is None:
                        fallback = Section.objects.create(interview=interview, title="Section 1", order=0)
                    question.section = fallback
                else:
                    section = get_object_or_404(Section, pk=section_id, interview=interview)
                    question.section = section
                if 'order' in data and isinstance(data.get('order'), int):
                    question.order = data.get('order')
                question.save()
                return JsonResponse({'success': True})

        messages.success(request, 'Interview updated successfully!')
        return redirect('interviews:edit', pk=pk)
    
    # Ensure at least one section exists; if none, create a default and attach unsectioned questions
    if interview.sections.count() == 0:
        Section.objects.create(interview=interview, title="Section 1", order=0)
    first_sec = interview.sections.order_by("order", "id").first()
    if first_sec:
        # Attach any legacy unsectioned questions to the first section to avoid a 'General' bucket
        Interview.objects.filter(pk=interview.pk)  # no-op to ensure interview stays referenced
        Question.objects.filter(interview=interview, section__isnull=True).update(section=first_sec)

    context = {
        'interview': interview,
        'sections': interview.sections.all(),
        'questions': interview.questions.select_related('section').all()
    }
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
            # Redirect back to take page instead of showing an error page
            return redirect('interviews:take', pk=pk)

        # Normalize candidate entity
        candidate, _ = Candidate.objects.get_or_create(
            email=candidate_email,
            defaults={'full_name': candidate_name}
        )
        # If we discovered name now and profile lacks it, update
        if not candidate.full_name and candidate_name:
            candidate.full_name = candidate_name
            candidate.save(update_fields=['full_name'])

        # Create response (keep legacy fields for search/back-compat)
        response = InterviewResponse.objects.create(
            interview=interview,
            candidate=candidate,
            candidate_name=candidate.full_name or candidate_name,
            candidate_email=candidate.email
        )

        # Save answers (relational) and build compact JSON snapshot
        answers_snapshot = []
        for question in interview.questions.all():
            answer = Answer.objects.create(response=response, question=question)

            if question.question_type in ['text', 'textarea']:
                text_val = request.POST.get(f'question_{question.id}', '') or ''
                answer.answer_text = text_val
                answer.save()
                answers_snapshot.append({
                    'question': question.id,
                    'question_text': question.question_text,
                    'text': text_val,
                    'option_ids': [],
                    'option_labels': [],
                })

            elif question.question_type == 'multiple_choice':
                option_id = request.POST.get(f'question_{question.id}')
                opt_ids, opt_labels = [], []
                if option_id:
                    try:
                        opt_id_int = int(option_id)
                        option = QuestionOption.objects.get(pk=opt_id_int, question=question)
                        answer.selected_options.add(option)
                        opt_ids = [option.id]
                        opt_labels = [option.option_text]
                    except (QuestionOption.DoesNotExist, ValueError, TypeError):
                        # Ignore invalid option values
                        pass
                answers_snapshot.append({
                    'question': question.id,
                    'question_text': question.question_text,
                    'text': '',
                    'option_ids': opt_ids,
                    'option_labels': opt_labels,
                })

        # Attach JSON snapshot for easy export/reporting
        response.answers_json = {'answers': answers_snapshot, 'source': 'form'}
        response.save(update_fields=['answers_json'])

        messages.success(request, 'Interview submitted successfully!')
        # Redirect owner (and staff/admin) to responses; others to public detail page
        if request.user.is_authenticated and (request.user == interview.created_by or request.user.is_staff or request.user.is_superuser):
            return redirect('interviews:responses', pk=pk)
        return redirect('interviews:detail', pk=pk)

    return render(request, 'interviews/take.html', {'interview': interview})


@login_required
@require_http_methods(["GET"])
def interview_responses(request, pk):
    """View responses for an interview (owner-only; staff/admin allowed). Non-owners are redirected to detail."""
    interview = get_object_or_404(Interview, pk=pk)
    if not request.user.is_authenticated or (request.user != interview.created_by and not request.user.is_staff and not request.user.is_superuser):
        messages.error(request, "You do not have permission to view responses for this interview.")
        return redirect('interviews:detail', pk=pk)
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
        # Compose questions grouped strictly by defined sections (no 'General' bucket)
        section_lines = []
        idx = 1
        try:
            sections = list(interview.sections.all().order_by("order", "id"))
        except Exception:
            sections = []
        if sections:
            for s in sections:
                try:
                    qtexts = list(
                        s.questions.all().order_by("order", "id").values_list("question_text", flat=True)
                    )
                except Exception:
                    qtexts = []
                section_lines.append(f"Section: {s.title}")
                if qtexts:
                    for q in qtexts:
                        section_lines.append(f"{idx}. {q}")
                        idx += 1
                else:
                    section_lines.append(f"{idx}. (no questions)")
                    idx += 1
        questions_block = "\n".join(section_lines) if section_lines else "(No questions configured)"

        instructions = (
            f"You are interviewing a candidate for '{interview.title}'. "
            "Ask ONLY the following questions in EXACTLY this order, one section at a time. "
            "Finish all questions in a section before starting the next. "
            "Do NOT add, invent, or substitute any other questions. "
            "After each answer, briefly acknowledge and move on to the next question. "
            "If the candidate has already answered a question implicitly, briefly confirm and proceed. "
            "If interrupted, stop speaking and listen (barge-in). "
            "Conclude politely after the final question.\n\n"
            "Questions (by section):\n"
            f"{questions_block}"
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
        # Enable server-side speech-to-text so we can show user's transcript in the UI
        "input_audio_transcription": {
            "model": "whisper-1"
        },
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


@require_http_methods(["GET"])
def ai_interview_info(request, pk):
    """
    Information page to collect candidate name and email before live interview.
    Consolidated here to avoid duplicate modules (ai_views.py removed).
    """
    interview = get_object_or_404(Interview, pk=pk, is_active=True)
    return render(request, 'interviews/ai_voice_info.html', {'interview': interview})


@require_http_methods(["GET"])
def ai_interview_start(request, pk):
    """
    Start the AI conversational interview (live realtime WebRTC page).
    Consolidated here to avoid duplicate modules (ai_views.py removed).
    """
    interview = get_object_or_404(Interview, pk=pk, is_active=True)
    # Provide ordered sections with their questions for the live UI (tabs + collected info)
    sections = interview.sections.all().order_by("order", "id").prefetch_related("questions")
    return render(
        request,
        'interviews/ai_voice_interview.html',
        {
            'interview': interview,
            'sections': sections,
            'candidate_name': (request.GET.get('name') or '').strip(),
            'candidate_email': (request.GET.get('email') or '').strip(),
            'submit_url': reverse('interviews:submit_json', args=[pk]),
        }
    )

# === JSON submission API (used by voice/JS and external clients) ===
@api_view(["POST"])
@authentication_classes([])  # no SessionAuthentication -> no CSRF requirement
@permission_classes([AllowAny])
def interview_submit_json(request, pk):
    """
    Accepts JSON submission for an interview:
    {
      "candidate_name": "...",
      "candidate_email": "...",
      "answers": [
        {"question": 123, "text": "free text", "option_ids": [1,2]},
        ...
      ],
      "transcript": "optional",
      "source": "realtime|form|api"
    }
    Persists a Candidate, InterviewResponse (with answers_json snapshot), and
    materializes Answer rows for manageability and reporting.
    """
    interview = get_object_or_404(Interview, pk=pk, is_active=True)

    ser = SubmitResponseSerializer(data=request.data, context={"interview": interview})
    if not ser.is_valid():
        return Response({"success": False, "errors": ser.errors}, status=400)
    data = ser.validated_data

    candidate_name = (data.get("candidate_name") or "").strip()
    candidate_email = (data.get("candidate_email") or "").strip().lower()

    candidate, _ = Candidate.objects.get_or_create(
        email=candidate_email,
        defaults={"full_name": candidate_name}
    )
    if not candidate.full_name and candidate_name:
        candidate.full_name = candidate_name
        candidate.save(update_fields=["full_name"])

    # Normalize/validate answers and enrich with labels
    answers_enriched = []
    for item in data.get("answers") or []:
        try:
            qid = int(item.get("question"))
        except Exception:
            continue
        try:
            q = Question.objects.get(pk=qid, interview=interview)
        except Question.DoesNotExist:
            continue

        option_ids = list(map(int, item.get("option_ids") or []))
        opt_labels = list(
            QuestionOption.objects.filter(question=q, id__in=option_ids).values_list("option_text", flat=True)
        )
        answers_enriched.append({
            "question": q.id,
            "question_text": q.question_text,
            "text": item.get("text") or "",
            "option_ids": option_ids,
            "option_labels": list(opt_labels),
        })

    response = InterviewResponse.objects.create(
        interview=interview,
        candidate=candidate,
        candidate_name=candidate.full_name or candidate_name,
        candidate_email=candidate.email,
        answers_json={
            "answers": answers_enriched,
            "transcript": data.get("transcript") or "",
            "source": data.get("source") or "api",
        }
    )

    # Materialize relational answers for admin/reporting
    for item in answers_enriched:
        try:
            q = Question.objects.get(pk=item["question"], interview=interview)
        except Question.DoesNotExist:
            continue
        ans = Answer.objects.create(response=response, question=q, answer_text=item.get("text", ""))
        if item.get("option_ids"):
            valid_opts = QuestionOption.objects.filter(question=q, id__in=item["option_ids"])
            if valid_opts:
                ans.selected_options.add(*list(valid_opts))

    return Response({"success": True, "response_id": response.id})


# ---- Friendly error handlers (avoid raw error pages; sensible renders/JSON) ----
def _is_ajax(request):
    try:
        return request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    except Exception:
        return False


def error_400(request, exception=None):
    if _is_ajax(request):
        return JsonResponse({'success': False, 'error': 'Bad request'}, status=400)
    return render(request, '400.html', status=400)


def error_403(request, exception=None):
    if _is_ajax(request):
        return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
    return render(request, '403.html', status=403)


def error_404(request, exception=None):
    if _is_ajax(request):
        return JsonResponse({'success': False, 'error': 'Not found'}, status=404)
    return render(request, '404.html', status=404)


def error_500(request):
    if _is_ajax(request):
        return JsonResponse({'success': False, 'error': 'Server error'}, status=500)
    return render(request, '500.html', status=500)
