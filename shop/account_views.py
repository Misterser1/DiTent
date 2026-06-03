import json
import re
import secrets
import logging
from json import JSONDecodeError
from datetime import timedelta
from functools import wraps

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.hashers import check_password, make_password
from django.core.cache import cache
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.mail import send_mail
from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from .cart_services import attach_cart_to_user, cart_payload, normalize_item, save_session_cart
from .checkout_views import sync_alfa_order_payment_status
from .models import CustomerProfile, CustomerType, DrawingOrder, EmailAuthCode, EmailAuthPurpose, Order, OrderItemType, OrderStatus
from .validators import validate_latin_email, validate_ru_phone


logger = logging.getLogger(__name__)


def request_json(request):
    try:
        return json.loads(request.body.decode('utf-8') or '{}')
    except JSONDecodeError:
        return {}


def require_authenticated(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'ok': False, 'error': 'Для кабинета нужно войти в аккаунт.'}, status=401)

        return view_func(request, *args, **kwargs)

    return wrapper


def profile_for(user):
    profile, _ = CustomerProfile.objects.get_or_create(user=user)
    return profile


def customer_type_from_label(value):
    labels = {
        'Физическое лицо': CustomerType.PERSON,
        'ИП': CustomerType.ENTREPRENEUR,
        'Юридическое лицо': CustomerType.COMPANY,
        'individual': CustomerType.PERSON,
        'entrepreneur': CustomerType.ENTREPRENEUR,
        'company': CustomerType.COMPANY,
        CustomerType.PERSON: CustomerType.PERSON,
        CustomerType.ENTREPRENEUR: CustomerType.ENTREPRENEUR,
        CustomerType.COMPANY: CustomerType.COMPANY,
    }
    return labels.get(value, CustomerType.PERSON)


def phone_payload(value):
    try:
        return validate_ru_phone(value)
    except ValidationError:
        return value or ''


def user_payload(user):
    profile = profile_for(user)
    return {
        'id': user.id,
        'email': user.email,
        'firstName': user.first_name,
        'lastName': user.last_name,
        'middleName': profile.middle_name,
        'phone': phone_payload(profile.phone),
        'type': profile.customer_type,
        'typeTitle': profile.get_customer_type_display(),
        'companyLegalForm': profile.company_legal_form,
        'companyName': profile.company_name,
        'inn': profile.inn,
        'kpp': profile.kpp,
        'ogrn': profile.ogrn,
        'legalAddress': profile.legal_address,
        'settlementAccount': profile.settlement_account,
        'bank': profile.bank,
    }


def order_status_key(order):
    if order.status == OrderStatus.WAITING_PAYMENT and not order.payment_ready_at:
        return 'pending-manager-confirmation'

    return {
        'waiting_manager': 'pending-manager-confirmation',
        'waiting_payment': 'manager-confirmed',
        'in_production': 'processing',
        'in_delivery': 'processing',
        'completed': 'delivered',
        'canceled': 'canceled',
    }.get(order.status, order.status)


def item_payload(item):
    parameters = item.parameters or {}
    return {
        'id': item.id,
        'type': 'catalog-product' if item.item_type == OrderItemType.CATALOG else 'custom-cover',
        'title': item.title,
        'sku': item.sku,
        'quantity': item.quantity,
        'unitPrice': float(item.unit_price),
        'totalPrice': float(item.total_price),
        'shape': {'key': item.shape, 'title': item.get_shape_display() if item.shape else 'Готовое изделие из каталога'},
        'dimensions': parameters.get('dimensions', []),
        'fabric': parameters.get('fabric', {}),
        'color': parameters.get('color', {}),
        'fastener': parameters.get('fastener', {}),
        'accessory': parameters.get('accessory'),
        'comments': parameters.get('comments', ''),
        'attachments': [{'id': file.id, 'name': file.original_name, 'url': file.file.url} for file in item.files.all()],
    }


