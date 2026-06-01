import json
from hashlib import sha256
from functools import lru_cache
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.cache import cache


REQUEST_TIMEOUT = getattr(settings, 'CDEK_REQUEST_TIMEOUT', 15)
LOCATION_CACHE_TIMEOUT = getattr(settings, 'CDEK_LOCATION_CACHE_SECONDS', 6 * 60 * 60)
LOCATION_CACHE_VERSION = 'v4'
CDEK_TOKEN_CACHE_KEY = 'cdek_oauth_token'

CDEK_COUNTRY_TITLES = {
    'RU': 'Россия',
    'KZ': 'Казахстан',
    'BY': 'Беларусь',
    'AM': 'Армения',
    'KG': 'Киргизия',
    'CN': 'Китай',
    'TR': 'Турция',
    'TH': 'Таиланд',
    'DE': 'Германия',
}

RU_REGIONS = [
    ('77', 'Москва'),
    ('78', 'Санкт-Петербург'),
    ('50', 'Московская область'),
    ('47', 'Ленинградская область'),
    ('23', 'Краснодарский край'),
    ('61', 'Ростовская область'),
    ('16', 'Республика Татарстан'),
    ('66', 'Свердловская область'),
    ('54', 'Новосибирская область'),
    ('52', 'Нижегородская область'),
    ('74', 'Челябинская область'),
    ('63', 'Самарская область'),
    ('59', 'Пермский край'),
    ('24', 'Красноярский край'),
    ('02', 'Республика Башкортостан'),
    ('25', 'Приморский край'),
    ('27', 'Хабаровский край'),
    ('38', 'Иркутская область'),
    ('72', 'Тюменская область'),
    ('86', 'Ханты-Мансийский автономный округ - Югра'),
    ('89', 'Ямало-Ненецкий автономный округ'),
    ('22', 'Алтайский край'),
    ('28', 'Амурская область'),
    ('29', 'Архангельская область'),
    ('30', 'Астраханская область'),
    ('31', 'Белгородская область'),
    ('32', 'Брянская область'),
    ('33', 'Владимирская область'),
    ('34', 'Волгоградская область'),
    ('35', 'Вологодская область'),
    ('36', 'Воронежская область'),
    ('79', 'Еврейская автономная область'),
    ('75', 'Забайкальский край'),
    ('37', 'Ивановская область'),
    ('07', 'Кабардино-Балкарская Республика'),
    ('39', 'Калининградская область'),
    ('40', 'Калужская область'),
    ('41', 'Камчатский край'),
    ('09', 'Карачаево-Черкесская Республика'),
    ('42', 'Кемеровская область - Кузбасс'),
    ('43', 'Кировская область'),
    ('44', 'Костромская область'),
    ('45', 'Курганская область'),
    ('46', 'Курская область'),
    ('48', 'Липецкая область'),
    ('49', 'Магаданская область'),
    ('51', 'Мурманская область'),
    ('83', 'Ненецкий автономный округ'),
    ('53', 'Новгородская область'),
    ('55', 'Омская область'),
    ('56', 'Оренбургская область'),
    ('57', 'Орловская область'),
    ('58', 'Пензенская область'),
    ('60', 'Псковская область'),
    ('01', 'Республика Адыгея'),
    ('04', 'Республика Алтай'),
    ('03', 'Республика Бурятия'),
    ('05', 'Республика Дагестан'),
    ('06', 'Республика Ингушетия'),
    ('08', 'Республика Калмыкия'),
    ('10', 'Республика Карелия'),
    ('11', 'Республика Коми'),
    ('82', 'Республика Крым'),
    ('12', 'Республика Марий Эл'),
    ('13', 'Республика Мордовия'),
    ('14', 'Республика Саха (Якутия)'),
    ('15', 'Республика Северная Осетия - Алания'),
    ('17', 'Республика Тыва'),
    ('19', 'Республика Хакасия'),
    ('62', 'Рязанская область'),
    ('64', 'Саратовская область'),
    ('65', 'Сахалинская область'),
    ('92', 'Севастополь'),
    ('67', 'Смоленская область'),
    ('26', 'Ставропольский край'),
    ('68', 'Тамбовская область'),
    ('69', 'Тверская область'),
    ('70', 'Томская область'),
    ('71', 'Тульская область'),
    ('18', 'Удмуртская Республика'),
    ('73', 'Ульяновская область'),
    ('76', 'Ярославская область'),
    ('20', 'Чеченская Республика'),
    ('21', 'Чувашская Республика'),
    ('87', 'Чукотский автономный округ'),
]

