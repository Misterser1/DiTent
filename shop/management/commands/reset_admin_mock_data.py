from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files import File
from django.core.management.base import BaseCommand
from django.db import transaction

from shop.models import (
    Accessory,
    Cart,
    CartItem,
    Category,
    Color,
    ConstructorAttachment,
    ConstructorGalleryImage,
    CoverShape,
    CustomerType,
    DrawingOrder,
    DrawingOrderFile,
    Fabric,
    Fastener,
    Formula,
    GalleryItem,
    Order,
    OrderItem,
    OrderItemFile,
    OrderItemType,
    OrderStatus,
    PaymentMethod,
    PaymentStatus,
    Product,
    ProductImage,
    PublishStatus,
    Review,
    SiteSettings,
)


class Command(BaseCommand):
    help = 'Clears custom admin data and creates 10 mock records in every admin section.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--yes-i-understand-this-deletes-orders',
            action='store_true',
            help='Required confirmation for destructive local mock reset.',
        )

    image_pool = [
        'catalog-img-1.png',
        'catalog-img-2.png',
        'catalog-img-3.png',
        'catalog-img-4.png',
        'card-img-1.png',
        'item-img-1.png',
        'item-img-2.png',
        'item-img-3.png',
        'item-img-4.png',
        'review-img.png',
    ]

    material_pool = [
        'material-img-1.png',
        'material-img-2.png',
        'material-img-3.png',
        'material-img-4.png',
        'material-img-5.png',
        'material-img-6.png',
    ]

    def asset_path(self, filename):
        return Path(settings.BASE_DIR) / 'assets' / 'image' / filename

    def attach_asset(self, instance, field_name, filename):
        path = self.asset_path(filename)

        if not path.exists():
            return

        field = getattr(instance, field_name)
        target_name = f'mock/{instance.__class__.__name__.lower()}/{instance.pk or "new"}-{filename}'

        with path.open('rb') as source:
            field.save(target_name, File(source), save=False)

    def clear_data(self):
        delete_order = [
            OrderItemFile,
            ProductImage,
            OrderItem,
            CartItem,
            Cart,
            ConstructorAttachment,
            DrawingOrderFile,
            DrawingOrder,
            Order,
            Product,
            Color,
            Fastener,
            Accessory,
            Fabric,
            Formula,
            ConstructorGalleryImage,
            GalleryItem,
            Review,
        ]

        for model in delete_order:
            model.objects.all().delete()

        Category.objects.filter(parent__isnull=False).delete()
        Category.objects.filter(parent__isnull=True).delete()

    def create_categories(self):
        roots_data = [
            ('Чехлы для садовой мебели', 'garden-furniture-covers'),
            ('Чехлы для оборудования', 'equipment-covers'),
            ('Чехлы для техники', 'technic-covers'),
            ('Чехлы для HoReCa', 'horeca-covers'),
            ('Специализированные чехлы', 'special-covers'),
        ]
        children_data = [
            ('Чехлы для столов', 'table-covers', 0),
            ('Чехлы для диванов', 'sofa-covers', 0),
            ('Чехлы для генераторов', 'generator-covers', 1),
            ('Чехлы для станков', 'machine-covers', 1),
            ('Чехлы по индивидуальному чертежу', 'custom-drawing-covers', 4),
        ]

        roots = []
        for index, (title, slug) in enumerate(roots_data, start=1):
            category = Category.objects.create(
                title=title,
                slug=slug,
                position=index,
                status=PublishStatus.ACTIVE if index < 5 else PublishStatus.DRAFT,
            )
            self.attach_asset(category, 'image', self.image_pool[(index - 1) % len(self.image_pool)])
            category.save()
            roots.append(category)

        children = []
        for index, (title, slug, root_index) in enumerate(children_data, start=1):
            category = Category.objects.create(
                title=title,
                slug=slug,
                parent=roots[root_index],
                position=index,
                status=PublishStatus.ACTIVE,
            )
            self.attach_asset(category, 'image', self.image_pool[(index + 4) % len(self.image_pool)])
            category.save()
            children.append(category)

        return roots + children, children

    def create_fabrics(self):
        fabrics = []
        property_types = [
            'Водонепроницаемая',
            'Износостойкая',
            'Морозостойкая',
            'Легкая',
            'Плотная',
        ]

        for index in range(1, 11):
            fabric = Fabric.objects.create(
                title=f'Ткань Mock {index}',
                price_per_square_meter=Decimal(350 + index * 75),
                density=f'{360 + index * 20} г/м²',
                roll_width_cm=140 + index,
                property_type=property_types[(index - 1) % len(property_types)],
                uv_resistance=(index % 5) + 1,
                durability=((index + 1) % 5) + 1,
                strength=((index + 2) % 5) + 1,
                care=((index + 3) % 5) + 1,
                purpose='Улица, навесы, сезонное хранение и защита от влаги.',
                description='Моковая ткань для проверки калькулятора, карточек и админки.',
                status=PublishStatus.ACTIVE if index <= 8 else PublishStatus.ARCHIVED,
            )
            fabrics.append(fabric)

        return fabrics

    def create_colors(self, fabrics):
        colors = []
        titles = ['Серый', 'Графит', 'Светло-серый', 'Темно-серый', 'Бежевый', 'Черный', 'Синий', 'Зеленый', 'Коричневый', 'Белый']

        for index, title in enumerate(titles, start=1):
            color = Color.objects.create(
                title=f'{title} Mock',
                fabric=fabrics[(index - 1) % len(fabrics)],
                status=PublishStatus.ACTIVE if index <= 8 else PublishStatus.ARCHIVED,
            )
            self.attach_asset(color, 'image', self.material_pool[(index - 1) % len(self.material_pool)])
            color.save()
            colors.append(color)

        return colors

    def create_fasteners(self):
        fasteners = []
        titles = [
            'Ремни на углах внутри',
            'Утяжка по нижнему краю',
            'Липучки по периметру',
            'Фастекс с ременной лентой',
            'Шнур с фиксатором',
            'Люверсы по нижнему краю',
            'Молния сервисного доступа',
            'Клапан вентиляции',
            'Карабины для фиксации',
            'Комбинированное крепление',
        ]

        for index, title in enumerate(titles, start=1):
            fastener = Fastener.objects.create(
                title=title,
                price=Decimal(index * 120),
                compatibility='Совместимо с прямоугольными, овальными и индивидуальными чехлами.',
                status=PublishStatus.ACTIVE if index <= 8 else PublishStatus.ARCHIVED,
            )
            self.attach_asset(fastener, 'image', 'filter-img.png')
            fastener.save()
            fasteners.append(fastener)

        return fasteners

    def create_accessories(self):
        accessories = []
        titles = [
            'Сумка для хранения',
            'Бирка с маркировкой',
            'Комплект ремней',
            'Ремкомплект ткани',
            'Дополнительная вентиляция',
            'Усиление углов',
            'Мягкая прокладка',
            'Чехол для хранения',
            'Паспорт изделия',
            'Экспресс-упаковка',
        ]

        for index, title in enumerate(titles, start=1):
            accessories.append(Accessory.objects.create(
                title=title,
                code=f'mock-accessory-{index}',
                price=Decimal(index * 90),
                status=PublishStatus.ACTIVE if index <= 8 else PublishStatus.ARCHIVED,
            ))

        return accessories

    def create_formulas(self):
        shapes = [
            CoverShape.RECTANGULAR,
            CoverShape.ROUND,
            CoverShape.WEDGE,
            CoverShape.OVAL,
            CoverShape.L_SHAPED,
            CoverShape.U_SHAPED,
        ]
        formulas = []

        for index in range(1, 11):
            shape = shapes[(index - 1) % len(shapes)]
            formulas.append(Formula.objects.create(
                title=f'Формула Mock {index}',
                shape=shape,
                code=f'mock_formula_{index}',
                coefficient=Decimal('0.900') + Decimal(index) / Decimal('100'),
                minimum_price=Decimal('1000.00') + Decimal(index * 50),
                seam_price_cm=Decimal(index),
                topstitch_price_cm=Decimal(index) / Decimal('2'),
                edging_price_cm=Decimal(index) / Decimal('3'),
                min_size_cm=10,
                max_size_cm=500,
                expression='(Smat * Rmat + seams_total + fastener_total + accessories_total) * K',
                parameters={'source': 'mock', 'index': index},
                status=PublishStatus.ACTIVE if index <= 8 else PublishStatus.DRAFT,
            ))

        return formulas

    def create_products(self, categories, fabrics, colors, fasteners):
        products = []
        titles = [
            'Чехол для прямоугольного стола',
            'Чехол для круглого стола',
            'Чехол для садового дивана',
            'Чехол для генератора',
            'Чехол для станка',
            'Чехол для гриля',
            'Чехол для кресла',
            'Чехол для комплекта мебели',
            'Чехол для оборудования',
            'Чехол по готовому размеру',
        ]

        for index, title in enumerate(titles, start=1):
            fabric = fabrics[(index - 1) % len(fabrics)]
            color = next((item for item in colors if item.fabric_id == fabric.id), colors[0])
            product = Product.objects.create(
                title=f'{title} Mock {index}',
                category=categories[(index - 1) % len(categories)],
                sku=f'DT-MOCK-{index:03d}',
                price=Decimal(1200 + index * 350),
                width_cm=80 + index * 10,
                depth_cm=60 + index * 8,
                height_cm=50 + index * 5,
                fabric=fabric,
                color=color,
                fastener=fasteners[(index - 1) % len(fasteners)],
                purpose='Защита изделия от осадков, пыли и сезонного хранения.',
                description='Готовая моковая карточка товара для проверки каталога и корзины.',
                stock=3 + index,
                status=PublishStatus.ACTIVE if index <= 8 else PublishStatus.ARCHIVED,
            )
            self.attach_asset(product, 'main_image', self.image_pool[(index + 3) % len(self.image_pool)])
            product.save()

            for position in range(1, 4):
                image = ProductImage.objects.create(product=product, position=position)
                self.attach_asset(image, 'image', self.image_pool[(index + position) % len(self.image_pool)])
                image.save()

            products.append(product)

        return products

    def create_orders(self, products):
        User = get_user_model()
        users = []

        for index in range(1, 11):
            user, _ = User.objects.get_or_create(
                username=f'mock-client-{index}',
                defaults={
                    'email': f'mock-client-{index}@example.com',
                    'first_name': f'Клиент {index}',
                    'last_name': 'Mock',
                },
            )
            users.append(user)

            product = products[(index - 1) % len(products)]
            quantity = (index % 3) + 1
            item_total = product.price * quantity
            delivery_total = Decimal(300 + index * 25)
            order = Order.objects.create(
                number=f'DT-MOCK-{index:06d}',
                user=user,
                status=list(OrderStatus.values)[(index - 1) % len(OrderStatus.values)],
                payment_status=list(PaymentStatus.values)[(index - 1) % len(PaymentStatus.values)],
                customer_type=list(CustomerType.values)[(index - 1) % len(CustomerType.values)],
                customer_name=f'Mock Клиент {index}',
                phone=f'+790000000{index:02d}',
                email=user.email,
                delivery_method='СДЭК до пункта выдачи',
                delivery_city='Москва',
                delivery_address=f'Пункт выдачи Mock {index}',
                track_number=f'TRACK-MOCK-{index:03d}' if index % 2 == 0 else '',
                payment_method=list(PaymentMethod.values)[(index - 1) % len(PaymentMethod.values)],
                items_total=item_total,
                delivery_total=delivery_total,
                vat_total=(item_total + delivery_total) * Decimal('0.20') / Decimal('1.20'),
                total=item_total + delivery_total,
                client_comment=f'Комментарий клиента mock {index}',
                manager_comment=f'Комментарий менеджера mock {index}',
                return_terms_accepted=True,
            )
            OrderItem.objects.create(
                order=order,
                product=product,
                item_type=OrderItemType.CATALOG,
                title=product.title,
                sku=product.sku,
                quantity=quantity,
                unit_price=product.price,
                total_price=item_total,
                parameters={
                    'dimensions': [
                        {'label': 'Ширина', 'code': 'A', 'value': product.width_cm},
                        {'label': 'Глубина', 'code': 'B', 'value': product.depth_cm},
                        {'label': 'Высота', 'code': 'H', 'value': product.height_cm},
                    ],
                    'fabric': {'title': product.fabric.title if product.fabric else ''},
                    'color': {'title': product.color.title if product.color else ''},
                    'fastener': {'title': product.fastener.title if product.fastener else ''},
                    'comments': 'Моковая позиция заказа.',
                },
            )

        return users

    def create_drawing_orders(self, users):
        for index in range(1, 11):
            order = DrawingOrder.objects.create(
                user=users[(index - 1) % len(users)],
                status=list(OrderStatus.values)[(index - 1) % len(OrderStatus.values)],
                customer_name=f'Заявка Mock {index}',
                phone=f'+791100000{index:02d}',
                email=f'drawing-{index}@example.com',
                comment=f'Нужен расчет по чертежу, изделие mock {index}.',
                manager_comment=f'Уточнить размеры и материал mock {index}.',
                return_terms_accepted=True,
            )
            file_item = DrawingOrderFile.objects.create(drawing_order=order, original_name=f'drawing-mock-{index}.png')
            self.attach_asset(file_item, 'file', self.image_pool[index % len(self.image_pool)])
            file_item.save()

    def create_content(self):
        for index in range(1, 11):
            item = ConstructorGalleryImage.objects.create(
                title=f'Изображение конструктора Mock {index}',
                position=index,
                status=PublishStatus.ACTIVE if index <= 8 else PublishStatus.DRAFT,
            )
            self.attach_asset(item, 'image', self.image_pool[(index + 1) % len(self.image_pool)])
            item.save()

            review = Review.objects.create(
                title=f'Все понравилось! Mock {index}',
                author_name=f'Клиент Mock {index}',
                text=f'Отзыв mock {index}: аккуратная работа, понятный расчет и удобное оформление заказа.',
                rating=(index % 5) + 1,
                location='г. Москва' if index % 2 else 'г. Санкт-Петербург',
                image_caption='Индивидуальные защитные чехлы для сада',
                status=PublishStatus.ACTIVE if index <= 8 else PublishStatus.DRAFT,
            )
            self.attach_asset(review, 'image', self.image_pool[(index + 2) % len(self.image_pool)])
            review.save()

    def update_site_settings(self):
        settings_obj = SiteSettings.load()
        settings_obj.company_name = 'ООО "DiTent Mock"'
        settings_obj.inn = '7700000000'
        settings_obj.kpp = '770001001'
        settings_obj.ogrn = '1247700000000'
        settings_obj.registration_date = '30.05.2026'
        settings_obj.director = 'Иванов Иван Иванович'
        settings_obj.phone = '+7 (900) 000-00-00'
        settings_obj.phone_href = '+79000000000'
        settings_obj.email = 'mock@ditent.local'
        settings_obj.address = 'г. Москва, ул. Тестовая, 10'
        settings_obj.whatsapp_url = 'https://wa.me/79000000000'
        settings_obj.telegram_url = 'https://t.me/ditent_mock'
        settings_obj.vk_url = 'https://vk.com/ditent_mock'
        self.attach_asset(settings_obj, 'map_image', 'map.png')
        settings_obj.save()

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.DEBUG:
            self.stderr.write(self.style.ERROR('Refusing to reset admin mock data when DEBUG=False.'))
            return

        if not options.get('yes_i_understand_this_deletes_orders'):
            self.stderr.write(self.style.ERROR(
                'This command deletes orders and admin content. Re-run with '
                '--yes-i-understand-this-deletes-orders in a local DEBUG environment.'
            ))
            return

        self.clear_data()
        _, product_categories = self.create_categories()
        fabrics = self.create_fabrics()
        colors = self.create_colors(fabrics)
        fasteners = self.create_fasteners()
        self.create_accessories()
        self.create_formulas()
        products = self.create_products(product_categories, fabrics, colors, fasteners)
        users = self.create_orders(products)
        self.create_drawing_orders(users)
        self.create_content()
        self.update_site_settings()

        self.stdout.write(self.style.SUCCESS('Custom admin data was reset and filled with mock records.'))