def order_payload(order):
    sync_alfa_order_payment_status(order)
    items = [item_payload(item) for item in order.items.all()]
    return {
        'id': order.number,
        'status': order_status_key(order),
        'statusTitle': OrderStatus.WAITING_MANAGER.label if order.status == OrderStatus.WAITING_PAYMENT and not order.payment_ready_at else order.get_status_display(),
        'createdAt': order.created_at.isoformat(),
        'updatedAt': order.updated_at.isoformat(),
        'items': items,
        'summary': {
            'subtotal': float(order.items_total),
            'discount': float(order.discount_total),
            'delivery': float(order.delivery_total),
            'vat': float(order.vat_total),
            'total': float(order.total),
        },
        'client': {
            'email': order.email,
            'phone': phone_payload(order.phone),
            'name': order.customer_name,
            'type': order.customer_type,
            'typeTitle': order.get_customer_type_display(),
            'companyLegalForm': order.company_legal_form,
            'companyName': order.company_name,
            'inn': order.inn,
            'kpp': order.kpp,
            'ogrn': order.ogrn,
            'legalAddress': order.legal_address,
            'settlementAccount': order.settlement_account,
            'bank': order.bank,
        },
        'delivery': {
            'method': order.delivery_method,
            'city': order.delivery_city,
            'address': order.delivery_address,
            'trackNumber': order.track_number,
            'cdekStatusCode': order.cdek_status_code,
            'cdekStatusName': order.cdek_status_name,
            'cdekStatusUpdatedAt': order.cdek_status_updated_at.isoformat() if order.cdek_status_updated_at else '',
            'cdekTrackingCheckedAt': order.cdek_tracking_checked_at.isoformat() if order.cdek_tracking_checked_at else '',
        },
        'payment': {
            'method': order.payment_method,
            'methodTitle': order.get_payment_method_display() if order.payment_method else '',
            'status': order.payment_status,
            'statusTitle': order.get_payment_status_display(),
        },
        'canRepeat': True,
        'canPay': bool(order.status == 'waiting_payment' and order.payment_ready_at and order.payment_form_url),
        'paymentUrl': order.payment_form_url if order.status == 'waiting_payment' and order.payment_ready_at else '',
    }


def drawing_order_status_key(order):
    return {
        'waiting_manager': 'pending-manager-calculation',
        'waiting_payment': 'manager-confirmed',
        'in_production': 'processing',
        'in_delivery': 'processing',
        'completed': 'delivered',
        'canceled': 'canceled',
    }.get(order.status, order.status)


def drawing_order_payload(order):
    files = [{'id': file.id, 'name': file.original_name or file.file.name, 'url': file.file.url} for file in order.files.all()]
    return {
        'id': f'DR-{order.pk:06d}',
        'type': 'drawing-order',
        'status': drawing_order_status_key(order),
        'statusTitle': 'Ожидает расчета менеджером' if order.status == 'waiting_manager' else order.get_status_display(),
        'createdAt': order.created_at.isoformat(),
        'updatedAt': order.updated_at.isoformat(),
        'items': [{
            'type': 'drawing-order',
            'title': 'Заявка по чертежу',
            'quantity': None,
            'totalPrice': None,
            'totalTitle': 'После расчета',
            'comments': order.comment,
            'attachments': files,
        }],
        'summary': {
            'subtotal': None,
            'discount': 0,
            'delivery': 0,
            'vat': 0,
            'total': None,
            'totalTitle': 'После расчета',
        },
        'client': {
            'email': order.email,
            'phone': phone_payload(order.phone),
            'name': order.customer_name,
            'type': order.customer_type,
            'typeTitle': order.get_customer_type_display(),
            'companyLegalForm': order.company_legal_form,
            'companyName': order.company_name,
            'inn': order.inn,
            'kpp': order.kpp,
            'ogrn': order.ogrn,
            'legalAddress': order.legal_address,
            'settlementAccount': order.settlement_account,
            'bank': order.bank,
        },
        'drawing': {
            'files': files,
            'filesCount': len(files),
            'comment': order.comment,
        },
        'payment': {
            'method': '',
            'methodTitle': '',
            'status': '',
            'statusTitle': '',
        },
        'canRepeat': False,
        'canPay': False,
    }


