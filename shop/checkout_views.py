import json
import logging
import uuid
from json import JSONDecodeError
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_http_methods, require_POST

from .alfa_acquiring import AlfaAcquiringError, get_payment_status, verify_callback_checksum
from .cart_services import attach_cart_to_user, clear_session_cart, ensure_catalog_stock, get_session_cart, parse_quantity
from .constructor_services import calculate_constructor_price
from .delivery_services import get_delivery_quote, get_pickup_point
from .location_services import cdek_enabled
from .models import (
    ConstructorAttachment,
    CustomerProfile,
    CustomerType,
    Order,
    OrderItem,
    OrderItemFile,
    OrderItemType,
    OrderStatus,
    PaymentStatus,
    Product,
    PublishStatus,
)
from .notifications import send_order_created_notifications, send_order_paid_notifications


logger = logging.getLogger(__name__)


def decimal_money(value):
    return Decimal(str(value)).quantize(Decimal('0.01'))


def order_number():
    return f'TMP-{uuid.uuid4().hex[:24]}'


def finalize_order_number(order):
    order.number = f'DT-{order.pk:06d}'
    order.save(update_fields=['number', 'updated_at'])


def get_customer(request, client):
    user = request.user
    profile, _ = CustomerProfile.objects.get_or_create(user=user)
    profile.middle_name = client.get('middleName', profile.middle_name)
    profile.phone = client.get('phone', profile.phone)
    profile.customer_type = customer_type_from_payload(client.get('type'))
    profile.save(update_fields=['middle_name', 'phone', 'customer_type', 'updated_at'])
    return user


def customer_type_from_payload(value):
    labels = {
        'Физическое лицо': CustomerType.PERSON,
        'ИП': CustomerType.ENTREPRENEUR,
        'Юридическое лицо': CustomerType.COMPANY,
        CustomerType.PERSON: CustomerType.PERSON,
        CustomerType.ENTREPRENEUR: CustomerType.ENTREPRENEUR,
        CustomerType.COMPANY: CustomerType.COMPANY,
    }
    return labels.get(value, CustomerType.PERSON)


def customer_name(client):
    parts = [client.get('lastName', ''), client.get('firstName', ''), client.get('middleName', '')]
    return ' '.join(part for part in parts if part).strip() or client.get('email') or 'Клиент'


def payment_method_from_payload(payment):
    value = payment.get('type') or ''
    return {
        'bank-card': 'card',
        'sbp': 'sbp',
        'invoice': 'invoice',
    }.get(value, '')


def payment_return_url(request, order, success=True):
    status = 'success' if success else 'fail'
    return request.build_absolute_uri(f'/payment/alfa/return/?order={order.number}&status={status}')


def text_value(payload, key, max_length=255):
    value = str(payload.get(key) or '').strip()
    return value[:max_length]


def is_valid_phone(phone):
    phone = (phone or '').strip()

    if not phone:
        return False

    if any(char not in '0123456789 +().-' for char in phone):
        return False

    if phone.count('+') > 1 or ('+' in phone and not phone.startswith('+')):
        return False

    digits = ''.join(char for char in phone if char.isdigit())
    return 10 <= len(digits) <= 15


def authenticated_checkout_client(user, client):
    if not getattr(user, 'is_authenticated', False):
        return client

    profile, _ = CustomerProfile.objects.get_or_create(user=user)
    merged = dict(client)
    merged['email'] = user.email or merged.get('email', '')

    if user.first_name:
        merged['firstName'] = user.first_name
    if user.last_name:
        merged['lastName'] = user.last_name
    if profile.middle_name:
        merged['middleName'] = profile.middle_name
    if is_valid_phone(profile.phone):
        merged['phone'] = profile.phone
    if not merged.get('type') and profile.customer_type:
        merged['type'] = profile.customer_type

    return merged


