import json
from decimal import Decimal
from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch
from urllib.error import HTTPError

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client, RequestFactory, TestCase, override_settings
from django.utils import timezone

from .alfa_acquiring import callback_checksum, get_payment_status, register_payment
from .constructor_services import calculation_metrics, validate_dimensions
from .models import Cart, CartItem, Category, Color, ConstructorAttachment, CoverShape, CustomerProfile, CustomerType, DrawingOrder, EmailAuthCode, EmailAuthPurpose, Fabric, Fastener, Formula, Order, OrderItem, OrderStatus, PaymentStatus, Product, PublishStatus, SiteSettings
from .validators import validate_uploaded_file


class UploadValidationTests(TestCase):
    @override_settings(
        DITENT_MAX_UPLOAD_SIZE=5,
        DITENT_ALLOWED_UPLOAD_TYPES=['image/png'],
        DITENT_ALLOWED_UPLOAD_EXTENSIONS=['.png'],
    )
    def test_rejects_disallowed_extension(self):
        file = SimpleUploadedFile('drawing.exe', b'abc', content_type='image/png')

        with self.assertRaises(ValidationError):
            validate_uploaded_file(file)

    @override_settings(
        DITENT_MAX_UPLOAD_SIZE=5,
        DITENT_ALLOWED_UPLOAD_TYPES=['image/png'],
        DITENT_ALLOWED_UPLOAD_EXTENSIONS=['.png'],
    )
    def test_rejects_oversized_file(self):
        file = SimpleUploadedFile('drawing.png', b'abcdef', content_type='image/png')

        with self.assertRaises(ValidationError):
            validate_uploaded_file(file)

    @override_settings(
        DITENT_MAX_UPLOAD_SIZE=1024,
        DITENT_ALLOWED_UPLOAD_TYPES=['image/png'],
        DITENT_ALLOWED_UPLOAD_EXTENSIONS=['.png'],
    )
    def test_rejects_file_with_spoofed_signature(self):
        file = SimpleUploadedFile('drawing.png', b'not a real png', content_type='image/png')

        with self.assertRaises(ValidationError):
            validate_uploaded_file(file)

    @override_settings(
        DITENT_MAX_UPLOAD_SIZE=1024,
        DITENT_ALLOWED_UPLOAD_TYPES=['image/png'],
        DITENT_ALLOWED_UPLOAD_EXTENSIONS=['.png'],
    )
    def test_accepts_file_with_valid_signature(self):
        file = SimpleUploadedFile('drawing.png', b'\x89PNG\r\n\x1a\n\x00\x00', content_type='image/png')

        self.assertIs(validate_uploaded_file(file), file)


class AlfaAcquiringTests(TestCase):
    @patch('shop.alfa_acquiring.post_form')
    def test_get_payment_status_accepts_alfa_success_error_code_zero(self, post_form_mock):
        post_form_mock.return_value = {
            'errorCode': '0',
            'errorMessage': 'Успешно',
            'orderStatus': 2,
        }

        response = get_payment_status('bank-order-paid')

        self.assertEqual(response['orderStatus'], 2)
        post_form_mock.assert_called_once_with('getOrderStatusExtended.do', {'orderId': 'bank-order-paid'})

    @patch('shop.alfa_acquiring.post_form')
    def test_register_payment_accepts_alfa_success_error_code_zero(self, post_form_mock):
        post_form_mock.return_value = {
            'errorCode': '0',
            'errorMessage': 'Успешно',
            'orderId': 'bank-order-new',
            'formUrl': 'https://bank.example/pay',
        }
        order = SimpleNamespace(number='DT-ALFA-001', total=Decimal('1200.00'))

        response = register_payment(order, 'https://site.example/return', 'https://site.example/fail')

        self.assertEqual(response['payment_order_id'], 'bank-order-new')
        self.assertEqual(response['payment_form_url'], 'https://bank.example/pay')


class ConstructorFormulaTests(TestCase):
    class FabricStub:
        roll_width_cm = Decimal('148')

    def constructor_payload(self):
        fabric = Fabric.objects.create(
            title='Constructor auth fabric',
            price_per_square_meter=Decimal('1200.00'),
            roll_width_cm=148,
            status=PublishStatus.ACTIVE,
        )
        color = Color.objects.create(title='Graphite', fabric=fabric, status=PublishStatus.ACTIVE)
        fastener = Fastener.objects.create(title='Zip', price=Decimal('100.00'), status=PublishStatus.ACTIVE)

        return {
            'shape': 'rectangular',
            'dimensions': [
                {'key': 'width', 'value': 100},
                {'key': 'depth', 'value': 80},
                {'key': 'height', 'value': 60},
            ],
            'fabricId': fabric.pk,
            'colorId': color.pk,
            'fastenerId': fastener.pk,
            'quantity': 1,
        }

    def test_wedge_uses_excel_formula_dimensions(self):
        dimensions = validate_dimensions(CoverShape.WEDGE, [
            {'key': 'length', 'value': 200},
            {'key': 'lowHeight', 'value': 80},
            {'key': 'depth', 'value': 90},
            {'key': 'highHeight', 'value': 120},
        ])

        metrics = calculation_metrics(CoverShape.WEDGE, dimensions, self.FabricStub())

        self.assertAlmostEqual(float(metrics['area']), 7.76977, places=4)
        self.assertAlmostEqual(float(metrics['seam_length']), 796.977, places=3)
        self.assertEqual(metrics['edging_length'], Decimal('580'))
        self.assertEqual(metrics['extra_seams'], Decimal('2'))
        self.assertEqual(metrics['extra_seam_length'], Decimal('200'))

    def test_constructor_calculate_rejects_malformed_json(self):
        response = self.client.post('/constructor/api/calculate/', data='{bad', content_type='application/json')

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()['ok'])

    def test_constructor_attachment_upload_requires_authentication(self):
        response = self.client.post(
            '/constructor/api/calculate/',
            data={
                'payload': json.dumps(self.constructor_payload()),
                'attachments': SimpleUploadedFile('scheme.pdf', b'%PDF-1.4', content_type='application/pdf'),
            },
        )

        self.assertEqual(response.status_code, 401)
        self.assertFalse(ConstructorAttachment.objects.exists())

    def test_constructor_attachment_upload_is_bound_to_current_user(self):
        User = get_user_model()
        user = User.objects.create_user(username='constructor-file-owner', email='constructor-file-owner@example.com')
        self.client.force_login(user)

        response = self.client.post(
            '/constructor/api/calculate/',
            data={
                'payload': json.dumps(self.constructor_payload()),
                'attachments': SimpleUploadedFile('scheme.pdf', b'%PDF-1.4', content_type='application/pdf'),
            },
        )

        self.assertEqual(response.status_code, 200)
        attachment = ConstructorAttachment.objects.get()
        self.assertEqual(attachment.user, user)
        self.assertEqual(response.json()['item']['attachments'][0]['id'], attachment.pk)

    def test_l_shape_uses_excel_formula_with_top_area(self):
        dimensions = validate_dimensions(CoverShape.L_SHAPED, [
            {'key': 'backLength', 'value': 240},
            {'key': 'rightDepth', 'value': 150},
            {'key': 'highHeight', 'value': 120},
            {'key': 'lowHeight', 'value': 80},
            {'key': 'leftDepth', 'value': 90},
            {'key': 'frontLength', 'value': 100},
            {'key': 'innerLength', 'value': 180},
            {'key': 'innerDepth', 'value': 60},
        ])

        metrics = calculation_metrics(CoverShape.L_SHAPED, dimensions, self.FabricStub())

        self.assertAlmostEqual(float(metrics['area']), 11.02, places=4)
        self.assertAlmostEqual(float(metrics['seam_length']), 986.977, places=3)
        self.assertEqual(metrics['edging_length'], Decimal('820'))
        self.assertEqual(metrics['extra_seams'], Decimal('2'))
        self.assertEqual(metrics['extra_seam_length'], Decimal('300'))

    def test_u_shape_uses_excel_formula_dimensions(self):
        dimensions = validate_dimensions(CoverShape.U_SHAPED, [
            {'key': 'backWidth', 'value': 300},
            {'key': 'leftDepth', 'value': 160},
            {'key': 'highHeight', 'value': 120},
            {'key': 'lowHeight', 'value': 80},
            {'key': 'leftFrontWidth', 'value': 80},
            {'key': 'rightFrontWidth', 'value': 70},
            {'key': 'innerDepth', 'value': 150},
            {'key': 'rightDepth', 'value': 150},
        ])

        metrics = calculation_metrics(CoverShape.U_SHAPED, dimensions, self.FabricStub())

        self.assertAlmostEqual(float(metrics['area']), 15.8231, places=4)
        self.assertAlmostEqual(float(metrics['seam_length']), 1780.065, places=3)
        self.assertEqual(metrics['edging_length'], Decimal('1050'))
        self.assertEqual(metrics['extra_seams'], Decimal('2'))
        self.assertEqual(metrics['extra_seam_length'], Decimal('270'))


