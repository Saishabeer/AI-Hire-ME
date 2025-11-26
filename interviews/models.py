from django.contrib.auth.models import User
from django.db import models
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

    @property
    def questions(self):
        """
        Compatibility shim after removing Question.interview FK.
        Returns a QuerySet of Questions belonging to this interview via Sections.
        """
        return Question.objects.filter(section__interview=self)


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

    # Removed direct interview FK; section implies interview context
    section = models.ForeignKey(
        Section, null=True, blank=True, on_delete=models.SET_NULL, related_name='questions'
    )
    question_text = models.TextField()
    question_type = models.CharField(max_length=20, choices=QUESTION_TYPES, default='text')
    is_required = models.BooleanField(default=True)
    # Global order across the interview (kept for backward compatibility)
    order = models.IntegerField(default=0)
    # For multiple_choice questions, store options inline as an ordered list of strings
    options = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        try:
            prefix = (
                self.section.interview.title
                if self.section and self.section.interview
                else "Question"
            )
        except Exception:
            prefix = "Question"
        return f"{prefix} - Q{self.order}: {self.question_text[:50]}"


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
    # Normalized link to Candidate
    candidate = models.ForeignKey(
        'Candidate',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='responses',
        db_index=True,
    )
    submitted_at = models.DateTimeField(default=timezone.now)
    # Store a compact JSON snapshot for easy management/exports (answers, transcript, source, etc.)
    answers_json = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-submitted_at']
        indexes = [
            models.Index(fields=['interview', 'submitted_at']),
        ]

    def __str__(self):
        display_name = self.candidate.full_name if self.candidate else "Unknown"
        return f"{display_name} - {self.interview.title}"


class Answer(models.Model):
    """Individual answers to questions"""

    response = models.ForeignKey(
        InterviewResponse, on_delete=models.CASCADE, related_name='answers'
    )
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    answer_text = models.TextField(blank=True)
    # For non-text questions, capture selected option values (strings) if applicable
    selected_options = models.JSONField(default=list, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['response', 'question']),
        ]

    def __str__(self):
        person = (
            self.response.candidate.full_name
            if getattr(self.response, "candidate", None)
            else "Unknown"
        )
        return f"{person} - {self.question.question_text[:30]}"
