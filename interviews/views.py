from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from .models import Interview, Question, QuestionOption, InterviewResponse, Answer
import json


def interview_list(request):
    """List all interviews"""
    interviews = Interview.objects.filter(is_active=True)
    if request.user.is_authenticated:
        user_interviews = Interview.objects.filter(created_by=request.user)
    else:
        user_interviews = None
    
    context = {
        'interviews': interviews,
        'user_interviews': user_interviews,
    }
    return render(request, 'interviews/list.html', context)


@login_required
def interview_create(request):
    """Create a new interview form"""
    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description', '')
        
        if not title:
            messages.error(request, 'Interview title is required')
            return redirect('interviews:create')
        
        interview = Interview.objects.create(
            title=title,
            description=description,
            created_by=request.user
        )
        
        messages.success(request, 'Interview created successfully!')
        return redirect('interviews:edit', pk=interview.pk)
    
    return render(request, 'interviews/create.html')


@login_required
def interview_edit(request, pk):
    """Edit interview form with Google Forms-like interface"""
    interview = get_object_or_404(Interview, pk=pk, created_by=request.user)
    
    if request.method == 'POST':
        # Update interview details
        interview.title = request.POST.get('title', interview.title)
        interview.description = request.POST.get('description', interview.description)
        interview.save()
        
        # Handle questions via AJAX
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            data = json.loads(request.body)
            action = data.get('action')
            
            if action == 'add_question':
                question = Question.objects.create(
                    interview=interview,
                    question_text=data.get('question_text', 'Untitled Question'),
                    question_type=data.get('question_type', 'text'),
                    is_required=data.get('is_required', True),
                    order=interview.questions.count()
                )
                return JsonResponse({'success': True, 'question_id': question.id})
            
            elif action == 'update_question':
                question = get_object_or_404(Question, pk=data.get('question_id'), interview=interview)
                question.question_text = data.get('question_text', question.question_text)
                question.question_type = data.get('question_type', question.question_type)
                question.is_required = data.get('is_required', question.is_required)
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
                    order=question.options.count()
                )
                return JsonResponse({'success': True, 'option_id': option.id})
            
            elif action == 'delete_option':
                option = get_object_or_404(QuestionOption, pk=data.get('option_id'))
                option.delete()
                return JsonResponse({'success': True})
        
        messages.success(request, 'Interview updated successfully!')
        return redirect('interviews:edit', pk=pk)
    
    context = {
        'interview': interview,
        'questions': interview.questions.all(),
    }
    return render(request, 'interviews/edit.html', context)


def interview_detail(request, pk):
    """View interview details"""
    interview = get_object_or_404(Interview, pk=pk)
    context = {
        'interview': interview,
    }
    return render(request, 'interviews/detail.html', context)


@login_required
def interview_preview(request, pk):
    """Preview the interview form"""
    interview = get_object_or_404(Interview, pk=pk, created_by=request.user)
    context = {
        'interview': interview,
        'preview_mode': True,
    }
    return render(request, 'interviews/preview.html', context)


@login_required
def interview_delete(request, pk):
    """Delete an interview"""
    interview = get_object_or_404(Interview, pk=pk, created_by=request.user)
    
    if request.method == 'POST':
        interview.delete()
        messages.success(request, 'Interview deleted successfully!')
        return redirect('interviews:list')
    
    context = {'interview': interview}
    return render(request, 'interviews/delete.html', context)


def interview_take(request, pk):
    """Take the interview (for candidates)"""
    interview = get_object_or_404(Interview, pk=pk, is_active=True)
    
    if request.method == 'POST':
        candidate_name = request.POST.get('candidate_name')
        candidate_email = request.POST.get('candidate_email')
        
        if not candidate_name or not candidate_email:
            messages.error(request, 'Name and email are required')
            # Redirect back to the unified AI interview page (form-based)
            return redirect('interviews:ai_interview', pk=pk)
        
        # Create response
        response = InterviewResponse.objects.create(
            interview=interview,
            candidate_name=candidate_name,
            candidate_email=candidate_email
        )
        
        # Save answers
        for question in interview.questions.all():
            answer = Answer.objects.create(
                response=response,
                question=question
            )
            
            # Handle text-based questions (text, textarea)
            if question.question_type in ['text', 'textarea']:
                answer.answer_text = request.POST.get(f'question_{question.id}', '')
                answer.save()
            # Handle multiple choice (single selection)
            elif question.question_type == 'multiple_choice':
                option_id = request.POST.get(f'question_{question.id}')
                if option_id:
                    # Ensure we add a valid QuestionOption instance tied to this question
                    try:
                        opt_id_int = int(option_id)
                        option = QuestionOption.objects.get(pk=opt_id_int, question=question)
                        answer.selected_options.add(option)
                    except (QuestionOption.DoesNotExist, ValueError, TypeError):
                        # Ignore invalid option values
                        pass
        
        messages.success(request, 'Interview submitted successfully!')
        return redirect('interviews:list')
    
    context = {
        'interview': interview,
    }
    # Render the same form-based page for GET
    return render(request, 'interviews/ai_voice_interview.html', context)


@login_required
def interview_responses(request, pk):
    """View responses for an interview"""
    interview = get_object_or_404(Interview, pk=pk, created_by=request.user)
    responses = interview.responses.all()
    
    context = {
        'interview': interview,
        'responses': responses,
    }
    return render(request, 'interviews/responses.html', context)
