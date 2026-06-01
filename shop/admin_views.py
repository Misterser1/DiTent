from decimal import Decimal

from django.contrib.auth import authenticate, get_user_model, login, logout
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, ProtectedError
from django.forms.models import model_to_dict
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_http_methods, require_POST

from .alfa_acquiring import AlfaAcquiringError, register_payment
from .catalog_views import category_fallback_image, image_or_fallback
from .cdek_tracking import CdekTrackingError, sync_order_cdek_tracking
from .checkout_views import sync_alfa_order_payment_status
from .forms import (
    AccessoryForm,
    CategoryForm,
    ColorForm,
    ConstructorGalleryImageForm,
    DrawingOrderForm,
    FabricForm,
    FastenerForm,
    FormulaForm,
    OrderForm,
    ProductForm,
    ReviewForm,
    SiteSettingsForm,
)
from .models import (
    Accessory,
    Category,
    Color,
    ConstructorGalleryImage,
    CoverShape,
    CustomerType,
    DrawingOrder,
    Fabric,
    FastenerCalculationType,
    Fastener,
    Formula,
    Order,
    OrderStatus,
    PaymentStatus,
    PaymentMethod,
    Product,
    ProductImage,
    PublishStatus,
    Review,
    SiteSettings,
)
from .notifications import send_order_payment_ready_notification
from .validators import validate_uploaded_files


CUSTOM_ADMIN_URL = '/ditent-cms/'
CUSTOM_ADMIN_LOGIN_URL = '/ditent-cms/login/'


