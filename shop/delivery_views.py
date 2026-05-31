import json
from json import JSONDecodeError

from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.views.decorators.http import require_POST

from .delivery_services import get_delivery_quote, get_pickup_points
from .location_services import cities, countries, regions


@require_POST
def delivery_quote_api(request):
    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except JSONDecodeError:
        return JsonResponse({'ok': False, 'error': 'Некорректный формат данных доставки.'}, status=400)

    quote = get_delivery_quote(payload)
    return JsonResponse({'ok': True, 'quote': quote.as_dict()})


@require_GET
def delivery_locations_api(request):
    kind = request.GET.get('type') or 'countries'
    country = request.GET.get('country') or 'RU'
    region = request.GET.get('region') or ''
    query = request.GET.get('q') or ''

    if kind == 'countries':
        items = countries()
    elif kind == 'regions':
        items = regions(country)
    elif kind == 'cities':
        items = cities(country, region_code=region, query=query)
    else:
        return JsonResponse({'ok': False, 'error': 'Некорректный тип справочника доставки.'}, status=400)

    return JsonResponse({'ok': True, 'items': items})


@require_GET
def delivery_pickup_points_api(request):
    city_code = request.GET.get('city') or ''

    if not city_code:
        return JsonResponse({'ok': False, 'error': 'Выберите город для загрузки пунктов выдачи.'}, status=400)

    try:
        items = get_pickup_points(city_code)
    except RuntimeError as error:
        return JsonResponse({'ok': False, 'error': str(error)}, status=502)

    return JsonResponse({'ok': True, 'items': items})