def get_user_by_email(email):
    User = get_user_model()
    return User.objects.filter(email__iexact=email).first()


def login_attempt_key(request, email):
    return f'ditent-login-attempts:{email}:{client_ip(request)}'


def client_ip(request):
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    return forwarded.split(',')[0].strip() or request.META.get('REMOTE_ADDR', 'unknown')


def login_attempts_exceeded(request, email):
    return int(cache.get(login_attempt_key(request, email), 0)) >= settings.DITENT_LOGIN_ATTEMPT_LIMIT


def record_failed_login(request, email):
    key = login_attempt_key(request, email)
    attempts = int(cache.get(key, 0)) + 1
    cache.set(key, attempts, settings.DITENT_LOGIN_ATTEMPT_WINDOW_SECONDS)
    return attempts


def clear_failed_login(request, email):
    cache.delete(login_attempt_key(request, email))


def auth_code_ip_key(request):
    return f'ditent-auth-code-ip:{client_ip(request)}'


def auth_code_ip_limit_exceeded(request):
    return int(cache.get(auth_code_ip_key(request), 0)) >= settings.DITENT_AUTH_CODE_IP_LIMIT


def record_auth_code_ip_request(request):
    key = auth_code_ip_key(request)
    count = int(cache.get(key, 0)) + 1
    cache.set(key, count, settings.DITENT_AUTH_CODE_IP_WINDOW_SECONDS)
    return count


def auth_code_rate_limit_response():
    return JsonResponse({
        'ok': False,
        'error': 'Слишком много запросов кода. Попробуйте позже.',
    }, status=429)


def unique_username(email):
    User = get_user_model()
    username_base = email.split('@')[0] or 'client'
    username = username_base
    counter = 1

    while User.objects.filter(username=username).exists():
        counter += 1
        username = f'{username_base}-{counter}'

    return username


def generate_email_code():
    return ''.join(secrets.choice('0123456789') for _ in range(6))


def truthy(value):
    if isinstance(value, bool):
        return value

    return str(value).strip().lower() in {'1', 'true', 'yes', 'on', 'checked'}


def text_payload(payload, key, max_length):
    return str(payload.get(key) or '').strip()[:max_length]


def only_digits(value):
    return ''.join(char for char in str(value or '') if char.isdigit())


def is_business_customer_type(value):
    return customer_type_from_label(value) in {CustomerType.ENTREPRENEUR, CustomerType.COMPANY}


def requisites_payload(payload):
    return {
        'companyLegalForm': text_payload(payload, 'companyLegalForm', 40),
        'companyName': text_payload(payload, 'companyName', 180),
        'inn': text_payload(payload, 'inn', 20),
        'kpp': text_payload(payload, 'kpp', 20),
        'ogrn': text_payload(payload, 'ogrn', 30),
        'legalAddress': text_payload(payload, 'legalAddress', 500),
        'settlementAccount': text_payload(payload, 'settlementAccount', 40),
        'bank': text_payload(payload, 'bank', 180),
    }


