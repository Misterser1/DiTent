from django.conf import settings
from django.conf.urls.static import static
from django.urls import path

from config.views import PAGE_TEMPLATES, render_static_page
from shop.account_views import (
    auth_code_request_api,
    auth_code_verify_api,
    auth_status_api,
    cabinet_order_detail_api,
    cabinet_orders_api,
    cabinet_profile_api,
    cabinet_profile_update_api,
    cabinet_repeat_order_api,
    login_api,
    logout_api,
    password_reset_api,
    register_api,
)
from shop.admin_views import admin_collection_api, admin_detail_api, admin_order_cdek_tracking_api, custom_admin_page
from shop.cart_views import cart_add_item_api, cart_delete_item_api, cart_detail_api, cart_update_item_api
from shop.catalog_views import catalog_page, category_page, product_page
from shop.checkout_views import alfa_payment_callback_api, alfa_payment_return_page, checkout_order_api, order_success_page
from shop.constructor_views import constructor_calculate_api, constructor_page
from shop.delivery_views import delivery_locations_api, delivery_pickup_points_api, delivery_quote_api
from shop.drawing_order_views import drawing_order_create_api


def page_name(template_name):
    return template_name.removesuffix('.html').replace('-', '_') or 'home'


urlpatterns = [
    path('', render_static_page, {'template_name': 'index.html'}, name='home'),
    path('catalog.html', catalog_page, name='catalog'),
    path('category.html', category_page, name='category'),
    path('constructor.html', constructor_page, name='constructor'),
    path('form.html', product_page, name='product'),
    path('admin.html', custom_admin_page, name='custom_admin'),
    path('order-success.html', order_success_page, name='order_success'),
    path('cart/api/', cart_detail_api, name='cart_detail_api'),
    path('cart/api/items/', cart_add_item_api, name='cart_add_item_api'),
    path('cart/api/items/<str:item_id>/quantity/', cart_update_item_api, name='cart_update_item_api'),
    path('cart/api/items/<str:item_id>/delete/', cart_delete_item_api, name='cart_delete_item_api'),
    path('auth/api/status/', auth_status_api, name='auth_status_api'),
    path('auth/api/code/request/', auth_code_request_api, name='auth_code_request_api'),
    path('auth/api/code/verify/', auth_code_verify_api, name='auth_code_verify_api'),
    path('auth/api/register/', register_api, name='register_api'),
    path('auth/api/login/', login_api, name='login_api'),
    path('auth/api/logout/', logout_api, name='logout_api'),
    path('auth/api/password-reset/', password_reset_api, name='password_reset_api'),
    path('cabinet/api/profile/', cabinet_profile_api, name='cabinet_profile_api'),
    path('cabinet/api/profile/update/', cabinet_profile_update_api, name='cabinet_profile_update_api'),
    path('cabinet/api/orders/', cabinet_orders_api, name='cabinet_orders_api'),
    path('cabinet/api/orders/<str:number>/', cabinet_order_detail_api, name='cabinet_order_detail_api'),
    path('cabinet/api/orders/<str:number>/repeat/', cabinet_repeat_order_api, name='cabinet_repeat_order_api'),
    path('constructor/api/calculate/', constructor_calculate_api, name='constructor_calculate_api'),
    path('checkout/api/delivery/', delivery_quote_api, name='delivery_quote_api'),
    path('checkout/api/delivery/locations/', delivery_locations_api, name='delivery_locations_api'),
    path('checkout/api/delivery/pickup-points/', delivery_pickup_points_api, name='delivery_pickup_points_api'),
    path('checkout/api/orders/', checkout_order_api, name='checkout_order_api'),
    path('payment/alfa/return/', alfa_payment_return_page, name='alfa_payment_return'),
    path('payment/alfa/callback/', alfa_payment_callback_api, name='alfa_payment_callback_api'),
    path('api/drawing-orders/', drawing_order_create_api, name='drawing_order_create_api'),
    path('custom-admin/api/<str:entity>/', admin_collection_api, name='custom_admin_collection_api'),
    path('custom-admin/api/orders/<int:pk>/cdek-tracking/', admin_order_cdek_tracking_api, name='admin_order_cdek_tracking_api'),
    path('custom-admin/api/<str:entity>/<int:pk>/', admin_detail_api, name='custom_admin_detail_api'),
]

urlpatterns += [
    path(template_name, render_static_page, {'template_name': template_name}, name=page_name(template_name))
    for template_name in sorted(PAGE_TEMPLATES)
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
