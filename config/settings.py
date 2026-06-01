import os
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')


def env_bool(name, default=False):
    value = os.getenv(name)

    if value is None:
        return default

    return value.strip().lower() in {'1', 'true', 'yes', 'on'}


def env_list(name, default=''):
    value = os.getenv(name, default)

    return [item.strip() for item in value.split(',') if item.strip()]


def env_int(name, default=0):
    value = os.getenv(name)

    if value is None:
        return default

    return int(value)


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/6.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-local-ditent-development-key')

# SECURITY WARNING: don't run with debug turned on in production!
IS_VERCEL = env_bool('VERCEL', False)
IS_RENDER = bool(os.getenv('RENDER'))
DEBUG = env_bool('DEBUG', not (IS_VERCEL or IS_RENDER))

ALLOWED_HOSTS = env_list('ALLOWED_HOSTS', '127.0.0.1,localhost')
CSRF_TRUSTED_ORIGINS = env_list('CSRF_TRUSTED_ORIGINS', '')

if IS_VERCEL:
    ALLOWED_HOSTS.extend(['.vercel.app'])
    CSRF_TRUSTED_ORIGINS.extend(['https://*.vercel.app'])

if IS_RENDER and os.getenv('RENDER_EXTERNAL_HOSTNAME'):
    render_hostname = os.getenv('RENDER_EXTERNAL_HOSTNAME')
    ALLOWED_HOSTS.append(render_hostname)
    CSRF_TRUSTED_ORIGINS.append(f'https://{render_hostname}')

SECURE_SSL_REDIRECT = env_bool('SECURE_SSL_REDIRECT', not DEBUG)
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_HSTS_SECONDS = env_int('SECURE_HSTS_SECONDS', 0 if DEBUG else 31536000)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool('SECURE_HSTS_INCLUDE_SUBDOMAINS', not DEBUG)
SECURE_HSTS_PRELOAD = env_bool('SECURE_HSTS_PRELOAD', not DEBUG)
SESSION_COOKIE_SECURE = env_bool('SESSION_COOKIE_SECURE', not DEBUG)
CSRF_COOKIE_SECURE = env_bool('CSRF_COOKIE_SECURE', not DEBUG)
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'
X_FRAME_OPTIONS = 'DENY'
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'same-origin'


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'shop',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
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
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'shop.context_processors.site_settings',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# Database
# https://docs.djangoproject.com/en/6.0/ref/settings/#databases

DATABASE_URL = os.getenv('DATABASE_URL')

if DATABASE_URL:
    DATABASES = {
        'default': dj_database_url.parse(DATABASE_URL, conn_max_age=600, conn_health_checks=True)
    }
elif os.getenv('DB_ENGINE', 'sqlite').lower() == 'postgresql':
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.getenv('DB_NAME', 'ditent'),
            'USER': os.getenv('DB_USER', ''),
            'PASSWORD': os.getenv('DB_PASSWORD', ''),
            'HOST': os.getenv('DB_HOST', 'localhost'),
            'PORT': os.getenv('DB_PORT', '5432'),
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / os.getenv('DB_NAME', 'db.sqlite3'),
        }
    }

CACHE_BACKEND = os.getenv('CACHE_BACKEND', 'django.core.cache.backends.locmem.LocMemCache')
CACHE_LOCATION = os.getenv('CACHE_LOCATION', 'ditent-local-cache')
CACHES = {
    'default': {
        'BACKEND': CACHE_BACKEND,
        'LOCATION': CACHE_LOCATION,
    }
}


# Password validation
# https://docs.djangoproject.com/en/6.0/ref/settings/#auth-password-validators

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
# https://docs.djangoproject.com/en/6.0/topics/i18n/

LANGUAGE_CODE = 'ru-ru'

TIME_ZONE = 'Europe/Moscow'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/6.0/howto/static-files/

STATIC_URL = '/assets/'
STATICFILES_DIRS = [BASE_DIR / 'assets']
STATIC_ROOT = BASE_DIR / os.getenv('STATIC_ROOT', 'staticfiles')

if not DEBUG:
    STORAGES = {
        'default': {
            'BACKEND': 'django.core.files.storage.FileSystemStorage',
        },
        'staticfiles': {
            'BACKEND': 'whitenoise.storage.CompressedStaticFilesStorage',
        },
    }

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / os.getenv('MEDIA_ROOT', 'media')