def validate_checkout_payload(payload, user=None):
    client = payload.get('client') or {}
    delivery = payload.get('delivery') or {}
    location = payload.get('location') or {}
    errors = {}
    client_data = {
        'type': text_value(client, 'type', 40),
        'email': text_value(client, 'email', 254).lower(),
        'firstName': text_value(client, 'firstName', 120),
        'lastName': text_value(client, 'lastName', 120),
        'middleName': text_value(client, 'middleName', 120),
        'phone': text_value(client, 'phone', 40),
        'comment': text_value(client, 'comment', 1000),
    }
    client_data = authenticated_checkout_client(user, client_data)

    email = client_data['email']
    try:
        validate_email(email)
    except ValidationError:
        errors['email'] = 'Введите корректный e-mail.'

    if not client_data['firstName'] and not client_data['lastName']:
        errors['name'] = 'Укажите имя или фамилию клиента.'

    if not is_valid_phone(client_data['phone']):
        errors['phone'] = 'Введите корректный номер телефона.'

    if not text_value(delivery, 'type', 40):
        errors['delivery'] = 'Выберите способ доставки.'

    if delivery.get('type') != 'manager' and not text_value(location, 'city', 120):
        errors['city'] = 'Укажите город доставки.'

    if delivery.get('type') == 'cdek-point' and not text_value(location, 'pickupPointCode', 80):
        errors['pickupPoint'] = 'Выберите пункт выдачи СДЭК.'

    if errors:
        raise ValidationError(errors)

    return {
        'client': client_data,
        'delivery': {
            'type': text_value(delivery, 'type', 40),
            'address': text_value(delivery, 'address', 500),
            'pickupPointCode': text_value(delivery, 'pickupPointCode', 80),
            'pickupPointTitle': text_value(delivery, 'pickupPointTitle', 255),
            'pickupPointAddress': text_value(delivery, 'pickupPointAddress', 500),
        },
        'location': {
            'country': text_value(location, 'country', 120),
            'countryCode': text_value(location, 'countryCode', 10),
            'region': text_value(location, 'region', 120),
            'regionCode': text_value(location, 'regionCode', 40),
            'city': text_value(location, 'city', 120),
            'cityCode': text_value(location, 'cityCode', 40),
            'pickupPointCode': text_value(location, 'pickupPointCode', 80),
            'pickupPointTitle': text_value(location, 'pickupPointTitle', 255),
            'pickupPointAddress': text_value(location, 'pickupPointAddress', 500),
        },
        'payment': payload.get('payment') or {},
    }


def create_catalog_item(order, item):
    try:
        product = Product.objects.select_for_update().get(sku=item.get('sku'), status=PublishStatus.ACTIVE)
    except Product.DoesNotExist as exc:
        raise ValidationError({'cart': 'Один из товаров в корзине больше недоступен. Обновите корзину.'}) from exc

    quantity = parse_quantity(item.get('quantity'))
    unit_price = product.price

    if product.stock < quantity:
        raise ValidationError({'quantity': f'Для товара {product.title} доступно только {product.stock} шт.'})

    order_item = OrderItem.objects.create(
        order=order,
        product=product,
        item_type=OrderItemType.CATALOG,
        title=product.title,
        sku=product.sku,
        parameters={
            'source': 'catalog',
            'dimensions': item.get('dimensions', []),
            'fabric': product.fabric.title if product.fabric else '',
            'color': product.color.title if product.color else '',
            'fastener': product.fastener.title if product.fastener else '',
        },
        quantity=quantity,
        unit_price=unit_price,
        total_price=unit_price * quantity,
    )

    product.stock -= quantity
    product.save(update_fields=['stock', 'updated_at'])
    return order_item


def validate_catalog_stock(cart):
    quantities = {}
    for item in cart:
        if item.get('type') != 'catalog-product':
            continue

        sku = item.get('sku')
        quantities[sku] = quantities.get(sku, 0) + parse_quantity(item.get('quantity'))

    for sku, quantity in quantities.items():
        try:
            product = Product.objects.get(sku=sku, status=PublishStatus.ACTIVE)
        except Product.DoesNotExist as exc:
            raise ValidationError({'cart': 'Один из товаров в корзине больше недоступен. Обновите корзину.'}) from exc

        if product.stock <= 0:
            raise ValidationError({'quantity': f'Товар {product.title} закончился.'})
        if quantity > product.stock:
            raise ValidationError({'quantity': f'Для товара {product.title} доступно только {product.stock} шт.'})


