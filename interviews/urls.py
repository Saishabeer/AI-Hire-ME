from django.urls import path
from . import views

app_name = 'interviews'

urlpatterns = [
    path('', views.interview_list, name='list'),
    path('create/', views.interview_create, name='create'),
    path('<int:pk>/', views.interview_detail, name='detail'),
    path('<int:pk>/edit/', views.interview_edit, name='edit'),
    path('<int:pk>/preview/', views.interview_preview, name='preview'),
    path('<int:pk>/delete/', views.interview_delete, name='delete'),
    path('<int:pk>/take/', views.interview_take, name='take'),
    path('<int:pk>/submit/', views.interview_submit_json, name='submit_json'),
    path('<int:pk>/responses/', views.interview_responses, name='responses'),
    
    # AI Conversational Interview (info + live) consolidated into views.py
    path('<int:pk>/ai-interview/', views.ai_interview_info, name='ai_interview'),
    path('<int:pk>/ai-interview/live/', views.ai_interview_start, name='ai_interview_live'),

    # Realtime: ephemeral token minting
    path('ai-interview/realtime/session/', views.realtime_session, name='ai_interview_realtime_session'),
]