DATA_UPLOAD_MAX_MEMORY_SIZE = env_int('DATA_UPLOAD_MAX_MEMORY_SIZE', 10 * 1024 * 1024)
FILE_UPLOAD_MAX_MEMORY_SIZE = env_int('FILE_UPLOAD_MAX_MEMORY_SIZE', 10 * 1024 * 1024)
DITENT_MAX_UPLOAD_SIZE = env_int('DITENT_MAX_UPLOAD_SIZE', 20 * 1024 * 1024)
DITENT_MAX_UPLOAD_COUNT = env_int('DITENT_MAX_UPLOAD_COUNT', 10)
DITENT_ALLOWED_UPLOAD_TYPES = env_list(
    'DITENT_ALLOWED_UPLOAD_TYPES',
    'image/jpeg,image/png,image/webp,image/gif,image/heic,image/heif,application/pdf,text/plain,application/zip,application/x-zip-compressed,application/octet-stream',
)
DITENT_ALLOWED_UPLOAD_EXTENSIONS = env_list(
    'DITENT_ALLOWED_UPLOAD_EXTENSIONS',
    '.jpg,.jpeg,.png,.webp,.gif,.heic,.heif,.pdf,.txt,.zip,.dwg,.dxf',
)
DITENT_MAX_CART_QUANTITY = env_int('DITENT_MAX_CART_QUANTITY', 999)
DITENT_AUTH_CODE_TTL_MINUTES = env_int('DITENT_AUTH_CODE_TTL_MINUTES', 10)
DITENT_AUTH_CODE_RESEND_SECONDS = env_int('DITENT_AUTH_CODE_RESEND_SECONDS', 60)
DITENT_AUTH_CODE_DEBUG_RESPONSE = env_bool('DITENT_AUTH_CODE_DEBUG_RESPONSE', False)
DITENT_AUTH_CODE_IP_LIMIT = env_int('DITENT_AUTH_CODE_IP_LIMIT', 10)
DITENT_AUTH_CODE_IP_WINDOW_SECONDS = env_int('DITENT_AUTH_CODE_IP_WINDOW_SECONDS', 60 * 60)
DITENT_LOGIN_ATTEMPT_LIMIT = env_int('DITENT_LOGIN_ATTEMPT_LIMIT', 5)
DITENT_LOGIN_ATTEMPT_WINDOW_SECONDS = env_int('DITENT_LOGIN_ATTEMPT_WINDOW_SECONDS', 15 * 60)

CDEK_API_BASE_URL = os.getenv('CDEK_API_BASE_URL', 'https://api.cdek.ru')
CDEK_CLIENT_ID = os.getenv('CDEK_CLIENT_ID', '')
CDEK_CLIENT_SECRET = os.getenv('CDEK_CLIENT_SECRET', '')
CDEK_REQUEST_TIMEOUT = env_int('CDEK_REQUEST_TIMEOUT', 15)
CDEK_LOCATION_CACHE_SECONDS = env_int('CDEK_LOCATION_CACHE_SECONDS', 6 * 60 * 60)
CDEK_LOCATION_COUNTRY_CODES = env_list('CDEK_LOCATION_COUNTRY_CODES', 'RU,KZ,BY,AM,KG,CN,TR,TH,DE')
CDEK_ORIGIN_CITY_CODE = env_int('CDEK_ORIGIN_CITY_CODE', 437)
CDEK_TARIFF_CODE_PICKUP = env_int('CDEK_TARIFF_CODE_PICKUP', 136)
CDEK_PACKAGE_WEIGHT_GRAMS = env_int('CDEK_PACKAGE_WEIGHT_GRAMS', 1000)
CDEK_PACKAGE_LENGTH_CM = env_int('CDEK_PACKAGE_LENGTH_CM', 30)
CDEK_PACKAGE_WIDTH_CM = env_int('CDEK_PACKAGE_WIDTH_CM', 30)
CDEK_PACKAGE_HEIGHT_CM = env_int('CDEK_PACKAGE_HEIGHT_CM', 10)

ALFA_ACQUIRING_BASE_URL = os.getenv('ALFA_ACQUIRING_BASE_URL', 'https://alfa.rbsuat.com/payment/rest')
ALFA_ACQUIRING_USERNAME = os.getenv('ALFA_ACQUIRING_USERNAME', '')
ALFA_ACQUIRING_PASSWORD = os.getenv('ALFA_ACQUIRING_PASSWORD', '')
ALFA_ACQUIRING_CURRENCY = os.getenv('ALFA_ACQUIRING_CURRENCY', '810')
ALFA_ACQUIRING_TIMEOUT = env_int('ALFA_ACQUIRING_TIMEOUT', 15)
ALFA_ACQUIRING_CALLBACK_TOKEN = os.getenv('ALFA_ACQUIRING_CALLBACK_TOKEN', '')

EMAIL_BACKEND = os.getenv('EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = os.getenv('EMAIL_HOST', '')
EMAIL_PORT = env_int('EMAIL_PORT', 587)
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS = env_bool('EMAIL_USE_TLS', True)
EMAIL_USE_SSL = env_bool('EMAIL_USE_SSL', False)
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', EMAIL_HOST_USER or 'no-reply@ditent.local')
DITENT_MANAGER_EMAILS = env_list('DITENT_MANAGER_EMAILS', '')
DITENT_EMAIL_NOTIFICATIONS_ENABLED = env_bool('DITENT_EMAIL_NOTIFICATIONS_ENABLED', True)

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


LOG_DIR = Path('/tmp/logs') if IS_VERCEL else BASE_DIR / os.getenv('LOG_DIR', 'logs')
LOG_DIR.mkdir(exist_ok=True)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'default': {
            'format': '[{asctime}] {levelname} {name}: {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'default',
        },
        'errors_file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': LOG_DIR / 'django-errors.log',
            'maxBytes': 1024 * 1024 * 5,
            'backupCount': 5,
            'formatter': 'default',
            'level': 'ERROR',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'errors_file'],
            'level': os.getenv('DJANGO_LOG_LEVEL', 'INFO'),
            'propagate': False,
        },
        'django.request': {
            'handlers': ['console', 'errors_file'],
            'level': 'ERROR',
            'propagate': False,
        },
        'shop': {
            'handlers': ['console', 'errors_file'],
            'level': os.getenv('SHOP_LOG_LEVEL', 'INFO'),
            'propagate': False,
        },
    },
}
