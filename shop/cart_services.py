import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist, ValidationError

from .constructor_services import calculate_constructor_price
from .models import Cart, CartItem, Product, PublishStatus


CART_SESSION_KEY = 'ditent_cart'
CART_USER_SESSION_KEY = 'ditent_cart_user_id'
VAT_RATE = Decimal('0.20')


def money(value):
    return Decimal(str(value or 0)).quantize(Decimal('0.01'))


def public_image(field_file, fallback='assets/image/card-img-1.png'):
    return field_file.url if field_file else fallback


def ensure_cart_session(request):
    if not request.session.session_key:
        request.session.create()


def raw_session_cart(request):
    return request.session.get(CART_SESSION_KEY, [])


def clear_raw_session_cart(request):
    request.session[CART_SESSION_KEY] = []
    request.session.modified = True


def is_authenticated(request):
    return bool(getattr(request, 'user', None) and request.user.is_authenticated)


def user_cart_model(user):
    cart, _ = Cart.objects.get_or_create(user=user)
    return cart


def user_cart_items(user):
    return [item.data for item in user_cart_model(user).items.all()]


def save_user_cart(user, cart_items):
    cart = user_cart_model(user)
    cart.items.all().delete()
    CartItem.objects.bulk_create([
        CartItem(cart=cart, data=item, position=index)
        for index, item in enumerate(cart_items)
    ])
    return cart_items


def clear_user_cart(user):
    user_cart_model(user).items.all().delete()


def get_session_cart(request):
    if is_authenticated(request):
        return user_cart_items(request.user)

    return raw_session_cart(request)


def save_session_cart(request, cart):
    if is_authenticated(request):
        save_user_cart(request.user, cart)
        request.session[CART_USER_SESSION_KEY] = request.user.id
    else:
        request.session[CART_SESSION_KEY] = cart

    request.session.modified = True


def clear_session_cart(request):
    request.session[CART_SESSION_KEY] = []
    if is_authenticated(request):
        clear_user_cart(request.user)

    request.session.modified = True


def attach_cart_to_user(request, user):
    merged_cart = merge_cart_items(user_cart_items(user), raw_session_cart(request))
    save_user_cart(user, merged_cart)
    clear_raw_session_cart(request)
    request.session[CART_USER_SESSION_KEY] = user.id
    request.session.modified = True


def parse_quantity(value):
    try:
        return min(settings.DITENT_MAX_CART_QUANTITY, max(1, int(value or 1)))
    except (TypeError, ValueError):
        return 1


def available_stock(product):
    return max(0, int(product.stock or 0))


def cart_quantity_for_sku(cart, sku, exclude_item_id=None):
    return sum(
        parse_quantity(item.get('quantity'))
        for item in cart
        if item.get('type') == 'catalog-product'
        and item.get('sku') == sku
        and item.get('id') != exclude_item_id
    )


def ensure_catalog_stock(product, quantity, cart=None, exclude_item_id=None):
    stock = available_stock(product)
    reserved = cart_quantity_for_sku(cart or [], product.sku, exclude_item_id=exclude_item_id)
    available = max(0, stock - reserved)

    if stock <= 0:
        raise ValidationError({'quantity': '\u0422\u043e\u0432\u0430\u0440 \u0437\u0430\u043a\u043e\u043d\u0447\u0438\u043b\u0441\u044f.'})

    if quantity > available:
        if available <= 0:
            raise ValidationError({'quantity': '\u0412\u0435\u0441\u044c \u0434\u043e\u0441\u0442\u0443\u043f\u043d\u044b\u0439 \u043e\u0441\u0442\u0430\u0442\u043e\u043a \u0443\u0436\u0435 \u0432 \u043a\u043e\u0440\u0437\u0438\u043d\u0435.'})

        raise ValidationError({
            'quantity': f'\u0414\u043e\u0441\u0442\u0443\u043f\u043d\u043e \u0442\u043e\u043b\u044c\u043a\u043e {available} \u0448\u0442.'
        })


def update_catalog_line_totals(item, product=None):
    if product:
        item['stock'] = available_stock(product)
        item['unitPrice'] = float(money(product.price))

    item['quantity'] = parse_quantity(item.get('quantity'))
    item['totalPrice'] = float(money(item.get('unitPrice')) * item['quantity'])
    return item


def merge_cart_items(stored_cart, incoming_cart):
    merged = [dict(item) for item in stored_cart]

    for raw_item in incoming_cart:
        item = dict(raw_item)

        if item.get('type') != 'catalog-product':
            merged.append(item)
            continue

        try:
            product = Product.objects.get(sku=item.get('sku'), status=PublishStatus.ACTIVE)
        except Product.DoesNotExist:
            continue

        existing = next(
            (
                cart_item
                for cart_item in merged
                if cart_item.get('type') == 'catalog-product' and cart_item.get('sku') == product.sku
            ),
            None,
        )

        if existing:
            available = max(0, available_stock(product) - cart_quantity_for_sku(merged, product.sku, exclude_item_id=existing.get('id')))
            quantity = min(parse_quantity(existing.get('quantity')) + parse_quantity(item.get('quantity')), available)
            if quantity <= 0:
                continue

            existing['quantity'] = quantity
            update_catalog_line_totals(existing, product)
            continue

        available = max(0, available_stock(product) - cart_quantity_for_sku(merged, product.sku))
        quantity = min(parse_quantity(item.get('quantity')), available)
        if quantity <= 0:
            continue

        item['quantity'] = quantity
        update_catalog_line_totals(item, product)
        merged.append(item)

    return merged


