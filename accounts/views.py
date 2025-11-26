from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.forms import UserCreationForm
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods


@require_http_methods(["GET", "POST"])
def register(request):
    """
    Simple user registration using Django's UserCreationForm.
    Renders templates/accounts/register.html and redirects to 'login' on success.
    """
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Account created successfully. You can sign in now.')
            return redirect('auth:login')
    else:
        form = UserCreationForm()
    return render(request, 'accounts/register.html', {'form': form})


@require_http_methods(["GET", "POST"])
def logout_view(request):
    """
    Allow GET or POST logout and redirect to home or provided ?next= URL.
    """
    logout(request)
    next_url = request.GET.get('next') or request.POST.get('next')
    if next_url:
        return redirect(next_url)
    messages.success(request, 'Signed out.')
    return redirect('home')
