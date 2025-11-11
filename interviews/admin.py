from django.contrib import admin
from .models import Interview, Question, QuestionOption, InterviewResponse, Answer


class QuestionOptionInline(admin.TabularInline):
    model = QuestionOption
    extra = 1


class QuestionInline(admin.StackedInline):
    model = Question
    extra = 1
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
    inlines = [QuestionInline]


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('question_text', 'interview', 'question_type', 'is_required', 'order')
    list_filter = ('question_type', 'is_required')
    search_fields = ('question_text', 'interview__title')
    inlines = [QuestionOptionInline]


@admin.register(QuestionOption)
class QuestionOptionAdmin(admin.ModelAdmin):
    list_display = ('option_text', 'question', 'order')
    list_filter = ('question__interview',)
    search_fields = ('option_text',)


@admin.register(InterviewResponse)
class InterviewResponseAdmin(admin.ModelAdmin):
    list_display = ('candidate_name', 'candidate_email', 'interview', 'submitted_at')
    list_filter = ('interview', 'submitted_at')
    search_fields = ('candidate_name', 'candidate_email')
    inlines = [AnswerInline]


@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    list_display = ('response', 'question', 'answer_text')
    list_filter = ('response__interview',)
    search_fields = ('answer_text', 'response__candidate_name')
