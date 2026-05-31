from django.http import Http404
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie

from shop.models import PublishStatus, Review


PAGE_TEMPLATES = {
    'index.html',
    'about.html',
    'admin.html',
    'admin-select-demo.html',
    'cabinet.html',
    'card.html',
    'catalog.html',
    'category.html',
    'constructor.html',
    'contacts.html',
    'delivery.html',
    'drawing-order-demo.html',
    'drawing-order.html',
    'form.html',
    'home-video-demo.html',
    'legal.html',
    'legal-demo.html',
    'privacy.html',
    'privacy-demo.html',
    'review.html',
}


def build_review_rows(reviews):
    rows = []

    for index in range(0, len(reviews), 2):
        items = reviews[index:index + 2]
        image_source = next((review for review in items if review.image), None)
        rows.append({
            'items': items,
            'image': image_source.image.url if image_source else '',
            'image_alt': image_source.image_caption or image_source.title if image_source else 'DiTent',
            'image_side': 'left' if len(rows) % 2 == 0 else 'right',
            'location': image_source.location if image_source else 'г. Москва',
            'caption': image_source.image_caption if image_source else 'Индивидуальные защитные чехлы для сада',
        })

    return rows


@ensure_csrf_cookie
def render_static_page(request, template_name='index.html'):
    if template_name not in PAGE_TEMPLATES:
        raise Http404('Page not found')

    context = {}
    if template_name == 'index.html':
        context = {
            'home_reviews': list(Review.objects.filter(status=PublishStatus.ACTIVE).order_by('-created_at')[:6]),
        }
    elif template_name == 'review.html':
        reviews = list(Review.objects.filter(status=PublishStatus.ACTIVE).order_by('-created_at'))
        context = {
            'review_rows': build_review_rows(reviews),
        }

    return render(request, f'pages/{template_name}', context)