FALLBACK_CITIES = [
    {'code': '44', 'title': 'Москва', 'regionCode': '77', 'region': 'Москва', 'countryCode': 'RU'},
    {'code': '137', 'title': 'Санкт-Петербург', 'regionCode': '78', 'region': 'Санкт-Петербург', 'countryCode': 'RU'},
    {'code': '270', 'title': 'Новосибирск', 'regionCode': '54', 'region': 'Новосибирская область', 'countryCode': 'RU'},
    {'code': '250', 'title': 'Екатеринбург', 'regionCode': '66', 'region': 'Свердловская область', 'countryCode': 'RU'},
    {'code': '426', 'title': 'Казань', 'regionCode': '16', 'region': 'Республика Татарстан', 'countryCode': 'RU'},
    {'code': '424', 'title': 'Нижний Новгород', 'regionCode': '52', 'region': 'Нижегородская область', 'countryCode': 'RU'},
    {'code': '438', 'title': 'Краснодар', 'regionCode': '23', 'region': 'Краснодарский край', 'countryCode': 'RU'},
    {'code': '329', 'title': 'Сочи', 'regionCode': '23', 'region': 'Краснодарский край', 'countryCode': 'RU'},
    {'code': '435', 'title': 'Ростов-на-Дону', 'regionCode': '61', 'region': 'Ростовская область', 'countryCode': 'RU'},
    {'code': '437', 'title': 'Самара', 'regionCode': '63', 'region': 'Самарская область', 'countryCode': 'RU'},
    {'code': '294', 'title': 'Челябинск', 'regionCode': '74', 'region': 'Челябинская область', 'countryCode': 'RU'},
    {'code': '431', 'title': 'Омск', 'regionCode': '55', 'region': 'Омская область', 'countryCode': 'RU'},
    {'code': '278', 'title': 'Красноярск', 'regionCode': '24', 'region': 'Красноярский край', 'countryCode': 'RU'},
    {'code': '480', 'title': 'Пермь', 'regionCode': '59', 'region': 'Пермский край', 'countryCode': 'RU'},
    {'code': '256', 'title': 'Уфа', 'regionCode': '02', 'region': 'Республика Башкортостан', 'countryCode': 'RU'},
    {'code': '496', 'title': 'Минск', 'regionCode': '', 'region': 'Минская область', 'countryCode': 'BY'},
    {'code': '563', 'title': 'Алматы', 'regionCode': '', 'region': 'Алматы', 'countryCode': 'KZ'},
    {'code': '532', 'title': 'Астана', 'regionCode': '', 'region': 'Астана', 'countryCode': 'KZ'},
]


def cdek_enabled():
    return bool(settings.CDEK_CLIENT_ID and settings.CDEK_CLIENT_SECRET)


def cdek_token(force_refresh=False):
    if not force_refresh:
        cached_token = cache.get(CDEK_TOKEN_CACHE_KEY)
        if cached_token:
            return cached_token

    payload = urlencode({
        'grant_type': 'client_credentials',
        'client_id': settings.CDEK_CLIENT_ID,
        'client_secret': settings.CDEK_CLIENT_SECRET,
    }).encode('utf-8')
    request = Request(
        f'{settings.CDEK_API_BASE_URL.rstrip("/")}/v2/oauth/token',
        data=payload,
        headers={'Content-Type': 'application/x-www-form-urlencoded'},
        method='POST',
    )
    data = cdek_request_json(request)
    token = data['access_token']
    expires_in = int(data.get('expires_in') or 3600)
    cache.set(CDEK_TOKEN_CACHE_KEY, token, max(60, expires_in - 60))
    return token