def catalog_dimensions(product):
    dimensions = []
    if product.width_cm:
        dimensions.append({'key': 'width', 'label': 'Ширина', 'code': 'A', 'value': product.width_cm})
    if product.depth_cm:
        dimensions.append({'key': 'depth', 'label': 'Глубина', 'code': 'B', 'value': product.depth_cm})
    if product.height_cm:
        dimensions.append({'key': 'height', 'label': 'Высота', 'code': 'H', 'value': product.height_cm})
    return dimensions


def serialize_catalog_item(product, quantity):
    unit_price = money(product.price)
    total_price = unit_price * quantity

    return {
        'id': f'catalog-{product.sku}-{uuid.uuid4().hex[:10]}',
        'type': 'catalog-product',
        'title': product.title,
        'sku': product.sku,
        'quantity': quantity,
        'stock': available_stock(product),
        'unitPrice': float(unit_price),
        'totalPrice': float(total_price),
        'image': public_image(product.main_image),
        'shape': {'title': 'Готовое изделие из каталога', 'code': 'CATALOG'},
        'dimensions': catalog_dimensions(product),
        'fabric': {'id': product.fabric_id, 'name': product.fabric.title if product.fabric else '', 'price': 0},
        'color': {'id': product.color_id, 'name': product.color.title if product.color else '', 'price': 0},
        'fastener': {'id': product.fastener_id, 'name': product.fastener.title if product.fastener else '', 'price': 0},
        'accessory': None,
        'comments': 'Готовое изделие из каталога',
    }


def serialize_constructor_item(payload):
    calculated = calculate_constructor_price({
        'shape': payload.get('shape', {}).get('key') if isinstance(payload.get('shape'), dict) else payload.get('shape'),
        'dimensions': payload.get('dimensions', []),
        'fabricId': payload.get('fabric', {}).get('id') or payload.get('fabricId'),
        'colorId': payload.get('color', {}).get('id') or payload.get('colorId'),
        'fastenerId': payload.get('fastener', {}).get('id') or payload.get('fastenerId'),
        'accessoryId': payload.get('accessory', {}).get('id') if payload.get('accessory') else payload.get('accessoryId'),
        'quantity': payload.get('quantity') or 1,
        'comments': payload.get('comments', ''),
    })

    return {
        'id': f'constructor-{calculated["sku"]}-{uuid.uuid4().hex[:10]}',
        'type': 'custom-cover',
        'title': calculated['shape']['title'],
        'sku': calculated['sku'],
        'quantity': calculated['quantity'],
        'unitPrice': calculated['unitPrice'],
        'totalPrice': calculated['totalPrice'],
        'image': payload.get('image') or 'assets/image/card-img-1.png',
        'shape': calculated['shape'],
        'dimensions': calculated['dimensions'],
        'fabric': calculated['fabric'],
        'color': calculated['color'],
        'fastener': calculated['fastener'],
        'accessory': calculated['accessory'],
        'comments': calculated.get('comments', ''),
        'attachments': payload.get('attachments', []),
    }


def normalize_item(payload, cart=None):
    item_type = payload.get('type')

    if item_type == 'catalog-product':
        sku = payload.get('sku')
        product_id = payload.get('productId')
        query = Product.objects.filter(status=PublishStatus.ACTIVE)
        product = query.get(pk=product_id) if product_id else query.get(sku=sku)
        quantity = parse_quantity(payload.get('quantity'))
        ensure_catalog_stock(product, quantity, cart=cart)
        return serialize_catalog_item(product, quantity)

    if item_type == 'custom-cover':
        return serialize_constructor_item(payload)

    raise ValidationError({'type': 'Неизвестный тип позиции корзины.'})


def add_item(request, payload):
    ensure_cart_session(request)
    cart = get_session_cart(request)
    item = normalize_item(payload, cart=cart)
    cart.append(item)
    save_session_cart(request, cart)
    return item


def update_quantity(request, item_id, quantity):
    cart = get_session_cart(request)
    updated_item = None

    for item in cart:
        if item.get('id') == item_id:
            next_quantity = parse_quantity(quantity)
            if item.get('type') == 'catalog-product':
                product = Product.objects.get(sku=item.get('sku'), status=PublishStatus.ACTIVE)
                ensure_catalog_stock(product, next_quantity, cart=cart, exclude_item_id=item_id)
                item['stock'] = available_stock(product)

            item['quantity'] = next_quantity
            item['totalPrice'] = float(money(item.get('unitPrice')) * item['quantity'])
            updated_item = item
            break

    if not updated_item:
        raise ObjectDoesNotExist('Позиция корзины не найдена.')

    save_session_cart(request, cart)
    return updated_item


def remove_item(request, item_id):
    cart = get_session_cart(request)
    next_cart = [item for item in cart if item.get('id') != item_id]

    if len(next_cart) == len(cart):
        raise ObjectDoesNotExist('Позиция корзины не найдена.')

    save_session_cart(request, next_cart)


def cart_summary(cart):
    subtotal = sum((money(item.get('unitPrice')) * parse_quantity(item.get('quantity')) for item in cart), Decimal('0.00'))
    discount = Decimal('0.00')
    delivery = Decimal('0.00')
    taxable_amount = max(subtotal - discount, Decimal('0.00'))
    vat = taxable_amount * VAT_RATE / (Decimal('1.00') + VAT_RATE)

    return {
        'subtotal': float(subtotal),
        'discount': float(discount),
        'delivery': float(delivery),
        'vat': float(vat.quantize(Decimal('0.01'))),
        'total': float(taxable_amount + delivery),
    }


def cart_payload(request):
    cart = get_session_cart(request)
    return {
        'ok': True,
        'cart': {
            'items': cart,
            'summary': cart_summary(cart),
            'count': sum(parse_quantity(item.get('quantity')) for item in cart),
            'userId': request.session.get(CART_USER_SESSION_KEY),
        },
    }
