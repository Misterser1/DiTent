import re

from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from .models import CustomerProfile, CustomerType, DrawingOrder, DrawingOrderFile, OrderStatus
from .notifications import send_drawing_order_created_notifications
from .validators import validate_latin_email, validate_ru_phone, validate_uploaded_files


def text_value(request, name):
    return str(request.POST.get(name) or '').strip()


def customer_type_from_form(value):
    return {
        'Физическое лицо': CustomerType.PERSON,
        'ИП': CustomerType.ENTREPRENEUR,
        'Юридическое лицо': CustomerType.COMPANY,
        'individual': CustomerType.PERSON,
        'entrepreneur': CustomerType.ENTREPRENEUR,
        'company': CustomerType.COMPANY,
        CustomerType.PERSON: CustomerType.PERSON,
        CustomerType.ENTREPRENEUR: CustomerType.ENTREPRENEUR,
        CustomerType.COMPANY: CustomerType.COMPANY,
    }.get(value, CustomerType.PERSON)


def field_value(request, name, max_length):
    return text_value(request, name)[:max_length]


def only_digits(value):
    return ''.join(char for char in str(value or '') if char.isdigit())


def business_requisites(request):
    return {
        'company_legal_form': field_value(request, 'companyLegalForm', 40),
        'company_name': field_value(request, 'companyName', 180),
        'inn': field_value(request, 'inn', 20),
        'kpp': field_value(request, 'kpp', 20),
        'ogrn': field_value(request, 'ogrn', 30),
        'legal_address': field_value(request, 'legalAddress', 500),
        'settlement_account': field_value(request, 'settlementAccount', 40),
        'bank': field_value(request, 'bank', 180),
    }


def validate_business_requisites(errors, requisites, customer_type):
    if customer_type not in {CustomerType.ENTREPRENEUR, CustomerType.COMPANY}:
        return

    is_company = customer_type == CustomerType.COMPANY

    if not requisites['company_legal_form']:
        errors['companyLegalForm'] = 'Выберите форму юр. лица.'
    if not requisites['company_name'] or len(requisites['company_name']) < 2:
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

    if not requisites['legal_address'] or len(requisites['legal_address']) < 5:
        errors['legalAddress'] = 'Введите юридический адрес.'

    settlement_account = only_digits(requisites['settlement_account'])
    if len(settlement_account) != 20:
        errors['settlementAccount'] = 'Введите 20 цифр расчетного счета.'

    if not requisites['bank'] or len(requisites['bank']) < 2:
        errors['bank'] = 'Введите банк.'


def is_valid_phone(phone):
    try:
        validate_ru_phone(phone)
    except ValidationError:
        return False

    return True


def has_meaningful_text(value):
    return any(char.isalnum() for char in value or '')


def validate_text_length(errors, field, value, max_length, message):
    if len(value or '') > max_length:
        errors[field] = message


def is_valid_dimensions(value):
    value = (value or '').strip()

    if not value:
        return True

    return (
        len(value) <= 180
        and bool(re.search(r'\d', value))
        and bool(re.fullmatch(r'[0-9A-Za-zА-Яа-яЁё\s.,:;xхХ*×/\\()\-+]+', value))
    )


@require_POST
def drawing_order_create_api(request):
    if not request.user.is_authenticated:
        return JsonResponse({'ok': False, 'error': 'Для отправки заявки нужно войти или зарегистрироваться.'}, status=401)

    files = request.FILES.getlist('drawing')
    errors = {}
    customer_name = text_value(request, 'clientName')
    phone = text_value(request, 'phone')
    email = text_value(request, 'email').lower()
    customer_type = customer_type_from_form(text_value(request, 'clientType'))
    requisites = business_requisites(request)
    item_name = text_value(request, 'itemName')
    dimensions = text_value(request, 'dimensions')
    comment = text_value(request, 'comment')

    if not files:
        errors['drawing'] = 'Загрузите чертеж, эскиз или фото изделия.'

    if not customer_name:
        errors['clientName'] = 'Укажите имя или компанию.'
    elif len(customer_name) < 2 or len(customer_name) > 180 or not has_meaningful_text(customer_name):
        errors['clientName'] = 'Введите корректное имя или название компании.'

    if not phone:
        errors['phone'] = 'Укажите телефон.'
    elif not is_valid_phone(phone):
        errors['phone'] = 'Введите корректный номер телефона.'
    else:
        phone = validate_ru_phone(phone)

    try:
        email = validate_latin_email(email)
    except ValidationError:
        errors['email'] = 'Введите корректный e-mail.'
    else:
        validate_text_length(errors, 'email', email, 254, 'E-mail должен быть не длиннее 254 символов.')

    if item_name and (len(item_name) > 180 or not has_meaningful_text(item_name)):
        errors['itemName'] = 'Укажите корректное название изделия.'

    if not is_valid_dimensions(dimensions):
        errors['dimensions'] = 'Укажите размеры в понятном формате, например: 300 x 100 x 75 см.'

    validate_text_length(errors, 'comment', comment, 2000, 'Комментарий должен быть не длиннее 2000 символов.')
    validate_business_requisites(errors, requisites, customer_type)

    if request.POST.get('agreement') not in {'on', 'true', '1', 'yes'}:
        errors['agreement'] = 'Подтвердите согласие на обработку данных.'

    if errors:
        return JsonResponse({'ok': False, 'errors': errors}, status=400)

    try:
        validate_uploaded_files(files)
    except ValidationError as exc:
        return JsonResponse({'ok': False, 'errors': {'drawing': exc.messages}}, status=400)

    drawing_order = DrawingOrder.objects.create(
        user=request.user,
        status=OrderStatus.WAITING_MANAGER,
        customer_type=customer_type,
        customer_name=customer_name,
        phone=phone,
        email=email,
        **requisites,
        comment='\n'.join(part for part in [
            f'Изделие: {item_name}' if item_name else '',
            f'Размеры: {dimensions}' if dimensions else '',
            comment,
        ] if part),
        return_terms_accepted=True,
    )

    profile, _ = CustomerProfile.objects.get_or_create(user=request.user)
    profile.phone = phone
    profile.customer_type = customer_type
    profile.company_legal_form = requisites['company_legal_form']
    profile.company_name = requisites['company_name']
    profile.inn = requisites['inn']
    profile.kpp = requisites['kpp']
    profile.ogrn = requisites['ogrn']
    profile.legal_address = requisites['legal_address']
    profile.settlement_account = requisites['settlement_account']
    profile.bank = requisites['bank']
    profile.save(update_fields=[
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

    for file in files:
        DrawingOrderFile.objects.create(
            drawing_order=drawing_order,
            file=file,
            original_name=file.name,
        )

    manager_url = request.build_absolute_uri('/ditent-cms/#drawing-orders')
    transaction.on_commit(
        lambda order_id=drawing_order.pk, manager_url=manager_url: send_drawing_order_created_notifications(
            order_id,
            manager_url=manager_url,
        )
    )

    return JsonResponse({
        'ok': True,
        'request': {
            'id': f'DR-{drawing_order.pk:06d}',
            'status': 'pending-manager-calculation',
            'statusTitle': 'Ожидает расчета менеджером',
            'files': drawing_order.files.count(),
        },
    }, status=201)