class CheckoutSecurityTests(TestCase):
    def add_checkout_product(self, sku='CHECKOUT-HELPER-1'):
        category = Category.objects.create(title='Checkout helper', slug=f'{sku.lower()}-category', status=PublishStatus.ACTIVE)
        product = Product.objects.create(
            category=category,
            title='Checkout helper product',
            sku=sku,
            price=Decimal('500.00'),
            stock=3,
            status=PublishStatus.ACTIVE,
        )
        self.client.post(
            '/cart/api/items/',
            data=json.dumps({'type': 'catalog-product', 'sku': product.sku, 'quantity': 1}),
            content_type='application/json',
        )
        return product

    def create_constructor_options(self):
        fabric = Fabric.objects.create(
            title='Checkout constructor fabric',
            price_per_square_meter=Decimal('1200.00'),
            roll_width_cm=148,
            status=PublishStatus.ACTIVE,
        )
        color = Color.objects.create(title='Checkout graphite', fabric=fabric, status=PublishStatus.ACTIVE)
        fastener = Fastener.objects.create(title='Checkout zipper', price=Decimal('100.00'), status=PublishStatus.ACTIVE)
        return fabric, color, fastener

    def test_cart_post_requires_csrf(self):
        client = Client(enforce_csrf_checks=True)

        response = client.post('/cart/api/items/', data='{}', content_type='application/json')

        self.assertEqual(response.status_code, 403)

    def test_cart_rejects_malformed_json(self):
        response = self.client.post('/cart/api/items/', data='{bad', content_type='application/json')

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()['ok'])

    def test_checkout_requires_authenticated_user(self):
        response = self.client.post(
            '/checkout/api/orders/',
            data=json.dumps({'returnTermsAccepted': True}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 401)

    def test_checkout_ignores_payload_items_without_server_cart(self):
        User = get_user_model()
        user = User.objects.create_user(username='client', email='client@example.com', password='password123')
        self.client.force_login(user)

        response = self.client.post(
            '/checkout/api/orders/',
            data=json.dumps({
                'returnTermsAccepted': True,
                'client': {
                    'firstName': 'Client',
                    'phone': '+79990000000',
                    'email': 'client@example.com',
                },
                'delivery': {'type': 'manager'},
                'location': {'city': 'Moscow'},
                'items': [{'type': 'catalog-product', 'sku': 'FAKE', 'quantity': 1, 'totalPrice': 1}],
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], 'Корзина пуста.')

    def test_checkout_requires_return_terms(self):
        User = get_user_model()
        user = User.objects.create_user(username='checkout-terms', email='checkout-terms@example.com', password='password123')
        self.client.force_login(user)
        self.add_checkout_product('CHECKOUT-TERMS-1')

        response = self.client.post(
            '/checkout/api/orders/',
            data=json.dumps({
                'returnTermsAccepted': False,
                'client': {
                    'firstName': 'Client',
                    'lastName': 'Terms',
                    'phone': '+79990000000',
                    'email': 'checkout-terms@example.com',
                },
                'delivery': {'type': 'manager'},
                'payment': {'type': 'invoice'},
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('возврата', response.json()['error'])

    def test_checkout_validates_client_payload(self):
        User = get_user_model()
        user = User.objects.create_user(username='checkout-invalid-client', email='checkout-invalid-client@example.com', password='password123')
        self.client.force_login(user)
        self.add_checkout_product('CHECKOUT-INVALID-CLIENT-1')

        response = self.client.post(
            '/checkout/api/orders/',
            data=json.dumps({
                'returnTermsAccepted': True,
                'client': {
                    'firstName': '',
                    'lastName': '',
                    'phone': '',
                    'email': 'bad-email',
                },
                'delivery': {'type': 'manager'},
                'payment': {'type': 'invoice'},
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('name', response.json()['errors'])
        self.assertIn('phone', response.json()['errors'])

    def test_checkout_rejects_short_numeric_phone(self):
        User = get_user_model()
        user = User.objects.create_user(username='checkout-short-phone', email='checkout-short-phone@example.com', password='password123')
        self.client.force_login(user)
        self.add_checkout_product('CHECKOUT-SHORT-PHONE-1')

        response = self.client.post(
            '/checkout/api/orders/',
            data=json.dumps({
                'returnTermsAccepted': True,
                'client': {
                    'firstName': 'Short',
                    'lastName': 'Phone',
                    'phone': '4819',
                    'email': 'academy.goahead@gmail.com',
                },
                'delivery': {'type': 'manager'},
                'payment': {'type': 'invoice'},
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('phone', response.json()['errors'])
        self.assertFalse(Order.objects.filter(user=user).exists())

    def test_checkout_prefers_authenticated_profile_over_stale_guest_client_data(self):
        User = get_user_model()
        user = User.objects.create_user(
            username='checkout-profile-priority',
            email='server.osmanov26@mail.ru',
            password='password123',
            first_name='Осман',
            last_name='Османов',
        )
        CustomerProfile.objects.create(
            user=user,
            middle_name='Серверович',
            phone='+79990000000',
            customer_type=CustomerType.PERSON,
        )
        self.client.force_login(user)
        self.add_checkout_product('CHECKOUT-PROFILE-PRIORITY-1')

        response = self.client.post(
            '/checkout/api/orders/',
            data=json.dumps({
                'returnTermsAccepted': True,
                'client': {
                    'firstName': 'Абдураманов',
                    'lastName': 'Зиннур',
                    'middleName': 'Шевкетович',
                    'phone': '+78889990000',
                    'email': 'academy.goahead@gmail.com',
                },
                'delivery': {'type': 'manager'},
                'payment': {'type': 'invoice'},
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        order = Order.objects.get(user=user)
        self.assertEqual(order.email, 'server.osmanov26@mail.ru')
        self.assertEqual(order.phone, '+79990000000')
        self.assertEqual(order.customer_name, 'Османов Осман Серверович')

    def test_checkout_reports_stale_catalog_item_without_creating_order(self):
        User = get_user_model()
        user = User.objects.create_user(username='checkout-stale-cart', email='stale-cart@example.com', password='password123')
        self.client.force_login(user)
        product = self.add_checkout_product('CHECKOUT-STALE-1')
        product.status = PublishStatus.ARCHIVED
        product.save(update_fields=['status', 'updated_at'])

        response = self.client.post(
            '/checkout/api/orders/',
            data=json.dumps({
                'returnTermsAccepted': True,
                'client': {
                    'firstName': 'Stale',
                    'lastName': 'Cart',
                    'phone': '+79990000000',
                    'email': user.email,
                },
                'delivery': {'type': 'manager'},
                'payment': {'type': 'invoice'},
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('cart', response.json()['errors'])
        self.assertFalse(Order.objects.filter(user=user).exists())

    def test_checkout_reports_stale_constructor_options_without_creating_order(self):
        User = get_user_model()
        user = User.objects.create_user(username='checkout-stale-constructor', email='stale-constructor@example.com', password='password123')
        self.client.force_login(user)
        cart = Cart.objects.create(user=user)
        CartItem.objects.create(
            cart=cart,
            data={
                'id': 'constructor-stale',
                'type': 'constructor',
                'shape': {'key': 'rectangular'},
                'dimensions': [
                    {'key': 'width', 'value': 100},
                    {'key': 'depth', 'value': 80},
                    {'key': 'height', 'value': 60},
                ],
                'fabric': {'id': 999999},
                'color': {'id': 999999},
                'fastener': {'id': 999999},
                'quantity': 1,
                'unitPrice': 1000,
                'totalPrice': 1000,
            },
        )

        response = self.client.post(
            '/checkout/api/orders/',
            data=json.dumps({
                'returnTermsAccepted': True,
                'client': {
                    'firstName': 'Stale',
                    'lastName': 'Constructor',
                    'phone': '+79990000000',
                    'email': user.email,
                },
                'delivery': {'type': 'manager'},
                'payment': {'type': 'invoice'},
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('cart', response.json()['errors'])
        self.assertFalse(Order.objects.filter(user=user).exists())

    def test_checkout_ignores_constructor_attachment_owned_by_another_user(self):
        User = get_user_model()
        owner = User.objects.create_user(username='attachment-owner', email='attachment-owner@example.com')
        user = User.objects.create_user(username='checkout-attachment-user', email='checkout-attachment-user@example.com', password='password123')
        self.client.force_login(user)
        fabric, color, fastener = self.create_constructor_options()
        foreign_attachment = ConstructorAttachment.objects.create(
            user=owner,
            file=SimpleUploadedFile('foreign.pdf', b'%PDF-1.4', content_type='application/pdf'),
            original_name='foreign.pdf',
            content_type='application/pdf',
            size=8,
        )
        cart = Cart.objects.create(user=user)
        CartItem.objects.create(
            cart=cart,
            data={
                'id': 'constructor-foreign-attachment',
                'type': 'constructor',
                'shape': {'key': 'rectangular'},
                'dimensions': [
                    {'key': 'width', 'value': 100},
                    {'key': 'depth', 'value': 80},
                    {'key': 'height', 'value': 60},
                ],
                'fabric': {'id': fabric.pk},
                'color': {'id': color.pk},
                'fastener': {'id': fastener.pk},
                'attachments': [{'id': foreign_attachment.pk}],
                'quantity': 1,
                'unitPrice': 1000,
                'totalPrice': 1000,
            },
        )

        response = self.client.post(
            '/checkout/api/orders/',
            data=json.dumps({
                'returnTermsAccepted': True,
                'client': {
                    'firstName': 'Attachment',
                    'lastName': 'User',
                    'phone': '+79990000000',
                    'email': user.email,
                },
                'delivery': {'type': 'manager'},
                'payment': {'type': 'invoice'},
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        order = Order.objects.get(user=user)
        self.assertEqual(order.items.get().files.count(), 0)

    def test_checkout_requires_cdek_pickup_point(self):
        User = get_user_model()
        user = User.objects.create_user(username='checkout-cdek-pickup', email='checkout-cdek-pickup@example.com', password='password123')
        self.client.force_login(user)
        self.add_checkout_product('CHECKOUT-CDEK-PICKUP-1')

        response = self.client.post(
            '/checkout/api/orders/',
            data=json.dumps({
                'returnTermsAccepted': True,
                'client': {
                    'firstName': 'Client',
                    'lastName': 'Cdek',
                    'phone': '+79990000000',
                    'email': 'checkout-cdek-pickup@example.com',
                },
                'delivery': {'type': 'cdek-point'},
                'location': {'country': 'Россия', 'city': 'Сочи', 'cityCode': '123'},
                'payment': {'type': 'sbp'},
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('pickupPoint', response.json()['errors'])

    @override_settings(CDEK_CLIENT_ID='client', CDEK_CLIENT_SECRET='secret')
    @patch('shop.checkout_views.get_pickup_point', return_value=None)
    def test_checkout_rejects_unknown_cdek_pickup_point(self, get_pickup_point_mock):
        User = get_user_model()
        user = User.objects.create_user(username='checkout-cdek-invalid-pickup', email='checkout-cdek-invalid@example.com', password='password123')
        self.client.force_login(user)
        self.add_checkout_product('CHECKOUT-CDEK-INVALID-PICKUP-1')

        response = self.client.post(
            '/checkout/api/orders/',
            data=json.dumps({
                'returnTermsAccepted': True,
                'client': {
                    'firstName': 'Client',
                    'lastName': 'Cdek',
                    'phone': '+79990000000',
                    'email': user.email,
                },
                'delivery': {'type': 'cdek-point'},
                'location': {
                    'country': 'Россия',
                    'city': 'Сочи',
                    'cityCode': '123',
                    'pickupPointCode': 'UNKNOWN',
                    'pickupPointAddress': 'Подставной адрес',
                },
                'payment': {'type': 'sbp'},
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('pickupPoint', response.json()['errors'])
        self.assertFalse(Order.objects.filter(user=user).exists())
        get_pickup_point_mock.assert_called_once_with('123', 'UNKNOWN')

    @override_settings(CDEK_CLIENT_ID='client', CDEK_CLIENT_SECRET='secret')
    @patch('shop.checkout_views.get_delivery_quote')
    @patch('shop.checkout_views.get_pickup_point')
    def test_checkout_uses_server_cdek_pickup_point_address(self, get_pickup_point_mock, get_delivery_quote_mock):
        get_pickup_point_mock.return_value = {
            'code': 'SOCHI-1',
            'title': 'Сочи ПВЗ',
            'address': 'Россия, Краснодарский край, Сочи, ул. Транспортная, 1',
        }
        get_delivery_quote_mock.return_value = SimpleNamespace(
            title='ТК "СДЭК" доставка до пункта выдачи',
            price=Decimal('321.00'),
        )
        User = get_user_model()
        user = User.objects.create_user(username='checkout-cdek-valid-pickup', email='checkout-cdek-valid@example.com', password='password123')
        self.client.force_login(user)
        self.add_checkout_product('CHECKOUT-CDEK-VALID-PICKUP-1')

        response = self.client.post(
            '/checkout/api/orders/',
            data=json.dumps({
                'returnTermsAccepted': True,
                'client': {
                    'firstName': 'Client',
                    'lastName': 'Cdek',
                    'phone': '+79990000000',
                    'email': user.email,
                },
                'delivery': {'type': 'cdek-point'},
                'location': {
                    'country': 'Россия',
                    'city': 'Сочи',
                    'cityCode': '123',
                    'pickupPointCode': 'SOCHI-1',
                    'pickupPointAddress': 'Подставной адрес',
                },
                'payment': {'type': 'sbp'},
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        order = Order.objects.get(user=user)
        self.assertEqual(order.delivery_total, Decimal('321.00'))
        self.assertEqual(order.delivery_address, 'ПВЗ SOCHI-1: Россия, Краснодарский край, Сочи, ул. Транспортная, 1')

    def test_checkout_saves_customer_type_and_manager_address(self):
        User = get_user_model()
        user = User.objects.create_user(username='checkout-company', email='company@example.com', password='password123')
        self.client.force_login(user)
        category = Category.objects.create(title='Catalog', slug='checkout-catalog', status=PublishStatus.ACTIVE)
        product = Product.objects.create(
            category=category,
            title='Checkout product',
            sku='CHECKOUT-1',
            price=Decimal('500.00'),
            stock=3,
            status=PublishStatus.ACTIVE,
        )
        self.client.post(
            '/cart/api/items/',
            data=json.dumps({'type': 'catalog-product', 'sku': product.sku, 'quantity': 1}),
            content_type='application/json',
        )

        response = self.client.post(
            '/checkout/api/orders/',
            data=json.dumps({
                'returnTermsAccepted': True,
                'client': {
                    'type': CustomerType.COMPANY,
                    'firstName': 'Client',
                    'lastName': 'Company',
                    'phone': '+79990000000',
                    'email': 'company@example.com',
                },
                'delivery': {
                    'type': 'manager',
                    'address': 'Москва, тестовый адрес',
                },
                'payment': {'type': 'invoice'},
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        order = Order.objects.get(user=user)
        self.assertEqual(order.customer_type, CustomerType.COMPANY)
        self.assertEqual(order.delivery_address, 'Москва, тестовый адрес')
        user.customer_profile.refresh_from_db()
        self.assertEqual(user.customer_profile.customer_type, CustomerType.COMPANY)

    @override_settings(DITENT_EMAIL_NOTIFICATIONS_ENABLED=False)
    def test_checkout_allows_duplicate_catalog_lines_up_to_stock_and_decrements_stock(self):
        User = get_user_model()
        user = User.objects.create_user(username='checkout-duplicate-lines', email='duplicate-lines@example.com', password='password123')
        self.client.force_login(user)
        category = Category.objects.create(title='Duplicate lines', slug='duplicate-lines', status=PublishStatus.ACTIVE)
        product = Product.objects.create(
            category=category,
            title='Duplicate stock product',
            sku='DUPLICATE-STOCK-1',
            price=Decimal('500.00'),
            stock=2,
            status=PublishStatus.ACTIVE,
        )
        for _ in range(2):
            self.client.post(
                '/cart/api/items/',
                data=json.dumps({'type': 'catalog-product', 'sku': product.sku, 'quantity': 1}),
                content_type='application/json',
            )

        response = self.client.post(
            '/checkout/api/orders/',
            data=json.dumps({
                'returnTermsAccepted': True,
                'client': {
                    'firstName': 'Duplicate',
                    'lastName': 'Lines',
                    'phone': '+79990000000',
                    'email': user.email,
                },
                'delivery': {'type': 'manager'},
                'payment': {'type': 'invoice'},
            }),
            content_type='application/json',
        )
        product.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(product.stock, 0)
        order = Order.objects.get(user=user)
        self.assertEqual(order.number, f'DT-{order.pk:06d}')
        self.assertEqual(order.items.count(), 2)

    def test_checkout_waits_manager_confirmation_for_card_payment(self):
        User = get_user_model()
        user = User.objects.create_user(username='checkout-card', email='card@example.com', password='password123')
        self.client.force_login(user)
        category = Category.objects.create(title='Catalog', slug='checkout-card-catalog', status=PublishStatus.ACTIVE)
        product = Product.objects.create(
            category=category,
            title='Checkout card product',
            sku='CHECKOUT-CARD-1',
            price=Decimal('700.00'),
            stock=3,
            status=PublishStatus.ACTIVE,
        )
        self.client.post(
            '/cart/api/items/',
            data=json.dumps({'type': 'catalog-product', 'sku': product.sku, 'quantity': 1}),
            content_type='application/json',
        )

        response = self.client.post(
            '/checkout/api/orders/',
            data=json.dumps({
                'returnTermsAccepted': True,
                'client': {
                    'firstName': 'Client',
                    'lastName': 'Card',
                    'phone': '+79990000000',
                    'email': 'card@example.com',
                },
                'delivery': {'type': 'manager'},
                'payment': {'type': 'bank-card'},
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()['order']
        self.assertEqual(payload['paymentUrl'], '')
        order = Order.objects.get(user=user)
        self.assertEqual(order.status, OrderStatus.WAITING_MANAGER)
        self.assertEqual(order.payment_gateway, '')
        self.assertEqual(order.payment_order_id, '')
        self.assertEqual(order.payment_form_url, '')
        self.assertIsNone(order.payment_ready_at)
        self.assertEqual(order.payment_status, PaymentStatus.NOT_PAID)

    def test_order_success_hides_payment_until_manager_confirmation(self):
        User = get_user_model()
        user = User.objects.create_user(username='success-payment', email='success-payment@example.com', password='password123')
        self.client.force_login(user)
        order = Order.objects.create(
            number='DT-SUCCESS-PAYMENT',
            user=user,
            status=OrderStatus.WAITING_PAYMENT,
            payment_status=PaymentStatus.WAITING_PAYMENT,
            customer_name='Success Payment',
            phone='+79990000000',
            email=user.email,
            payment_method='sbp',
            payment_form_url='https://bank.example/pay',
            total=Decimal('1000.00'),
        )

        response = self.client.get(f'/order-success.html?order={order.number}')

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['can_pay_online'])

    def test_order_success_shows_payment_after_manager_confirmation(self):
        User = get_user_model()
        user = User.objects.create_user(username='success-payment-ready', email='success-payment-ready@example.com', password='password123')
        self.client.force_login(user)
        order = Order.objects.create(
            number='DT-SUCCESS-READY',
            user=user,
            status=OrderStatus.WAITING_PAYMENT,
            payment_status=PaymentStatus.WAITING_PAYMENT,
            customer_name='Success Payment Ready',
            phone='+79990000000',
            email=user.email,
            payment_method='sbp',
            payment_form_url='https://bank.example/pay-ready',
            payment_ready_at=timezone.now(),
            total=Decimal('1000.00'),
        )

        response = self.client.get(f'/order-success.html?order={order.number}')

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['can_pay_online'])


class AdminOrderVisibilityTests(TestCase):
    def setUp(self):
        self.admin_user = get_user_model().objects.create_user(
            username='custom-admin',
            email='custom-admin@example.com',
            password='admin-password-123',
            is_staff=True,
        )
        self.client.force_login(self.admin_user)

    def test_custom_admin_requires_staff_login(self):
        self.client.logout()

        page_response = self.client.get('/ditent-cms/')
        api_response = self.client.get('/custom-admin/api/orders/')

        self.assertEqual(page_response.status_code, 302)
        self.assertIn('/ditent-cms/login/', page_response['Location'])
        self.assertEqual(api_response.status_code, 403)
        self.assertFalse(api_response.json()['ok'])

    def test_custom_admin_login_accepts_staff_credentials(self):
        self.client.logout()

        response = self.client.post('/ditent-cms/login/', data={
            'username': self.admin_user.email,
            'password': 'admin-password-123',
            'next': '/ditent-cms/',
        })

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], '/ditent-cms/')

    def test_custom_admin_login_rejects_non_staff_user(self):
        self.client.logout()
        user = get_user_model().objects.create_user(
            username='custom-admin-client',
            email='custom-admin-client@example.com',
            password='client-password-123',
            is_staff=False,
        )

        response = self.client.post('/ditent-cms/login/', data={
            'username': user.email,
            'password': 'client-password-123',
            'next': '/ditent-cms/',
        })

        self.assertEqual(response.status_code, 400)
        self.assertContains(response, 'нет доступа к админке', status_code=400)

    def test_legacy_admin_html_redirects_to_cms_url(self):
        response = self.client.get('/admin.html')

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], '/ditent-cms/')

    @override_settings(DEBUG=True)
    def test_admin_api_unknown_entity_returns_json_404(self):
        collection_response = self.client.get('/custom-admin/api/unknown-section/')
        detail_response = self.client.get('/custom-admin/api/unknown-section/1/')

        self.assertEqual(collection_response.status_code, 404)
        self.assertFalse(collection_response.json()['ok'])
        self.assertEqual(detail_response.status_code, 404)
        self.assertFalse(detail_response.json()['ok'])

    @override_settings(DEBUG=True)
    def test_admin_api_prevents_creating_singleton_or_order_sections(self):
        settings_response = self.client.post('/custom-admin/api/site-settings/', data={})
        orders_response = self.client.post('/custom-admin/api/orders/', data={})
        drawing_response = self.client.post('/custom-admin/api/drawing-orders/', data={})

        self.assertEqual(settings_response.status_code, 405)
        self.assertEqual(orders_response.status_code, 405)
        self.assertEqual(drawing_response.status_code, 405)

    @override_settings(DEBUG=True)
    def test_admin_api_prevents_deleting_orders_and_site_settings(self):
        user = get_user_model().objects.create_user(username='admin-delete-user', email='admin-delete@example.com')
        order = Order.objects.create(
            number='DT-ADMIN-DELETE',
            user=user,
            status=OrderStatus.WAITING_MANAGER,
            payment_status=PaymentStatus.NOT_PAID,
            customer_name='Admin Delete',
            phone='+79990000000',
            email=user.email,
        )
        settings = SiteSettings.load()

        order_response = self.client.delete(f'/custom-admin/api/orders/{order.pk}/')
        settings_response = self.client.delete(f'/custom-admin/api/site-settings/{settings.pk}/')

        self.assertEqual(order_response.status_code, 405)
        self.assertEqual(settings_response.status_code, 405)
        self.assertTrue(Order.objects.filter(pk=order.pk).exists())
        self.assertTrue(SiteSettings.objects.filter(pk=settings.pk).exists())

    @override_settings(DEBUG=True)
    def test_admin_site_settings_api_saves_manager_emails(self):
        settings = SiteSettings.load()

        response = self.client.post(f'/custom-admin/api/site-settings/{settings.pk}/', data={
            'company_name': 'ООО "ДиТент"',
            'email': 'info@ditent.ru',
            'manager_emails': 'manager@ditent.ru, sales@ditent.ru; order@ditent.ru',
        })
        settings.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['ok'])
        self.assertEqual(settings.manager_emails, 'manager@ditent.ru\nsales@ditent.ru\norder@ditent.ru')
        self.assertEqual(response.json()['item']['manager_emails'], settings.manager_emails)

    @override_settings(DEBUG=True)
    def test_admin_site_settings_api_rejects_invalid_manager_email(self):
        settings = SiteSettings.load()
        settings.manager_emails = 'manager@ditent.ru'
        settings.save(update_fields=['manager_emails', 'updated_at'])

        response = self.client.post(f'/custom-admin/api/site-settings/{settings.pk}/', data={
            'company_name': 'ООО "ДиТент"',
            'email': 'info@ditent.ru',
            'manager_emails': 'manager@ditent.ru\nbad-email',
        })
        settings.refresh_from_db()

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()['ok'])
        self.assertIn('manager_emails', response.json()['errors'])
        self.assertEqual(settings.manager_emails, 'manager@ditent.ru')

    @override_settings(DEBUG=True)
    def test_admin_product_api_rejects_negative_price(self):
        parent = Category.objects.create(title='Catalog', slug='admin-negative-catalog', status=PublishStatus.ACTIVE)
        category = Category.objects.create(title='Covers', slug='admin-negative-covers', parent=parent, status=PublishStatus.ACTIVE)

        response = self.client.post('/custom-admin/api/products/', data={
            'title': 'Negative price product',
            'category': category.pk,
            'sku': 'NEG-PRICE-1',
            'price': '-1',
            'stock': '1',
            'status': PublishStatus.ACTIVE,
        })

        self.assertEqual(response.status_code, 400)
        self.assertIn('price', response.json()['errors'])
        self.assertFalse(Product.objects.filter(sku='NEG-PRICE-1').exists())

    @override_settings(DEBUG=True)
    def test_admin_order_api_rejects_negative_totals(self):
        user = get_user_model().objects.create_user(username='admin-negative-order', email='admin-negative-order@example.com')
        order = Order.objects.create(
            number='DT-ADMIN-NEGATIVE',
            user=user,
            status=OrderStatus.WAITING_MANAGER,
            payment_status=PaymentStatus.NOT_PAID,
            customer_type=CustomerType.PERSON,
            customer_name='Negative Order',
            phone='+79990000000',
            email=user.email,
            total=Decimal('100.00'),
        )

        response = self.client.post(f'/custom-admin/api/orders/{order.pk}/', data={
            'number': order.number,
            'status': OrderStatus.WAITING_MANAGER,
            'payment_status': PaymentStatus.NOT_PAID,
            'customer_type': CustomerType.PERSON,
            'customer_name': order.customer_name,
            'phone': order.phone,
            'email': order.email,
            'delivery_method': '',
            'delivery_city': '',
            'delivery_address': '',
            'track_number': '',
            'payment_method': '',
            'items_total': '100.00',
            'delivery_total': '0.00',
            'discount_total': '0.00',
            'vat_total': '0.00',
            'total': '-1.00',
            'client_comment': '',
            'manager_comment': '',
            'return_terms_accepted': 'on',
        })
        order.refresh_from_db()

        self.assertEqual(response.status_code, 400)
        self.assertIn('total', response.json()['errors'])
        self.assertEqual(order.total, Decimal('100.00'))

    @override_settings(DEBUG=True)
    def test_admin_formula_api_rejects_invalid_size_range(self):
        response = self.client.post('/custom-admin/api/formulas/', data={
            'title': 'Invalid size formula',
            'shape': CoverShape.RECTANGULAR,
            'code': 'invalid_size_formula',
            'coefficient': '1.000',
            'minimum_price': '1000.00',
            'seam_price_cm': '0.00',
            'topstitch_price_cm': '0.00',
            'edging_price_cm': '0.00',
            'min_size_cm': '300',
            'max_size_cm': '100',
            'expression': '',
            'parameters': '{}',
            'status': PublishStatus.ACTIVE,
        })

        self.assertEqual(response.status_code, 400)
        self.assertIn('max_size_cm', response.json()['errors'])
        self.assertFalse(Formula.objects.filter(code='invalid_size_formula').exists())

    @override_settings(DEBUG=True)
    def test_admin_orders_api_hides_mock_orders(self):
        User = get_user_model()
        user = User.objects.create_user(username='admin-order-user', email='admin-order@example.com')
        real_order = Order.objects.create(
            number='DT-REAL-001',
            user=user,
            status=OrderStatus.WAITING_MANAGER,
            payment_status=PaymentStatus.NOT_PAID,
            customer_name='Real Client',
            phone='+79990000000',
            email=user.email,
            total=Decimal('1000.00'),
        )
        mock_order = Order.objects.create(
            number='DT-MOCK-999999',
            user=user,
            status=OrderStatus.WAITING_MANAGER,
            payment_status=PaymentStatus.NOT_PAID,
            customer_name='Mock Client',
            phone='+79990000000',
            email=user.email,
            total=Decimal('1000.00'),
        )

        response = self.client.get('/custom-admin/api/orders/')

        self.assertEqual(response.status_code, 200)
        numbers = [item['number'] for item in response.json()['items']]
        self.assertIn(real_order.number, numbers)
        self.assertNotIn(mock_order.number, numbers)

        detail_response = self.client.get(f'/custom-admin/api/orders/{mock_order.pk}/')
        self.assertEqual(detail_response.status_code, 404)

    @override_settings(DEBUG=True)
    def test_admin_orders_api_uses_manager_confirmation_label_before_payment_ready(self):
        User = get_user_model()
        user = User.objects.create_user(username='admin-order-status-user', email='admin-order-status@example.com')
        order = Order.objects.create(
            number='DT-STATUS-001',
            user=user,
            status=OrderStatus.WAITING_PAYMENT,
            payment_status=PaymentStatus.WAITING_PAYMENT,
            customer_name='Status Client',
            phone='+79990000000',
            email=user.email,
            payment_form_url='https://bank.example/pay',
            total=Decimal('1000.00'),
        )

        response = self.client.get('/custom-admin/api/orders/')

        self.assertEqual(response.status_code, 200)
        payload = next(item for item in response.json()['items'] if item['number'] == order.number)
        self.assertEqual(payload['status_label'], OrderStatus.WAITING_MANAGER.label)
        self.assertEqual(payload['payment_status_label'], PaymentStatus.NOT_PAID.label)

    @patch('shop.admin_views.register_payment')
    def test_admin_confirmation_creates_online_payment_link_once(self, register_payment_mock):
        from shop.admin_views import prepare_order_payment_after_manager_confirmation

        register_payment_mock.return_value = {
            'payment_order_id': 'bank-order-1',
            'payment_form_url': 'https://bank.example/pay-1',
        }
        request = RequestFactory().post('/custom-admin/api/orders/1/')
        user = get_user_model().objects.create_user(username='admin-payment-user', email='admin-payment@example.com')
        order = Order.objects.create(
            number='DT-ADMIN-PAY',
            user=user,
            status=OrderStatus.WAITING_PAYMENT,
            payment_status=PaymentStatus.NOT_PAID,
            customer_name='Admin Payment',
            phone='+79990000000',
            email=user.email,
            payment_method='sbp',
            total=Decimal('1000.00'),
        )

        prepare_order_payment_after_manager_confirmation(request, order)
        order.refresh_from_db()

        self.assertEqual(order.payment_status, PaymentStatus.WAITING_PAYMENT)
        self.assertEqual(order.payment_gateway, 'alfa')
        self.assertEqual(order.payment_order_id, 'bank-order-1')
        self.assertEqual(order.payment_form_url, 'https://bank.example/pay-1')
        self.assertIsNotNone(order.payment_ready_at)
        register_payment_mock.assert_called_once()

        prepare_order_payment_after_manager_confirmation(request, order)
        register_payment_mock.assert_called_once()

    @patch('shop.admin_views.register_payment')
    def test_admin_save_does_not_create_new_payment_for_paid_order(self, register_payment_mock):
        from shop.admin_views import prepare_order_payment_after_manager_confirmation

        request = RequestFactory().post('/custom-admin/api/orders/1/')
        user = get_user_model().objects.create_user(username='admin-paid-user', email='admin-paid@example.com')
        order = Order.objects.create(
            number='DT-ADMIN-PAID',
            user=user,
            status=OrderStatus.WAITING_PAYMENT,
            payment_status=PaymentStatus.PAID,
            customer_name='Admin Paid',
            phone='+79990000000',
            email=user.email,
            payment_method='sbp',
            payment_ready_at=timezone.now(),
            total=Decimal('1000.00'),
        )

        prepare_order_payment_after_manager_confirmation(request, order)
        order.refresh_from_db()

        register_payment_mock.assert_not_called()
        self.assertEqual(order.payment_status, PaymentStatus.PAID)
        self.assertEqual(order.payment_form_url, '')

    @override_settings(DEBUG=True, CDEK_CLIENT_ID='client', CDEK_CLIENT_SECRET='secret')
    @patch('shop.cdek_tracking.cdek_get')
    def test_admin_cdek_tracking_marks_delivered_order_completed(self, cdek_get_mock):
        cdek_get_mock.return_value = {
            'entity': {
                'uuid': 'cdek-uuid-1',
                'cdek_number': '1234567890',
                'statuses': [
                    {'code': 'ACCEPTED_AT_PICK_UP_POINT', 'name': 'Поступил в пункт выдачи', 'date_time': '2026-05-31T10:00:00+03:00'},
                    {'code': 'DELIVERED', 'name': 'Вручен', 'date_time': '2026-05-31T12:00:00+03:00'},
                ],
            }
        }
        user = get_user_model().objects.create_user(username='admin-cdek-user', email='admin-cdek@example.com')
        order = Order.objects.create(
            number='DT-CDEK-001',
            user=user,
            status=OrderStatus.IN_DELIVERY,
            payment_status=PaymentStatus.PAID,
            customer_name='CDEK Client',
            phone='+79990000000',
            email=user.email,
            delivery_method='ТК "СДЭК" доставка до пункта выдачи',
            track_number='1234567890',
            total=Decimal('1000.00'),
        )

        response = self.client.post(f'/custom-admin/api/orders/{order.pk}/cdek-tracking/')
        order.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(order.status, OrderStatus.COMPLETED)
        self.assertEqual(order.cdek_order_uuid, 'cdek-uuid-1')
        self.assertEqual(order.cdek_status_code, 'DELIVERED')
        self.assertEqual(order.cdek_status_name, 'Вручен')
        self.assertIsNotNone(order.cdek_tracking_checked_at)
        self.assertEqual(response.json()['item']['status_label'], OrderStatus.COMPLETED.label)

    @override_settings(DEBUG=True, CDEK_CLIENT_ID='client', CDEK_CLIENT_SECRET='secret')
    @patch('shop.cdek_tracking.cdek_get')
    def test_admin_cdek_tracking_does_not_move_unconfirmed_order_to_delivery(self, cdek_get_mock):
        cdek_get_mock.return_value = {
            'entity': {
                'uuid': 'cdek-uuid-2',
                'cdek_number': '1234567891',
                'statuses': [
                    {'code': 'ACCEPTED_AT_PICK_UP_POINT', 'name': 'Поступил в пункт выдачи', 'date_time': '2026-05-31T10:00:00+03:00'},
                ],
            }
        }
        user = get_user_model().objects.create_user(username='admin-cdek-wait-user', email='admin-cdek-wait@example.com')
        order = Order.objects.create(
            number='DT-CDEK-002',
            user=user,
            status=OrderStatus.WAITING_PAYMENT,
            payment_status=PaymentStatus.WAITING_PAYMENT,
            customer_name='CDEK Wait Client',
            phone='+79990000000',
            email=user.email,
            track_number='1234567891',
            total=Decimal('1000.00'),
        )

        response = self.client.post(f'/custom-admin/api/orders/{order.pk}/cdek-tracking/')
        order.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(order.status, OrderStatus.WAITING_PAYMENT)
        self.assertEqual(order.cdek_status_code, 'ACCEPTED_AT_PICK_UP_POINT')

    @override_settings(CDEK_CLIENT_ID='client', CDEK_CLIENT_SECRET='secret')
    @patch('shop.cdek_tracking.cdek_get')
    def test_sync_cdek_tracking_command_updates_orders_with_track_numbers(self, cdek_get_mock):
        cdek_get_mock.return_value = {
            'entity': {
                'uuid': 'cdek-uuid-3',
                'cdek_number': '1234567892',
                'statuses': [
                    {'code': 'DELIVERED', 'name': 'Вручен', 'date_time': '2026-05-31T12:00:00+03:00'},
                ],
            }
        }
        user = get_user_model().objects.create_user(username='command-cdek-user', email='command-cdek@example.com')
        order = Order.objects.create(
            number='DT-CDEK-003',
            user=user,
            status=OrderStatus.IN_DELIVERY,
            payment_status=PaymentStatus.PAID,
            customer_name='Command CDEK Client',
            phone='+79990000000',
            email=user.email,
            track_number='1234567892',
            total=Decimal('1000.00'),
        )
        out = StringIO()

        call_command('sync_cdek_tracking', '--order=DT-CDEK-003', stdout=out)
        order.refresh_from_db()

        self.assertEqual(order.status, OrderStatus.COMPLETED)
        self.assertEqual(order.cdek_status_code, 'DELIVERED')
        self.assertIn('Synced: 1. Failed: 0.', out.getvalue())

    @patch('shop.checkout_views.get_payment_status')
    def test_alfa_return_marks_order_paid_and_hides_payment_link(self, get_payment_status_mock):
        get_payment_status_mock.return_value = {'orderStatus': 2}
        user = get_user_model().objects.create_user(username='payment-return-user', email='payment-return@example.com')
        self.client.force_login(user)
        order = Order.objects.create(
            number='DT-PAYMENT-RETURN',
            user=user,
            status=OrderStatus.WAITING_PAYMENT,
            payment_status=PaymentStatus.WAITING_PAYMENT,
            customer_name='Payment Return',
            phone='+79990000000',
            email=user.email,
            payment_method='sbp',
            payment_gateway='alfa',
            payment_order_id='bank-order-return',
            payment_form_url='https://bank.example/pay-return',
            payment_ready_at=timezone.now(),
            total=Decimal('1000.00'),
        )

        response = self.client.get(f'/payment/alfa/return/?order={order.number}&status=success')
        order.refresh_from_db()

        self.assertEqual(response.status_code, 302)
        self.assertIn(f'/order-success.html?order={order.number}&payment=success', response['Location'])
        self.assertEqual(order.payment_status, PaymentStatus.PAID)
        self.assertEqual(order.payment_form_url, '')

    @patch('shop.checkout_views.get_payment_status')
    def test_alfa_return_does_not_downgrade_paid_order_on_late_fail_status(self, get_payment_status_mock):
        get_payment_status_mock.return_value = {'orderStatus': 6}
        user = get_user_model().objects.create_user(username='payment-return-paid-user', email='payment-return-paid@example.com')
        self.client.force_login(user)
        order = Order.objects.create(
            number='DT-PAYMENT-RETURN-PAID',
            user=user,
            status=OrderStatus.WAITING_PAYMENT,
            payment_status=PaymentStatus.PAID,
            customer_name='Payment Return Paid',
            phone='+79990000000',
            email=user.email,
            payment_method='sbp',
            payment_gateway='alfa',
            payment_order_id='bank-order-return-paid',
            payment_form_url='',
            payment_ready_at=timezone.now(),
            total=Decimal('1000.00'),
        )

        response = self.client.get(f'/payment/alfa/return/?order={order.number}&status=fail')
        order.refresh_from_db()

        self.assertEqual(response.status_code, 302)
        self.assertIn(f'/order-success.html?order={order.number}&payment=success', response['Location'])
        self.assertEqual(order.payment_status, PaymentStatus.PAID)

    @override_settings(DEBUG=True, ALFA_ACQUIRING_CALLBACK_TOKEN='')
    def test_alfa_callback_marks_order_paid_without_browser_return(self):
        user = get_user_model().objects.create_user(username='payment-callback-user', email='payment-callback@example.com')
        order = Order.objects.create(
            number='DT-PAYMENT-CALLBACK',
            user=user,
            status=OrderStatus.WAITING_PAYMENT,
            payment_status=PaymentStatus.WAITING_PAYMENT,
            customer_name='Payment Callback',
            phone='+79990000000',
            email=user.email,
            payment_method='sbp',
            payment_gateway='alfa',
            payment_order_id='bank-order-callback',
            payment_form_url='https://bank.example/pay-callback',
            payment_ready_at=timezone.now(),
            total=Decimal('1000.00'),
        )

        response = self.client.get('/payment/alfa/callback/', {
            'mdOrder': order.payment_order_id,
            'orderNumber': order.number,
            'operation': 'deposited',
            'status': '1',
        })
        order.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['updated'])
        self.assertEqual(order.payment_status, PaymentStatus.PAID)
        self.assertEqual(order.payment_form_url, '')

    @override_settings(ALFA_ACQUIRING_CALLBACK_TOKEN='callback-secret')
    def test_alfa_callback_requires_valid_checksum_when_token_configured(self):
        user = get_user_model().objects.create_user(username='payment-callback-signed-user', email='payment-callback-signed@example.com')
        order = Order.objects.create(
            number='DT-PAYMENT-CALLBACK-SIGNED',
            user=user,
            status=OrderStatus.WAITING_PAYMENT,
            payment_status=PaymentStatus.WAITING_PAYMENT,
            customer_name='Payment Callback Signed',
            phone='+79990000000',
            email=user.email,
            payment_method='sbp',
            payment_gateway='alfa',
            payment_order_id='bank-order-callback-signed',
            payment_form_url='https://bank.example/pay-callback-signed',
            payment_ready_at=timezone.now(),
            total=Decimal('1000.00'),
        )
        params = {
            'mdOrder': order.payment_order_id,
            'orderNumber': order.number,
            'operation': 'deposited',
            'status': '1',
        }

        invalid_response = self.client.get('/payment/alfa/callback/', {**params, 'checksum': 'bad'})
        self.assertEqual(invalid_response.status_code, 400)

        valid_response = self.client.get('/payment/alfa/callback/', {
            **params,
            'checksum': callback_checksum(params, 'callback-secret'),
        })
        order.refresh_from_db()

        self.assertEqual(valid_response.status_code, 200)
        self.assertEqual(order.payment_status, PaymentStatus.PAID)

    @override_settings(DEBUG=False, ALFA_ACQUIRING_CALLBACK_TOKEN='')
    def test_alfa_callback_requires_token_in_production(self):
        response = self.client.get('/payment/alfa/callback/', {
            'operation': 'deposited',
            'status': '1',
        })

        self.assertEqual(response.status_code, 503)

    @override_settings(DEBUG=True, ALFA_ACQUIRING_CALLBACK_TOKEN='')
    def test_alfa_callback_refund_marks_order_refunded(self):
        user = get_user_model().objects.create_user(username='payment-callback-refund-user', email='payment-callback-refund@example.com')
        order = Order.objects.create(
            number='DT-PAYMENT-CALLBACK-REFUND',
            user=user,
            status=OrderStatus.WAITING_PAYMENT,
            payment_status=PaymentStatus.PAID,
            customer_name='Payment Callback Refund',
            phone='+79990000000',
            email=user.email,
            payment_method='sbp',
            payment_gateway='alfa',
            payment_order_id='bank-order-callback-refund',
            payment_ready_at=timezone.now(),
            total=Decimal('1000.00'),
        )

        response = self.client.post('/payment/alfa/callback/', {
            'mdOrder': order.payment_order_id,
            'orderNumber': order.number,
            'operation': 'refunded',
            'status': '1',
        })
        order.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(order.payment_status, PaymentStatus.REFUNDED)

    @override_settings(DEBUG=True, ALFA_ACQUIRING_CALLBACK_TOKEN='')
    def test_alfa_callback_decline_does_not_downgrade_paid_order(self):
        user = get_user_model().objects.create_user(username='payment-callback-decline-user', email='payment-callback-decline@example.com')
        order = Order.objects.create(
            number='DT-PAYMENT-CALLBACK-DECLINE',
            user=user,
            status=OrderStatus.WAITING_PAYMENT,
            payment_status=PaymentStatus.PAID,
            customer_name='Payment Callback Decline',
            phone='+79990000000',
            email=user.email,
            payment_method='sbp',
            payment_gateway='alfa',
            payment_order_id='bank-order-callback-decline',
            payment_ready_at=timezone.now(),
            total=Decimal('1000.00'),
        )

        response = self.client.post('/payment/alfa/callback/', {
            'mdOrder': order.payment_order_id,
            'orderNumber': order.number,
            'operation': 'declinedByTimeout',
            'status': '1',
        })
        order.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()['updated'])
        self.assertEqual(order.payment_status, PaymentStatus.PAID)

    @override_settings(DEBUG=True, ALFA_ACQUIRING_CALLBACK_TOKEN='')
    def test_alfa_callback_decline_marks_waiting_payment_order_not_paid(self):
        user = get_user_model().objects.create_user(username='payment-callback-decline-wait-user', email='payment-callback-decline-wait@example.com')
        order = Order.objects.create(
            number='DT-PAYMENT-CALLBACK-DECLINE-WAIT',
            user=user,
            status=OrderStatus.WAITING_PAYMENT,
            payment_status=PaymentStatus.WAITING_PAYMENT,
            customer_name='Payment Callback Decline Wait',
            phone='+79990000000',
            email=user.email,
            payment_method='sbp',
            payment_gateway='alfa',
            payment_order_id='bank-order-callback-decline-wait',
            payment_form_url='https://bank.example/pay-callback-decline-wait',
            payment_ready_at=timezone.now(),
            total=Decimal('1000.00'),
        )

        response = self.client.post('/payment/alfa/callback/', {
            'mdOrder': order.payment_order_id,
            'orderNumber': order.number,
            'operation': 'declinedByTimeout',
            'status': '1',
        })
        order.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['updated'])
        self.assertEqual(order.payment_status, PaymentStatus.NOT_PAID)

    @override_settings(DEBUG=True, ALFA_ACQUIRING_CALLBACK_TOKEN='')
    def test_alfa_callback_rejects_mismatched_order_number(self):
        user = get_user_model().objects.create_user(username='payment-callback-mismatch-user', email='payment-callback-mismatch@example.com')
        order = Order.objects.create(
            number='DT-PAYMENT-CALLBACK-MISMATCH',
            user=user,
            status=OrderStatus.WAITING_PAYMENT,
            payment_status=PaymentStatus.WAITING_PAYMENT,
            customer_name='Payment Callback Mismatch',
            phone='+79990000000',
            email=user.email,
            payment_method='sbp',
            payment_gateway='alfa',
            payment_order_id='bank-order-callback-mismatch',
            payment_form_url='https://bank.example/pay-callback-mismatch',
            payment_ready_at=timezone.now(),
            total=Decimal('1000.00'),
        )

        response = self.client.get('/payment/alfa/callback/', {
            'mdOrder': order.payment_order_id,
            'orderNumber': 'DT-OTHER',
            'operation': 'deposited',
            'status': '1',
        })
        order.refresh_from_db()

        self.assertEqual(response.status_code, 400)
        self.assertEqual(order.payment_status, PaymentStatus.WAITING_PAYMENT)


class CsrfProtectionTests(TestCase):
    def test_checkout_order_requires_csrf_token(self):
        client = Client(enforce_csrf_checks=True)
        user = get_user_model().objects.create_user(username='csrf-checkout', email='csrf-checkout@example.com')
        client.force_login(user)

        response = client.post('/checkout/api/orders/', data='{}', content_type='application/json')

        self.assertEqual(response.status_code, 403)

    def test_cabinet_profile_update_requires_csrf_token(self):
        client = Client(enforce_csrf_checks=True)
        user = get_user_model().objects.create_user(username='csrf-profile', email='csrf-profile@example.com')
        client.force_login(user)

        response = client.post('/cabinet/api/profile/update/', data='{}', content_type='application/json')

        self.assertEqual(response.status_code, 403)

    def test_drawing_order_create_requires_csrf_token(self):
        client = Client(enforce_csrf_checks=True)
        user = get_user_model().objects.create_user(username='csrf-drawing', email='csrf-drawing@example.com')
        client.force_login(user)

        response = client.post('/api/drawing-orders/', data={})

        self.assertEqual(response.status_code, 403)

    @override_settings(DEBUG=True)
    def test_custom_admin_write_requires_csrf_token(self):
        client = Client(enforce_csrf_checks=True)
        settings = SiteSettings.load()

        post_response = client.post(f'/custom-admin/api/site-settings/{settings.pk}/', data={
            'company_name': 'ООО "ДиТент"',
            'email': 'info@ditent.ru',
        })
        delete_response = client.delete(f'/custom-admin/api/site-settings/{settings.pk}/')

        self.assertEqual(post_response.status_code, 403)
        self.assertEqual(delete_response.status_code, 403)

    @override_settings(DEBUG=True, ALFA_ACQUIRING_CALLBACK_TOKEN='')
    def test_payment_callback_is_csrf_exempt_for_bank_notifications(self):
        client = Client(enforce_csrf_checks=True)
        user = get_user_model().objects.create_user(username='csrf-callback-user', email='csrf-callback@example.com')
        order = Order.objects.create(
            number='DT-CSRF-CALLBACK',
            user=user,
            status=OrderStatus.WAITING_PAYMENT,
            payment_status=PaymentStatus.WAITING_PAYMENT,
            customer_name='CSRF Callback',
            phone='+79990000000',
            email=user.email,
            payment_method='sbp',
            payment_gateway='alfa',
            payment_order_id='bank-order-csrf-callback',
            payment_form_url='https://bank.example/pay-csrf',
            payment_ready_at=timezone.now(),
            total=Decimal('1000.00'),
        )

        response = client.post('/payment/alfa/callback/', {
            'mdOrder': order.payment_order_id,
            'orderNumber': order.number,
            'operation': 'deposited',
            'status': '1',
        })

        self.assertEqual(response.status_code, 200)


class CartStockTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(
            title='Catalog',
            slug='catalog',
            status=PublishStatus.ACTIVE,
        )
        self.product = Product.objects.create(
            category=self.category,
            title='Stock product',
            sku='STOCK-2',
            price=Decimal('200.00'),
            stock=2,
            status=PublishStatus.ACTIVE,
        )

    def add_catalog_item(self, quantity):
        return self.client.post(
            '/cart/api/items/',
            data=json.dumps({
                'type': 'catalog-product',
                'sku': self.product.sku,
                'quantity': quantity,
            }),
            content_type='application/json',
        )

    def test_rejects_catalog_quantity_above_stock(self):
        response = self.add_catalog_item(3)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], '\u0414\u043e\u0441\u0442\u0443\u043f\u043d\u043e \u0442\u043e\u043b\u044c\u043a\u043e 2 \u0448\u0442.')

    def test_rejects_catalog_quantity_across_cart_entries(self):
        first_response = self.add_catalog_item(2)
        second_response = self.add_catalog_item(1)

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 400)
        self.assertEqual(
            second_response.json()['error'],
            '\u0412\u0435\u0441\u044c \u0434\u043e\u0441\u0442\u0443\u043f\u043d\u044b\u0439 \u043e\u0441\u0442\u0430\u0442\u043e\u043a \u0443\u0436\u0435 \u0432 \u043a\u043e\u0440\u0437\u0438\u043d\u0435.',
        )

    def test_rejects_catalog_quantity_update_above_stock(self):
        add_response = self.add_catalog_item(1)
        item_id = add_response.json()['cart']['items'][0]['id']

        response = self.client.post(
            f'/cart/api/items/{item_id}/quantity/',
            data=json.dumps({'quantity': 3}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], '\u0414\u043e\u0441\u0442\u0443\u043f\u043d\u043e \u0442\u043e\u043b\u044c\u043a\u043e 2 \u0448\u0442.')

    def test_login_persists_guest_cart_for_user(self):
        User = get_user_model()
        user = User.objects.create_user(
            username='cart-user',
            email='cart-user@example.com',
            password='password123',
        )

        add_response = self.add_catalog_item(1)
        login_response = self.client.post(
            '/auth/api/login/',
            data=json.dumps({'email': user.email, 'password': 'password123'}),
            content_type='application/json',
        )
        self.client.post('/auth/api/logout/')
        second_client = Client()
        second_login_response = second_client.post(
            '/auth/api/login/',
            data=json.dumps({'email': user.email, 'password': 'password123'}),
            content_type='application/json',
        )
        cart_response = second_client.get('/cart/api/')

        self.assertEqual(add_response.status_code, 200)
        self.assertEqual(login_response.status_code, 200)
        self.assertEqual(second_login_response.status_code, 200)
        self.assertEqual(cart_response.status_code, 200)
        self.assertEqual(cart_response.json()['cart']['userId'], user.id)
        self.assertEqual(len(cart_response.json()['cart']['items']), 1)
        self.assertEqual(cart_response.json()['cart']['items'][0]['sku'], self.product.sku)
        self.assertEqual(cart_response.json()['cart']['items'][0]['quantity'], 1)


class DeliveryLocationTests(TestCase):
    @override_settings(
        CDEK_API_BASE_URL='https://api.cdek.example',
        CDEK_CLIENT_ID='client',
        CDEK_CLIENT_SECRET='secret',
    )
    @patch('shop.location_services.cdek_request_json')
    def test_cdek_get_refreshes_expired_oauth_token(self, cdek_request_json_mock):
        from shop import location_services

        cache.delete(location_services.CDEK_TOKEN_CACHE_KEY)
        token_responses = iter([
            {'access_token': 'expired-token', 'expires_in': 3600},
            {'access_token': 'fresh-token', 'expires_in': 3600},
        ])
        deliverypoints_calls = []

        def fake_cdek_request(request, attempts=2):
            if request.full_url.endswith('/v2/oauth/token'):
                return next(token_responses)

            deliverypoints_calls.append(request.headers.get('Authorization'))
            if len(deliverypoints_calls) == 1:
                raise HTTPError(request.full_url, 401, 'Unauthorized', hdrs=None, fp=None)

            return [{'code': 'PVZ1'}]

        cdek_request_json_mock.side_effect = fake_cdek_request

        result = location_services.cdek_get('/v2/deliverypoints', {'city_code': '1588'})

        self.assertEqual(result, [{'code': 'PVZ1'}])
        self.assertEqual(deliverypoints_calls, ['Bearer expired-token', 'Bearer fresh-token'])

    @override_settings(
        CDEK_CLIENT_ID='client',
        CDEK_CLIENT_SECRET='secret',
        CDEK_LOCATION_COUNTRY_CODES=['RU', 'TR', 'DE'],
    )
    @patch('shop.location_services.cdek_get')
    def test_country_list_contains_only_countries_with_pickup_points(self, cdek_get_mock):
        from shop import location_services

        location_services.cdek_country_has_pickup.cache_clear()
        cdek_get_mock.side_effect = lambda path, params: (
            [{'code': 'PVZ1'}] if params.get('country_code') in {'RU', 'TR'} else []
        )

        response = self.client.get('/checkout/api/delivery/locations/?type=countries')

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item['code'] for item in response.json()['items']], ['RU', 'TR'])
        self.assertNotIn('/v2/location/countries', [call.args[0] for call in cdek_get_mock.call_args_list])

    @override_settings(CDEK_CLIENT_ID='client', CDEK_CLIENT_SECRET='secret')
    @patch('shop.location_services.cdek_get')
    def test_region_list_returns_only_regions_with_pickup_points(self, cdek_get_mock):
        from shop import location_services

        location_services.cdek_pickup_regions.cache_clear()
        cdek_get_mock.return_value = [
            {
                'code': 'PVZ-A',
                'location': {
                    'country_code': 'TR',
                    'region_code': '10',
                    'region': 'Регион А',
                },
            },
            {
                'code': 'PVZ-B',
                'location': {
                    'country_code': 'TR',
                    'region_code': '10',
                    'region': 'Регион А',
                },
            },
            {
                'code': 'PVZ-C',
                'location': {
                    'country_code': 'TR',
                    'region_code': '20',
                    'region': 'Регион Б',
                },
            },
        ]

        response = self.client.get('/checkout/api/delivery/locations/?type=regions&country=TR')

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item['title'] for item in response.json()['items']], ['Регион А', 'Регион Б'])
        cdek_get_mock.assert_called_once_with('/v2/deliverypoints', {
            'country_code': 'TR',
            'type': 'PVZ',
            'is_handout': 'true',
        })

    @override_settings(CDEK_CLIENT_ID='', CDEK_CLIENT_SECRET='')
    def test_delivery_location_api_returns_fallback_locations(self):
        countries_response = self.client.get('/checkout/api/delivery/locations/?type=countries')
        regions_response = self.client.get('/checkout/api/delivery/locations/?type=regions&country=RU')
        cities_response = self.client.get('/checkout/api/delivery/locations/?type=cities&country=RU&q=Сочи')

        self.assertEqual(countries_response.status_code, 200)
        self.assertEqual(regions_response.status_code, 200)
        self.assertEqual(cities_response.status_code, 200)
        self.assertIn('RU', [item['code'] for item in countries_response.json()['items']])
        self.assertIn('Краснодарский край', [item['title'] for item in regions_response.json()['items']])
        self.assertEqual(cities_response.json()['items'][0]['title'], 'Сочи')


    @override_settings(
        CDEK_CLIENT_ID='client',
        CDEK_CLIENT_SECRET='secret',
        CDEK_ORIGIN_CITY_CODE=437,
        CDEK_TARIFF_CODE_PICKUP=136,
    )
    @patch('shop.delivery_services.cdek_post')
    def test_delivery_quote_uses_cdek_calculator(self, cdek_post_mock):
        cdek_post_mock.return_value = {
            'total_sum': 451.50,
            'period_min': 3,
            'period_max': 4,
        }

        response = self.client.post(
            '/checkout/api/delivery/',
            data=json.dumps({
                'method': 'cdek-point',
                'cityCode': '44',
                'itemsCount': 1,
                'subtotal': 2000,
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        quote = response.json()['quote']
        self.assertEqual(quote['provider'], 'cdek')
        self.assertEqual(quote['price'], 451.5)
        cdek_post_mock.assert_called_once()

    @override_settings(CDEK_CLIENT_ID='client', CDEK_CLIENT_SECRET='secret')
    @patch('shop.delivery_services.cdek_get')
    def test_pickup_points_api_returns_cdek_points(self, cdek_get_mock):
        cdek_get_mock.return_value = [{
            'code': 'MSK1',
            'name': 'MSK1, Москва',
            'work_time': 'Пн-Пт 10:00-20:00',
            'phones': [{'number': '+79990000000'}],
            'location': {
                'address_full': 'Россия, Москва, ул. Тестовая, 1',
                'latitude': 55.7,
                'longitude': 37.6,
            },
        }]

        response = self.client.get('/checkout/api/delivery/pickup-points/?city=44')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['items'][0]['code'], 'MSK1')
        self.assertEqual(response.json()['items'][0]['address'], 'Россия, Москва, ул. Тестовая, 1')
        cdek_get_mock.assert_called_once_with('/v2/deliverypoints', {
            'city_code': '44',
            'type': 'PVZ',
            'is_handout': 'true',
            'size': 30,
        })

    @override_settings(CDEK_CLIENT_ID='client', CDEK_CLIENT_SECRET='secret')
    @patch('shop.delivery_services.cdek_get')
    def test_pickup_points_api_reports_cdek_errors(self, cdek_get_mock):
        cdek_get_mock.side_effect = RuntimeError('CDEK failed')

        response = self.client.get('/checkout/api/delivery/pickup-points/?city=44')

        self.assertEqual(response.status_code, 502)
        self.assertFalse(response.json()['ok'])
        self.assertIn('СДЭК временно не вернул пункты выдачи', response.json()['error'])

    @override_settings(CDEK_CLIENT_ID='client', CDEK_CLIENT_SECRET='secret')
    @patch('shop.location_services.cdek_get')
    def test_country_city_list_uses_pickup_points_when_region_is_empty(self, cdek_get_mock):
        from shop import location_services

        location_services.cdek_pickup_cities.cache_clear()
        cdek_get_mock.return_value = [
            {
                'code': 'DE1',
                'location': {
                    'city_code': 8569,
                    'city': 'Лейпциг',
                    'region_code': 235,
                    'region': 'Саксония',
                    'country_code': 'DE',
                },
            },
            {
                'code': 'DE2',
                'location': {
                    'city_code': 73944,
                    'city': 'Шёнек',
                    'region_code': 417,
                    'region': 'Гессен',
                    'country_code': 'DE',
                },
            },
        ]

        response = self.client.get('/checkout/api/delivery/locations/?type=cities&country=DE')

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item['title'] for item in response.json()['items']], ['Лейпциг', 'Шёнек'])
        cdek_get_mock.assert_called_once_with('/v2/deliverypoints', {
            'country_code': 'DE',
            'type': 'PVZ',
            'is_handout': 'true',
        })

    @override_settings(CDEK_CLIENT_ID='client', CDEK_CLIENT_SECRET='secret')
    @patch('shop.location_services.cdek_get')
    def test_city_search_filters_region_when_cdek_partial_search_is_empty(self, cdek_get_mock):
        cdek_get_mock.return_value = [
            {
                'code': 'GRZ1',
                'location': {
                    'city_code': 441,
                    'city': 'Грозный',
                    'region_code': 71,
                    'region': 'Чеченская Республика',
                    'sub_region': '',
                    'country_code': 'RU',
                },
            },
            {
                'code': 'ARG1',
                'location': {
                    'city_code': 3143,
                    'city': 'Аргун',
                    'region_code': 71,
                    'region': 'Чеченская Республика',
                    'sub_region': '',
                    'country_code': 'RU',
                },
            },
        ]

        response = self.client.get('/checkout/api/delivery/locations/?type=cities&country=RU&region=71&q=Гроз')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['items'][0]['title'], 'Грозный')

    @override_settings(CDEK_CLIENT_ID='client', CDEK_CLIENT_SECRET='secret')
    @patch('shop.location_services.cdek_get')
    def test_empty_city_search_returns_region_cities(self, cdek_get_mock):
        cdek_get_mock.return_value = [
            {
                'code': 'BRY1',
                'location': {
                    'city_code': 10,
                    'city': 'Брянск',
                    'region_code': 81,
                    'region': 'Брянская область',
                    'sub_region': '',
                    'country_code': 'RU',
                },
            },
            {
                'code': 'KLI1',
                'location': {
                    'city_code': 11,
                    'city': 'Клинцы',
                    'region_code': 81,
                    'region': 'Брянская область',
                    'sub_region': '',
                    'country_code': 'RU',
                },
            },
            {
                'code': 'ZHA1',
                'location': {
                    'city_code': 12,
                    'city': 'Желтая Акация',
                    'region_code': 81,
                    'region': 'Брянская область',
                    'sub_region': '',
                    'country_code': 'RU',
                },
            },
        ]

        response = self.client.get('/checkout/api/delivery/locations/?type=cities&country=RU&region=81')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item['title'] for item in response.json()['items']],
            ['Брянск', 'Желтая Акация', 'Клинцы'],
        )
        cdek_get_mock.assert_called_once_with('/v2/deliverypoints', {
            'country_code': 'RU',
            'region_code': '81',
            'type': 'PVZ',
            'is_handout': 'true',
        })

    @override_settings(CDEK_CLIENT_ID='client', CDEK_CLIENT_SECRET='secret')
    @patch('shop.location_services.cdek_get')
    def test_city_search_deduplicates_identical_cdek_city_labels(self, cdek_get_mock):
        cdek_get_mock.return_value = [
            {
                'code': 'GRZ1',
                'location': {
                    'city_code': 16636,
                    'city': 'Грозный',
                    'region_code': 61,
                    'region': 'Адыгея',
                    'sub_region': 'Майкопский район',
                    'country_code': 'RU',
                },
            },
            {
                'code': 'GRZ2',
                'location': {
                    'city_code': 1851908,
                    'city': 'Грозный',
                    'region_code': 61,
                    'region': 'Адыгея',
                    'sub_region': 'Майкопский район',
                    'country_code': 'RU',
                },
            },
        ]

        response = self.client.get('/checkout/api/delivery/locations/?type=cities&country=RU&region=61&q=Грозный')

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item['title'] for item in response.json()['items']], ['Грозный'])

    @override_settings(CDEK_CLIENT_ID='client', CDEK_CLIENT_SECRET='secret')
    @patch('shop.location_services.cdek_get')
    def test_city_list_filters_deprecated_pickup_locations(self, cdek_get_mock):
        cdek_get_mock.return_value = [
            {
                'code': 'ACTIVE',
                'location': {
                    'city_code': 1,
                    'city': 'Алматы',
                    'region_code': 10,
                    'region': 'Алматы',
                    'sub_region': '',
                    'country_code': 'KZ',
                },
            },
            {
                'code': 'OLD',
                'location': {
                    'city_code': 2,
                    'city': '(удален) Восточно-Казахстанская область (устарела)',
                    'region_code': 20,
                    'region': '(удален) Восточно-Казахстанская область (устарела)',
                    'sub_region': '',
                    'country_code': 'KZ',
                },
            },
        ]

        response = self.client.get('/checkout/api/delivery/locations/?type=cities&country=KZ')

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item['title'] for item in response.json()['items']], ['Алматы'])


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', DITENT_AUTH_CODE_DEBUG_RESPONSE=True)
class EmailAuthTests(TestCase):
    def test_code_request_rejects_malformed_json_without_500(self):
        response = self.client.post('/auth/api/code/request/', data='{bad', content_type='application/json')

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()['ok'])

    @patch('shop.account_views.send_mail', side_effect=RuntimeError('smtp down'))
    def test_code_request_reports_email_delivery_failure(self, send_mail_mock):
        user = get_user_model().objects.create_user(username='smtp-fail', email='smtp-fail@example.com')

        response = self.client.post(
            '/auth/api/code/request/',
            data=json.dumps({'purpose': 'login', 'email': user.email, 'agreement': True}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 502)
        self.assertFalse(response.json()['ok'])
        self.assertTrue(EmailAuthCode.objects.get(email=user.email).used_at)

    def test_registers_user_after_code_confirmation(self):
        response = self.client.post(
            '/auth/api/code/request/',
            data=json.dumps({
                'purpose': 'register',
                'email': 'new@example.com',
                'firstName': 'Ivan',
                'lastName': 'Ivanov',
                'phone': '+79990000000',
                'customerType': 'Физическое лицо',
                'agreement': True,
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        code = response.json()['debugCode']
        verify_response = self.client.post(
            '/auth/api/code/verify/',
            data=json.dumps({'purpose': 'register', 'email': 'new@example.com', 'code': code}),
            content_type='application/json',
        )

        self.assertEqual(verify_response.status_code, 200)
        self.assertEqual(verify_response.json()['user']['email'], 'new@example.com')
        user = get_user_model().objects.get(email='new@example.com')
        self.assertEqual(user.first_name, 'Ivan')
        self.assertEqual(user.last_name, 'Ivanov')
        self.assertEqual(user.customer_profile.phone, '+79990000000')
        self.assertEqual(user.customer_profile.customer_type, CustomerType.PERSON)

    def test_registration_rejects_invalid_phone(self):
        response = self.client.post(
            '/auth/api/code/request/',
            data=json.dumps({
                'purpose': 'register',
                'email': 'invalid-phone@example.com',
                'firstName': 'Ivan',
                'lastName': 'Ivanov',
                'phone': 'фывафывафыва',
                'agreement': True,
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['errors']['phone'], 'Введите корректный номер телефона.')
        self.assertFalse(EmailAuthCode.objects.filter(email='invalid-phone@example.com').exists())

    def test_registration_rejects_invalid_name_and_email(self):
        response = self.client.post(
            '/auth/api/code/request/',
            data=json.dumps({
                'purpose': 'register',
                'email': 'invalid-email',
                'firstName': 'Rustem123',
                'lastName': 'R',
                'middleName': 'Test!',
                'phone': '+79990000000',
                'agreement': True,
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['errors']['email'], 'Введите корректный e-mail.')
        self.assertEqual(response.json()['errors']['firstName'], 'Введите корректное имя.')
        self.assertEqual(response.json()['errors']['lastName'], 'Введите корректную фамилию.')
        self.assertEqual(response.json()['errors']['middleName'], 'Введите корректное отчество.')
        self.assertFalse(EmailAuthCode.objects.filter(email='invalid-email').exists())

    def test_login_existing_user_after_code_confirmation(self):
        user = get_user_model().objects.create_user(username='existing', email='existing@example.com')

        response = self.client.post(
            '/auth/api/code/request/',
            data=json.dumps({'purpose': 'login', 'email': user.email, 'agreement': True}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        verify_response = self.client.post(
            '/auth/api/code/verify/',
            data=json.dumps({'purpose': 'login', 'email': user.email, 'code': response.json()['debugCode']}),
            content_type='application/json',
        )

        self.assertEqual(verify_response.status_code, 200)
        self.assertEqual(verify_response.json()['user']['email'], user.email)

    def test_code_request_throttle_returns_retry_time(self):
        user = get_user_model().objects.create_user(username='throttle', email='throttle@example.com')
        payload = {'purpose': 'login', 'email': user.email, 'agreement': True}

        first_response = self.client.post(
            '/auth/api/code/request/',
            data=json.dumps(payload),
            content_type='application/json',
        )
        second_response = self.client.post(
            '/auth/api/code/request/',
            data=json.dumps(payload),
            content_type='application/json',
        )

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 429)
        self.assertIn('retryAfterSeconds', second_response.json())
        self.assertGreater(second_response.json()['retryAfterSeconds'], 0)

    @override_settings(DITENT_AUTH_CODE_IP_LIMIT=2, DITENT_AUTH_CODE_IP_WINDOW_SECONDS=300)
    def test_code_request_is_rate_limited_by_ip_across_emails(self):
        cache.clear()

        for index in range(3):
            get_user_model().objects.create_user(username=f'code-ip-{index}', email=f'code-ip-{index}@example.com')

        first_response = self.client.post(
            '/auth/api/code/request/',
            data=json.dumps({'purpose': 'login', 'email': 'code-ip-0@example.com', 'agreement': True}),
            content_type='application/json',
        )
        second_response = self.client.post(
            '/auth/api/code/request/',
            data=json.dumps({'purpose': 'login', 'email': 'code-ip-1@example.com', 'agreement': True}),
            content_type='application/json',
        )
        limited_response = self.client.post(
            '/auth/api/code/request/',
            data=json.dumps({'purpose': 'login', 'email': 'code-ip-2@example.com', 'agreement': True}),
            content_type='application/json',
        )

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(limited_response.status_code, 429)
        self.assertEqual(EmailAuthCode.objects.count(), 2)

    def test_rejects_wrong_code(self):
        get_user_model().objects.create_user(username='existing', email='wrong@example.com')
        self.client.post(
            '/auth/api/code/request/',
            data=json.dumps({'purpose': EmailAuthPurpose.LOGIN, 'email': 'wrong@example.com', 'agreement': True}),
            content_type='application/json',
        )

        response = self.client.post(
            '/auth/api/code/verify/',
            data=json.dumps({'purpose': 'login', 'email': 'wrong@example.com', 'code': '000000'}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(EmailAuthCode.objects.filter(email='wrong@example.com').first().attempts, 1)

    @override_settings(DITENT_LOGIN_ATTEMPT_LIMIT=2, DITENT_LOGIN_ATTEMPT_WINDOW_SECONDS=300)
    def test_password_login_is_rate_limited_after_failed_attempts(self):
        user = get_user_model().objects.create_user(username='rate-login', email='rate-login@example.com', password='password123')

        for _ in range(2):
            response = self.client.post(
                '/auth/api/login/',
                data=json.dumps({'email': user.email, 'password': 'bad-password'}),
                content_type='application/json',
            )
            self.assertEqual(response.status_code, 400)

        locked_response = self.client.post(
            '/auth/api/login/',
            data=json.dumps({'email': user.email, 'password': 'password123'}),
            content_type='application/json',
        )

        self.assertEqual(locked_response.status_code, 429)

    def test_password_reset_endpoint_sends_login_code_for_existing_user(self):
        user = get_user_model().objects.create_user(username='reset-user', email='reset-user@example.com')

        response = self.client.post(
            '/auth/api/password-reset/',
            data=json.dumps({'email': user.email}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(EmailAuthCode.objects.filter(email=user.email, purpose=EmailAuthPurpose.LOGIN, used_at__isnull=True).exists())
        self.assertEqual(len(mail.outbox), 1)

    @override_settings(DITENT_AUTH_CODE_IP_LIMIT=1, DITENT_AUTH_CODE_IP_WINDOW_SECONDS=300)
    def test_password_reset_is_rate_limited_by_ip(self):
        cache.clear()
        get_user_model().objects.create_user(username='reset-limit', email='reset-limit@example.com')

        first_response = self.client.post(
            '/auth/api/password-reset/',
            data=json.dumps({'email': 'reset-limit@example.com'}),
            content_type='application/json',
        )
        limited_response = self.client.post(
            '/auth/api/password-reset/',
            data=json.dumps({'email': 'missing-reset-limit@example.com'}),
            content_type='application/json',
        )

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(limited_response.status_code, 429)
        self.assertEqual(EmailAuthCode.objects.count(), 1)

    def test_email_lookup_is_case_insensitive(self):
        user = get_user_model().objects.create_user(username='case-user', email='case-user@example.com', password='password123')

        response = self.client.post(
            '/auth/api/login/',
            data=json.dumps({'email': 'CASE-USER@EXAMPLE.COM', 'password': 'password123'}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['user']['email'], user.email)


class CabinetProfileTests(TestCase):
    def test_auth_status_returns_profile_for_checkout_prefill(self):
        user = get_user_model().objects.create_user(
            username='prefill-user',
            email='prefill@example.com',
            first_name='Иван',
            last_name='Петров',
        )
        profile = CustomerProfile.objects.create(user=user)
        profile.middle_name = 'Иванович'
        profile.phone = '+79990000000'
        profile.customer_type = CustomerType.ENTREPRENEUR
        profile.save(update_fields=['middle_name', 'phone', 'customer_type', 'updated_at'])
        self.client.force_login(user)

        response = self.client.get('/auth/api/status/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['user']['firstName'], 'Иван')
        self.assertEqual(response.json()['user']['lastName'], 'Петров')
        self.assertEqual(response.json()['user']['middleName'], 'Иванович')
        self.assertEqual(response.json()['user']['phone'], '+79990000000')
        self.assertEqual(response.json()['user']['type'], CustomerType.ENTREPRENEUR)

    def test_updates_default_customer_type_with_profile(self):
        user = get_user_model().objects.create_user(username='cabinet-user', email='cabinet@example.com')
        self.client.force_login(user)

        response = self.client.post(
            '/cabinet/api/profile/update/',
            data=json.dumps({
                'email': 'cabinet-new@example.com',
                'firstName': 'Иван',
                'lastName': 'Петров',
                'middleName': '',
                'phone': '+79990000000',
                'type': CustomerType.COMPANY,
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        user.refresh_from_db()
        self.assertEqual(user.email, 'cabinet-new@example.com')
        self.assertEqual(user.customer_profile.customer_type, CustomerType.COMPANY)
        self.assertEqual(response.json()['profile']['type'], CustomerType.COMPANY)

    def test_profile_update_rejects_invalid_fields(self):
        user = get_user_model().objects.create_user(username='invalid-profile', email='invalid-profile@example.com')
        self.client.force_login(user)

        response = self.client.post(
            '/cabinet/api/profile/update/',
            data=json.dumps({
                'email': 'bad-email',
                'firstName': 'Иван1',
                'lastName': 'Петров',
                'phone': '+79990000000',
                'type': CustomerType.PERSON,
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], 'Введите корректный e-mail.')

    def test_cabinet_orders_returns_real_orders_for_current_user(self):
        User = get_user_model()
        user = User.objects.create_user(username='orders-user', email='orders@example.com')
        other_user = User.objects.create_user(username='other-orders-user', email='other-orders@example.com')
        order = Order.objects.create(
            number='ORD-100',
            user=user,
            customer_name='Иван Петров',
            phone='+79990000000',
            email='orders@example.com',
            delivery_method='manager',
            items_total=Decimal('500.00'),
            total=Decimal('500.00'),
            return_terms_accepted=True,
        )
        payable_order = Order.objects.create(
            number='ORD-PAYABLE',
            user=user,
            status=OrderStatus.WAITING_PAYMENT,
            payment_status=PaymentStatus.WAITING_PAYMENT,
            customer_name='Payable Client',
            phone='+79990000000',
            email='orders@example.com',
            delivery_method='manager',
            payment_form_url='https://bank.example/pay-order',
            payment_ready_at=timezone.now(),
            items_total=Decimal('900.00'),
            total=Decimal('900.00'),
            return_terms_accepted=True,
        )
        OrderItem.objects.create(
            order=order,
            title='Тестовый товар',
            sku='SKU-100',
            quantity=1,
            unit_price=Decimal('500.00'),
            total_price=Decimal('500.00'),
        )
        OrderItem.objects.create(
            order=payable_order,
            title='Payable product',
            sku='SKU-PAYABLE',
            quantity=1,
            unit_price=Decimal('900.00'),
            total_price=Decimal('900.00'),
        )
        Order.objects.create(
            number='ORD-OTHER',
            user=other_user,
            customer_name='Другой клиент',
            phone='+79990000001',
            email='other-orders@example.com',
            total=Decimal('100.00'),
        )
        drawing_order = DrawingOrder.objects.create(
            user=user,
            customer_name='Иван Петров',
            phone='+79990000000',
            email='orders@example.com',
            comment='Нужен расчет по чертежу',
            return_terms_accepted=True,
        )
        DrawingOrder.objects.create(
            user=other_user,
            customer_name='Другой клиент',
            phone='+79990000001',
            email='other-orders@example.com',
            comment='Чужая заявка',
            return_terms_accepted=True,
        )
        self.client.force_login(user)

        response = self.client.get('/cabinet/api/orders/')

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        order_ids = [item['id'] for item in payload['orders']]
        self.assertIn('ORD-100', order_ids)
        self.assertIn('ORD-PAYABLE', order_ids)
        self.assertIn(f'DR-{drawing_order.pk:06d}', order_ids)
        self.assertNotIn('ORD-OTHER', order_ids)

        catalog_payload = next(item for item in payload['orders'] if item['id'] == 'ORD-100')
        payable_payload = next(item for item in payload['orders'] if item['id'] == 'ORD-PAYABLE')
        self.assertTrue(payable_payload['canPay'])
        self.assertEqual(payable_payload['paymentUrl'], 'https://bank.example/pay-order')
        drawing_payload = next(item for item in payload['orders'] if item['id'] == f'DR-{drawing_order.pk:06d}')
        self.assertEqual(catalog_payload['items'][0]['title'], 'Тестовый товар')
        self.assertEqual(drawing_payload['type'], 'drawing-order')
        self.assertFalse(drawing_payload['canRepeat'])
        self.assertFalse(drawing_payload['canPay'])
        self.assertEqual(drawing_payload['summary']['totalTitle'], 'После расчета')
        self.assertEqual(drawing_payload['items'][0]['comments'], 'Нужен расчет по чертежу')


    def test_repeat_order_reports_when_all_items_are_unavailable(self):
        User = get_user_model()
        user = User.objects.create_user(username='repeat-unavailable', email='repeat-unavailable@example.com')
        category = Category.objects.create(title='Repeat category', slug='repeat-category', status=PublishStatus.ACTIVE)
        product = Product.objects.create(
            category=category,
            title='Repeat unavailable product',
            sku='REPEAT-UNAVAILABLE-1',
            price=Decimal('500.00'),
            stock=0,
            status=PublishStatus.ARCHIVED,
        )
        current_product = Product.objects.create(
            category=category,
            title='Current cart product',
            sku='CURRENT-CART-1',
            price=Decimal('900.00'),
            stock=2,
            status=PublishStatus.ACTIVE,
        )
        order = Order.objects.create(
            number='ORD-REPEAT-UNAVAILABLE',
            user=user,
            customer_name='Repeat User',
            phone='+79990000000',
            email=user.email,
            total=Decimal('500.00'),
        )
        OrderItem.objects.create(
            order=order,
            product=product,
            title=product.title,
            sku=product.sku,
            quantity=1,
            unit_price=Decimal('500.00'),
            total_price=Decimal('500.00'),
        )
        self.client.force_login(user)
        self.client.post(
            '/cart/api/items/',
            data=json.dumps({'type': 'catalog-product', 'sku': current_product.sku, 'quantity': 1}),
            content_type='application/json',
        )

        response = self.client.post(f'/cabinet/api/orders/{order.number}/repeat/')

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()['ok'])
        self.assertEqual(CartItem.objects.count(), 1)
        self.assertEqual(CartItem.objects.get().data['sku'], current_product.sku)

    def test_repeat_order_recalculates_current_catalog_price(self):
        User = get_user_model()
        user = User.objects.create_user(username='repeat-current-price', email='repeat-current-price@example.com')
        category = Category.objects.create(title='Repeat price category', slug='repeat-price-category', status=PublishStatus.ACTIVE)
        product = Product.objects.create(
            category=category,
            title='Repeat current price product',
            sku='REPEAT-PRICE-1',
            price=Decimal('700.00'),
            stock=3,
            status=PublishStatus.ACTIVE,
        )
        order = Order.objects.create(
            number='ORD-REPEAT-PRICE',
            user=user,
            customer_name='Repeat Price User',
            phone='+79990000000',
            email=user.email,
            total=Decimal('500.00'),
        )
        OrderItem.objects.create(
            order=order,
            product=product,
            title=product.title,
            sku=product.sku,
            quantity=1,
            unit_price=Decimal('500.00'),
            total_price=Decimal('500.00'),
        )
        self.client.force_login(user)

        response = self.client.post(f'/cabinet/api/orders/{order.number}/repeat/')

        self.assertEqual(response.status_code, 200)
        item = response.json()['cart']['items'][0]
        self.assertEqual(item['sku'], product.sku)
        self.assertEqual(item['unitPrice'], 700.0)
        self.assertEqual(response.json()['skippedCount'], 0)


class DrawingOrderTests(TestCase):
    def test_drawing_order_requires_auth(self):
        response = self.client.post('/api/drawing-orders/')

        self.assertEqual(response.status_code, 401)

    @override_settings(
        DITENT_MAX_UPLOAD_SIZE=20 * 1024 * 1024,
        DITENT_MAX_UPLOAD_COUNT=10,
        DITENT_ALLOWED_UPLOAD_TYPES=['application/pdf'],
        DITENT_ALLOWED_UPLOAD_EXTENSIONS=['.pdf'],
    )
    def test_creates_drawing_order_with_file(self):
        User = get_user_model()
        user = User.objects.create_user(username='drawing-client', email='drawing@example.com', password='password123')
        self.client.force_login(user)

        response = self.client.post(
            '/api/drawing-orders/',
            data={
                'clientName': 'Client',
                'phone': '+79990000000',
                'email': 'drawing@example.com',
                'agreement': 'on',
                'itemName': 'Table',
                'dimensions': '100 x 80 x 60',
                'drawing': SimpleUploadedFile('drawing.pdf', b'%PDF-1.4', content_type='application/pdf'),
            },
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(DrawingOrder.objects.filter(user=user).count(), 1)

    @override_settings(
        DITENT_MAX_UPLOAD_SIZE=20 * 1024 * 1024,
        DITENT_MAX_UPLOAD_COUNT=10,
        DITENT_ALLOWED_UPLOAD_TYPES=['application/pdf'],
        DITENT_ALLOWED_UPLOAD_EXTENSIONS=['.pdf'],
    )
    def test_rejects_invalid_drawing_order_phone(self):
        User = get_user_model()
        user = User.objects.create_user(username='drawing-invalid-phone', email='drawing-invalid@example.com')
        self.client.force_login(user)

        response = self.client.post(
            '/api/drawing-orders/',
            data={
                'clientName': 'Client',
                'phone': 'телефон!!!',
                'email': 'drawing-invalid@example.com',
                'agreement': 'on',
                'drawing': SimpleUploadedFile('drawing.pdf', b'%PDF-1.4', content_type='application/pdf'),
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['errors']['phone'], 'Введите корректный номер телефона.')
        self.assertFalse(DrawingOrder.objects.filter(user=user).exists())

    @override_settings(
        DITENT_MAX_UPLOAD_SIZE=20 * 1024 * 1024,
        DITENT_MAX_UPLOAD_COUNT=10,
        DITENT_ALLOWED_UPLOAD_TYPES=['application/pdf'],
        DITENT_ALLOWED_UPLOAD_EXTENSIONS=['.pdf'],
    )
    def test_rejects_invalid_drawing_order_text_fields(self):
        User = get_user_model()
        user = User.objects.create_user(username='drawing-invalid-fields', email='drawing-fields@example.com')
        self.client.force_login(user)

        response = self.client.post(
            '/api/drawing-orders/',
            data={
                'clientName': '!!!',
                'phone': '+79990000000',
                'email': 'drawing-fields@example.com',
                'agreement': 'on',
                'itemName': '@@@',
                'dimensions': '!!!',
                'comment': 'x' * 2001,
                'drawing': SimpleUploadedFile('drawing.pdf', b'%PDF-1.4', content_type='application/pdf'),
            },
        )

        self.assertEqual(response.status_code, 400)
        errors = response.json()['errors']
        self.assertIn('clientName', errors)
        self.assertIn('itemName', errors)
        self.assertIn('dimensions', errors)
        self.assertIn('comment', errors)
        self.assertFalse(DrawingOrder.objects.filter(user=user).exists())


class ProductionSystemCheckTests(TestCase):
    def run_production_checks(self):
        from .checks import production_external_service_checks

        return production_external_service_checks(None)

    @override_settings(DEBUG=True)
    def test_external_service_checks_are_silent_in_development(self):
        self.assertEqual(self.run_production_checks(), [])

    @override_settings(
        DEBUG=False,
        CDEK_CLIENT_ID='',
        CDEK_CLIENT_SECRET='',
        ALFA_ACQUIRING_USERNAME='',
        ALFA_ACQUIRING_PASSWORD='',
        ALFA_ACQUIRING_CALLBACK_TOKEN='',
        ALFA_ACQUIRING_BASE_URL='https://alfa.rbsuat.com/payment/rest',
        EMAIL_BACKEND='django.core.mail.backends.console.EmailBackend',
        DEFAULT_FROM_EMAIL='no-reply@ditent.local',
        DITENT_AUTH_CODE_DEBUG_RESPONSE=True,
    )
    def test_external_service_checks_block_missing_production_integrations(self):
        messages = self.run_production_checks()
        ids = {message.id for message in messages}

        self.assertTrue({'shop.E001', 'shop.E002', 'shop.E003', 'shop.E004', 'shop.E005'}.issubset(ids))
        self.assertIn('shop.E010', ids)
        self.assertIn('shop.E012', ids)
        self.assertIn('shop.E020', ids)
        self.assertIn('shop.E030', ids)
        self.assertIn('shop.E040', ids)
        self.assertIn('shop.E050', ids)

    @override_settings(
        DEBUG=False,
        CDEK_CLIENT_ID='client-id-7f4a9b2c',
        CDEK_CLIENT_SECRET='secret-8a7f6e5d',
        ALFA_ACQUIRING_USERNAME='merchant-user-42',
        ALFA_ACQUIRING_PASSWORD='merchant-password-42',
        ALFA_ACQUIRING_CALLBACK_TOKEN='callback-token',
        ALFA_ACQUIRING_BASE_URL='https://securepay.company.ru/payment/rest',
        EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend',
        EMAIL_HOST='smtp.company.ru',
        DEFAULT_FROM_EMAIL='no-reply@company.ru',
        DITENT_MANAGER_EMAILS=['manager@company.ru'],
        DITENT_AUTH_CODE_DEBUG_RESPONSE=False,
        DITENT_EMAIL_NOTIFICATIONS_ENABLED=True,
        DATABASES={
            'default': {
                'ENGINE': 'django.db.backends.postgresql',
                'NAME': 'ditent',
                'USER': 'ditent',
                'PASSWORD': 'password',
                'HOST': '127.0.0.1',
                'PORT': '5432',
            }
        },
        CACHES={
            'default': {
                'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
                'LOCATION': 'E:/work/DiTent_repo/.test-cache',
            }
        },
    )
    def test_external_service_checks_accept_complete_production_settings(self):
        self.assertEqual(self.run_production_checks(), [])

    @override_settings(
        DEBUG=False,
        CDEK_CLIENT_ID='client-id-7f4a9b2c',
        CDEK_CLIENT_SECRET='secret-8a7f6e5d',
        ALFA_ACQUIRING_USERNAME='merchant-user-42',
        ALFA_ACQUIRING_PASSWORD='merchant-password-42',
        ALFA_ACQUIRING_CALLBACK_TOKEN='callback-token',
        ALFA_ACQUIRING_BASE_URL='https://payment.example.com/payment/rest',
        EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend',
        EMAIL_HOST='smtp.example.com',
        DEFAULT_FROM_EMAIL='no-reply@example.com',
        DITENT_MANAGER_EMAILS=['manager@example.com'],
        DITENT_AUTH_CODE_DEBUG_RESPONSE=False,
        DATABASES={
            'default': {
                'ENGINE': 'django.db.backends.postgresql',
                'NAME': 'ditent',
                'USER': 'ditent',
                'PASSWORD': 'password',
                'HOST': '127.0.0.1',
                'PORT': '5432',
            }
        },
        CACHES={
            'default': {
                'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
                'LOCATION': 'E:/work/DiTent_repo/.test-cache',
            }
        },
    )
    def test_external_service_checks_reject_placeholder_production_settings(self):
        ids = {message.id for message in self.run_production_checks()}

        self.assertIn('shop.E014', ids)
        self.assertIn('shop.E012', ids)
        self.assertIn('shop.E021', ids)
        self.assertIn('shop.E027', ids)


@override_settings(
    DEBUG=False,
    CDEK_CLIENT_ID='client-id-7f4a9b2c',
    CDEK_CLIENT_SECRET='secret-8a7f6e5d',
    ALFA_ACQUIRING_USERNAME='merchant-user-42',
    ALFA_ACQUIRING_PASSWORD='merchant-password-42',
    ALFA_ACQUIRING_CALLBACK_TOKEN='callback-token-42',
    ALFA_ACQUIRING_BASE_URL='https://securepay.company.ru/payment/rest',
    EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend',
    EMAIL_HOST='smtp.company.ru',
    DEFAULT_FROM_EMAIL='no-reply@company.ru',
    DITENT_MANAGER_EMAILS=['manager@company.ru'],
    DITENT_AUTH_CODE_DEBUG_RESPONSE=False,
    DATABASES={
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': 'ditent',
            'USER': 'ditent',
            'PASSWORD': 'password',
            'HOST': '127.0.0.1',
            'PORT': '5432',
        }
    },
    CACHES={
        'default': {
            'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
            'LOCATION': 'E:/work/DiTent_repo/.test-cache',
        }
    },
)
class ProductionSmokeCommandTests(TestCase):
    @patch('shop.management.commands.production_smoke.get_payment_status')
    @patch('shop.management.commands.production_smoke.cdek_get')
    @patch('shop.management.commands.production_smoke.send_mail')
    def test_production_smoke_checks_external_integrations(self, send_mail_mock, cdek_get_mock, get_payment_status_mock):
        send_mail_mock.return_value = 1
        cdek_get_mock.return_value = [{'code': 'PVZ1'}]
        get_payment_status_mock.return_value = {'orderStatus': 2}
        out = StringIO()

        call_command(
            'production_smoke',
            '--email-to=manager@company.ru',
            '--cdek-city-code=44',
            '--alfa-order-id=bank-order-1',
            stdout=out,
        )

        output = out.getvalue()
        self.assertIn('Production smoke checks passed', output)
        send_mail_mock.assert_called_once()
        cdek_get_mock.assert_called_once_with('/v2/deliverypoints', {
            'city_code': '44',
            'type': 'PVZ',
            'is_handout': 'true',
            'size': 1,
        })
        get_payment_status_mock.assert_called_once_with('bank-order-1')

    @patch('shop.management.commands.production_smoke.cdek_get', return_value=[{'code': 'PVZ1'}])
    @patch('shop.management.commands.production_smoke.send_mail', return_value=1)
    def test_production_smoke_warns_when_alfa_order_id_is_not_passed(self, send_mail_mock, cdek_get_mock):
        out = StringIO()

        call_command('production_smoke', '--email-to=manager@company.ru', stdout=out)

        self.assertIn('Alfa status check skipped', out.getvalue())
        self.assertIn('Production smoke checks passed', out.getvalue())

    @patch('shop.management.commands.production_smoke.cdek_get', return_value=[{'code': 'PVZ1'}])
    @patch('shop.management.commands.production_smoke.send_mail', side_effect=RuntimeError('smtp down'))
    def test_production_smoke_fails_when_smtp_fails(self, send_mail_mock, cdek_get_mock):
        with self.assertRaises(CommandError):
            call_command('production_smoke', '--email-to=manager@company.ru', '--skip-alfa')


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    DITENT_MANAGER_EMAILS=['manager@example.com'],
    DITENT_EMAIL_NOTIFICATIONS_ENABLED=True,
)
class EmailNotificationTests(TestCase):
    def test_manager_emails_from_admin_settings_have_priority(self):
        settings = SiteSettings.load()
        settings.manager_emails = 'admin-manager@example.com\nsales@example.com'
        settings.save(update_fields=['manager_emails', 'updated_at'])

        from .notifications import manager_recipients

        self.assertEqual(manager_recipients(), ['admin-manager@example.com', 'sales@example.com'])

    def test_checkout_order_sends_manager_and_client_emails(self):
        User = get_user_model()
        user = User.objects.create_user(username='notify-client', email='notify-client@example.com', password='password123')
        self.client.force_login(user)
        category = Category.objects.create(title='Notify category', slug='notify-category', status=PublishStatus.ACTIVE)
        product = Product.objects.create(
            category=category,
            title='Notify product',
            sku='NOTIFY-PRODUCT-1',
            price=Decimal('1000.00'),
            stock=3,
            status=PublishStatus.ACTIVE,
        )
        self.client.post(
            '/cart/api/items/',
            data=json.dumps({'type': 'catalog-product', 'sku': product.sku, 'quantity': 1}),
            content_type='application/json',
        )

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                '/checkout/api/orders/',
                data=json.dumps({
                    'returnTermsAccepted': True,
                    'client': {
                        'firstName': 'Notify',
                        'lastName': 'Client',
                        'phone': '+79990000000',
                        'email': 'notify-client@example.com',
                    },
                    'delivery': {'type': 'manager'},
                    'payment': {'type': 'invoice'},
                }),
                content_type='application/json',
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(mail.outbox[0].to, ['manager@example.com'])
        self.assertIn('Новый заказ', mail.outbox[0].subject)
        self.assertEqual(mail.outbox[1].to, ['notify-client@example.com'])
        self.assertIn('принят', mail.outbox[1].subject)

    @override_settings(
        DITENT_MAX_UPLOAD_SIZE=20 * 1024 * 1024,
        DITENT_MAX_UPLOAD_COUNT=10,
        DITENT_ALLOWED_UPLOAD_TYPES=['application/pdf'],
        DITENT_ALLOWED_UPLOAD_EXTENSIONS=['.pdf'],
    )
    def test_drawing_order_sends_manager_and_client_emails(self):
        User = get_user_model()
        user = User.objects.create_user(username='notify-drawing', email='notify-drawing@example.com', password='password123')
        self.client.force_login(user)

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                '/api/drawing-orders/',
                data={
                    'clientName': 'Drawing Client',
                    'phone': '+79990000000',
                    'email': 'notify-drawing@example.com',
                    'agreement': 'on',
                    'itemName': 'Cover',
                    'dimensions': '100 x 80 x 60',
                    'drawing': SimpleUploadedFile('drawing.pdf', b'%PDF-1.4', content_type='application/pdf'),
                },
            )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(mail.outbox[0].to, ['manager@example.com'])
        self.assertIn('Новая заявка по чертежу', mail.outbox[0].subject)
        self.assertEqual(mail.outbox[1].to, ['notify-drawing@example.com'])
        self.assertIn('Заявка по чертежу', mail.outbox[1].subject)