def cdek_request_json(request, attempts=2):
    last_error = None

    for _ in range(attempts):
        try:
            with urlopen(request, timeout=REQUEST_TIMEOUT) as response:
                return json.loads(response.read().decode('utf-8'))
        except Exception as error:
            last_error = error

    raise last_error


def cdek_get(path, params):
    query = urlencode({key: value for key, value in params.items() if value not in (None, '', [])})

    for force_refresh in (False, True):
        request = Request(
            f'{settings.CDEK_API_BASE_URL.rstrip("/")}{path}?{query}',
            headers={'Authorization': f'Bearer {cdek_token(force_refresh=force_refresh)}', 'Accept': 'application/json'},
        )
        try:
            return cdek_request_json(request)
        except HTTPError as error:
            if error.code == 401 and not force_refresh:
                cache.delete(CDEK_TOKEN_CACHE_KEY)
                continue
            raise


def cached_cdek_get(cache_name, path, params):
    cache_payload = json.dumps({'path': path, 'params': params}, sort_keys=True, ensure_ascii=False)
    cache_key = f'cdek_location:{LOCATION_CACHE_VERSION}:{cache_name}:{sha256(cache_payload.encode("utf-8")).hexdigest()}'
    cached = cache.get(cache_key)

    if cached is not None:
        return cached

    data = cdek_get(path, params)
    cache.set(cache_key, data, LOCATION_CACHE_TIMEOUT)
    return data


def cdek_post(path, payload):
    for force_refresh in (False, True):
        request = Request(
            f'{settings.CDEK_API_BASE_URL.rstrip("/")}{path}',
            data=json.dumps(payload).encode('utf-8'),
            headers={
                'Authorization': f'Bearer {cdek_token(force_refresh=force_refresh)}',
                'Content-Type': 'application/json',
                'Accept': 'application/json',
            },
            method='POST',
        )
        try:
            return cdek_request_json(request)
        except HTTPError as error:
            if error.code == 401 and not force_refresh:
                cache.delete(CDEK_TOKEN_CACHE_KEY)
                continue
            raise


def fallback_countries():
    return [
        {'code': code, 'title': CDEK_COUNTRY_TITLES.get(code, code)}
        for code in settings.CDEK_LOCATION_COUNTRY_CODES
    ]


def fallback_regions(country_code):
    if country_code != 'RU':
        return []

    return [{'code': code, 'title': title, 'countryCode': 'RU'} for code, title in RU_REGIONS]


def fallback_cities(country_code, region_code='', query='', limit=20):
    query = query.lower().strip()
    cities = [
        city for city in FALLBACK_CITIES
        if (not country_code or city['countryCode'] == country_code)
        and (not region_code or city['regionCode'] == region_code)
        and (not query or query in city['title'].lower())
    ]
    return cities[:limit]


def cdek_city_item(item, country_code):
    return {
        'code': str(item.get('code') or ''),
        'title': (item.get('city') or '').strip(),
        'regionCode': str(item.get('region_code') or ''),
        'region': item.get('region') or '',
        'subRegion': item.get('sub_region') or '',
        'countryCode': item.get('country_code') or country_code,
    }


def split_cdek_city_title(city):
    parts = [part.strip() for part in str(city or '').split(',') if part.strip()]
    if not parts:
        return '', ''

    return parts[0], ', '.join(parts[1:])


def cdek_pickup_city_item(item, country_code):
    location = item.get('location') or {}
    city_title, city_suffix = split_cdek_city_title(location.get('city'))

    return {
        'code': str(location.get('city_code') or ''),
        'title': city_title,
        'regionCode': str(location.get('region_code') or ''),
        'region': location.get('region') or '',
        'subRegion': location.get('sub_region') or city_suffix,
        'countryCode': location.get('country_code') or country_code,
    }


def normalize_city_text(value):
    return str(value or '').lower().replace('ё', 'е').strip()


def is_deprecated_location_title(value):
    normalized = normalize_city_text(value)
    return any(marker in normalized for marker in ('удален', 'удалён', 'устарел'))


