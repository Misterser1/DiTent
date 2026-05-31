from decimal import Decimal

from django.conf import settings

from .location_services import cdek_enabled, cdek_get, cdek_post


class DeliveryQuote:
    def __init__(self, method, title, price, days, provider='manager', note='', tariff_code=''):
        self.method = method
        self.title = title
        self.price = Decimal(str(price)).quantize(Decimal('0.01'))
        self.days = days
        self.provider = provider
        self.note = note
        self.tariff_code = tariff_code

    def as_dict(self):
        return {
            'method': self.method,
            'title': self.title,
            'price': float(self.price),
            'days': self.days,
            'provider': self.provider,
            'note': self.note,
            'tariffCode': self.tariff_code,
            'manual': self.provider in {'manager', 'cdek-unavailable'},
        }


class BaseDeliveryProvider:
    code = ''

    def quote(self, payload):
        raise NotImplementedError


def decimal_value(value, fallback='0'):
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal(fallback)


def int_value(value, fallback=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def build_package(payload):
    items_count = max(1, int_value(payload.get('itemsCount'), 1))
    weight = max(1, int_value(getattr(settings, 'CDEK_PACKAGE_WEIGHT_GRAMS', 1000), 1000)) * items_count
    length = max(1, int_value(getattr(settings, 'CDEK_PACKAGE_LENGTH_CM', 30), 30))
    width = max(1, int_value(getattr(settings, 'CDEK_PACKAGE_WIDTH_CM', 30), 30))
    height = max(1, int_value(getattr(settings, 'CDEK_PACKAGE_HEIGHT_CM', 10), 10))

    return {
        'weight': weight,
        'length': length,
        'width': width,
        'height': height,
    }


def cdek_days(data):
    period_min = data.get('period_min') or data.get('calendar_min')
    period_max = data.get('period_max') or data.get('calendar_max')

    if period_min and period_max:
        return f'{period_min}-{period_max} дн.' if period_min != period_max else f'{period_min} дн.'

    return 'После расчета'


class CdekPointProvider(BaseDeliveryProvider):
    code = 'cdek-point'

    def quote(self, payload):
        if not cdek_enabled():
            return DeliveryQuote(
                method=self.code,
                title='ТК "СДЭК" доставка до пункта выдачи',
                price=0,
                days='После расчета',
                provider='cdek-unavailable',
                note='API-ключи СДЭК не настроены. Доставку рассчитает менеджер.',
            )

        city_code = int_value(payload.get('cityCode'))
        if not city_code:
            return DeliveryQuote(
                method=self.code,
                title='ТК "СДЭК" доставка до пункта выдачи',
                price=0,
                days='После выбора города',
                provider='cdek-unavailable',
                note='Выберите город доставки, чтобы рассчитать СДЭК.',
            )

        tariff_code = int_value(getattr(settings, 'CDEK_TARIFF_CODE_PICKUP', 136), 136)
        request_payload = {
            'type': 1,
            'tariff_code': tariff_code,
            'from_location': {'code': int_value(getattr(settings, 'CDEK_ORIGIN_CITY_CODE', 437), 437)},
            'to_location': {'code': city_code},
            'packages': [build_package(payload)],
        }

        subtotal = decimal_value(payload.get('subtotal'))
        if subtotal > 0:
            request_payload['services'] = [{'code': 'INSURANCE', 'parameter': float(subtotal)}]

        try:
            data = cdek_post('/v2/calculator/tariff', request_payload)
        except Exception:
            return DeliveryQuote(
                method=self.code,
                title='ТК "СДЭК" доставка до пункта выдачи',
                price=0,
                days='После расчета',
                provider='cdek-unavailable',
                note='СДЭК временно не вернул расчет. Менеджер проверит доставку вручную.',
                tariff_code=str(tariff_code),
            )

        price = data.get('total_sum') or data.get('delivery_sum') or 0
        return DeliveryQuote(
            method=self.code,
            title='ТК "СДЭК" доставка до пункта выдачи',
            price=price,
            days=cdek_days(data),
            provider='cdek',
            note='Предварительный расчет СДЭК. Итог подтверждает менеджер перед запуском заказа.',
            tariff_code=str(tariff_code),
        )


class ManagerDeliveryProvider(BaseDeliveryProvider):
    code = 'manager'

    def quote(self, payload):
        return DeliveryQuote(
            method=self.code,
            title='Доставка после согласования с менеджером',
            price=0,
            days='После согласования',
            provider='manager',
            note='Менеджер рассчитает доставку после проверки заказа.',
        )


PROVIDERS = {
    CdekPointProvider.code: CdekPointProvider(),
    ManagerDeliveryProvider.code: ManagerDeliveryProvider(),
}


def get_delivery_quote(payload):
    method = payload.get('method') or 'manager'
    provider = PROVIDERS.get(method, PROVIDERS['manager'])
    return provider.quote(payload)


def get_pickup_points(city_code, limit=30):
    if not cdek_enabled() or not city_code:
        return []

    try:
        data = cdek_get('/v2/deliverypoints', {
            'city_code': city_code,
            'type': 'PVZ',
            'is_handout': 'true',
            'size': limit,
        })
    except Exception as error:
        raise RuntimeError('СДЭК временно не вернул пункты выдачи. Попробуйте выбрать город еще раз.') from error

    points = []
    for item in data[:limit]:
        location = item.get('location') or {}
        phones = item.get('phones') or []
        points.append({
            'code': item.get('code') or '',
            'title': item.get('name') or item.get('code') or '',
            'address': location.get('address_full') or location.get('address') or '',
            'workTime': item.get('work_time') or '',
            'phone': phones[0].get('number') if phones else '',
            'latitude': location.get('latitude'),
            'longitude': location.get('longitude'),
        })

    return points


def get_pickup_point(city_code, pickup_point_code):
    pickup_point_code = str(pickup_point_code or '').strip()
    if not cdek_enabled() or not city_code or not pickup_point_code:
        return None

    for point in get_pickup_points(city_code, limit=1000):
        if point['code'] == pickup_point_code:
            return point

    return None