def validate_requisites_payload(payload, customer_type):
    if not is_business_customer_type(customer_type):
        return {}

    errors = {}
    requisites = requisites_payload(payload)
    is_company = customer_type_from_label(customer_type) == CustomerType.COMPANY

    if not requisites['companyLegalForm']:
        errors['companyLegalForm'] = 'Выберите форму юр. лица.'
    if not requisites['companyName'] or len(requisites['companyName']) < 2:
        errors['companyName'] = 'Введите название компании.'

    inn = only_digits(requisites['inn'])
    if len(inn) not in ({10} if is_company else {12}):
        errors['inn'] = 'Введите корректный ИНН.'

    kpp = only_digits(requisites['kpp'])
    if is_company and len(kpp) != 9:
        errors['kpp'] = 'Введите корректный КПП.'
    if not is_company and kpp and len(kpp) != 9:
        errors['kpp'] = 'Введите корректный КПП или оставьте поле пустым.'

    ogrn = only_digits(requisites['ogrn'])
    if len(ogrn) not in ({13} if is_company else {15}):
        errors['ogrn'] = 'Введите корректный ОГРН или ОГРНИП.'

    if not requisites['legalAddress'] or len(requisites['legalAddress']) < 5:
        errors['legalAddress'] = 'Введите юридический адрес.'

    settlement_account = only_digits(requisites['settlementAccount'])
    if len(settlement_account) != 20:
        errors['settlementAccount'] = 'Введите 20 цифр расчетного счета.'

    if not requisites['bank'] or len(requisites['bank']) < 2:
        errors['bank'] = 'Введите банк.'

    return errors


def is_valid_phone(phone):
    try:
        validate_ru_phone(phone)
    except ValidationError:
        return False

    return True


def is_valid_person_name(value, required=True):
    value = (value or '').strip()

    if not value:
        return not required

    if len(value) < 2 or len(value) > 80:
        return False

    return bool(re.fullmatch(r"[A-Za-zА-Яа-яЁё]+(?:[ '-][A-Za-zА-Яа-яЁё]+)*", value))


def validate_email_auth_payload(payload, purpose):
    errors = {}

    try:
        email = validate_latin_email(payload.get('email'))
    except ValidationError:
        email = (payload.get('email') or '').strip().lower()
        errors['email'] = 'Введите корректный e-mail.'

    if purpose == EmailAuthPurpose.REGISTER:
        if not is_valid_person_name(payload.get('lastName')):
            errors['lastName'] = 'Введите корректную фамилию.'
        if not is_valid_person_name(payload.get('firstName')):
            errors['firstName'] = 'Введите корректное имя.'
        if not is_valid_person_name(payload.get('middleName'), required=False):
            errors['middleName'] = 'Введите корректное отчество.'
        if not is_valid_phone(payload.get('phone')):
            errors['phone'] = 'Введите корректный номер телефона.'
        else:
            payload['phone'] = validate_ru_phone(payload.get('phone'))
        if not truthy(payload.get('agreement')):
            errors['agreement'] = 'Подтвердите согласие на обработку данных.'
        errors.update(validate_requisites_payload(payload, payload.get('customerType')))

    if purpose == EmailAuthPurpose.LOGIN and not truthy(payload.get('agreement')):
        errors['agreement'] = 'Подтвердите согласие на обработку данных.'

    return email, errors


def send_email_auth_code(email, code, purpose):
    title = 'входа' if purpose == EmailAuthPurpose.LOGIN else 'регистрации'
    subject = f'Код {title} DiTent'
    message = (
        f'Ваш код {title} DiTent: {code}\n\n'
        f'Код действует {settings.DITENT_AUTH_CODE_TTL_MINUTES} минут. '
        'Если вы не запрашивали код, просто проигнорируйте это письмо.'
    )
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [email], fail_silently=False)


@require_GET
def auth_status_api(request):
    return JsonResponse({
        'ok': True,
        'authenticated': request.user.is_authenticated,
        'user': user_payload(request.user) if request.user.is_authenticated else None,
    })


