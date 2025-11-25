from django.contrib import admin
from django.urls import path, include
from django.http import HttpResponse
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from interviews import views as interview_views  # Home view

def empty_favicon(_request):
    # Silence /favicon.ico 404 noise during development
    return HttpResponse(b'', content_type='image/x-icon', status=204)

urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),

    # Home → interviews list
    path('', interview_views.interview_list, name='home'),

    # Auth routes at root: /login, /logout, /register, /signup (instance-namespace: 'auth')
    path('', include(('accounts.urls', 'accounts'), namespace='auth')),
    
    # Also expose them under /accounts/ with a separate 'accounts' namespace
    path('accounts/', include(('accounts.urls', 'accounts'), namespace='accounts')),

    # Interviews app
    path('interviews/', include(('interviews.urls', 'interviews'), namespace='interviews')),

    # Favicon (avoid 404 spam)
    path('favicon.ico', empty_favicon),
]

# Friendly error handlers to avoid raw error status pages
handler400 = 'interviews.views.error_400'
handler403 = 'interviews.views.error_403'
handler404 = 'interviews.views.error_404'
handler500 = 'interviews.views.error_500'
# Serve static files in development even if StaticFilesHandler isn’t active yet
urlpatterns += staticfiles_urlpatterns()