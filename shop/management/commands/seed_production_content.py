from decimal import Decimal
from io import BytesIO
from pathlib import Path
import shutil

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction

from shop.models import (
    Accessory,
    Category,
    Color,
    ConstructorGalleryImage,
    CoverShape,
    Fabric,
    Fastener,
    FastenerCalculationType,
    Formula,
    GalleryItem,
    OrderItem,
    Product,
    ProductImage,
    PublishStatus,
    Review,
    SiteSettings,
)

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
except ImportError:  # pragma: no cover - command is only useful with Pillow installed.
    Image = None
    ImageDraw = None
    ImageFilter = None
    ImageFont = None


class Command(BaseCommand):
    help = 'Fills the admin panel with realistic production-like content without touching real orders.'

    image_root = 'seed_content'

    def handle(self, *args, **options):
        if Image is None:
            self.stderr.write(self.style.ERROR('Pillow is required to generate seed images.'))
            return

        self.clear_generated_media()

        with transaction.atomic():
            self.archive_legacy_mock_records()
            categories = self.seed_categories()
            fabrics, colors = self.seed_fabrics_and_colors()
            fasteners = self.seed_fasteners()
            self.seed_accessories()
            self.seed_formulas()
            self.seed_products(categories, fabrics, colors, fasteners)
            self.seed_constructor_gallery()
            self.seed_gallery()
            self.seed_reviews()
            self.seed_site_settings()
            self.cleanup_unseeded_content()

        self.stdout.write(self.style.SUCCESS('Production-like admin content has been seeded.'))

    def clear_generated_media(self):
        media_root = Path(settings.MEDIA_ROOT).resolve()
        if not media_root.exists():
            return

        for path in media_root.glob('*/seed_content'):
            resolved = path.resolve()
            if resolved.name == 'seed_content' and media_root in resolved.parents:
                shutil.rmtree(resolved)

    def archive_legacy_mock_records(self):
        for model in (Category, Fabric, Fastener, Product, Formula, ConstructorGalleryImage, GalleryItem, Review):
            model.objects.filter(title__icontains='Mock').update(status=PublishStatus.ARCHIVED)

        Product.objects.filter(sku__startswith='DT-MOCK-').update(status=PublishStatus.ARCHIVED)
        Accessory.objects.filter(code__startswith='mock-').update(status=PublishStatus.ARCHIVED)

    def cleanup_unseeded_content(self):
        seeded_skus = {
            'DT-GARDEN-TABLE-240',
            'DT-ROUND-TABLE-140',
            'DT-SOFA-210',
            'DT-SET-300-220',
            'DT-GENERATOR-90',
            'DT-GRILL-145',
            'DT-MACHINE-160',
            'DT-HEATER-110',
            'DT-BAR-180',
            'DT-LOUNGER-200',
            'DT-AC-95',
            'DT-COFFEE-120',
        }
        seeded_category_slugs = {
            'garden-furniture-covers',
            'equipment-covers',
            'grill-bbq-covers',
            'horeca-terrace-covers',
            'custom-drawing-covers',
            'table-covers',
            'sofa-armchair-covers',
            'generator-covers',
            'machine-covers',
            'outdoor-bar-covers',
        }
        seeded_fabrics = {
            'ПВХ 650 г/м² TENTPRO',
            'Oxford 600D PU',
            'ПВХ морозостойкая 900 г/м²',
            'Акриловая ткань SunGuard',
            'Ripstop 420D Outdoor',
            'ПВХ 450 г/м² Light',
        }
        seeded_color_titles = {'Графит', 'Серый', 'Бежевый', 'Темно-зеленый'}
        seeded_fasteners = {
            'Люверсы по нижнему краю, шаг 30 см',
            'Утяжка со шнуром и фиксатором',
            'Ремни с фастексами по углам',
            'Липучка Velcro по периметру',
            'Молния сервисного доступа',
            'Вентиляционный клапан',
            'Усиление нижнего края',
        }
        seeded_accessories = {
            'storage-bag',
            'marking-label',
            'repair-kit',
            'extra-vent',
            'product-passport',
            'shipping-pack',
        }
        seeded_formulas = {
            'rectangular-production',
            'round-production',
            'wedge-production',
            'oval-production',
            'l-shaped-production',
            'u-shaped-production',
        }
        seeded_constructor_titles = {
            'Прямоугольная форма для садовой мебели',
            'Круглая форма для столов и резервуаров',
            'Клиновидная форма для техники',
            'Овальная форма для нестандартной мебели',
            'Г-образная форма для угловых зон',
            'П-образная форма для сложных контуров',
        }
        seeded_gallery_titles = {
            'Комплект чехлов для террасы ресторана',
            'Чехол для генератора на производстве',
            'Чехлы для садового комплекта',
            'Промышленный чехол для станка',
            'Чехол для гриль-зоны',
            'Индивидуальный чехол по чертежу',
        }
        seeded_review_authors = {
            'Анна Соколова',
            'Илья Морозов',
            'Марина Белова',
            'Дмитрий Орлов',
            'Сергей Климов',
        }

        stale_products = Product.objects.exclude(sku__in=seeded_skus)
        OrderItem.objects.filter(product__in=stale_products).update(product=None)
        stale_products.delete()

        Review.objects.exclude(author_name__in=seeded_review_authors).delete()
        GalleryItem.objects.exclude(title__in=seeded_gallery_titles).delete()
        ConstructorGalleryImage.objects.exclude(title__in=seeded_constructor_titles).delete()
        Formula.objects.exclude(code__in=seeded_formulas).delete()
        Accessory.objects.exclude(code__in=seeded_accessories).delete()
        Fastener.objects.exclude(title__in=seeded_fasteners).delete()
        Color.objects.exclude(fabric__title__in=seeded_fabrics, title__in=seeded_color_titles).delete()
        Fabric.objects.exclude(title__in=seeded_fabrics).delete()

        stale_categories = list(Category.objects.exclude(slug__in=seeded_category_slugs))
        for category in sorted(stale_categories, key=lambda item: item.parent_id is None):
            category.delete()

    def font(self, size, bold=False):
        candidates = [
            Path('C:/Windows/Fonts/segoeuib.ttf' if bold else 'C:/Windows/Fonts/segoeui.ttf'),
            Path('C:/Windows/Fonts/arialbd.ttf' if bold else 'C:/Windows/Fonts/arial.ttf'),
            Path(settings.BASE_DIR) / 'assets' / 'fonts' / ('Inter-Bold.ttf' if bold else 'Inter-Regular.ttf'),
        ]
        for path in candidates:
            if path.exists():
                return ImageFont.truetype(str(path), size)
        return ImageFont.load_default()

    def save_jpeg(self, instance, field_name, folder, filename, image):
        buffer = BytesIO()
        image.convert('RGB').save(buffer, format='JPEG', quality=88, optimize=True)
        getattr(instance, field_name).save(
            f'{self.image_root}/{folder}/{filename}.jpg',
            ContentFile(buffer.getvalue()),
            save=False,
        )

    def gradient(self, size, top, bottom):
        width, height = size
        image = Image.new('RGB', size, top)
        draw = ImageDraw.Draw(image)
        for y in range(height):
            ratio = y / max(height - 1, 1)
            color = tuple(int(top[i] * (1 - ratio) + bottom[i] * ratio) for i in range(3))
            draw.line((0, y, width, y), fill=color)
        return image

    def wrap_text(self, text, font, max_width):
        words = text.split()
        lines = []
        line = ''
        probe = Image.new('RGB', (1, 1))
        draw = ImageDraw.Draw(probe)
        for word in words:
            candidate = f'{line} {word}'.strip()
            if draw.textbbox((0, 0), candidate, font=font)[2] <= max_width:
                line = candidate
            else:
                if line:
                    lines.append(line)
                line = word
        if line:
            lines.append(line)
        return lines

    def label_image(self, title, subtitle, accent=(103, 172, 219), kind='product', fabric=(70, 80, 86)):
        image = self.gradient((1200, 850), (245, 248, 250), (223, 231, 236))
        draw = ImageDraw.Draw(image, 'RGBA')

        draw.rounded_rectangle((78, 80, 1122, 770), radius=42, fill=(255, 255, 255, 230))
        draw.rectangle((78, 515, 1122, 770), fill=(240, 244, 247, 255))

        if kind == 'material':
            self.draw_material(draw, image, fabric)
        elif kind == 'fastener':
            self.draw_fastener(draw, accent)
        elif kind == 'review':
            self.draw_review_scene(draw, accent, fabric)
        elif kind == 'map':
            self.draw_map(draw, accent)
        else:
            self.draw_cover(draw, accent, fabric)

        title_font = self.font(54, bold=True)
        subtitle_font = self.font(31)
        small_font = self.font(24)

        y = 585
        for line in self.wrap_text(title, title_font, 850)[:2]:
            draw.text((118, y), line, fill=(20, 27, 34), font=title_font)
            y += 62

        draw.text((120, y + 8), subtitle, fill=(83, 96, 108), font=subtitle_font)
        draw.rounded_rectangle((900, 612, 1048, 660), radius=24, fill=accent + (255,))
        draw.text((928, 623), 'DiTENT', fill=(255, 255, 255), font=small_font)
        return image

    def swatch_image(self, title, color):
        image = self.gradient((900, 900), color, tuple(max(0, c - 42) for c in color))
        draw = ImageDraw.Draw(image, 'RGBA')
        for x in range(-900, 900, 34):
            draw.line((x, 900, x + 900, 0), fill=(255, 255, 255, 16), width=12)
        image = image.filter(ImageFilter.GaussianBlur(0.35))
        draw = ImageDraw.Draw(image, 'RGBA')
        draw.rounded_rectangle((65, 650, 835, 825), radius=28, fill=(255, 255, 255, 228))
        draw.text((105, 690), title, fill=(26, 32, 38), font=self.font(48, bold=True))
        draw.text((105, 752), 'образец ткани', fill=(91, 103, 114), font=self.font(30))
        return image

    def draw_cover(self, draw, accent, fabric):
        draw.ellipse((265, 155, 935, 560), fill=(210, 216, 220, 255))
        draw.rounded_rectangle((250, 245, 950, 575), radius=48, fill=fabric + (255,))
        draw.polygon((250, 300, 950, 300, 870, 195, 330, 195), fill=tuple(min(255, c + 28) for c in fabric) + (255,))
        draw.line((330, 195, 250, 300, 250, 575), fill=(255, 255, 255, 66), width=7)
        draw.line((870, 195, 950, 300, 950, 575), fill=(0, 0, 0, 34), width=7)
        draw.line((292, 540, 908, 540), fill=accent + (220,), width=12)
        for x in (345, 505, 665, 825):
            draw.ellipse((x, 526, x + 28, 554), fill=(232, 236, 239, 255), outline=(120, 132, 143, 255), width=3)

    def draw_material(self, draw, image, fabric):
        patch = self.swatch_image('', fabric).resize((620, 360))
        image.paste(patch, (290, 170))
        draw.rounded_rectangle((290, 170, 910, 530), radius=32, outline=(255, 255, 255, 210), width=8)

    def draw_fastener(self, draw, accent):
        draw.rounded_rectangle((330, 205, 870, 445), radius=52, fill=(58, 67, 74, 255))
        draw.rounded_rectangle((420, 270, 780, 375), radius=32, outline=(240, 244, 247, 255), width=26)
        draw.line((265, 326, 420, 326), fill=accent + (255,), width=26)
        draw.line((780, 326, 935, 326), fill=accent + (255,), width=26)
        draw.ellipse((250, 298, 306, 354), fill=(239, 244, 247, 255), outline=(83, 96, 108, 255), width=4)
        draw.ellipse((894, 298, 950, 354), fill=(239, 244, 247, 255), outline=(83, 96, 108, 255), width=4)

    def draw_review_scene(self, draw, accent, fabric):
        self.draw_cover(draw, accent, fabric)
        draw.rounded_rectangle((765, 150, 965, 330), radius=30, fill=(255, 255, 255, 232))
        for i in range(5):
            x = 795 + i * 32
            draw.text((x, 188), '★', fill=accent + (255,), font=self.font(28, bold=True))
        draw.text((795, 245), 'готово', fill=(42, 50, 57), font=self.font(32, bold=True))

    def draw_map(self, draw, accent):
        draw.rounded_rectangle((170, 145, 1030, 545), radius=44, fill=(233, 239, 243, 255))
        roads = [
            ((210, 405), (430, 335), (660, 370), (990, 260)),
            ((270, 190), (500, 305), (760, 290), (940, 475)),
            ((335, 515), (520, 410), (610, 225), (780, 150)),
        ]
        for points in roads:
            draw.line(points, fill=(255, 255, 255, 255), width=28, joint='curve')
            draw.line(points, fill=(198, 207, 215, 255), width=5)
        draw.ellipse((552, 272, 648, 368), fill=accent + (255,))
        draw.ellipse((584, 303, 616, 335), fill=(255, 255, 255, 255))

    def seed_categories(self):
        root_rows = [
            ('Чехлы для садовой мебели', 'garden-furniture-covers', 'Столы, диваны, кресла и комплекты', (80, 101, 105)),
            ('Чехлы для техники и оборудования', 'equipment-covers', 'Генераторы, станки, тепловые пушки', (62, 76, 83)),
            ('Чехлы для грилей и барбекю', 'grill-bbq-covers', 'Защита уличных кухонь и гриль-зон', (47, 62, 66)),
            ('Чехлы для HoReCa и террас', 'horeca-terrace-covers', 'Рестораны, кафе, летние площадки', (91, 78, 61)),
            ('Индивидуальные чехлы по чертежу', 'custom-drawing-covers', 'Изготовление по размерам клиента', (67, 88, 104)),
        ]
        roots = {}
        for position, (title, slug, subtitle, fabric) in enumerate(root_rows, start=1):
            category, _ = Category.objects.update_or_create(
                slug=slug,
                defaults={
                    'title': title,
                    'parent': None,
                    'position': position,
                    'status': PublishStatus.ACTIVE,
                },
            )
            self.save_jpeg(category, 'image', 'categories', slug, self.label_image(title, subtitle, fabric=fabric))
            category.save()
            roots[slug] = category

        child_rows = [
            ('Чехлы для столов', 'table-covers', 'garden-furniture-covers', 'Прямоугольные, круглые и овальные столы', (88, 102, 96)),
            ('Чехлы для диванов и кресел', 'sofa-armchair-covers', 'garden-furniture-covers', 'Мягкая уличная мебель и лаунж-зоны', (80, 94, 98)),
            ('Чехлы для генераторов', 'generator-covers', 'equipment-covers', 'Работа на улице и сезонное хранение', (56, 66, 73)),
            ('Чехлы для станков и оборудования', 'machine-covers', 'equipment-covers', 'Производственные и складские зоны', (68, 74, 81)),
            ('Чехлы для уличных барных стоек', 'outdoor-bar-covers', 'horeca-terrace-covers', 'Коммерческие террасы и летние бары', (93, 82, 68)),
        ]
        categories = dict(roots)
        for position, (title, slug, parent_slug, subtitle, fabric) in enumerate(child_rows, start=1):
            category, _ = Category.objects.update_or_create(
                slug=slug,
                defaults={
                    'title': title,
                    'parent': roots[parent_slug],
                    'position': position,
                    'status': PublishStatus.ACTIVE,
                },
            )
            self.save_jpeg(category, 'image', 'categories', slug, self.label_image(title, subtitle, fabric=fabric))
            category.save()
            categories[slug] = category
        return categories

    def seed_fabrics_and_colors(self):
        fabric_rows = [
            ('ПВХ 650 г/м² TENTPRO', '1450.00', '650 г/м²', 250, 'водонепроницаемая', 5, 5, 5, 4, 'Основная ткань для уличных чехлов, мебели и техники. Хорошо держит форму, не боится дождя и солнца.'),
            ('Oxford 600D PU', '780.00', '240 г/м²', 150, 'водоотталкивающая', 4, 4, 3, 5, 'Легкая ткань для сезонного хранения, небольших чехлов и изделий, где важен малый вес.'),
            ('ПВХ морозостойкая 900 г/м²', '1980.00', '900 г/м²', 250, 'усиленная морозостойкая', 5, 5, 5, 3, 'Плотная ткань для техники, промышленного оборудования и эксплуатации на улице круглый год.'),
            ('Акриловая ткань SunGuard', '1650.00', '320 г/м²', 152, 'дышащая УФ-стойкая', 5, 4, 4, 5, 'Премиальная ткань для террас, ресторанной мебели и видимых зон с повышенными требованиями к внешнему виду.'),
            ('Ripstop 420D Outdoor', '920.00', '210 г/м²', 150, 'армированная легкая', 4, 4, 4, 5, 'Армированная ткань для переносных чехлов, сумок хранения и небольших защитных изделий.'),
            ('ПВХ 450 г/м² Light', '1120.00', '450 г/м²', 250, 'легкая тентовая', 4, 4, 4, 4, 'Универсальный материал для чехлов средней нагрузки, навесных элементов и сезонной защиты.'),
        ]
        swatches = [
            ('Графит', (58, 65, 70)),
            ('Серый', (128, 137, 143)),
            ('Бежевый', (179, 164, 136)),
            ('Темно-зеленый', (55, 89, 72)),
            ('Синий', (47, 88, 133)),
            ('Черный', (34, 38, 42)),
            ('Молочный', (214, 209, 194)),
            ('Терракота', (145, 92, 64)),
        ]
        fabrics = {}
        colors = {}
        for row in fabric_rows:
            title, price, density, roll, prop, uv, durability, strength, care, description = row
            fabric, _ = Fabric.objects.update_or_create(
                title=title,
                defaults={
                    'price_per_square_meter': Decimal(price),
                    'density': density,
                    'roll_width_cm': roll,
                    'property_type': prop,
                    'uv_resistance': uv,
                    'durability': durability,
                    'strength': strength,
                    'care': care,
                    'purpose': 'Пошив защитных чехлов для улицы, техники, мебели и коммерческих объектов.',
                    'description': description,
                    'status': PublishStatus.ACTIVE,
                },
            )
            fabrics[title] = fabric
            for color_title, rgb in swatches[:4]:
                color, _ = Color.objects.update_or_create(
                    fabric=fabric,
                    title=color_title,
                    defaults={'status': PublishStatus.ACTIVE},
                )
                filename = f'{self.slug(title)}-{self.slug(color_title)}'
                self.save_jpeg(color, 'image', 'colors', filename, self.swatch_image(f'{color_title} / {title}', rgb))
                color.save()
                colors[(title, color_title)] = color
        return fabrics, colors

    def seed_fasteners(self):
        rows = [
            ('Люверсы по нижнему краю, шаг 30 см', '420.00', 'Для чехлов ПВХ и Oxford; удобно фиксировать шнуром или стяжками.'),
            ('Утяжка со шнуром и фиксатором', '650.00', 'Базовый вариант для садовой мебели, грилей и компактной техники.'),
            ('Ремни с фастексами по углам', '900.00', 'Подходит для ветреных площадок и чехлов на крупную мебель.'),
            ('Липучка Velcro по периметру', '780.00', 'Для плотной посадки на сложных формах и частого снятия чехла.'),
            ('Молния сервисного доступа', '1200.00', 'Нужна, если к оборудованию должен быть быстрый доступ без полного снятия чехла.'),
            ('Вентиляционный клапан', '450.00', 'Снижает риск конденсата под плотными тканями.'),
            ('Усиление нижнего края', '520.00', 'Рекомендуется для тяжелых ПВХ-тканей и эксплуатации на улице.'),
        ]
        fasteners = {}
        for index, (title, price, compatibility) in enumerate(rows, start=1):
            fastener, _ = Fastener.objects.update_or_create(
                title=title,
                defaults={
                    'calculation_type': FastenerCalculationType.FIXED,
                    'price': Decimal(price),
                    'compatibility': compatibility,
                    'status': PublishStatus.ACTIVE,
                },
            )
            self.save_jpeg(
                fastener,
                'image',
                'fasteners',
                self.slug(title),
                self.label_image(title, f'Комплект: {price} руб.', accent=(103, 172, 219), kind='fastener'),
            )
            fastener.save()
            fasteners[title] = fastener
        return fasteners

    def seed_accessories(self):
        rows = [
            ('Сумка для хранения чехла', 'storage-bag', '690.00'),
            ('Маркировочная бирка с названием изделия', 'marking-label', '120.00'),
            ('Ремкомплект ткани и клея', 'repair-kit', '490.00'),
            ('Дополнительный вентиляционный клапан', 'extra-vent', '450.00'),
            ('Паспорт изделия и схема установки', 'product-passport', '180.00'),
            ('Индивидуальная упаковка для отправки', 'shipping-pack', '350.00'),
        ]
        for title, code, price in rows:
            Accessory.objects.update_or_create(
                code=code,
                defaults={'title': title, 'price': Decimal(price), 'status': PublishStatus.ACTIVE},
            )

    def seed_formulas(self):
        parameter_sets = {
            CoverShape.RECTANGULAR: [('A', 'Длина'), ('B', 'Глубина'), ('C', 'Высота')],
            CoverShape.ROUND: [('A', 'Диаметр'), ('B', 'Высота')],
            CoverShape.WEDGE: [('A', 'Задняя длина'), ('B', 'Передняя длина'), ('C', 'Глубина'), ('D', 'Высота')],
            CoverShape.OVAL: [('A', 'Большая ось'), ('B', 'Малая ось'), ('C', 'Высота')],
            CoverShape.L_SHAPED: [('A', 'Задняя длина'), ('B', 'Правая глубина'), ('C', 'Высота'), ('D', 'Левая высота'), ('E', 'Левая глубина'), ('F', 'Передняя длина'), ('G', 'Внутренняя длина'), ('H', 'Внутренняя глубина')],
            CoverShape.U_SHAPED: [('A', 'Задняя длина'), ('B', 'Правая глубина'), ('C', 'Высота'), ('D', 'Левая высота'), ('E', 'Левая глубина'), ('F', 'Передняя длина'), ('G', 'Внутренняя длина'), ('H', 'Внутренняя глубина')],
        }
        rows = [
            ('Прямоугольный чехол: площадь + боковины', CoverShape.RECTANGULAR, 'rectangular-production', '1.000', '1500.00', '(A * B + 2 * (A * C) + 2 * (B * C)) / 10000'),
            ('Круглый чехол: верх + цилиндрическая стенка', CoverShape.ROUND, 'round-production', '1.050', '1600.00', '(3.1416 * (A / 2) * (A / 2) + 3.1416 * A * B) / 10000'),
            ('Клиновидный чехол: средняя длина + боковые панели', CoverShape.WEDGE, 'wedge-production', '1.120', '1900.00', '(((A + B) / 2) * C + A * D + B * D + 2 * (C * D)) / 10000'),
            ('Овальный чехол: верх + боковая стенка', CoverShape.OVAL, 'oval-production', '1.080', '1800.00', '(3.1416 * (A / 2) * (B / 2) + 3.1416 * ((A + B) / 2) * C) / 10000'),
            ('Г-образный чехол: внешний контур минус внутренний вырез', CoverShape.L_SHAPED, 'l-shaped-production', '1.180', '2300.00', '((A * B + F * E - G * H) + (A + B + E + F + G + H) * C) / 10000'),
            ('П-образный чехол: три секции и внутренний проем', CoverShape.U_SHAPED, 'u-shaped-production', '1.240', '2600.00', '((A * B + F * E - G * H) + (A + B + E + F + G + H) * C) / 10000'),
        ]
        for title, shape, code, coefficient, minimum, expression in rows:
            Formula.objects.update_or_create(
                code=code,
                defaults={
                    'title': title,
                    'shape': shape,
                    'coefficient': Decimal(coefficient),
                    'minimum_price': Decimal(minimum),
                    'seam_price_cm': Decimal('2.50'),
                    'topstitch_price_cm': Decimal('1.80'),
                    'edging_price_cm': Decimal('1.40'),
                    'min_size_cm': 10,
                    'max_size_cm': 500,
                    'expression': expression,
                    'parameters': {
                        'dimensions': [{'code': code, 'label': label, 'unit': 'см'} for code, label in parameter_sets[shape]],
                        'allowances': {'seam_cm': 3, 'fit_cm': 2},
                        'note': 'Расчетная формула для предварительной стоимости. Финальная цена подтверждается менеджером после проверки размеров.',
                    },
                    'status': PublishStatus.ACTIVE,
                },
            )

    def seed_products(self, categories, fabrics, colors, fasteners):
        products = [
            ('Чехол для прямоугольного стола 240x100x78', 'DT-GARDEN-TABLE-240', 'table-covers', 'ПВХ 650 г/м² TENTPRO', 'Графит', 'Утяжка со шнуром и фиксатором', '6950.00', 240, 100, 78, 8),
            ('Чехол для круглого стола D140 H75', 'DT-ROUND-TABLE-140', 'table-covers', 'Акриловая ткань SunGuard', 'Бежевый', 'Утяжка со шнуром и фиксатором', '5400.00', 140, 140, 75, 6),
            ('Чехол для садового дивана 210x90x80', 'DT-SOFA-210', 'sofa-armchair-covers', 'ПВХ 650 г/м² TENTPRO', 'Серый', 'Ремни с фастексами по углам', '8900.00', 210, 90, 80, 5),
            ('Чехол для комплекта мебели 300x220x90', 'DT-SET-300-220', 'garden-furniture-covers', 'ПВХ морозостойкая 900 г/м²', 'Графит', 'Ремни с фастексами по углам', '18400.00', 300, 220, 90, 3),
            ('Чехол для генератора 90x60x70', 'DT-GENERATOR-90', 'generator-covers', 'ПВХ 650 г/м² TENTPRO', 'Темно-зеленый', 'Вентиляционный клапан', '6200.00', 90, 60, 70, 10),
            ('Чехол для гриля 145x65x115', 'DT-GRILL-145', 'grill-bbq-covers', 'ПВХ 450 г/м² Light', 'Черный', 'Липучка Velcro по периметру', '7900.00', 145, 65, 115, 7),
            ('Чехол для станка 160x80x140', 'DT-MACHINE-160', 'machine-covers', 'ПВХ морозостойкая 900 г/м²', 'Серый', 'Молния сервисного доступа', '15300.00', 160, 80, 140, 2),
            ('Чехол для тепловой пушки 110x55x65', 'DT-HEATER-110', 'equipment-covers', 'Ripstop 420D Outdoor', 'Графит', 'Люверсы по нижнему краю, шаг 30 см', '4300.00', 110, 55, 65, 9),
            ('Чехол для уличной барной стойки 180x70x115', 'DT-BAR-180', 'outdoor-bar-covers', 'Акриловая ткань SunGuard', 'Темно-зеленый', 'Липучка Velcro по периметру', '12800.00', 180, 70, 115, 4),
            ('Чехол для шезлонга 200x75x45', 'DT-LOUNGER-200', 'garden-furniture-covers', 'Oxford 600D PU', 'Бежевый', 'Утяжка со шнуром и фиксатором', '3900.00', 200, 75, 45, 12),
            ('Чехол для наружного блока кондиционера 95x40x70', 'DT-AC-95', 'equipment-covers', 'ПВХ 450 г/м² Light', 'Серый', 'Вентиляционный клапан', '4100.00', 95, 40, 70, 8),
            ('Чехол для кофейной станции HoReCa 120x60x90', 'DT-COFFEE-120', 'horeca-terrace-covers', 'Акриловая ткань SunGuard', 'Графит', 'Молния сервисного доступа', '9800.00', 120, 60, 90, 5),
        ]
        for title, sku, category_slug, fabric_title, color_title, fastener_title, price, width, depth, height, stock in products:
            fabric = fabrics[fabric_title]
            color = colors.get((fabric_title, color_title)) or Color.objects.filter(fabric=fabric).first()
            product, _ = Product.objects.update_or_create(
                sku=sku,
                defaults={
                    'title': title,
                    'category': categories[category_slug],
                    'price': Decimal(price),
                    'width_cm': width,
                    'depth_cm': depth,
                    'height_cm': height,
                    'fabric': fabric,
                    'color': color,
                    'fastener': fasteners[fastener_title],
                    'purpose': 'Готовое изделие из каталога для быстрой покупки или ориентира по цене индивидуального пошива.',
                    'description': f'{title}. Пошив из материала {fabric_title}, усиленный нижний край, аккуратная посадка по размерам и комплект креплений.',
                    'stock': stock,
                    'status': PublishStatus.ACTIVE,
                },
            )
            rgb = self.color_rgb(color_title)
            self.save_jpeg(product, 'main_image', 'products', self.slug(sku), self.label_image(title, f'{width} x {depth} x {height} см', fabric=rgb))
            product.save()
            product.images.all().delete()
            for position, suffix in enumerate(('front', 'detail'), start=1):
                gallery = ProductImage(product=product, position=position)
                image = self.label_image(
                    title,
                    'деталь крепления' if suffix == 'detail' else 'вид изделия',
                    accent=(103, 172, 219),
                    kind='fastener' if suffix == 'detail' else 'product',
                    fabric=rgb,
                )
                self.save_jpeg(gallery, 'image', 'products/gallery', f'{self.slug(sku)}-{suffix}', image)
                gallery.save()

    def seed_constructor_gallery(self):
        rows = [
            ('Прямоугольная форма для садовой мебели', 'rectangular', (70, 82, 89)),
            ('Круглая форма для столов и резервуаров', 'round', (83, 92, 86)),
            ('Клиновидная форма для техники', 'wedge', (63, 75, 84)),
            ('Овальная форма для нестандартной мебели', 'oval', (93, 86, 74)),
            ('Г-образная форма для угловых зон', 'l-shaped', (68, 83, 94)),
            ('П-образная форма для сложных контуров', 'u-shaped', (76, 78, 88)),
        ]
        for position, (title, code, fabric) in enumerate(rows, start=1):
            item, _ = ConstructorGalleryImage.objects.update_or_create(
                title=title,
                defaults={'position': position, 'status': PublishStatus.ACTIVE},
            )
            self.save_jpeg(item, 'image', 'constructor', code, self.label_image(title, 'пример формы для конструктора', fabric=fabric))
            item.save()

    def seed_gallery(self):
        rows = [
            ('Комплект чехлов для террасы ресторана', 'Защитили мебель летней площадки от дождя и пыли.', (87, 77, 64)),
            ('Чехол для генератора на производстве', 'ПВХ 650 г/м², клапан вентиляции и ремни фиксации.', (58, 68, 76)),
            ('Чехлы для садового комплекта', 'Единый комплект для стола, дивана и кресел.', (77, 93, 88)),
            ('Промышленный чехол для станка', 'Усиленная ткань и молния сервисного доступа.', (61, 70, 79)),
            ('Чехол для гриль-зоны', 'Плотная посадка, нижняя утяжка и защита от осадков.', (44, 49, 52)),
            ('Индивидуальный чехол по чертежу', 'Сложная форма по размерам клиента.', (70, 86, 101)),
        ]
        for position, (title, description, fabric) in enumerate(rows, start=1):
            item, _ = GalleryItem.objects.update_or_create(
                title=title,
                defaults={'description': description, 'position': position, 'status': PublishStatus.ACTIVE},
            )
            self.save_jpeg(item, 'image', 'gallery', self.slug(title), self.label_image(title, description, fabric=fabric))
            item.save()

    def seed_reviews(self):
        rows = [
            ('Точно попали в размер', 'Анна Соколова', 'Заказывали чехлы для мебели на террасу кафе. Сняли размеры, согласовали крепления, после дождя мебель остается сухой.', 5, 'Москва', 'Терраса ресторана'),
            ('Удобно для генератора', 'Илья Морозов', 'Понравилось, что сделали вентиляционный клапан и молнию для доступа к панели. Чехол сидит плотно, ремни не дают его сдуть ветром.', 5, 'Краснодар', 'Чехол для генератора'),
            ('Аккуратный внешний вид', 'Марина Белова', 'Нужны были чехлы не только практичные, но и нормальные внешне. Ткань подобрали спокойную, швы ровные, на террасе смотрится хорошо.', 5, 'Сочи', 'Комплект для лаунж-зоны'),
            ('Быстро согласовали чертеж', 'Дмитрий Орлов', 'Отправили схему оборудования, менеджер уточнил высоты и вырезы. Получили изделие без переделок.', 5, 'Ростов-на-Дону', 'Индивидуальный пошив'),
            ('Хорошая плотная ткань', 'Сергей Климов', 'Для станка выбрали усиленную ПВХ ткань. Чехол тяжелый, но для цеха это плюс: не рвется и хорошо закрывает углы.', 4, 'Воронеж', 'Промышленный чехол'),
        ]
        for index, (title, author, text, rating, location, caption) in enumerate(rows, start=1):
            review, _ = Review.objects.update_or_create(
                author_name=author,
                defaults={
                    'title': title,
                    'text': text,
                    'rating': rating,
                    'location': f'г. {location}',
                    'image_caption': caption,
                    'status': PublishStatus.ACTIVE,
                },
            )
            self.save_jpeg(review, 'image', 'reviews', self.slug(author), self.label_image(caption, location, kind='review', fabric=(68 + index * 4, 78 + index * 3, 84 + index * 2)))
            review.save()

    def seed_site_settings(self):
        settings_obj = SiteSettings.load()
        settings_obj.company_name = 'ООО «ДиТент»'
        settings_obj.inn = '9704218430'
        settings_obj.kpp = '770401001'
        settings_obj.ogrn = '1247700452187'
        settings_obj.registration_date = '18.04.2024'
        settings_obj.director = 'Романов Алексей Сергеевич'
        settings_obj.phone = '+7 (495) 120-48-62'
        settings_obj.phone_href = '+74951204862'
        settings_obj.email = 'info@ditent.ru'
        settings_obj.manager_emails = 'manager@ditent.ru\nsales@ditent.ru'
        settings_obj.address = 'г. Москва, Варшавское шоссе, 42, стр. 3'
        settings_obj.whatsapp_url = 'https://wa.me/74951204862'
        settings_obj.telegram_url = 'https://t.me/ditent_ru'
        settings_obj.vk_url = 'https://vk.com/ditent_ru'
        self.save_jpeg(settings_obj, 'map_image', 'settings', 'office-map', self.label_image('Офис и производство', settings_obj.address, kind='map'))
        settings_obj.save()

    def slug(self, value):
        translit = {
            'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e', 'ж': 'zh', 'з': 'z',
            'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm', 'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r',
            'с': 's', 'т': 't', 'у': 'u', 'ф': 'f', 'х': 'h', 'ц': 'c', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
            'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
        }
        result = []
        for char in value.lower():
            if char in translit:
                result.append(translit[char])
            elif char.isalnum():
                result.append(char)
            else:
                result.append('-')
        return '-'.join(part for part in ''.join(result).split('-') if part)[:90]

    def color_rgb(self, title):
        palette = {
            'Графит': (58, 65, 70),
            'Серый': (128, 137, 143),
            'Бежевый': (179, 164, 136),
            'Темно-зеленый': (55, 89, 72),
            'Синий': (47, 88, 133),
            'Черный': (34, 38, 42),
            'Молочный': (214, 209, 194),
            'Терракота': (145, 92, 64),
        }
        return palette.get(title, (70, 80, 86))