def create_constructor_item(order, item):
    payload = {
        'shape': item.get('shape', {}).get('key'),
        'dimensions': item.get('dimensions', []),
        'fabricId': item.get('fabric', {}).get('id'),
        'colorId': item.get('color', {}).get('id'),
        'fastenerId': item.get('fastener', {}).get('id'),
        'accessoryId': item.get('accessory', {}).get('id') if item.get('accessory') else None,
        'quantity': item.get('quantity') or 1,
        'comments': item.get('comments', ''),
    }
    try:
        calculated = calculate_constructor_price(payload)
    except ObjectDoesNotExist as exc:
        raise ValidationError({'cart': 'Один из параметров изделия больше недоступен. Обновите корзину.'}) from exc

    order_item = OrderItem.objects.create(
        order=order,
        item_type=OrderItemType.CONSTRUCTOR,
        title=calculated['shape']['title'],
        sku=calculated['sku'],
        shape=calculated['shape']['dbShape'],
        parameters={
            'source': 'constructor',
            'dimensions': calculated['dimensions'],
            'fabric': calculated['fabric'],
            'color': calculated['color'],
            'fastener': calculated['fastener'],
            'accessory': calculated['accessory'],
            'comments': calculated.get('comments', ''),
            'formulaCode': calculated.get('formulaCode', ''),
        },
        quantity=calculated['quantity'],
        unit_price=decimal_money(calculated['unitPrice']),
        total_price=decimal_money(calculated['totalPrice']),
    )

    attachment_ids = [
        attachment.get('id')
        for attachment in item.get('attachments', [])
        if attachment.get('id')
    ]
    for attachment in ConstructorAttachment.objects.filter(id__in=attachment_ids, user=order.user):
        OrderItemFile.objects.create(
            order_item=order_item,
            file=attachment.file,
            original_name=attachment.original_name,
        )

    return order_item


ALFA_PAID_ORDER_STATUSES = {1, 2}
ALFA_FAILED_ORDER_STATUSES = {3, 4, 5, 6}


def apply_alfa_order_status(order, order_status, client_url=''):
    was_paid = order.payment_status == PaymentStatus.PAID

    if order_status in ALFA_PAID_ORDER_STATUSES:
        if order.payment_status != PaymentStatus.REFUNDED:
            update_fields = ['payment_status', 'payment_form_url', 'updated_at']
            order.payment_status = PaymentStatus.PAID
            order.payment_form_url = ''
            if order.status == OrderStatus.WAITING_PAYMENT:
                order.status = OrderStatus.IN_PRODUCTION
                update_fields.append('status')
            order.save(update_fields=update_fields)
            if not was_paid:
                transaction.on_commit(lambda order_id=order.pk, url=client_url: send_order_paid_notifications(order_id, url))
        return 'success'

    if order_status in ALFA_FAILED_ORDER_STATUSES:
        if order.payment_status == PaymentStatus.PAID:
            return 'success'
        if order.payment_status == PaymentStatus.REFUNDED:
            return 'fail'
        order.payment_status = PaymentStatus.NOT_PAID
        order.save(update_fields=['payment_status', 'updated_at'])
        return 'fail'

    return 'pending'


def sync_alfa_order_payment_status(order, client_url=''):
    if not order:
        return ''

    if order.payment_status == PaymentStatus.PAID:
        if order.status == OrderStatus.WAITING_PAYMENT:
            order.status = OrderStatus.IN_PRODUCTION
            order.save(update_fields=['status', 'updated_at'])
        return 'success'

    if order.payment_status == PaymentStatus.REFUNDED:
        return 'fail'

    if order.payment_gateway != 'alfa' or not order.payment_order_id:
        return ''

    try:
        payment_status = get_payment_status(order.payment_order_id)
    except AlfaAcquiringError:
        logger.exception('Failed to sync Alfa payment status for order %s', order.number)
        return ''

    return apply_alfa_order_status(order, int(payment_status.get('orderStatus', -1)), client_url)


