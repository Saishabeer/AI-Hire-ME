"""
Django settings for AI Interviewer project.
"""

from pathlib import Path
import os

"""Project settings (decouple removed; env via os.getenv with optional dotenv)."""

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Optionally load variables from a .env file if python-dotenv is available
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv(dotenv_path=BASE_DIR / ".env")
except Exception:
    pass

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-dev-key-change-in-production-12345')

# OpenAI configuration (read from environment or .env)
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')

# Back-compat/env aliasing for client modules that read env directly
# Map OPENAI_BASE_URL -> OPENAI_API_BASE (ensure trailing /v1)
if not os.getenv('OPENAI_API_BASE'):
    _base = os.getenv('OPENAI_BASE_URL', '').strip()
    if _base:
        _b = _base.rstrip('/')
        if not _b.endswith('/v1'):
            _b = _b + '/v1'
        os.environ['OPENAI_API_BASE'] = _b

# Map TRANSCRIBE_MODEL -> OPENAI_TRANSCRIBE_MODEL
if not os.getenv('OPENAI_TRANSCRIBE_MODEL') and os.getenv('TRANSCRIBE_MODEL'):
    os.environ['OPENAI_TRANSCRIBE_MODEL'] = os.getenv('TRANSCRIBE_MODEL', '').strip()

# Expose realtime model/voice to Django settings (used by ai_views)
OPENAI_REALTIME_MODEL = os.getenv('OPENAI_REALTIME_MODEL', 'gpt-4o-realtime-preview-2024-12-17')
OPENAI_REALTIME_VOICE = os.getenv('OPENAI_REALTIME_VOICE', os.getenv('OPENAI_TTS_VOICE', 'alloy'))
# Keep TTS voice for other modules if they reference it
OPENAI_TTS_VOICE = os.getenv('OPENAI_TTS_VOICE', OPENAI_REALTIME_VOICE)

# SECURITY WARNING: don't run with debug turned on in production!
def _get_bool(name: str, default: bool) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return str(v).strip().lower() in {"1", "true", "yes", "on"}

DEBUG = _get_bool('DEBUG', True)

def _get_list(name: str, default: list[str]) -> list[str]:
    v = os.getenv(name)
    if not v:
        return default
    return [s.strip() for s in str(v).split(',') if s.strip()]

ALLOWED_HOSTS = _get_list('ALLOWED_HOSTS', ['localhost', '127.0.0.1'])

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Third party apps
    'rest_framework',
    'corsheaders',
    
    # Local apps
    'interviews',
    'accounts',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('POSTGRES_DB', 'Hire_Me'),
        'USER': os.getenv('POSTGRES_USER', 'postgres'),
        'PASSWORD': os.getenv('POSTGRES_PASSWORD', ''),
        'HOST': os.getenv('POSTGRES_HOST', '127.0.0.1'),
        'PORT': os.getenv('POSTGRES_PORT', '5432'),
        'CONN_MAX_AGE': int(os.getenv('POSTGRES_CONN_MAX_AGE', '60')),
        'ATOMIC_REQUESTS': True,
        'OPTIONS': {
            # 'sslmode': os.getenv('POSTGRES_SSLMODE', 'prefer'),
        },
    }
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kolkata'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# CORS settings
CORS_ALLOWED_ORIGINS = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

# REST Framework settings
REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticatedOrReadOnly',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 10
}

# Ensure Django redirects use root-level auth paths
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'
