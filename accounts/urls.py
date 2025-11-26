from django.contrib.auth import views as auth_views
from django.urls import path

from . import views  # expects a 'register' view in accounts/views.py

app_name = 'accounts'

urlpatterns = [
    # Login (renders templates/accounts/login.html)
    path('login/', auth_views.LoginView.as_view(template_name='accounts/login.html'), name='login'),
    # Logout (GET/POST) handled by simple view to avoid 405 on GET
    path('logout/', views.logout_view, name='logout'),
    # Registration (renders templates/accounts/register.html)
    path('register/', views.register, name='register'),
    # Alias so {% url 'signup' %} resolves (used in templates/accounts/login.html)
    path('signup/', views.register, name='signup'),
]