@require_POST
def checkout_order_api(request):
    try:
        if not request.user.is_authenticated:
            return JsonResponse({'ok': False, 'error': 'Для оформления заказа нужно войти или зарегистрироваться.'}, status=401)

        try:
            payload = json.loads(request.body.decode('utf-8') or '{}')
        except JSONDecodeError:
            return JsonResponse({'ok': False, 'error': 'Некорректный формат данных заказа.'}, status=400)

        session_cart = get_session_cart(request)
        cart = session_cart

        if not cart:
            return JsonResponse({'ok': False, 'error': 'Корзина пуста.'}, status=400)

        if not payload.get('returnTermsAccepted'):
            return JsonResponse({'ok': False, 'error': 'Подтвердите условия возврата перед оформлением заказа.'}, status=400)

        validated = validate_checkout_payload(payload, request.user)
        validate_catalog_stock(cart)
        selected_pickup_point = None
        if validated['delivery']['type'] == 'cdek-point' and cdek_enabled():
            try:
                selected_pickup_point = get_pickup_point(
                    validated['location'].get('cityCode'),
                    validated['location'].get('pickupPointCode') or validated['delivery'].get('pickupPointCode'),
                )
            except RuntimeError as exc:
                raise ValidationError({'pickupPoint': str(exc)}) from exc

            if not selected_pickup_point:
                raise ValidationError({
                    'pickupPoint': 'Выбранный пункт выдачи СДЭК недоступен. Обновите список ПВЗ и выберите пункт заново.'
                })

        with transaction.atomic():
            client = validated['client']
            delivery = validated['delivery']
            location = validated['location']
            if selected_pickup_point:
                delivery['pickupPointCode'] = selected_pickup_point['code']
                delivery['pickupPointTitle'] = selected_pickup_point['title']
                delivery['pickupPointAddress'] = selected_pickup_point['address']
                location['pickupPointCode'] = selected_pickup_point['code']
                location['pickupPointTitle'] = selected_pickup_point['title']
                location['pickupPointAddress'] = selected_pickup_point['address']
            delivery_quote = get_delivery_quote({
                'method': delivery.get('type'),
                'city': location.get('city'),
                'cityCode': location.get('cityCode'),
                'pickupPointCode': location.get('pickupPointCode'),
                'itemsCount': sum(parse_quantity(item.get('quantity')) for item in cart),
                'subtotal': sum(Decimal(str(item.get('totalPrice') or 0)) for item in cart),
                'items': cart,
            })
            delivery_address = delivery.get('address') or location.get('pickupPointAddress') or ''
            if location.get('pickupPointCode') and location.get('pickupPointAddress'):
                delivery_address = f'ПВЗ {location.get("pickupPointCode")}: {location.get("pickupPointAddress")}'
            user = get_customer(request, client)
            attach_cart_to_user(request, user)
            payment_method = payment_method_from_payload(validated['payment'])
            order = Order.objects.create(
                number=order_number(),
                user=user,
                status=OrderStatus.WAITING_MANAGER,
                payment_status=PaymentStatus.NOT_PAID,
                customer_type=customer_type_from_payload(client.get('type')),
                customer_name=customer_name(client),
                phone=client.get('phone', ''),
                email=client.get('email', user.email),
                delivery_method=delivery_quote.title,
                delivery_city=location.get('city', ''),
                delivery_address=delivery_address,
                payment_method=payment_method,
                client_comment=client.get('comment', ''),
                return_terms_accepted=True,
            )
            finalize_order_number(order)

            server_items = []
            for item in cart:
                order_item = create_catalog_item(order, item) if item.get('type') == 'catalog-product' else create_constructor_item(order, item)
                server_items.append(order_item)

            items_total = sum((item.total_price for item in server_items), Decimal('0.00'))
            delivery_total = delivery_quote.price
            order.items_total = items_total
            order.delivery_total = delivery_total
            order.total = items_total + delivery_total
            update_fields = ['items_total', 'delivery_total', 'total', 'updated_at']
            payment_url = ''
            order.save(update_fields=update_fields)
            clear_session_cart(request)
            manager_url = request.build_absolute_uri('/ditent-cms/#orders')
            client_url = request.build_absolute_uri(f'/order-success.html?order={order.number}')
            transaction.on_commit(
                lambda order_id=order.pk, manager_url=manager_url, client_url=client_url: send_order_created_notifications(
                    order_id,
                    manager_url=manager_url,
                    client_url=client_url,
                )
            )

        return JsonResponse({
            'ok': True,
            'order': {
                'id': order.number,
                'status': 'pending-manager-confirmation',
                'statusTitle': order.get_status_display(),
                'total': float(order.total),
                'paymentUrl': payment_url,
            },
        })
    except ValidationError as exc:
        return JsonResponse({'ok': False, 'errors': getattr(exc, 'message_dict', None) or exc.messages}, status=400)
    except AlfaAcquiringError as exc:
        return JsonResponse({'ok': False, 'error': str(exc)}, status=400)
    except Exception as exc:
        logger.exception('Checkout order creation failed')
        return JsonResponse({'ok': False, 'error': 'Не удалось оформить заказ. Попробуйте позже или свяжитесь с менеджером.'}, status=500)