def safe_admin_next_url(request, value):
    fallback = reverse('custom_admin')
    if value and url_has_allowed_host_and_scheme(value, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return value
    return fallback


def custom_admin_legacy_redirect(request):
    return redirect('custom_admin')


@ensure_csrf_cookie
@require_http_methods(['GET', 'POST'])
def custom_admin_login_page(request):
    next_url = safe_admin_next_url(request, request.POST.get('next') or request.GET.get('next'))

    if request.user.is_authenticated and request.user.is_staff:
        return redirect(next_url)

    context = {
        'next_url': next_url,
        'username': '',
        'error': '',
    }

    if request.method == 'GET':
        return render(request, 'pages/admin-login.html', context)

    username = (request.POST.get('username') or '').strip()
    password = request.POST.get('password') or ''
    context['username'] = username

    authenticated = authenticate(request, username=username, password=password)
    if authenticated is None and '@' in username:
        user = get_user_model().objects.filter(email__iexact=username).first()
        if user:
            authenticated = authenticate(request, username=user.get_username(), password=password)

    if authenticated is None or not authenticated.is_active or not authenticated.is_staff:
        context['error'] = 'Неверный логин или пароль, либо у пользователя нет доступа к админке.'
        return render(request, 'pages/admin-login.html', context, status=400)

    login(request, authenticated)
    return redirect(next_url)


@require_POST
def custom_admin_logout_page(request):
    logout(request)
    return redirect('custom_admin_login')


def require_custom_admin(request):
    if not request.user.is_authenticated or not request.user.is_staff:
        login_url = f'{reverse("custom_admin_login")}?next={request.get_full_path()}'
        return redirect(login_url)

    return None


def require_custom_admin_api(request):
    if not request.user.is_authenticated or not request.user.is_staff:
        return JsonResponse({'ok': False, 'error': 'Недостаточно прав для доступа к админке.'}, status=403)

    return None


def image_url(field_file):
    return field_file.url if field_file else ''


def choice_label(value, choices):
    return dict(choices).get(value, value)


def decimal_to_string(value):
    if value is None:
        return ''

    return str(value).rstrip('0').rstrip('.') if isinstance(value, Decimal) else str(value)


MOCK_ORDER_NUMBER_PREFIX = 'DT-MOCK-'
MOCK_DRAWING_EMAIL_PREFIX = 'drawing-'


def real_orders(queryset=None):
    return (queryset or Order.objects.all()).exclude(number__startswith=MOCK_ORDER_NUMBER_PREFIX)


def real_drawing_orders(queryset=None):
    return (queryset or DrawingOrder.objects.all()).exclude(email__startswith=MOCK_DRAWING_EMAIL_PREFIX)


def waits_manager_confirmation(order):
    return order.status == OrderStatus.WAITING_PAYMENT and not order.payment_ready_at


def admin_order_status_label(order):
    return OrderStatus.WAITING_MANAGER.label if waits_manager_confirmation(order) else order.get_status_display()


def admin_order_payment_status_label(order):
    return PaymentStatus.NOT_PAID.label if waits_manager_confirmation(order) else order.get_payment_status_display()


def set_admin_order_labels(orders):
    for order in orders:
        order.admin_status_label = admin_order_status_label(order)
        order.admin_payment_status_label = admin_order_payment_status_label(order)
    return orders


def serialize_category(category):
    return {
        'id': category.id,
        'title': category.title,
        'slug': category.slug,
        'parent': category.parent_id,
        'parent_title': category.parent.title if category.parent else '—',
        'image': image_or_fallback(category.image, category_fallback_image(category)),
        'position': getattr(category, 'display_position', category.position),
        'position_label': getattr(category, 'display_position_label', str(getattr(category, 'display_position', category.position))),
        'products_count': getattr(category, 'products_count', category.products.count()),
        'status': category.status,
        'status_label': choice_label(category.status, PublishStatus.choices),
    }


def serialize_product(product):
    gallery_items = product.images.all().order_by('position', 'id')

    return {
        'id': product.id,
        'title': product.title,
        'category': product.category_id,
        'category_title': product.category.title,
        'sku': product.sku,
        'price': decimal_to_string(product.price),
        'width_cm': product.width_cm,
        'depth_cm': product.depth_cm,
        'height_cm': product.height_cm,
        'fabric': product.fabric_id,
        'fabric_title': product.fabric.title if product.fabric else '',
        'color': product.color_id,
        'color_title': product.color.title if product.color else '',
        'fastener': product.fastener_id,
        'fastener_title': product.fastener.title if product.fastener else '',
        'main_image': image_url(product.main_image),
        'purpose': product.purpose,
        'description': product.description,
        'stock': product.stock,
        'status': product.status,
        'status_label': choice_label(product.status, PublishStatus.choices),
        'gallery_images': [image_url(item.image) for item in gallery_items],
        'gallery_items': [
            {
                'id': item.id,
                'url': image_url(item.image),
                'name': item.image.name.rsplit('/', 1)[-1] if item.image else '',
            }
            for item in gallery_items
        ],
    }


def serialize_model(instance):
    data = model_to_dict(instance)
    data['id'] = instance.id
    data['created_at'] = instance.created_at.isoformat() if hasattr(instance, 'created_at') else ''
    data['updated_at'] = instance.updated_at.isoformat() if hasattr(instance, 'updated_at') else ''

    for key, value in list(data.items()):
        if isinstance(value, Decimal):
            data[key] = decimal_to_string(value)

    for field in instance._meta.fields:
        if field.get_internal_type() in {'ImageField', 'FileField'}:
            data[field.name] = image_url(getattr(instance, field.name))

    return data


def display_value(value):
    if not value:
        return ''
    if isinstance(value, dict):
        return value.get('title') or value.get('name') or value.get('label') or ''
    return str(value)


def format_dimensions(dimensions):
    if not isinstance(dimensions, list):
        return ''

    parts = []
    for dimension in dimensions:
        if not isinstance(dimension, dict):
            continue
        label = dimension.get('label') or dimension.get('key') or 'Размер'
        code = dimension.get('code')
        value = dimension.get('value')
        if value in (None, ''):
            continue
        title = f'{label} {code}' if code else label
        parts.append(f'{title}: {value} см')
    return ', '.join(parts)


def order_item_details(item):
    parameters = item.parameters or {}
    details = []
    dimensions = format_dimensions(parameters.get('dimensions'))

    if dimensions:
        details.append({'label': 'Размеры', 'value': dimensions})

    for key, label in (
        ('fabric', 'Ткань'),
        ('color', 'Цвет'),
        ('fastener', 'Крепление'),
        ('accessory', 'Аксессуар'),
    ):
        value = display_value(parameters.get(key))
        if value:
            details.append({'label': label, 'value': value})

    comments = display_value(parameters.get('comments'))
    if comments:
        details.append({'label': 'Комментарий', 'value': comments})

    formula = display_value(parameters.get('formulaCode'))
    if formula:
        details.append({'label': 'Формула', 'value': formula})

    return {
        'title': item.title,
        'sku': item.sku,
        'quantity': item.quantity,
        'unit_price': decimal_to_string(item.unit_price),
        'total_price': decimal_to_string(item.total_price),
        'details': details,
    }


def order_items_summary(order):
    return '||'.join(
        '|'.join((
            item.title,
            '; '.join(f"{detail['label']}: {detail['value']}" for detail in order_item_details(item)['details'])[:180],
            f'{item.quantity} шт. · {decimal_to_string(item.total_price)} ₽',
        ))
        for item in order.items.all()
    )


def serialize_order(order):
    sync_alfa_order_payment_status(order)
    data = serialize_model(order)
    data['status_label'] = admin_order_status_label(order)
    data['payment_status_label'] = admin_order_payment_status_label(order)
    data['cdek_status_label'] = order.cdek_status_name or order.cdek_status_code or ''
    data['customer_type_label'] = order.get_customer_type_display()
    data['payment_method_label'] = order.get_payment_method_display() if order.payment_method else ''
    data['items'] = [order_item_details(item) for item in order.items.all()]
    data['items_summary'] = order_items_summary(order)
    return data


def admin_payment_return_url(request, order, success=True):
    status = 'success' if success else 'fail'
    return request.build_absolute_uri(f'/payment/alfa/return/?order={order.number}&status={status}')


def should_create_online_payment(order):
    return (
        order.status == OrderStatus.WAITING_PAYMENT
        and order.payment_status == PaymentStatus.WAITING_PAYMENT
        and order.payment_method in {PaymentMethod.CARD, PaymentMethod.SBP}
        and not order.payment_form_url
        and order.total > 0
    )


def prepare_order_payment_after_manager_confirmation(request, order):
    was_payment_ready = bool(order.payment_ready_at)

    if order.status != OrderStatus.WAITING_PAYMENT:
        if order.payment_ready_at:
            order.payment_ready_at = None
            order.save(update_fields=['payment_ready_at', 'updated_at'])
        return

    if order.payment_status == PaymentStatus.NOT_PAID:
        order.payment_status = PaymentStatus.WAITING_PAYMENT
        order.save(update_fields=['payment_status', 'updated_at'])

    if not order.payment_ready_at:
        order.payment_ready_at = timezone.now()
        order.save(update_fields=['payment_ready_at', 'updated_at'])

    if not should_create_online_payment(order):
        if not was_payment_ready and order.payment_ready_at:
            client_url = request.build_absolute_uri(f'/order-success.html?order={order.number}')
            transaction.on_commit(
                lambda order_id=order.pk, client_url=client_url: send_order_payment_ready_notification(
                    order_id,
                    client_url=client_url,
                )
            )
        return

    payment = register_payment(
        order,
        return_url=admin_payment_return_url(request, order, True),
        fail_url=admin_payment_return_url(request, order, False),
    )
    order.payment_gateway = 'alfa'
    order.payment_order_id = payment['payment_order_id']
    order.payment_form_url = payment['payment_form_url']
    order.payment_ready_at = order.payment_ready_at or timezone.now()
    order.payment_status = PaymentStatus.WAITING_PAYMENT
    order.save(update_fields=['payment_gateway', 'payment_order_id', 'payment_form_url', 'payment_ready_at', 'payment_status', 'updated_at'])
    if not was_payment_ready:
        client_url = request.build_absolute_uri(f'/order-success.html?order={order.number}')
        transaction.on_commit(
            lambda order_id=order.pk, client_url=client_url: send_order_payment_ready_notification(
                order_id,
                client_url=client_url,
            )
        )


def serialize_drawing_order(order):
    data = serialize_model(order)
    data['status_label'] = order.get_status_display()
    data['files_count'] = order.files.count()
    data['files'] = [
        {'name': file.original_name or file.file.name, 'url': file.file.url}
        for file in order.files.all()
    ]
    return data


ENTITY_CONFIG = {
    'categories': (Category, CategoryForm, serialize_category),
    'products': (Product, ProductForm, serialize_product),
    'fabrics': (Fabric, FabricForm, serialize_model),
    'colors': (Color, ColorForm, serialize_model),
    'fasteners': (Fastener, FastenerForm, serialize_model),
    'accessories': (Accessory, AccessoryForm, serialize_model),
    'formulas': (Formula, FormulaForm, serialize_model),
    'orders': (Order, OrderForm, serialize_order),
    'drawing-orders': (DrawingOrder, DrawingOrderForm, serialize_drawing_order),
    'constructor-images': (ConstructorGalleryImage, ConstructorGalleryImageForm, serialize_model),
    'reviews': (Review, ReviewForm, serialize_model),
    'site-settings': (SiteSettings, SiteSettingsForm, serialize_model),
}
READONLY_CREATE_ENTITIES = {'orders', 'drawing-orders', 'site-settings'}
PROTECTED_DELETE_ENTITIES = {'orders', 'drawing-orders', 'site-settings'}


def get_entity_config(entity):
    if entity not in ENTITY_CONFIG:
        raise PermissionDenied

    return ENTITY_CONFIG[entity]


def get_api_entity_config(entity):
    config = ENTITY_CONFIG.get(entity)

    if not config:
        return None, JsonResponse({'ok': False, 'error': 'Раздел админки не найден.'}, status=404)

    return config, None


def prepare_categories(categories):
    categories = list(categories)
    children_by_parent = {}

    for category in categories:
        children_by_parent.setdefault(category.parent_id, []).append(category)
        category.admin_image = image_or_fallback(category.image, category_fallback_image(category))

    for group in children_by_parent.values():
        group.sort(key=lambda item: (item.position, item.title.lower(), item.id))
        for index, category in enumerate(group, start=1):
            category.display_position = index

    for category in categories:
        category.next_child_position = len(children_by_parent.get(category.id, [])) + 1

    ordered = []

    def append_branch(parent_id, parent_label=''):
        for index, category in enumerate(children_by_parent.get(parent_id, []), start=1):
            category.display_position_label = f'{parent_label}.{index}' if parent_label else str(index)
            ordered.append(category)
            append_branch(category.id, category.display_position_label)

    append_branch(None)

    for category in categories:
        if category not in ordered:
            ordered.append(category)

    return ordered, len(children_by_parent.get(None, [])) + 1


@ensure_csrf_cookie
def custom_admin_page(request):
    access_response = require_custom_admin(request)
    if access_response:
        return access_response

    categories, next_root_category_position = prepare_categories(
        Category.objects.select_related('parent').annotate(products_count=Count('products')).order_by('parent_id', 'position', 'title')
    )
    root_categories = [category for category in categories if not category.parent_id]
    product_categories = [category for category in categories if category.parent_id]
    products = Product.objects.select_related('category', 'fabric', 'color', 'fastener').prefetch_related('images').order_by('title')
    orders = set_admin_order_labels(real_orders(Order.objects).select_related('user').prefetch_related('items').order_by('-created_at'))
    drawing_orders = real_drawing_orders(DrawingOrder.objects).select_related('user').prefetch_related('files').order_by('-created_at')
    site_settings = SiteSettings.load()

    context = {
        'admin_api_base': '/custom-admin/api/',
        'publish_statuses': PublishStatus.choices,
        'order_statuses': OrderStatus.choices,
        'payment_statuses': PaymentStatus.choices,
        'customer_types': CustomerType.choices,
        'payment_methods': PaymentMethod.choices,
        'cover_shapes': CoverShape.choices,
        'fastener_calculation_types': FastenerCalculationType.choices,
        'categories': categories,
        'root_categories': root_categories,
        'product_categories': product_categories,
        'next_root_category_position': next_root_category_position,
        'products': products,
        'fabrics': Fabric.objects.order_by('title'),
        'colors': Color.objects.select_related('fabric').order_by('fabric__title', 'title'),
        'fasteners': Fastener.objects.order_by('title'),
        'formulas': Formula.objects.order_by('shape', 'title'),
        'orders': orders,
        'drawing_orders': drawing_orders,
        'constructor_images': ConstructorGalleryImage.objects.order_by('position', 'id'),
        'reviews': Review.objects.order_by('-created_at'),
        'site_settings': site_settings,
        'summary': {
            'categories': len(categories),
            'products': products.count(),
            'materials': Fabric.objects.count(),
            'new_orders': real_orders(Order.objects).filter(status=OrderStatus.WAITING_MANAGER).count() + real_drawing_orders(DrawingOrder.objects).filter(status=OrderStatus.WAITING_MANAGER).count(),
        },
    }

    return render(request, 'pages/admin.html', context)


@require_http_methods(['GET', 'POST'])
def admin_collection_api(request, entity):
    access_response = require_custom_admin_api(request)
    if access_response:
        return access_response

    entity_config, error_response = get_api_entity_config(entity)
    if error_response:
        return error_response

    model, form_class, serializer = entity_config

    if request.method == 'GET':
        queryset = model.objects.all()

        if entity == 'categories':
            queryset = queryset.select_related('parent').annotate(products_count=Count('products')).order_by('position', 'title')
            items, _ = prepare_categories(queryset)
            return JsonResponse({'items': [serializer(item) for item in items]})
        elif entity == 'products':
            queryset = queryset.select_related('category', 'fabric', 'color', 'fastener').prefetch_related('images').order_by('title')
        elif entity == 'colors':
            queryset = queryset.select_related('fabric').order_by('fabric__title', 'title')
        elif entity == 'orders':
            queryset = real_orders(queryset).select_related('user').prefetch_related('items').order_by('-created_at')
        elif entity == 'drawing-orders':
            queryset = real_drawing_orders(queryset).select_related('user').prefetch_related('files').order_by('-created_at')

        return JsonResponse({'items': [serializer(item) for item in queryset]})

    if entity in READONLY_CREATE_ENTITIES:
        return JsonResponse({'ok': False, 'error': 'Создание записи в этом разделе недоступно.'}, status=405)

    form = form_class(request.POST, request.FILES)

    if not form.is_valid():
        return JsonResponse({'ok': False, 'errors': form.errors}, status=400)

    try:
        validate_product_gallery(entity, request)
    except ValidationError as exc:
        return JsonResponse({'ok': False, 'errors': {'gallery_images': exc.messages}}, status=400)

    try:
        with transaction.atomic():
            instance = form.save()
            save_product_gallery(entity, instance, request)
            if entity == 'orders':
                prepare_order_payment_after_manager_confirmation(request, instance)
    except AlfaAcquiringError as exc:
        return JsonResponse({'ok': False, 'error': str(exc)}, status=400)

    if entity == 'categories':
        items, _ = prepare_categories(
            Category.objects.select_related('parent').annotate(products_count=Count('products')).order_by('parent_id', 'position', 'title')
        )
        instance = next((item for item in items if item.pk == instance.pk), instance)

    return JsonResponse({'ok': True, 'item': serializer(instance)}, status=201)


@require_http_methods(['GET', 'POST', 'DELETE'])
def admin_detail_api(request, entity, pk):
    access_response = require_custom_admin_api(request)
    if access_response:
        return access_response

    entity_config, error_response = get_api_entity_config(entity)
    if error_response:
        return error_response

    model, form_class, serializer = entity_config
    queryset = model.objects.all()
    if entity == 'orders':
        queryset = real_orders(queryset)
    elif entity == 'drawing-orders':
        queryset = real_drawing_orders(queryset)
    instance = get_object_or_404(queryset, pk=pk)

    if request.method == 'GET':
        if entity == 'categories':
            items, _ = prepare_categories(
                Category.objects.select_related('parent').annotate(products_count=Count('products')).order_by('parent_id', 'position', 'title')
            )
            instance = next((item for item in items if item.pk == instance.pk), instance)
        return JsonResponse({'item': serializer(instance)})

    if request.method == 'DELETE':
        if entity in PROTECTED_DELETE_ENTITIES:
            return JsonResponse({'ok': False, 'error': 'Удаление записи в этом разделе недоступно.'}, status=405)

        try:
            instance.delete()
        except ProtectedError:
            return JsonResponse(
                {'ok': False, 'error': 'Запись связана с другими данными и не может быть удалена.'},
                status=409,
            )

        return JsonResponse({'ok': True})

    form = form_class(request.POST, request.FILES, instance=instance)

    if not form.is_valid():
        return JsonResponse({'ok': False, 'errors': form.errors}, status=400)

    try:
        validate_product_gallery(entity, request)
    except ValidationError as exc:
        return JsonResponse({'ok': False, 'errors': {'gallery_images': exc.messages}}, status=400)

    try:
        with transaction.atomic():
            instance = form.save()
            save_product_gallery(entity, instance, request)
            if entity == 'orders':
                prepare_order_payment_after_manager_confirmation(request, instance)
    except AlfaAcquiringError as exc:
        return JsonResponse({'ok': False, 'error': str(exc)}, status=400)

    if entity == 'categories':
        items, _ = prepare_categories(
            Category.objects.select_related('parent').annotate(products_count=Count('products')).order_by('parent_id', 'position', 'title')
        )
        instance = next((item for item in items if item.pk == instance.pk), instance)

    return JsonResponse({'ok': True, 'item': serializer(instance)})


@require_http_methods(['POST'])
def admin_order_cdek_tracking_api(request, pk):
    access_response = require_custom_admin_api(request)
    if access_response:
        return access_response

    order = get_object_or_404(real_orders(Order.objects.all()), pk=pk)
    if not order.track_number and not order.cdek_order_uuid:
        return JsonResponse({'ok': False, 'error': 'Укажите трек-номер или UUID заказа СДЭК.'}, status=400)

    try:
        sync_order_cdek_tracking(order)
    except CdekTrackingError as exc:
        return JsonResponse({'ok': False, 'error': str(exc)}, status=502)

    return JsonResponse({'ok': True, 'item': serialize_order(order)})


def validate_product_gallery(entity, request):
    if entity != 'products':
        return

    gallery_files = request.FILES.getlist('gallery_images')
    if not gallery_files:
        return

    validate_uploaded_files(gallery_files)


def save_product_gallery(entity, instance, request):
    if entity != 'products':
        return

    gallery_files = request.FILES.getlist('gallery_images')
    has_keep_ids = 'gallery_keep_ids' in request.POST

    if not gallery_files and not has_keep_ids:
        return

    keep_ids = {
        int(value)
        for value in request.POST.getlist('gallery_keep_ids')
        if str(value).isdigit()
    }

    if has_keep_ids:
        instance.images.exclude(id__in=keep_ids).delete()
    elif gallery_files:
        instance.images.all().delete()

    start_position = instance.images.count() + 1
    for index, image in enumerate(gallery_files, start=start_position):
        ProductImage.objects.create(product=instance, image=image, position=index)