def dedupe_city_items(items):
    deduped = []
    seen = set()

    for item in items:
        key = (
            normalize_city_text(item.get('title', '')),
            item.get('regionCode', ''),
            normalize_city_text(item.get('region', '')),
            normalize_city_text(item.get('subRegion', '')),
        )

        if key in seen:
            continue

        seen.add(key)
        deduped.append(item)

    return deduped


def sort_city_items(items):
    return sorted(items, key=lambda item: (
        normalize_city_text(item.get('title', '')),
        normalize_city_text(item.get('subRegion', '')),
    ))


@lru_cache(maxsize=256)
def cdek_country_has_pickup(country_code):
    if not country_code:
        return False

    data = cached_cdek_get('country_has_pickup', '/v2/deliverypoints', {
        'country_code': country_code,
        'type': 'PVZ',
        'is_handout': 'true',
        'size': 1,
    })
    return bool(data)


@lru_cache(maxsize=512)
def cdek_region_has_pickup(country_code, region_code):
    if not country_code or not region_code:
        return False

    data = cached_cdek_get('region_has_pickup', '/v2/deliverypoints', {
        'country_code': country_code,
        'region_code': region_code,
        'type': 'PVZ',
        'is_handout': 'true',
        'size': 1,
    })
    return bool(data)


@lru_cache(maxsize=128)
def cdek_pickup_regions(country_code):
    if not country_code:
        return []

    data = cached_cdek_get('pickup_regions', '/v2/deliverypoints', {
        'country_code': country_code,
        'type': 'PVZ',
        'is_handout': 'true',
    })
    regions_by_code = {}

    for item in data:
        location = item.get('location') or {}
        region_code = str(location.get('region_code') or '')
        region_title = location.get('region') or ''

        if not region_code or not region_title or is_deprecated_location_title(region_title):
            continue

        regions_by_code.setdefault(region_code, {
            'code': region_code,
            'title': region_title,
            'countryCode': country_code,
        })

    return sorted(regions_by_code.values(), key=lambda item: normalize_city_text(item.get('title', '')))


@lru_cache(maxsize=256)
def cdek_pickup_cities(country_code, region_code=''):
    if not country_code:
        return []

    params = {
        'country_code': country_code,
        'type': 'PVZ',
        'is_handout': 'true',
    }

    if region_code:
        params['region_code'] = region_code

    data = cached_cdek_get('pickup_cities', '/v2/deliverypoints', params)
    return sort_city_items(dedupe_city_items([
        cdek_pickup_city_item(item, country_code)
        for item in data
        if (item.get('location') or {}).get('city') and (item.get('location') or {}).get('city_code')
        and not is_deprecated_location_title((item.get('location') or {}).get('city'))
        and not is_deprecated_location_title((item.get('location') or {}).get('region'))
        and not is_deprecated_location_title((item.get('location') or {}).get('sub_region'))
    ]))


def countries():
    if cdek_enabled():
        items = []
        for country_code in settings.CDEK_LOCATION_COUNTRY_CODES:
            try:
                has_pickup = cdek_country_has_pickup(country_code)
            except Exception:
                has_pickup = False

            if has_pickup:
                items.append({
                    'code': country_code,
                    'title': CDEK_COUNTRY_TITLES.get(country_code, country_code),
                })

        return items

    return fallback_countries()


def regions(country_code):
    if cdek_enabled():
        try:
            return cdek_pickup_regions(country_code)
        except Exception:
            return []

    return fallback_regions(country_code)


def cities(country_code, region_code='', query='', limit=1000):
    if cdek_enabled():
        try:
            normalized_query = normalize_city_text(query)
            if country_code:
                region_items = list(cdek_pickup_cities(country_code, region_code))

                if normalized_query:
                    region_items = [
                        item for item in region_items
                        if normalized_query in normalize_city_text(item.get('title', ''))
                    ]

                return sort_city_items(region_items)[:limit]

            data = cdek_get('/v2/location/cities', {
                'country_codes': country_code,
                'city': query,
                'size': limit,
                'page': 0,
            })
            return sort_city_items(dedupe_city_items([
                cdek_city_item(item, country_code)
                for item in data
                if item.get('city')
            ]))
        except Exception:
            return []

    return fallback_cities(country_code, region_code=region_code, query=query, limit=limit)