@require_POST
def register_api(request):
    payload = request_json(request)
    password = payload.get('password') or ''

    try:
        email = validate_latin_email(payload.get('email'))
    except ValidationError:
        return JsonResponse({'ok': False, 'error': 'Введите корректный e-mail.'}, status=400)
    if len(password) < 6:
        return JsonResponse({'ok': False, 'error': 'Пароль должен быть не короче 6 символов.'}, status=400)
    if payload.get('phone'):
        try:
            payload['phone'] = validate_ru_phone(payload.get('phone'))
        except ValidationError:
            return JsonResponse({'ok': False, 'error': 'Введите корректный номер телефона.'}, status=400)
    if not truthy(payload.get('agreement')):
        return JsonResponse({'ok': False, 'error': 'Подтвердите согласие на обработку данных.'}, status=400)
    requisite_errors = validate_requisites_payload(payload, payload.get('type') or payload.get('customerType'))
    if requisite_errors:
        return JsonResponse({'ok': False, 'errors': requisite_errors, 'error': 'Проверьте реквизиты.'}, status=400)
    if get_user_by_email(email):
        return JsonResponse({'ok': False, 'error': 'Аккаунт с таким e-mail уже существует. Войдите или восстановите пароль.'}, status=400)

    User = get_user_model()
    username_base = email.split('@')[0] or 'client'
    username = username_base
    counter = 1
    while User.objects.filter(username=username).exists():
        counter += 1
        username = f'{username_base}-{counter}'

    user = User.objects.create_user(
        username=username,
        email=email,
        password=password,
        first_name=payload.get('firstName', ''),
        last_name=payload.get('lastName', ''),
    )
    profile = profile_for(user)
    profile.middle_name = payload.get('middleName', '')
    profile.phone = payload.get('phone', '')
    profile.customer_type = customer_type_from_label(payload.get('type') or payload.get('customerType'))
    profile.company_legal_form = text_payload(payload, 'companyLegalForm', 40)
    profile.company_name = text_payload(payload, 'companyName', 180)
    profile.inn = text_payload(payload, 'inn', 20)
    profile.kpp = text_payload(payload, 'kpp', 20)
    profile.ogrn = text_payload(payload, 'ogrn', 30)
    profile.legal_address = text_payload(payload, 'legalAddress', 500)
    profile.settlement_account = text_payload(payload, 'settlementAccount', 40)
    profile.bank = text_payload(payload, 'bank', 180)
    profile.save()
    login(request, user)
    attach_cart_to_user(request, user)

    return JsonResponse({'ok': True, 'user': user_payload(user), **cart_payload(request)})


@require_POST
def login_api(request):
    payload = request_json(request)
    email = (payload.get('email') or '').strip().lower()
    password = payload.get('password') or ''
    user = get_user_by_email(email)

    if email and login_attempts_exceeded(request, email):
        return JsonResponse({'ok': False, 'error': 'Слишком много попыток входа. Попробуйте позже.'}, status=429)

    if not user:
        return JsonResponse({'ok': False, 'error': 'Пользователь с таким e-mail не найден.'}, status=400)

    authenticated = authenticate(request, username=user.username, password=password)
    if not authenticated:
        record_failed_login(request, email)
        return JsonResponse({'ok': False, 'error': 'Неверный пароль.'}, status=400)

    clear_failed_login(request, email)
    login(request, authenticated)
    attach_cart_to_user(request, authenticated)
    return JsonResponse({'ok': True, 'user': user_payload(authenticated), **cart_payload(request)})


