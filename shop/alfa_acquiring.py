import json
import hmac
from decimal import Decimal
from hashlib import sha256
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings


class AlfaAcquiringError(Exception):
    pass


CHECKSUM_EXCLUDED_PARAMS = {'checksum', 'sign_alias'}
SUCCESS_ERROR_CODES = {None, '', '0', 0}


def endpoint(path):
    return f'{settings.ALFA_ACQUIRING_BASE_URL.rstrip("/")}/{path.lstrip("/")}'


def require_config():
    if not settings.ALFA_ACQUIRING_USERNAME or not settings.ALFA_ACQUIRING_PASSWORD:
        raise AlfaAcquiringError('Не настроены тестовые доступы Альфа-Банка.')


def post_form(path, payload):
    require_config()
    data = urlencode({
        'userName': settings.ALFA_ACQUIRING_USERNAME,
        'password': settings.ALFA_ACQUIRING_PASSWORD,
        **payload,
    }).encode('utf-8')
    request = Request(
        endpoint(path),
        data=data,
        headers={'Content-Type': 'application/x-www-form-urlencoded; charset=utf-8'},
        method='POST',
    )

    try:
        with urlopen(request, timeout=settings.ALFA_ACQUIRING_TIMEOUT) as response:
            return json.loads(response.read().decode('utf-8') or '{}')
    except HTTPError as exc:
        body = exc.read().decode('utf-8', errors='ignore')
        raise AlfaAcquiringError(f'Альфа-Банк вернул ошибку HTTP {exc.code}: {body[:300]}') from exc
    except URLError as exc:
        raise AlfaAcquiringError(f'Не удалось подключиться к Альфа-Банку: {exc.reason}') from exc
    except json.JSONDecodeError as exc:
        raise AlfaAcquiringError('Альфа-Банк вернул некорректный ответ.') from exc


def amount_to_kopecks(amount):
    return int((Decimal(amount).quantize(Decimal('0.01')) * 100).to_integral_value())


def alfa_response_has_error(response):
    return response.get('errorCode') not in SUCCESS_ERROR_CODES


def callback_signature_payload(params):
    return ''.join(
        f'{key};{params[key]};'
        for key in sorted(params)
        if key not in CHECKSUM_EXCLUDED_PARAMS
    )


def callback_checksum(params, token):
    payload = callback_signature_payload(params)
    return hmac.new(token.encode('utf-8'), payload.encode('utf-8'), sha256).hexdigest().upper()


def verify_callback_checksum(params, token):
    checksum = (params.get('checksum') or '').upper()
    if not token:
        return True
    if not checksum:
        return False
    return hmac.compare_digest(callback_checksum(params, token), checksum)


def register_payment(order, return_url, fail_url):
    response = post_form('register.do', {
        'orderNumber': order.number,
        'amount': amount_to_kopecks(order.total),
        'currency': settings.ALFA_ACQUIRING_CURRENCY,
        'returnUrl': return_url,
        'failUrl': fail_url,
        'description': f'Заказ DiTent {order.number}',
        'language': 'ru',
    })

    if alfa_response_has_error(response):
        message = response.get('errorMessage') or response.get('error') or 'Не удалось создать платеж.'
        raise AlfaAcquiringError(message)

    order_id = response.get('orderId')
    form_url = response.get('formUrl')
    if not order_id or not form_url:
        raise AlfaAcquiringError('Альфа-Банк не вернул ссылку на оплату.')

    return {
        'payment_order_id': order_id,
        'payment_form_url': form_url,
    }


def get_payment_status(payment_order_id):
    if not payment_order_id:
        raise AlfaAcquiringError('Не указан ID платежа Альфа-Банка.')

    response = post_form('getOrderStatusExtended.do', {'orderId': payment_order_id})

    if alfa_response_has_error(response):
        message = response.get('errorMessage') or response.get('error') or 'Не удалось проверить статус платежа.'
        raise AlfaAcquiringError(message)

    return response
