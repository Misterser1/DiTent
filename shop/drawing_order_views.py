import re

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from .models import CustomerType, DrawingOrder, DrawingOrderFile, OrderStatus
from .notifications import send_drawing_order_created_notifications
from .validators import validate_uploaded_files


def text_value(request, name):
    return str(request.POST.get(name) or '').strip()


def customer_type_from_form(value):
    return {
        'individual': CustomerType.PERSON,
        'company': CustomerType.COMPANY,
        CustomerType.PERSON: CustomerType.PERSON,
        CustomerType.COMPANY: CustomerType.COMPANY,
    }.get(value, CustomerType.PERSON)


def is_valid_phone(phone):
    value = (phone or '').strip()

    if not value or len(value) > 40:
        return False

    if re.search(r'[^\d\s()+.-]', value):
        return False

    if value.count('+') > 1 or ('+' in value and not value.startswith('+')):
        return False

    digits = re.sub(r'\D', '', value)
    return 10 <= len(digits) <= 15


def has_meaningful_text(value):
    return bool(re.search(r'[A-Za-zА-Яа-яЁё0-9]', value or ''))


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

    try:
        validate_email(email)
    except ValidationError:
        errors['email'] = 'Введите корректный e-mail.'
    else:
        validate_text_length(errors, 'email', email, 254, 'E-mail должен быть не длиннее 254 символов.')

    if item_name and (len(item_name) > 180 or not has_meaningful_text(item_name)):
        errors['itemName'] = 'Укажите корректное название изделия.'

    if not is_valid_dimensions(dimensions):
        errors['dimensions'] = 'Укажите размеры в понятном формате, например: 300 x 100 x 75 см.'

    validate_text_length(errors, 'comment', comment, 2000, 'Комментарий должен быть не длиннее 2000 символов.')

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
        customer_name=customer_name,
        phone=phone,
        email=email,
        comment='\n'.join(part for part in [
            f'Изделие: {item_name}' if item_name else '',
            f'Размеры: {dimensions}' if dimensions else '',
            comment,
        ] if part),
        return_terms_accepted=True,
    )

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