@require_POST
def auth_code_request_api(request):
    payload = request_json(request)
    purpose = payload.get('purpose') if payload.get('purpose') in EmailAuthPurpose.values else EmailAuthPurpose.LOGIN
    email, errors = validate_email_auth_payload(payload, purpose)

    if errors:
        return JsonResponse({'ok': False, 'errors': errors, 'error': 'Проверьте данные формы.'}, status=400)

    existing_user = get_user_by_email(email)
    if purpose == EmailAuthPurpose.LOGIN and not existing_user:
        return JsonResponse({'ok': False, 'error': 'Аккаунт с таким e-mail не найден. Пройдите регистрацию.'}, status=404)
    if purpose == EmailAuthPurpose.REGISTER and existing_user:
        return JsonResponse({'ok': False, 'error': 'Аккаунт с таким e-mail уже существует. Войдите по коду.'}, status=400)

    if auth_code_ip_limit_exceeded(request):
        return auth_code_rate_limit_response()

    now = timezone.now()
    recent_code = EmailAuthCode.objects.filter(
        email=email,
        purpose=purpose,
        created_at__gt=now - timedelta(seconds=settings.DITENT_AUTH_CODE_RESEND_SECONDS),
    ).first()
    if recent_code:
        retry_at = recent_code.created_at + timedelta(seconds=settings.DITENT_AUTH_CODE_RESEND_SECONDS)
        retry_after = max(1, int((retry_at - now).total_seconds()))
        return JsonResponse({
            'ok': False,
            'error': f'Код уже отправлен. Новый код можно запросить через {retry_after} сек.',
            'retryAfterSeconds': retry_after,
            'retryAt': retry_at.isoformat(),
        }, status=429)

    record_auth_code_ip_request(request)
    code = generate_email_code()
    EmailAuthCode.objects.filter(email=email, purpose=purpose, used_at__isnull=True).update(used_at=now)
    auth_code = EmailAuthCode.objects.create(
        email=email,
        purpose=purpose,
        code_hash=make_password(code),
        payload={
            'email': email,
            'firstName': (payload.get('firstName') or '').strip(),
            'lastName': (payload.get('lastName') or '').strip(),
            'middleName': (payload.get('middleName') or '').strip(),
            'phone': validate_ru_phone(payload.get('phone')) if payload.get('phone') else '',
            'type': payload.get('type') or payload.get('customerType') or '',
            **requisites_payload(payload),
        },
        expires_at=now + timedelta(minutes=settings.DITENT_AUTH_CODE_TTL_MINUTES),
    )

    try:
        send_email_auth_code(email, code, purpose)
    except Exception:
        auth_code.used_at = now
        auth_code.save(update_fields=['used_at', 'updated_at'])
        logger.exception('Failed to send auth code email to %s', email)
        return JsonResponse({'ok': False, 'error': 'Не удалось отправить код на e-mail. Попробуйте позже.'}, status=502)

    response = {
        'ok': True,
        'message': 'Код отправлен на e-mail.',
        'expiresAt': auth_code.expires_at.isoformat(),
    }
    if settings.DITENT_AUTH_CODE_DEBUG_RESPONSE:
        response['debugCode'] = code

    return JsonResponse(response)


