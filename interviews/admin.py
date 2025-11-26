from django.contrib import admin

from .models import Answer, Candidate, Interview, InterviewResponse, Question, Section


class SectionInline(admin.TabularInline):
    model = Section
    extra = 0
    show_change_link = True


class AnswerInline(admin.TabularInline):
    model = Answer
    extra = 0
    readonly_fields = ('question', 'answer_text')


@admin.register(Interview)
class InterviewAdmin(admin.ModelAdmin):
    list_display = ('title', 'created_by', 'created_at', 'is_active')
    list_filter = ('is_active', 'created_at')
    search_fields = ('title', 'description')
    inlines = [SectionInline]


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('question_text', 'section', 'question_type', 'is_required', 'order')
    list_filter = ('question_type', 'is_required')
    search_fields = ('question_text', 'section__interview__title')


@admin.register(InterviewResponse)
class InterviewResponseAdmin(admin.ModelAdmin):
    list_display = ('candidate', 'interview', 'submitted_at')
    list_filter = ('interview', 'submitted_at')
    search_fields = (
        'candidate__full_name',
        'candidate__email',
    )
    inlines = [AnswerInline]


@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    list_display = ('response', 'question', 'answer_text')
    list_filter = ('response__interview',)
    search_fields = (
        'answer_text',
        'response__candidate__full_name',
        'response__candidate__email',
    )


@admin.register(Candidate)
class CandidateAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'email', 'phone', 'location', 'created_at')
    search_fields = ('full_name', 'email', 'phone', 'location')
    list_filter = ('created_at',)
