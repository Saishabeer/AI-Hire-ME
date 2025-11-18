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


class InterviewResponse(models.Model):
    """Candidate's response to an interview"""
    interview = models.ForeignKey(Interview, on_delete=models.CASCADE, related_name='responses')
    candidate_name = models.CharField(max_length=255)
    candidate_email = models.EmailField()
    submitted_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        ordering = ['-submitted_at']
    
    def __str__(self):
        return f"{self.candidate_name} - {self.interview.title}"


class Answer(models.Model):
    """Individual answers to questions"""
    response = models.ForeignKey(InterviewResponse, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    answer_text = models.TextField(blank=True)
    selected_options = models.ManyToManyField(QuestionOption, blank=True)
    
    def __str__(self):
        return f"{self.response.candidate_name} - {self.question.question_text[:30]}"
