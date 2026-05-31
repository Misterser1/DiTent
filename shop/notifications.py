import logging
from decimal import Decimal

from django.conf import settings
from django.core.mail import EmailMessage

from .models import DrawingOrder, Order, SiteSettings

logger = logging.getLogger(__name__)


def notifications_enabled():
    return getattr(settings, 'DITENT_EMAIL_NOTIFICATIONS_ENABLED', True)


def manager_recipients():
    site_settings = SiteSettings.load()
    recipients = parse_email_list(site_settings.manager_emails)
    if recipients:
        return recipients

    recipients = list(getattr(settings, 'DITENT_MANAGER_EMAILS', []))
    if recipients:
        return recipients

    return [site_settings.email] if site_settings.email else []


def parse_email_list(value):
    return [
        email.strip()
        for email in str(value or '').replace(';', ',').replace('\n', ',').split(',')
        if email.strip()
    ]


def money(value):
    if value is None:
        return '0 руб.'

    amount = Decimal(value).quantize(Decimal('0.01'))
    return f'{amount:,.2f}'.replace(',', ' ').replace('.', ',') + ' руб.'


def safe_send(subject, body, recipients):
    if not notifications_enabled() or not recipients:
        return False

    try:
        EmailMessage(
            subject=subject,
            body=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=recipients,
        ).send(fail_silently=False)
    except Exception:
        logger.exception('Failed to send email notification: %s', subject)
        return False

    return True


def absolute_url(request, path):
    if not request:
        return path
    return request.build_absolute_uri(path)


def order_items_text(order):
    lines = []
    for item in order.items.all():
        lines.append(f'- {item.title}: {item.quantity} шт. x {money(item.unit_price)} = {money(item.total_price)}')
    return '\n'.join(lines) if lines else '- Позиции не найдены'


def order_contacts_text(order):
    return '\n'.join([
        f'Клиент: {order.customer_name}',
        f'Телефон: {order.phone}',
        f'E-mail: {order.email}',
        f'Доставка: {order.delivery_method}',
        f'Город: {order.delivery_city or "-"}',
        f'Адрес / ПВЗ: {order.delivery_address or "-"}',
        f'Комментарий: {order.client_comment or "-"}',
    ])


def send_order_created_notifications(order_id, manager_url='', client_url=''):
    order = Order.objects.prefetch_related('items').get(pk=order_id)
    manager_subject = f'Новый заказ {order.number} на сайте DiTent'
    manager_body = '\n\n'.join([
        f'Создан новый заказ {order.number}.',
        order_contacts_text(order),
        'Состав заказа:',
        order_items_text(order),
        f'Итого: {money(order.total)}',
        f'Открыть в админке: {manager_url or "/admin.html#orders"}',
    ])
    safe_send(manager_subject, manager_body, manager_recipients())

    client_subject = f'Заказ {order.number} принят'
    client_body = '\n\n'.join([
        f'{order.customer_name}, ваш заказ {order.number} принят.',
        'Менеджер проверит параметры, подтвердит возможность изготовления и свяжется с вами.',
        'Состав заказа:',
        order_items_text(order),
        f'Итого: {money(order.total)}',
        f'Страница заказа: {client_url or f"/order-success.html?order={order.number}"}',
    ])
    safe_send(client_subject, client_body, [order.email] if order.email else [])


def send_drawing_order_created_notifications(order_id, manager_url=''):
    order = DrawingOrder.objects.prefetch_related('files').get(pk=order_id)
    request_number = f'DR-{order.pk:06d}'
    files = '\n'.join(f'- {file.original_name or file.file.name}' for file in order.files.all()) or '- Файлы не найдены'

    manager_subject = f'Новая заявка по чертежу {request_number}'
    manager_body = '\n\n'.join([
        f'Создана новая заявка по чертежу {request_number}.',
        f'Клиент: {order.customer_name}',
        f'Телефон: {order.phone}',
        f'E-mail: {order.email}',
        f'Комментарий:\n{order.comment or "-"}',
        f'Файлы:\n{files}',
        f'Открыть в админке: {manager_url or "/admin.html#drawing-orders"}',
    ])
    safe_send(manager_subject, manager_body, manager_recipients())

    client_subject = f'Заявка по чертежу {request_number} принята'
    client_body = '\n\n'.join([
        f'{order.customer_name}, ваша заявка по чертежу {request_number} принята.',
        'Менеджер проверит файлы и параметры, рассчитает стоимость и свяжется с вами.',
        f'Файлов получено: {order.files.count()}',
    ])
    safe_send(client_subject, client_body, [order.email] if order.email else [])


def send_order_payment_ready_notification(order_id, client_url=''):
    order = Order.objects.get(pk=order_id)
    subject = f'Заказ {order.number} подтвержден, оплата доступна'
    payment_line = f'Ссылка на оплату: {order.payment_form_url}' if order.payment_form_url else f'Страница заказа: {client_url}'
    body = '\n\n'.join([
        f'{order.customer_name}, менеджер подтвердил заказ {order.number}.',
        f'Сумма к оплате: {money(order.total)}',
        payment_line,
    ])
    safe_send(subject, body, [order.email] if order.email else [])


def send_order_paid_notifications(order_id, client_url=''):
    order = Order.objects.get(pk=order_id)
    manager_subject = f'Заказ {order.number} оплачен'
    manager_body = '\n\n'.join([
        f'Заказ {order.number} оплачен.',
        f'Клиент: {order.customer_name}',
        f'Телефон: {order.phone}',
        f'E-mail: {order.email}',
        f'Сумма: {money(order.total)}',
    ])
    safe_send(manager_subject, manager_body, manager_recipients())

    client_subject = f'Оплата заказа {order.number} получена'
    client_body = '\n\n'.join([
        f'{order.customer_name}, оплата заказа {order.number} получена.',
        'Менеджер передаст заказ в дальнейшую работу.',
        f'Страница заказа: {client_url or f"/order-success.html?order={order.number}"}',
    ])
    safe_send(client_subject, client_body, [order.email] if order.email else [])
