from django.urls import path
from . import views, ai_views

app_name = 'interviews'

urlpatterns = [
    path('', views.interview_list, name='list'),
    path('create/', views.interview_create, name='create'),
    path('<int:pk>/', views.interview_detail, name='detail'),
    path('<int:pk>/edit/', views.interview_edit, name='edit'),
    path('<int:pk>/preview/', views.interview_preview, name='preview'),
    path('<int:pk>/delete/', views.interview_delete, name='delete'),
    path('<int:pk>/take/', views.interview_take, name='take'),
    path('<int:pk>/responses/', views.interview_responses, name='responses'),
    
    # AI Conversational Interview (info + live)
    path('<int:pk>/ai-interview/', ai_views.ai_interview_info, name='ai_interview'),
    path('<int:pk>/ai-interview/live/', ai_views.ai_interview_start, name='ai_interview_live'),

    # AI Conversational Interview API (session-scoped)
    path('ai-interview/init/', ai_views.init_session, name='ai_interview_session_init'),
    path('ai-interview/transcribe/', ai_views.transcribe, name='ai_interview_session_transcribe'),
    path('ai-interview/respond/', ai_views.respond, name='ai_interview_session_respond'),
    path('ai-interview/speak/', ai_views.speak, name='ai_interview_session_speak'),
    path('ai-interview/submit/', ai_views.submit, name='ai_interview_session_submit'),

    # Realtime: route to views.realtime_session to avoid adding new files
    path('ai-interview/realtime/session/', views.realtime_session, name='ai_interview_realtime_session'),
]