@require_POST
def auth_code_verify_api(request):
    payload = request_json(request)
    purpose = payload.get('purpose') if payload.get('purpose') in EmailAuthPurpose.values else EmailAuthPurpose.LOGIN
    code = ''.join(char for char in str(payload.get('code') or '') if char.isdigit())

    try:
        email = validate_latin_email(payload.get('email'))
    except ValidationError:
        email = ''

    if not email or len(code) != 6:
        return JsonResponse({'ok': False, 'error': 'Введите e-mail и 6-значный код.'}, status=400)

    auth_code = EmailAuthCode.objects.filter(email=email, purpose=purpose, used_at__isnull=True).first()
    now = timezone.now()

    if not auth_code or auth_code.expires_at <= now:
        return JsonResponse({'ok': False, 'error': 'Код недействителен или истек. Запросите новый код.'}, status=400)
    if auth_code.attempts >= auth_code.max_attempts:
        auth_code.used_at = now
        auth_code.save(update_fields=['used_at', 'updated_at'])
        return JsonResponse({'ok': False, 'error': 'Превышено количество попыток. Запросите новый код.'}, status=400)

    auth_code.attempts += 1
    auth_code.save(update_fields=['attempts', 'updated_at'])

    if not check_password(code, auth_code.code_hash):
        return JsonResponse({'ok': False, 'error': 'Неверный код.'}, status=400)

    User = get_user_model()
    user = get_user_by_email(email)

    if purpose == EmailAuthPurpose.REGISTER:
        if user:
            return JsonResponse({'ok': False, 'error': 'Аккаунт с таким e-mail уже существует. Войдите по коду.'}, status=400)

        user = User.objects.create_user(
            username=unique_username(email),
            email=email,
            password=None,
            first_name=auth_code.payload.get('firstName', ''),
            last_name=auth_code.payload.get('lastName', ''),
        )
        user.set_unusable_password()
        user.save(update_fields=['password'])
        profile = profile_for(user)
        profile.middle_name = auth_code.payload.get('middleName', '')
        profile.phone = auth_code.payload.get('phone', '')
        profile.customer_type = customer_type_from_label(auth_code.payload.get('type'))
        profile.company_legal_form = auth_code.payload.get('companyLegalForm', '')
        profile.company_name = auth_code.payload.get('companyName', '')
        profile.inn = auth_code.payload.get('inn', '')
        profile.kpp = auth_code.payload.get('kpp', '')
        profile.ogrn = auth_code.payload.get('ogrn', '')
        profile.legal_address = auth_code.payload.get('legalAddress', '')
        profile.settlement_account = auth_code.payload.get('settlementAccount', '')
        profile.bank = auth_code.payload.get('bank', '')
        profile.save(update_fields=[
            'middle_name',
            'phone',
            'customer_type',
            'company_legal_form',
            'company_name',
            'inn',
            'kpp',
            'ogrn',
            'legal_address',
            'settlement_account',
            'bank',
            'updated_at',
        ])
    elif not user:
        return JsonResponse({'ok': False, 'error': 'Аккаунт с таким e-mail не найден. Пройдите регистрацию.'}, status=404)

    auth_code.used_at = now
    auth_code.save(update_fields=['used_at', 'updated_at'])
    login(request, user)
    attach_cart_to_user(request, user)

    return JsonResponse({'ok': True, 'user': user_payload(user), **cart_payload(request)})


@require_POST
def logout_api(request):
    logout(request)
    return JsonResponse({'ok': True})


@require_POST
def password_reset_api(request):
    payload = request_json(request)

    try:
        email = validate_latin_email(payload.get('email'))
    except ValidationError:
        return JsonResponse({'ok': False, 'error': 'Введите корректный e-mail.'}, status=400)

    if auth_code_ip_limit_exceeded(request):
        return auth_code_rate_limit_response()

    record_auth_code_ip_request(request)
    user = get_user_by_email(email)
    if user:
        now = timezone.now()
        code = generate_email_code()
        EmailAuthCode.objects.filter(email=email, purpose=EmailAuthPurpose.LOGIN, used_at__isnull=True).update(used_at=now)
        auth_code = EmailAuthCode.objects.create(
            email=email,
            purpose=EmailAuthPurpose.LOGIN,
            code_hash=make_password(code),
            expires_at=now + timedelta(minutes=settings.DITENT_AUTH_CODE_TTL_MINUTES),
        )
        try:
            send_email_auth_code(email, code, EmailAuthPurpose.LOGIN)
        except Exception:
            auth_code.used_at = now
            auth_code.save(update_fields=['used_at', 'updated_at'])
            logger.exception('Failed to send password reset login code to %s', email)

    return JsonResponse({'ok': True, 'message': 'Если аккаунт существует, код входа будет отправлен на e-mail.'})


@require_authenticated
@require_GET
def cabinet_profile_api(request):
    return JsonResponse({'ok': True, 'profile': user_payload(request.user)})


