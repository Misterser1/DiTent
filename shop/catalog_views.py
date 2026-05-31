from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import ensure_csrf_cookie

from .models import Category, Product, PublishStatus


SECTION_ALIASES = {
    'garden': 'garden-furniture-covers',
    'equipment': 'equipment-covers',
    'special': 'special-covers',
    'tables': 'table-covers',
    'generators': 'generator-covers',
}

CATEGORY_FALLBACK_IMAGES = {
    'garden-furniture-covers': 'assets/image/catalog-img-1.png',
    'equipment-covers': 'assets/image/catalog-img-2.png',
    'tech-covers': 'assets/image/catalog-img-3.png',
    'special-covers': 'assets/image/catalog-img-4.png',
}
PRODUCT_FALLBACK_IMAGES = {
    'garden-furniture-covers': 'assets/image/card-img-1.png',
    'equipment-covers': 'assets/image/catalog-img-2.png',
    'tech-covers': 'assets/image/catalog-img-3.png',
    'special-covers': 'assets/image/catalog-img-4.png',
}
DEFAULT_CATEGORY_IMAGE = 'assets/image/catalog-img-1.png'
DEFAULT_PRODUCT_IMAGE = 'assets/image/card-img-1.png'


def format_price(value):
    if value is None:
        return ''

    return f'{int(value):,}'.replace(',', ' ') + ' руб.'


def format_decimal_for_js(value):
    if value is None:
        return '0'

    return format(value, 'f')


def image_or_fallback(field_file, fallback):
    return field_file.url if field_file else fallback


def root_slug(category):
    return category.parent.slug if category.parent else category.slug


def category_fallback_image(category):
    return CATEGORY_FALLBACK_IMAGES.get(category.slug) or CATEGORY_FALLBACK_IMAGES.get(root_slug(category), DEFAULT_CATEGORY_IMAGE)


def product_fallback_image(product):
    return PRODUCT_FALLBACK_IMAGES.get(root_slug(product.category), DEFAULT_PRODUCT_IMAGE)


def product_queryset():
    return (
        Product.objects.filter(status=PublishStatus.ACTIVE)
        .select_related('category', 'category__parent', 'fabric', 'color', 'fastener')
        .prefetch_related('images')
    )


def active_categories():
    return Category.objects.filter(status=PublishStatus.ACTIVE)


def get_category_slug(request, default=None):
    raw_slug = request.GET.get('slug') or request.GET.get('category') or request.GET.get('section') or default
    return SECTION_ALIASES.get(raw_slug, raw_slug)


def enrich_category(category):
    category.public_url = f'category.html?slug={category.slug}'
    category.public_image = image_or_fallback(category.image, category_fallback_image(category))
    return category


def product_dimensions(product):
    values = [
        ('Ширина', 'A', product.width_cm),
        ('Глубина', 'B', product.depth_cm),
        ('Высота', 'H', product.height_cm),
    ]
    return [item for item in values if item[2]]


def dimensions_text(product):
    dimensions = product_dimensions(product)
    if not dimensions:
        return 'Размеры уточняются менеджером'

    return ', '.join(f'{label.lower()} {value} см' for label, _, value in dimensions)


def cart_dimensions_data(product):
    return ';'.join(f'{label}|{code}:{value}' for label, code, value in product_dimensions(product))


def product_summary(product):
    parts = [
        product.fabric.title if product.fabric else '',
        product.color.title if product.color else '',
        product.fastener.title if product.fastener else '',
    ]
    summary = ', '.join(part for part in parts if part)
    return summary or product.description or product.purpose or 'Готовое изделие из каталога'


def enrich_product(product):
    product.public_url = f'form.html?product={product.id}'
    product.public_image = image_or_fallback(product.main_image, product_fallback_image(product))
    product.public_price = format_price(product.price)
    product.cart_price = format_decimal_for_js(product.price)
    product.dimensions_text = dimensions_text(product)
    product.cart_dimensions = cart_dimensions_data(product)
    product.summary = product_summary(product)
    product.gallery_images = [product.public_image]

    for image in product.images.all():
        product.gallery_images.append(image_or_fallback(image.image, product.public_image))

    return product


@ensure_csrf_cookie
def catalog_page(request):
    categories = (
        active_categories()
        .filter(parent__isnull=True)
        .annotate(active_products_count=Count('children__products', filter=Q(children__products__status=PublishStatus.ACTIVE)))
        .order_by('position', 'title')
    )

    context = {
        'categories': [enrich_category(category) for category in categories],
    }
    return render(request, 'pages/catalog.html', context)


@ensure_csrf_cookie
def category_page(request):
    root_categories = active_categories().filter(parent__isnull=True).order_by('position', 'title')
    root_slug = get_category_slug(request, default=root_categories.first().slug if root_categories.exists() else None)

    if not root_slug:
        raise Http404('Category not found')

    current = get_object_or_404(
        active_categories().select_related('parent'),
        slug=root_slug,
    )
    root = current.parent if current.parent else current

    child_categories = (
        active_categories()
        .filter(parent=root)
        .annotate(active_products_count=Count('products', filter=Q(products__status=PublishStatus.ACTIVE)))
        .order_by('position', 'title')
    )
    child_categories = [enrich_category(category) for category in child_categories]

    selected = current if current.parent else (child_categories[0] if child_categories else current)
    products = [enrich_product(product) for product in product_queryset().filter(category=selected).order_by('title')]

    context = {
        'root_category': enrich_category(root),
        'selected_category': enrich_category(selected),
        'child_categories': child_categories,
        'products': products,
    }
    return render(request, 'pages/category.html', context)


@ensure_csrf_cookie
def product_page(request):
    product_id = request.GET.get('product')
    sku = request.GET.get('sku')
    queryset = product_queryset()

    if product_id:
        product = get_object_or_404(queryset, pk=product_id)
    elif sku:
        product = get_object_or_404(queryset, sku=sku)
    else:
        product = queryset.order_by('title').first()
        if not product:
            raise Http404('Product not found')

    product = enrich_product(product)
    related_products = [
        enrich_product(item)
        for item in product_queryset()
        .filter(category=product.category)
        .exclude(pk=product.pk)
        .order_by('title')[:8]
    ]

    if not related_products:
        related_products = [
            enrich_product(item)
            for item in product_queryset().exclude(pk=product.pk).order_by('title')[:8]
        ]

    context = {
        'product': product,
        'related_products': related_products,
    }
    return render(request, 'pages/form.html', context)
