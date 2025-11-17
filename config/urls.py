"""
URL configuration for AI Interviewer project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from interviews import views as interview_views
from django.contrib.staticfiles.urls import staticfiles_urlpatterns

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('interviews/', include('interviews.urls')),
    # Root maps directly to the interview list page
    path('', interview_views.interview_list, name='home'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    # Serve static files from STATICFILES_DIRS via staticfiles finders in development
    urlpatterns += staticfiles_urlpatterns()