def alfa_payment_return_page(request):
    number = request.GET.get('order', '')
    status = request.GET.get('status', '')
    order = None

    if request.user.is_authenticated and number:
        order = Order.objects.filter(number=number, user=request.user).first()

    if order and order.payment_order_id:
        try:
            status = sync_alfa_order_payment_status(
                order,
                request.build_absolute_uri(f'/order-success.html?order={order.number}'),
            ) or status or 'pending'
        except AlfaAcquiringError:
            status = status or 'pending'

    suffix = f'&payment={status}' if status else ''
    return redirect(f'/order-success.html?order={number}{suffix}')


def query_params(request):
    source = request.POST if request.method == 'POST' and request.POST else request.GET
    return {key: source.get(key, '') for key in source.keys()}


def order_by_alfa_callback(params):
    md_order = params.get('mdOrder') or params.get('orderId') or ''
    order_number = params.get('orderNumber') or ''
    order = None

    if md_order:
        order = Order.objects.filter(payment_order_id=md_order).first()
    if not order and order_number:
        order = Order.objects.filter(number=order_number).first()
    if order and order_number and order.number != order_number:
        raise ValidationError('Callback orderNumber does not match payment order.')
    return order


def apply_alfa_callback_status(order, operation, status):
    if status != '1':
        return False

    if operation == 'deposited':
        apply_alfa_order_status(order, 2)
        return True

    if operation == 'refunded':
        if order.payment_status != PaymentStatus.REFUNDED:
            order.payment_status = PaymentStatus.REFUNDED
            order.payment_form_url = ''
            order.save(update_fields=['payment_status', 'payment_form_url', 'updated_at'])
        return True

    if operation in {'reversed', 'declinedByTimeout', 'declinedCardpresent'}:
        if order.payment_status in {PaymentStatus.PAID, PaymentStatus.REFUNDED}:
            return False
        if order.payment_status != PaymentStatus.NOT_PAID:
            order.payment_status = PaymentStatus.NOT_PAID
            order.save(update_fields=['payment_status', 'updated_at'])
            return True
        return False

    return False


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def alfa_payment_callback_api(request):
    params = query_params(request)

    if not settings.ALFA_ACQUIRING_CALLBACK_TOKEN and not settings.DEBUG:
        return JsonResponse({'ok': False, 'error': 'Payment callback token is not configured.'}, status=503)

    if not verify_callback_checksum(params, settings.ALFA_ACQUIRING_CALLBACK_TOKEN):
        return JsonResponse({'ok': False, 'error': 'Invalid callback checksum.'}, status=400)

    try:
        order = order_by_alfa_callback(params)
    except ValidationError as exc:
        return JsonResponse({'ok': False, 'error': str(exc)}, status=400)

    if not order:
        return JsonResponse({'ok': False, 'error': 'Order not found.'}, status=404)

    operation = params.get('operation') or ''
    callback_status = str(params.get('status') or '')
    updated = apply_alfa_callback_status(order, operation, callback_status)

    return JsonResponse({'ok': True, 'updated': updated})


@ensure_csrf_cookie
def order_success_page(request):
    number = request.GET.get('order')
    order = None
    can_pay_online = False
    order_status_title = ''
    payment_status_title = ''

    if request.user.is_authenticated and number:
        order = (
            Order.objects
            .filter(number=number, user=request.user)
            .prefetch_related('items')
            .first()
        )
        can_pay_online = bool(
            order
            and order.status == OrderStatus.WAITING_PAYMENT
            and order.payment_ready_at
            and order.payment_form_url
            and order.payment_status != PaymentStatus.PAID
        )
        if order:
            if order.status == OrderStatus.WAITING_PAYMENT and not order.payment_ready_at:
                order_status_title = OrderStatus.WAITING_MANAGER.label
                payment_status_title = PaymentStatus.NOT_PAID.label
            else:
                order_status_title = order.get_status_display()
                payment_status_title = order.get_payment_status_display()

    return render(request, 'pages/order-success.html', {
        'order': order,
        'order_number': number,
        'can_pay_online': can_pay_online,
        'order_status_title': order_status_title,
        'payment_status_title': payment_status_title,
    })