@require_authenticated
@require_POST
def cabinet_profile_update_api(request):
    payload = request_json(request)
    profile = profile_for(request.user)

    try:
        email = validate_latin_email(payload.get('email'))
    except ValidationError:
        return JsonResponse({'ok': False, 'error': 'Введите корректный e-mail.'}, status=400)
    if not is_valid_person_name(payload.get('lastName')):
        return JsonResponse({'ok': False, 'error': 'Введите корректную фамилию.'}, status=400)
    if not is_valid_person_name(payload.get('firstName')):
        return JsonResponse({'ok': False, 'error': 'Введите корректное имя.'}, status=400)
    if not is_valid_person_name(payload.get('middleName'), required=False):
        return JsonResponse({'ok': False, 'error': 'Введите корректное отчество.'}, status=400)
    try:
        phone = validate_ru_phone(payload.get('phone'))
    except ValidationError:
        return JsonResponse({'ok': False, 'error': 'Введите корректный номер телефона.'}, status=400)
    requisite_errors = validate_requisites_payload(payload, profile.customer_type)
    if requisite_errors:
        return JsonResponse({'ok': False, 'error': next(iter(requisite_errors.values())), 'errors': requisite_errors}, status=400)

    existing = get_user_by_email(email)
    if existing and existing.pk != request.user.pk:
        return JsonResponse({'ok': False, 'error': 'Этот e-mail уже используется другим аккаунтом.'}, status=400)

    user = request.user
    user.email = email
    user.first_name = payload.get('firstName', '')
    user.last_name = payload.get('lastName', '')
    user.save(update_fields=['email', 'first_name', 'last_name'])
    profile.middle_name = payload.get('middleName', '')
    profile.phone = phone
    profile.company_legal_form = text_payload(payload, 'companyLegalForm', 40)
    profile.company_name = text_payload(payload, 'companyName', 180)
    profile.inn = text_payload(payload, 'inn', 20)
    profile.kpp = text_payload(payload, 'kpp', 20)
    profile.ogrn = text_payload(payload, 'ogrn', 30)
    profile.legal_address = text_payload(payload, 'legalAddress', 500)
    profile.settlement_account = text_payload(payload, 'settlementAccount', 40)
    profile.bank = text_payload(payload, 'bank', 180)
    profile.save(update_fields=[
        'middle_name',
        'phone',
        'company_legal_form',
        'company_name',
        'inn',
        'kpp',
        'ogrn',
        'legal_address',
        'settlement_account',
        'bank',
        'updated_at',
    ])

    return JsonResponse({'ok': True, 'profile': user_payload(user)})


@require_authenticated
@require_GET
def cabinet_orders_api(request):
    orders = (
        Order.objects
        .filter(user=request.user)
        .prefetch_related('items', 'items__files')
        .order_by('-created_at')
    )
    drawing_orders = (
        DrawingOrder.objects
        .filter(user=request.user)
        .prefetch_related('files')
        .order_by('-created_at')
    )
    payload = [order_payload(order) for order in orders] + [drawing_order_payload(order) for order in drawing_orders]
    payload.sort(key=lambda item: item.get('createdAt') or '', reverse=True)
    return JsonResponse({'ok': True, 'orders': payload})


@require_authenticated
@require_GET
def cabinet_order_detail_api(request, number):
    order = (
        Order.objects
        .filter(user=request.user, number=number)
        .prefetch_related('items', 'items__files')
        .first()
    )

    if not order:
        return JsonResponse({'ok': False, 'error': 'Заказ не найден.'}, status=404)

    return JsonResponse({'ok': True, 'order': order_payload(order)})


@require_authenticated
@require_POST
def cabinet_repeat_order_api(request, number):
    order = (
        Order.objects
        .filter(user=request.user, number=number)
        .prefetch_related('items', 'items__files')
        .first()
    )

    if not order:
        return JsonResponse({'ok': False, 'error': 'Заказ не найден.'}, status=404)

    next_cart = []
    added_count = 0
    skipped_count = 0
    for item in order_payload(order)['items']:
        try:
            next_cart.append(normalize_item(item, cart=next_cart))
            added_count += 1
        except (ValidationError, ObjectDoesNotExist):
            skipped_count += 1

    if added_count == 0:
        return JsonResponse({
            'ok': False,
            'error': 'Позиции этого заказа больше недоступны для повторения.',
        }, status=400)

    with transaction.atomic():
        save_session_cart(request, next_cart)

    payload = cart_payload(request)
    payload['skippedCount'] = skipped_count
    return JsonResponse(payload)
