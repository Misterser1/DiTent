import json
from json import JSONDecodeError

from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

from .cart_services import add_item, cart_payload, remove_item, update_quantity


def error_message(exc):
    if isinstance(exc, ValidationError):
        if hasattr(exc, 'message_dict'):
            for messages in exc.message_dict.values():
                if messages:
                    return messages[0]
        if hasattr(exc, 'messages') and exc.messages:
            return exc.messages[0]

    return str(exc)


def request_json(request):
    try:
        return json.loads(request.body.decode('utf-8') or '{}')
    except JSONDecodeError:
        raise ValidationError({'payload': 'Некорректный формат JSON.'})


@require_GET
def cart_detail_api(request):
    return JsonResponse(cart_payload(request))


@require_POST
def cart_add_item_api(request):
    try:
        add_item(request, request_json(request))
        return JsonResponse(cart_payload(request))
    except (ValidationError, ObjectDoesNotExist) as exc:
        return JsonResponse({'ok': False, 'error': error_message(exc)}, status=400)


@require_POST
def cart_update_item_api(request, item_id):
    try:
        payload = request_json(request)
        update_quantity(request, item_id, payload.get('quantity'))
        return JsonResponse(cart_payload(request))
    except (ValidationError, ObjectDoesNotExist) as exc:
        return JsonResponse({'ok': False, 'error': error_message(exc)}, status=400)


@require_POST
def cart_delete_item_api(request, item_id):
    try:
        remove_item(request, item_id)
        return JsonResponse(cart_payload(request))
    except ObjectDoesNotExist as exc:
        return JsonResponse({'ok': False, 'error': error_message(exc)}, status=404)
