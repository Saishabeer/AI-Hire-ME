from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Interview(models.Model):
    """Interview Form - similar to Google Forms"""
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='interviews')
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return self.title


class Section(models.Model):
    """Logical grouping of questions within an interview"""
    interview = models.ForeignKey(Interview, on_delete=models.CASCADE, related_name='sections')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return f"{self.interview.title} — {self.title}"


class Question(models.Model):
    """Questions in an interview form"""
    QUESTION_TYPES = [
        ('text', 'Short Answer'),
        ('textarea', 'Detailed Answer'),
        ('multiple_choice', 'Multiple Choice'),
    ]
    
    interview = models.ForeignKey(Interview, on_delete=models.CASCADE, related_name='questions')
    # Optional section assignment; questions can be moved across sections later
    section = models.ForeignKey(Section, null=True, blank=True, on_delete=models.SET_NULL, related_name='questions')
    question_text = models.TextField()
    question_type = models.CharField(max_length=20, choices=QUESTION_TYPES, default='text')
    is_required = models.BooleanField(default=True)
    # Global order across the interview (kept for backward compatibility)
    order = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['order']
    
    def __str__(self):
        return f"{self.interview.title} - Q{self.order}: {self.question_text[:50]}"


class QuestionOption(models.Model):
    """Options for multiple choice, checkbox, and dropdown questions"""
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='options')
    option_text = models.CharField(max_length=255)
    order = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['order']
    
    def __str__(self):
        return self.option_text


class Candidate(models.Model):
    """Normalized candidate entity, shared across multiple interview responses."""
    full_name = models.CharField(max_length=255)
    email = models.EmailField(unique=True, db_index=True)
    phone = models.CharField(max_length=20, blank=True)
    location = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['full_name', 'email']

    def __str__(self):
        return f"{self.full_name} <{self.email}>"


class InterviewResponse(models.Model):
    """Candidate's response to an interview"""
    interview = models.ForeignKey(Interview, on_delete=models.CASCADE, related_name='responses')
    # New normalized link to Candidate; keep legacy name/email for backward compatibility and import
    candidate = models.ForeignKey('Candidate', null=True, blank=True, on_delete=models.SET_NULL, related_name='responses', db_index=True)
    candidate_name = models.CharField(max_length=255)
    candidate_email = models.EmailField()
    submitted_at = models.DateTimeField(default=timezone.now)
    # Store a compact JSON snapshot for easy management/exports (answers, transcript, source, etc.)
    answers_json = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-submitted_at']
        indexes = [
            models.Index(fields=['interview', 'submitted_at']),
        ]

    def __str__(self):
        display_name = self.candidate.full_name if self.candidate else self.candidate_name
        return f"{display_name} - {self.interview.title}"


class Answer(models.Model):
    """Individual answers to questions"""
    response = models.ForeignKey(InterviewResponse, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    answer_text = models.TextField(blank=True)
    selected_options = models.ManyToManyField(QuestionOption, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['response', 'question']),
        ]

    def __str__(self):
        person = self.response.candidate.full_name if getattr(self.response, "candidate", None) else self.response.candidate_name
        return f"{person} - {self.question.question_text[:30]}"
