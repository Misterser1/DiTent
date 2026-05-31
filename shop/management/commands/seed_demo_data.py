from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from shop.models import (
    Accessory,
    Category,
    Color,
    Fabric,
    Fastener,
    Formula,
    Order,
    Product,
    PublishStatus,
)


class Command(BaseCommand):
    help = 'Creates initial demo data for the custom admin.'

    def handle(self, *args, **options):
        garden, _ = Category.objects.get_or_create(
            slug='garden-furniture-covers',
            defaults={'title': 'Чехлы для садовой мебели', 'position': 1, 'status': PublishStatus.ACTIVE},
        )
        equipment, _ = Category.objects.get_or_create(
            slug='equipment-covers',
            defaults={'title': 'Чехлы для оборудования', 'position': 2, 'status': PublishStatus.ACTIVE},
        )
        special, _ = Category.objects.get_or_create(
            slug='special-covers',
            defaults={'title': 'Специализированные чехлы', 'position': 3, 'status': PublishStatus.DRAFT},
        )
        tables, _ = Category.objects.get_or_create(
            slug='table-covers',
            defaults={'title': 'Чехлы для столов', 'parent': garden, 'position': 4, 'status': PublishStatus.ACTIVE},
        )
        generators, _ = Category.objects.get_or_create(
            slug='generator-covers',
            defaults={'title': 'Чехлы для генераторов', 'parent': equipment, 'position': 5, 'status': PublishStatus.ACTIVE},
        )

        fabric, _ = Fabric.objects.get_or_create(
            title='ПВХ Dejia 470',
            defaults={
                'price_per_square_meter': Decimal('900.00'),
                'density': '470 г/м²',
                'roll_width_cm': 148,
                'property_type': 'Водонепроницаемая',
                'uv_resistance': 5,
                'durability': 5,
                'strength': 5,
                'care': 4,
                'purpose': 'Улица, под навесом, умеренное воздействие УФ-излучения',
                'description': 'Тяжелая и сверхпрочная ткань с ПВХ-пропиткой для уличной эксплуатации.',
            },
        )
        oxford, _ = Fabric.objects.get_or_create(
            title='Оксфорд 600D',
            defaults={
                'price_per_square_meter': Decimal('500.00'),
                'density': '600 г/м²',
                'roll_width_cm': 150,
                'property_type': 'Износостойкая',
                'uv_resistance': 4,
                'durability': 4,
                'strength': 4,
                'care': 5,
            },
        )

        gray, _ = Color.objects.get_or_create(title='Серый', fabric=fabric)
        Color.objects.get_or_create(title='Графит', fabric=fabric)
        Color.objects.get_or_create(title='Светло-серый', fabric=oxford)
        Color.objects.get_or_create(title='Темно-серый', fabric=oxford)

        fastener, _ = Fastener.objects.get_or_create(
            title='Ремни на углах внутри',
            defaults={'price': Decimal('0.00'), 'compatibility': 'Для прямоугольных и овальных чехлов'},
        )
        Fastener.objects.get_or_create(
            title='Утяжка по нижнему краю',
            defaults={'price': Decimal('150.00'), 'compatibility': 'Универсальное крепление'},
        )

        Accessory.objects.get_or_create(
            code='bag-l',
            defaults={'title': 'Сумка для хранения чехла', 'price': Decimal('600.00'), 'status': PublishStatus.ACTIVE},
        )
        Accessory.objects.get_or_create(
            code='bag-s',
            defaults={'title': 'Компактная сумка', 'price': Decimal('200.00'), 'status': PublishStatus.ACTIVE},
        )

        Product.objects.get_or_create(
            sku='DT-TABLE-300-100-75',
            defaults={
                'title': 'Чехол для стола 300x100x75',
                'category': tables,
                'price': Decimal('1000.00'),
                'width_cm': 300,
                'depth_cm': 100,
                'height_cm': 75,
                'fabric': oxford,
                'color': gray,
                'fastener': fastener,
                'stock': 8,
                'purpose': 'Улица, под навесом, умеренное воздействие УФ-излучения',
                'description': 'Готовый защитный чехол для стола из влагостойкой ткани.',
            },
        )
        Product.objects.get_or_create(
            sku='DT-GEN-001',
            defaults={
                'title': 'Чехол для генератора',
                'category': generators,
                'price': Decimal('3200.00'),
                'width_cm': 90,
                'depth_cm': 60,
                'height_cm': 70,
                'fabric': fabric,
                'color': gray,
                'fastener': fastener,
                'stock': 12,
                'purpose': 'Улица, техническая зона, защита от влаги и пыли',
                'description': 'Готовый защитный чехол для генератора.',
            },
        )

        Formula.objects.get_or_create(
            code='rectangular_base',
            defaults={
                'title': 'Прямоугольная базовая',
                'shape': 'rectangular',
                'coefficient': Decimal('1.000'),
                'expression': '(Smat * Rmat + Lseam * Rseam + Ledge * Redge + Z * ((Rseam + Rtopstitch) * Lextra)) * K + options_total',
            },
        )
        Formula.objects.get_or_create(
            code='round_base',
            defaults={
                'title': 'Круглая базовая',
                'shape': 'round',
                'coefficient': Decimal('0.950'),
                'expression': '(Smat * Rmat + Lseam * Rseam + Ledge * Redge + Z * ((Rseam + Rtopstitch) * Lextra)) * K + options_total',
                'status': PublishStatus.ACTIVE,
            },
        )

        formula_defaults = [
            ('wedge_base', 'Клиновидная базовая', 'wedge', Decimal('1.080')),
            ('oval_base', 'Овальная базовая', 'oval', Decimal('1.030')),
            ('l_shaped_base', 'Г-образная базовая', 'l_shaped', Decimal('1.180')),
            ('u_shaped_base', 'П-образная базовая', 'u_shaped', Decimal('1.220')),
        ]
        for code, title, shape, coefficient in formula_defaults:
            Formula.objects.get_or_create(
                code=code,
                defaults={
                    'title': title,
                    'shape': shape,
                    'coefficient': coefficient,
                    'expression': '(Smat * Rmat + Lseam * Rseam + Ledge * Redge + Z * ((Rseam + Rtopstitch) * Lextra)) * K + options_total',
                    'status': PublishStatus.ACTIVE,
                },
            )
        Formula.objects.filter(
            code__in=['rectangular_base', 'round_base', *[item[0] for item in formula_defaults]]
        ).update(status=PublishStatus.ACTIVE)

        User = get_user_model()
        user, _ = User.objects.get_or_create(
            username='demo-client',
            defaults={'email': 'ivan@example.com', 'first_name': 'Иван', 'last_name': 'Петров'},
        )
        Order.objects.get_or_create(
            number='DT-1024',
            defaults={
                'user': user,
                'customer_name': 'Иван Петров',
                'phone': '+7 900 123-45-67',
                'email': 'ivan@example.com',
                'delivery_method': 'СДЭК до пункта выдачи',
                'delivery_city': 'Сочи',
                'delivery_address': 'Пункт выдачи СДЭК, ул. Горького, 53',
                'items_total': Decimal('10800.00'),
                'delivery_total': Decimal('2000.00'),
                'total': Decimal('12800.00'),
                'client_comment': 'Нужна плотная фиксация, чехол будет использоваться на улице.',
                'manager_comment': 'Проверить размеры перед подтверждением стоимости доставки.',
                'return_terms_accepted': True,
            },
        )

        self.stdout.write(self.style.SUCCESS('Demo data is ready.'))
