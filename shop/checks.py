from django.conf import settings
from django.core.checks import Error, Tags, Warning, register
from django.core.validators import validate_email
from django.core.exceptions import ValidationError


LOCAL_EMAIL_BACKENDS = {
    'django.core.mail.backends.console.EmailBackend',
    'django.core.mail.backends.dummy.EmailBackend',
    'django.core.mail.backends.locmem.EmailBackend',
}

LOCAL_CACHE_BACKENDS = {
    'django.core.cache.backends.dummy.DummyCache',
    'django.core.cache.backends.locmem.LocMemCache',
}

REQUIRED_PRODUCTION_SETTINGS = (
    ('CDEK_CLIENT_ID', 'shop.E001'),
    ('CDEK_CLIENT_SECRET', 'shop.E002'),
    ('ALFA_ACQUIRING_USERNAME', 'shop.E003'),
    ('ALFA_ACQUIRING_PASSWORD', 'shop.E004'),
    ('ALFA_ACQUIRING_CALLBACK_TOKEN', 'shop.E005'),
)

PLACEHOLDER_MARKERS = (
    'example.com',
    'change-me',
    'your-',
    'placeholder',
)


def is_blank(value):
    return value is None or str(value).strip() == ''


def is_placeholder(value):
    normalized = str(value or '').strip().lower()
    return any(marker in normalized for marker in PLACEHOLDER_MARKERS)


def required_setting_errors(settings_with_ids):
    errors = []

    for setting_name, check_id in settings_with_ids:
        if is_blank(getattr(settings, setting_name, '')):
            errors.append(
                Error(
                    f'Не задана настройка {setting_name}.',
                    hint='Заполните значение в production .env перед запуском сайта.',
                    id=check_id,
                )
            )

    return errors


def email_settings_errors():
    errors = []

    if not getattr(settings, 'DITENT_EMAIL_NOTIFICATIONS_ENABLED', True):
        errors.append(
            Warning(
                'Email-уведомления DiTent отключены.',
                hint='Для продакшена обычно нужно DITENT_EMAIL_NOTIFICATIONS_ENABLED=True, чтобы менеджеры и клиенты получали письма.',
                id='shop.W001',
            )
        )

    email_backend = getattr(settings, 'EMAIL_BACKEND', '')
    if email_backend in LOCAL_EMAIL_BACKENDS:
        errors.append(
            Error(
                f'Для production указан локальный EMAIL_BACKEND: {email_backend}.',
                hint='Подключите реальный SMTP/backend отправки писем.',
                id='shop.E010',
            )
        )

    if email_backend == 'django.core.mail.backends.smtp.EmailBackend' and is_blank(getattr(settings, 'EMAIL_HOST', '')):
        errors.append(
            Error(
                'Для SMTP не задан EMAIL_HOST.',
                hint='Укажите SMTP-хост в production .env.',
                id='shop.E011',
            )
        )

    if email_backend == 'django.core.mail.backends.smtp.EmailBackend' and is_placeholder(getattr(settings, 'EMAIL_HOST', '')):
        errors.append(
            Error(
                'EMAIL_HOST содержит placeholder-значение.',
                hint='Укажите реальный SMTP-хост почтового провайдера.',
                id='shop.E014',
            )
        )

    default_from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', '')
    if is_blank(default_from_email) or default_from_email.endswith('.local') or is_placeholder(default_from_email):
        errors.append(
            Error(
                'DEFAULT_FROM_EMAIL не похож на production email отправителя.',
                hint='Укажите рабочий адрес отправителя, например no-reply@company-domain.ru.',
                id='shop.E012',
            )
        )
    else:
        try:
            validate_email(default_from_email)
        except ValidationError:
            errors.append(
                Error(
                    'DEFAULT_FROM_EMAIL содержит некорректный email.',
                    hint='Исправьте адрес отправителя в production .env.',
                    id='shop.E013',
                )
            )

    return errors


def database_settings_errors():
    engine = settings.DATABASES.get('default', {}).get('ENGINE', '')

    if engine == 'django.db.backends.sqlite3':
        return [
            Error(
                'Production запущен на SQLite.',
                hint='Для боевого сайта настройте PostgreSQL через DB_ENGINE=postgresql и параметры DB_*.',
                id='shop.E040',
            )
        ]

    return []


def cache_settings_errors():
    backend = settings.CACHES.get('default', {}).get('BACKEND', '')

    if backend in LOCAL_CACHE_BACKENDS:
        return [
            Error(
                'Production использует локальный cache backend.',
                hint='Настройте общий cache backend для rate-limit и кеша СДЭК, например Redis/Memcached/DatabaseCache.',
                id='shop.E050',
            )
        ]

    return []


def placeholder_setting_errors():
    errors = []

    for setting_name, check_id in (
        ('ALFA_ACQUIRING_BASE_URL', 'shop.E021'),
        ('CDEK_CLIENT_ID', 'shop.E022'),
        ('CDEK_CLIENT_SECRET', 'shop.E023'),
        ('ALFA_ACQUIRING_USERNAME', 'shop.E024'),
        ('ALFA_ACQUIRING_PASSWORD', 'shop.E025'),
        ('ALFA_ACQUIRING_CALLBACK_TOKEN', 'shop.E026'),
    ):
        value = getattr(settings, setting_name, '')
        if not is_blank(value) and is_placeholder(value):
            errors.append(
                Error(
                    f'{setting_name} содержит placeholder-значение.',
                    hint='Замените пример из .env.example на реальные production-доступы.',
                    id=check_id,
                )
            )

    manager_emails = getattr(settings, 'DITENT_MANAGER_EMAILS', [])
    if any(is_placeholder(email) for email in manager_emails):
        errors.append(
            Error(
                'DITENT_MANAGER_EMAILS содержит placeholder email.',
                hint='Укажите реальные email менеджеров или настройте их в админке сайта.',
                id='shop.E027',
            )
        )

    return errors


@register(Tags.security, deploy=True)
def production_external_service_checks(app_configs, **kwargs):
    if settings.DEBUG:
        return []

    errors = []
    errors.extend(required_setting_errors(REQUIRED_PRODUCTION_SETTINGS))

    alfa_base_url = getattr(settings, 'ALFA_ACQUIRING_BASE_URL', '')
    if 'rbsuat' in alfa_base_url.lower():
        errors.append(
            Error(
                'ALFA_ACQUIRING_BASE_URL указывает на тестовый шлюз Альфа-Банка.',
                hint='Для production замените URL на боевой шлюз банка.',
                id='shop.E020',
            )
        )

    if getattr(settings, 'DITENT_AUTH_CODE_DEBUG_RESPONSE', False):
        errors.append(
            Error(
                'DITENT_AUTH_CODE_DEBUG_RESPONSE включен при DEBUG=False.',
                hint='Отключите выдачу кодов авторизации в ответе API на production.',
                id='shop.E030',
            )
        )

    errors.extend(placeholder_setting_errors())
    errors.extend(email_settings_errors())
    errors.extend(database_settings_errors())
    errors.extend(cache_settings_errors())
    return errors
