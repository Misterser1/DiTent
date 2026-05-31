import json
from json import JSONDecodeError

from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST

from .constructor_services import calculate_constructor_price, constructor_config, decimal_string
from .models import Accessory, Color, ConstructorAttachment, ConstructorGalleryImage, Fabric, Fastener, PublishStatus
from .validators import validate_uploaded_files


def image_url(field_file, fallback=''):
    return field_file.url if field_file else fallback


def serialize_fabric(fabric):
    return {
        'id': fabric.id,
        'title': fabric.title,
        'price': decimal_string(fabric.price_per_square_meter),
        'density': fabric.density,
        'propertyType': fabric.property_type,
        'description': fabric.description,
        'purpose': fabric.purpose,
        'uv': fabric.uv_resistance or 0,
        'durability': fabric.durability or 0,
        'strength': fabric.strength or 0,
        'care': fabric.care or 0,
    }


def serialize_color(color):
    return {
        'id': color.id,
        'title': color.title,
        'fabricId': color.fabric_id,
        'image': image_url(color.image, 'assets/image/material-img-1.png'),
    }


def serialize_fastener(fastener):
    return {
        'id': fastener.id,
        'title': fastener.title,
        'price': decimal_string(fastener.price),
        'calculationType': fastener.calculation_type,
        'compatibility': fastener.compatibility,
        'image': image_url(fastener.image, 'assets/image/filter-img.png'),
    }


def serialize_accessory(accessory):
    return {
        'id': accessory.id,
        'title': accessory.title,
        'code': accessory.code,
        'price': decimal_string(accessory.price),
    }


def constructor_gallery_images():
    items = [
        {'url': image.image.url, 'title': image.title}
        for image in ConstructorGalleryImage.objects.filter(status=PublishStatus.ACTIVE).order_by('position', 'id')
        if image.image
    ]

    return items or [
        {'url': 'assets/image/img-1.png', 'title': 'Схема чехла'},
        {'url': 'assets/image/img-2.png', 'title': 'Пример применения'},
    ]


def get_constructor_context():
    fabrics = list(
        Fabric.objects
        .filter(status=PublishStatus.ACTIVE)
        .annotate(active_colors_count=Count('colors', filter=Q(colors__status=PublishStatus.ACTIVE)))
        .filter(active_colors_count__gt=0)
        .order_by('title')
    )
    colors = list(Color.objects.filter(status=PublishStatus.ACTIVE, fabric__in=fabrics).select_related('fabric').order_by('fabric__title', 'title'))
    fasteners = list(Fastener.objects.filter(status=PublishStatus.ACTIVE).order_by('title'))
    accessories = list(Accessory.objects.filter(status=PublishStatus.ACTIVE).order_by('title'))
    gallery_images = constructor_gallery_images()
    config = {
        **constructor_config(),
        'fabrics': [serialize_fabric(item) for item in fabrics],
        'colors': [serialize_color(item) for item in colors],
        'fasteners': [serialize_fastener(item) for item in fasteners],
        'accessories': [serialize_accessory(item) for item in accessories],
    }

    return {
        'constructor_config': config,
        'constructor_images': gallery_images,
        'constructor_main_image': gallery_images[-1],
        'shapes': config['shapes'],
        'fabrics': fabrics,
        'colors': colors,
        'fasteners': fasteners,
        'accessories': accessories,
    }


@ensure_csrf_cookie
def constructor_page(request):
    return render(request, 'pages/constructor.html', get_constructor_context())


def attachment_payload(attachment):
    return {
        'id': attachment.id,
        'name': attachment.original_name,
        'size': attachment.size,
        'type': attachment.content_type,
        'url': attachment.file.url,
    }


@require_POST
def constructor_calculate_api(request):
    try:
        payload = json.loads(request.POST.get('payload') or request.body or '{}')
        files = request.FILES.getlist('attachments')
        if files and not request.user.is_authenticated:
            return JsonResponse({'ok': False, 'error': 'Для загрузки файлов нужно войти или зарегистрироваться.'}, status=401)

        result = calculate_constructor_price(payload)
        attachments = []
        validate_uploaded_files(files)

        for file in files:
            attachment = ConstructorAttachment.objects.create(
                user=request.user,
                file=file,
                original_name=file.name,
                content_type=file.content_type or '',
                size=file.size,
            )
            attachments.append(attachment_payload(attachment))

        result['attachments'] = attachments or payload.get('attachments', [])
        return JsonResponse({'ok': True, 'item': result})
    except JSONDecodeError:
        return JsonResponse({'ok': False, 'errors': 'Некорректный формат JSON.'}, status=400)
    except (ValidationError, ObjectDoesNotExist) as exc:
        return JsonResponse({'ok': False, 'errors': getattr(exc, 'message_dict', None) or str(exc)}, status=400)
