from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class PublishStatus(models.TextChoices):
    ACTIVE = 'active', 'Активен'
    DRAFT = 'draft', 'Черновик'
    ARCHIVED = 'archived', 'Снят с публикации'


class OrderStatus(models.TextChoices):
    WAITING_MANAGER = 'waiting_manager', 'Ожидает подтверждения менеджером'
    WAITING_PAYMENT = 'waiting_payment', 'Ожидает оплаты'
    IN_PRODUCTION = 'in_production', 'В производстве'
    IN_DELIVERY = 'in_delivery', 'Передан в доставку'
    COMPLETED = 'completed', 'Завершен'
    CANCELED = 'canceled', 'Отменен'


class PaymentStatus(models.TextChoices):
    NOT_PAID = 'not_paid', 'Не оплачен'
    WAITING_PAYMENT = 'waiting_payment', 'Ожидает оплаты'
    PAID = 'paid', 'Оплачен'
    REFUNDED = 'refunded', 'Возврат'


class CustomerType(models.TextChoices):
    PERSON = 'person', 'Физическое лицо'
    ENTREPRENEUR = 'entrepreneur', 'ИП'
    COMPANY = 'company', 'Юридическое лицо'


class EmailAuthPurpose(models.TextChoices):
    LOGIN = 'login', 'Вход'
    REGISTER = 'register', 'Регистрация'


class PaymentMethod(models.TextChoices):
    CARD = 'card', 'Банковская карта'
    SBP = 'sbp', 'СБП'
    INVOICE = 'invoice', 'Расчетный счет'
    CASH = 'cash', 'Наличные'


class FastenerCalculationType(models.TextChoices):
    FIXED = 'fixed', 'Цена за комплект'


class CoverShape(models.TextChoices):
    RECTANGULAR = 'rectangular', 'Прямоугольная'
    ROUND = 'round', 'Круглая'
    WEDGE = 'wedge', 'Клиновидная'
    OVAL = 'oval', 'Овальная'
    L_SHAPED = 'l_shaped', 'Г-образная'
    U_SHAPED = 'u_shaped', 'П-образная'


class OrderItemType(models.TextChoices):
    CATALOG = 'catalog', 'Товар из каталога'
    CONSTRUCTOR = 'constructor', 'Товар из конструктора'


def upload_to(instance, filename):
    model_name = instance.__class__.__name__.lower()
    return f'{model_name}/{filename}'


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField('Дата создания', auto_now_add=True)
    updated_at = models.DateTimeField('Дата обновления', auto_now=True)

    class Meta:
        abstract = True


class Category(TimeStampedModel):
    title = models.CharField('Название', max_length=180)
    slug = models.SlugField('URL', max_length=190, unique=True)
    parent = models.ForeignKey(
        'self',
        verbose_name='Родительская категория',
        related_name='children',
        on_delete=models.PROTECT,
        blank=True,
        null=True,
    )
    image = models.ImageField('Изображение', upload_to=upload_to, blank=True)
    position = models.PositiveIntegerField('Порядок', default=0)
    status = models.CharField('Статус', max_length=20, choices=PublishStatus.choices, default=PublishStatus.ACTIVE)

    class Meta:
        verbose_name = 'Категория'
        verbose_name_plural = 'Категории'
        ordering = ('position', 'title')
        indexes = [
            models.Index(fields=('status', 'position')),
            models.Index(fields=('parent', 'position')),
        ]

    def __str__(self):
        return self.title


class Fabric(TimeStampedModel):
    title = models.CharField('Название', max_length=180)
    price_per_square_meter = models.DecimalField('Цена за м²', max_digits=10, decimal_places=2)
    density = models.CharField('Плотность', max_length=80, blank=True)
    roll_width_cm = models.PositiveIntegerField('Ширина полотна, см', blank=True, null=True)
    property_type = models.CharField('Тип свойства', max_length=120, blank=True)
    uv_resistance = models.PositiveSmallIntegerField('УФ-стойкость', validators=[MinValueValidator(1), MaxValueValidator(5)], blank=True, null=True)
    durability = models.PositiveSmallIntegerField('Долговечность', validators=[MinValueValidator(1), MaxValueValidator(5)], blank=True, null=True)
    strength = models.PositiveSmallIntegerField('Прочность', validators=[MinValueValidator(1), MaxValueValidator(5)], blank=True, null=True)
    care = models.PositiveSmallIntegerField('Уход', validators=[MinValueValidator(1), MaxValueValidator(5)], blank=True, null=True)
    purpose = models.TextField('Назначение', blank=True)
    description = models.TextField('Описание', blank=True)
    status = models.CharField('Статус', max_length=20, choices=PublishStatus.choices, default=PublishStatus.ACTIVE)

    class Meta:
        verbose_name = 'Ткань'
        verbose_name_plural = 'Ткани'
        ordering = ('title',)

    def __str__(self):
        return self.title


class Color(TimeStampedModel):
    title = models.CharField('Название', max_length=120)
    fabric = models.ForeignKey(Fabric, verbose_name='Материал', related_name='colors', on_delete=models.PROTECT)
    image = models.ImageField('Изображение цвета', upload_to=upload_to, blank=True)
    status = models.CharField('Статус', max_length=20, choices=PublishStatus.choices, default=PublishStatus.ACTIVE)

    class Meta:
        verbose_name = 'Цвет'
        verbose_name_plural = 'Цвета'
        ordering = ('fabric__title', 'title')
        constraints = [
            models.UniqueConstraint(fields=('fabric', 'title'), name='unique_color_per_fabric'),
        ]

    def __str__(self):
        return f'{self.title} / {self.fabric}'


class Fastener(TimeStampedModel):
    title = models.CharField('Название', max_length=180)
    calculation_type = models.CharField(
        'Тип цены',
        max_length=20,
        choices=FastenerCalculationType.choices,
        default=FastenerCalculationType.FIXED,
    )
    price = models.DecimalField('Цена', max_digits=10, decimal_places=2, default=Decimal('0.00'))
    compatibility = models.CharField('Совместимость', max_length=255, blank=True)
    image = models.ImageField('Изображение', upload_to=upload_to, blank=True)
    status = models.CharField('Статус', max_length=20, choices=PublishStatus.choices, default=PublishStatus.ACTIVE)

    class Meta:
        verbose_name = 'Крепление'
        verbose_name_plural = 'Крепления'
        ordering = ('title',)

    def __str__(self):
        return self.title


class Accessory(TimeStampedModel):
    title = models.CharField('Название', max_length=180)
    code = models.SlugField('Код', max_length=80, unique=True)
    price = models.DecimalField('Цена', max_digits=10, decimal_places=2, default=Decimal('0.00'))
    status = models.CharField('Статус', max_length=20, choices=PublishStatus.choices, default=PublishStatus.ACTIVE)

    class Meta:
        verbose_name = 'Аксессуар'
        verbose_name_plural = 'Аксессуары'
        ordering = ('title',)

    def __str__(self):
        return self.title


class Product(TimeStampedModel):
    title = models.CharField('Название', max_length=220)
    category = models.ForeignKey(Category, verbose_name='Категория', related_name='products', on_delete=models.PROTECT)
    sku = models.CharField('Артикул', max_length=80, unique=True)
    price = models.DecimalField('Цена', max_digits=12, decimal_places=2)
    width_cm = models.PositiveIntegerField('Ширина, см', validators=[MinValueValidator(10), MaxValueValidator(500)], blank=True, null=True)
    depth_cm = models.PositiveIntegerField('Глубина, см', validators=[MinValueValidator(10), MaxValueValidator(500)], blank=True, null=True)
    height_cm = models.PositiveIntegerField('Высота, см', validators=[MinValueValidator(10), MaxValueValidator(500)], blank=True, null=True)
    fabric = models.ForeignKey(Fabric, verbose_name='Ткань', related_name='products', on_delete=models.PROTECT, blank=True, null=True)
    color = models.ForeignKey(Color, verbose_name='Цвет', related_name='products', on_delete=models.PROTECT, blank=True, null=True)
    fastener = models.ForeignKey(Fastener, verbose_name='Крепление', related_name='products', on_delete=models.PROTECT, blank=True, null=True)
    main_image = models.ImageField('Главное изображение', upload_to=upload_to, blank=True)
    purpose = models.TextField('Назначение', blank=True)
    description = models.TextField('Описание', blank=True)
    stock = models.PositiveIntegerField('Остаток', default=0)
    status = models.CharField('Статус', max_length=20, choices=PublishStatus.choices, default=PublishStatus.ACTIVE)

    class Meta:
        verbose_name = 'Товар'
        verbose_name_plural = 'Товары'
        ordering = ('title',)
        indexes = [
            models.Index(fields=('category', 'status')),
            models.Index(fields=('sku',)),
        ]

    def __str__(self):
        return self.title


class ProductImage(TimeStampedModel):
    product = models.ForeignKey(Product, verbose_name='Товар', related_name='images', on_delete=models.CASCADE)
    image = models.ImageField('Изображение', upload_to=upload_to)
    position = models.PositiveIntegerField('Порядок', default=0)

    class Meta:
        verbose_name = 'Изображение товара'
        verbose_name_plural = 'Изображения товара'
        ordering = ('position', 'id')

    def __str__(self):
        return f'{self.product} - изображение {self.position}'


class Formula(TimeStampedModel):
    title = models.CharField('Название', max_length=180)
    shape = models.CharField('Форма чехла', max_length=30, choices=CoverShape.choices)
    code = models.SlugField('Код', max_length=120, unique=True)
    coefficient = models.DecimalField('Коэффициент K', max_digits=8, decimal_places=3, default=Decimal('1.000'))
    minimum_price = models.DecimalField('Минимальная стоимость изделия', max_digits=12, decimal_places=2, default=Decimal('1000.00'))
    seam_price_cm = models.DecimalField('Стачной шов, руб./см', max_digits=10, decimal_places=2, default=Decimal('0.00'))
    topstitch_price_cm = models.DecimalField('Отстрочный шов, руб./см', max_digits=10, decimal_places=2, default=Decimal('0.00'))
    edging_price_cm = models.DecimalField('Окантовочный шов, руб./см', max_digits=10, decimal_places=2, default=Decimal('0.00'))
    min_size_cm = models.PositiveIntegerField('Минимальный размер, см', validators=[MinValueValidator(10), MaxValueValidator(500)], default=10)
    max_size_cm = models.PositiveIntegerField('Максимальный размер, см', validators=[MinValueValidator(10), MaxValueValidator(500)], default=500)
    expression = models.TextField('Формула / выражение', blank=True)
    parameters = models.JSONField('Параметры', default=dict, blank=True)
    status = models.CharField('Статус', max_length=20, choices=PublishStatus.choices, default=PublishStatus.ACTIVE)

    class Meta:
        verbose_name = 'Формула'
        verbose_name_plural = 'Формулы'
        ordering = ('shape', 'title')
        indexes = [
            models.Index(fields=('shape', 'status')),
        ]

    def __str__(self):
        return self.title


class Order(TimeStampedModel):
    number = models.CharField('Номер заказа', max_length=40, unique=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='Пользователь', related_name='orders', on_delete=models.PROTECT)
    status = models.CharField('Статус заказа', max_length=30, choices=OrderStatus.choices, default=OrderStatus.WAITING_MANAGER)
    payment_status = models.CharField('Статус оплаты', max_length=30, choices=PaymentStatus.choices, default=PaymentStatus.NOT_PAID)
    customer_type = models.CharField('Тип клиента', max_length=30, choices=CustomerType.choices, default=CustomerType.PERSON)
    customer_name = models.CharField('Имя / компания', max_length=180)
    phone = models.CharField('Телефон', max_length=40)
    email = models.EmailField('Email')
    delivery_method = models.CharField('Способ доставки', max_length=120, blank=True)
    delivery_city = models.CharField('Город доставки', max_length=120, blank=True)
    delivery_address = models.TextField('Адрес доставки', blank=True)
    track_number = models.CharField('Трек-номер', max_length=120, blank=True)
    cdek_order_uuid = models.CharField('UUID заказа СДЭК', max_length=120, blank=True)
    cdek_status_code = models.CharField('Код статуса СДЭК', max_length=80, blank=True)
    cdek_status_name = models.CharField('Статус СДЭК', max_length=255, blank=True)
    cdek_status_updated_at = models.DateTimeField('Дата статуса СДЭК', blank=True, null=True)
    cdek_tracking_checked_at = models.DateTimeField('Проверка СДЭК', blank=True, null=True)
    payment_method = models.CharField('Способ оплаты', max_length=30, choices=PaymentMethod.choices, blank=True)
    payment_gateway = models.CharField('Платежный шлюз', max_length=40, blank=True)
    payment_order_id = models.CharField('ID платежа в шлюзе', max_length=120, blank=True)
    payment_form_url = models.URLField('Ссылка на оплату', max_length=1000, blank=True)
    payment_ready_at = models.DateTimeField('Оплата доступна с', blank=True, null=True)
    items_total = models.DecimalField('Товары', max_digits=12, decimal_places=2, default=Decimal('0.00'))
    delivery_total = models.DecimalField('Доставка', max_digits=12, decimal_places=2, default=Decimal('0.00'))
    discount_total = models.DecimalField('Скидка', max_digits=12, decimal_places=2, default=Decimal('0.00'))
    vat_total = models.DecimalField('НДС', max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total = models.DecimalField('Итого', max_digits=12, decimal_places=2, default=Decimal('0.00'))
    client_comment = models.TextField('Комментарий клиента', blank=True)
    manager_comment = models.TextField('Комментарий менеджера', blank=True)
    return_terms_accepted = models.BooleanField('Условия возврата подтверждены', default=False)

    class Meta:
        verbose_name = 'Заказ'
        verbose_name_plural = 'Заказы'
        ordering = ('-created_at',)
        indexes = [
            models.Index(fields=('user', '-created_at')),
            models.Index(fields=('status', '-created_at')),
        ]

    def __str__(self):
        return self.number


class OrderItem(TimeStampedModel):
    order = models.ForeignKey(Order, verbose_name='Заказ', related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, verbose_name='Товар из каталога', related_name='order_items', on_delete=models.PROTECT, blank=True, null=True)
    item_type = models.CharField('Тип позиции', max_length=30, choices=OrderItemType.choices, default=OrderItemType.CATALOG)
    title = models.CharField('Название', max_length=220)
    sku = models.CharField('Артикул', max_length=100, blank=True)
    shape = models.CharField('Форма чехла', max_length=30, choices=CoverShape.choices, blank=True)
    parameters = models.JSONField('Параметры позиции', default=dict, blank=True)
    quantity = models.PositiveIntegerField('Количество', validators=[MinValueValidator(1)], default=1)
    unit_price = models.DecimalField('Цена за единицу', max_digits=12, decimal_places=2)
    total_price = models.DecimalField('Сумма', max_digits=12, decimal_places=2)

    class Meta:
        verbose_name = 'Позиция заказа'
        verbose_name_plural = 'Позиции заказа'
        ordering = ('id',)

    def __str__(self):
        return f'{self.title} x {self.quantity}'


class Cart(TimeStampedModel):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, related_name='cart', on_delete=models.CASCADE)

    class Meta:
        verbose_name = 'Cart'
        verbose_name_plural = 'Carts'

    def __str__(self):
        return f'Cart #{self.pk} / {self.user}'


class CartItem(TimeStampedModel):
    cart = models.ForeignKey(Cart, related_name='items', on_delete=models.CASCADE)
    data = models.JSONField(default=dict)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = 'Cart item'
        verbose_name_plural = 'Cart items'
        ordering = ('position', 'id')
        indexes = [
            models.Index(fields=('cart', 'position')),
        ]

    def __str__(self):
        return str(self.data.get('title') or f'Cart item #{self.pk}')


class ConstructorAttachment(TimeStampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='Пользователь', related_name='constructor_attachments', on_delete=models.CASCADE, blank=True, null=True)
    file = models.FileField('Файл конструктора', upload_to=upload_to)
    original_name = models.CharField('Исходное имя файла', max_length=255)
    content_type = models.CharField('Тип файла', max_length=120, blank=True)
    size = models.PositiveIntegerField('Размер файла, байт', default=0)

    class Meta:
        verbose_name = 'Временный файл конструктора'
        verbose_name_plural = 'Временные файлы конструктора'
        ordering = ('-created_at',)

    def __str__(self):
        return self.original_name


class OrderItemFile(TimeStampedModel):
    order_item = models.ForeignKey(OrderItem, verbose_name='Позиция заказа', related_name='files', on_delete=models.CASCADE)
    file = models.FileField('Файл', upload_to=upload_to)
    original_name = models.CharField('Исходное имя файла', max_length=255, blank=True)

    class Meta:
        verbose_name = 'Файл позиции заказа'
        verbose_name_plural = 'Файлы позиции заказа'
        ordering = ('id',)

    def __str__(self):
        return self.original_name or self.file.name


class CustomerProfile(TimeStampedModel):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, verbose_name='Пользователь', related_name='customer_profile', on_delete=models.CASCADE)
    middle_name = models.CharField('Отчество', max_length=120, blank=True)
    phone = models.CharField('Телефон', max_length=40, blank=True)
    customer_type = models.CharField('Тип клиента', max_length=30, choices=CustomerType.choices, default=CustomerType.PERSON)

    class Meta:
        verbose_name = 'Профиль клиента'
        verbose_name_plural = 'Профили клиентов'

    def __str__(self):
        return self.user.email or self.user.username


class EmailAuthCode(TimeStampedModel):
    email = models.EmailField('Email')
    purpose = models.CharField('Назначение', max_length=20, choices=EmailAuthPurpose.choices)
    code_hash = models.CharField('Хэш кода', max_length=255)
    payload = models.JSONField('Данные формы', default=dict, blank=True)
    expires_at = models.DateTimeField('Истекает')
    used_at = models.DateTimeField('Использован', blank=True, null=True)
    attempts = models.PositiveSmallIntegerField('Попытки', default=0)
    max_attempts = models.PositiveSmallIntegerField('Максимум попыток', default=5)

    class Meta:
        verbose_name = 'Код входа по email'
        verbose_name_plural = 'Коды входа по email'
        ordering = ('-created_at',)
        indexes = [
            models.Index(fields=('email', 'purpose', '-created_at')),
            models.Index(fields=('expires_at', 'used_at')),
        ]

    def __str__(self):
        return f'{self.email} / {self.purpose}'


class DrawingOrder(TimeStampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='Пользователь', related_name='drawing_orders', on_delete=models.PROTECT, blank=True, null=True)
    status = models.CharField('Статус', max_length=30, choices=OrderStatus.choices, default=OrderStatus.WAITING_MANAGER)
    customer_name = models.CharField('Имя / компания', max_length=180)
    phone = models.CharField('Телефон', max_length=40)
    email = models.EmailField('Email')
    comment = models.TextField('Комментарий', blank=True)
    manager_comment = models.TextField('Комментарий менеджера', blank=True)
    return_terms_accepted = models.BooleanField('Условия возврата подтверждены', default=False)

    class Meta:
        verbose_name = 'Заказ по чертежу'
        verbose_name_plural = 'Заказы по чертежу'
        ordering = ('-created_at',)

    def __str__(self):
        return f'Заказ по чертежу #{self.pk or "новый"}'


class DrawingOrderFile(TimeStampedModel):
    drawing_order = models.ForeignKey(DrawingOrder, verbose_name='Заказ по чертежу', related_name='files', on_delete=models.CASCADE)
    file = models.FileField('Файл', upload_to=upload_to)
    original_name = models.CharField('Исходное имя файла', max_length=255, blank=True)

    class Meta:
        verbose_name = 'Файл заказа по чертежу'
        verbose_name_plural = 'Файлы заказа по чертежу'
        ordering = ('id',)

    def __str__(self):
        return self.original_name or self.file.name


class ConstructorGalleryImage(TimeStampedModel):
    title = models.CharField('Название', max_length=180)
    image = models.ImageField('Изображение', upload_to=upload_to)
    position = models.PositiveIntegerField('Порядок', default=0)
    status = models.CharField('Статус', max_length=20, choices=PublishStatus.choices, default=PublishStatus.ACTIVE)

    class Meta:
        verbose_name = 'Изображение конструктора'
        verbose_name_plural = 'Изображения конструктора'
        ordering = ('position', 'id')

    def __str__(self):
        return self.title


class GalleryItem(TimeStampedModel):
    title = models.CharField('Название', max_length=180)
    image = models.ImageField('Изображение', upload_to=upload_to, blank=True)
    video_url = models.URLField('Ссылка на видео', blank=True)
    description = models.TextField('Описание', blank=True)
    position = models.PositiveIntegerField('Порядок', default=0)
    status = models.CharField('Статус', max_length=20, choices=PublishStatus.choices, default=PublishStatus.ACTIVE)

    class Meta:
        verbose_name = 'Элемент галереи'
        verbose_name_plural = 'Галерея'
        ordering = ('position', '-created_at')

    def __str__(self):
        return self.title


class Review(TimeStampedModel):
    title = models.CharField('Заголовок', max_length=180, default='Все понравилось!')
    author_name = models.CharField('Автор', max_length=120)
    text = models.TextField('Текст отзыва')
    rating = models.PositiveSmallIntegerField('Оценка', validators=[MinValueValidator(1), MaxValueValidator(5)], default=5)
    image = models.ImageField('Изображение', upload_to=upload_to, blank=True)
    location = models.CharField('Город / метка', max_length=120, blank=True, default='г. Москва')
    image_caption = models.CharField('Подпись на изображении', max_length=180, blank=True, default='Индивидуальные защитные чехлы для сада')
    status = models.CharField('Статус', max_length=20, choices=PublishStatus.choices, default=PublishStatus.ACTIVE)

    class Meta:
        verbose_name = 'Отзыв'
        verbose_name_plural = 'Отзывы'
        ordering = ('-created_at',)

    def __str__(self):
        return f'{self.author_name} - {self.rating}/5'


class SiteSettings(TimeStampedModel):
    company_name = models.CharField('Организация', max_length=180, default='ООО "Ваше Название"')
    inn = models.CharField('ИНН', max_length=20, blank=True, default='9703149875')
    kpp = models.CharField('КПП', max_length=20, blank=True, default='770301001')
    ogrn = models.CharField('ОГРН', max_length=30, blank=True, default='1237700457862')
    registration_date = models.CharField('Дата регистрации', max_length=40, blank=True, default='07.07.2023')
    director = models.CharField('Руководитель', max_length=180, blank=True, default='Иванов Иван Иванович')
    phone = models.CharField('Телефон', max_length=40, blank=True, default='+7 (222) 222 00-00')
    phone_href = models.CharField('Телефон для ссылки', max_length=40, blank=True, default='+72222220000')
    email = models.EmailField('Email', blank=True, default='info@namecompany.ru')
    manager_emails = models.TextField('Email менеджеров для уведомлений', blank=True, default='')
    address = models.CharField('Адрес', max_length=255, blank=True, default='г. Москва')
    whatsapp_url = models.URLField('WhatsApp', blank=True, default='https://wa.me/72222220000')
    telegram_url = models.URLField('Telegram', blank=True, default='https://t.me/namecompany')
    vk_url = models.URLField('VK', blank=True, default='https://vk.com/namecompany')
    map_image = models.ImageField('Изображение карты', upload_to=upload_to, blank=True)

    class Meta:
        verbose_name = 'Настройки сайта'
        verbose_name_plural = 'Настройки сайта'

    def __str__(self):
        return 'Настройки сайта'

    @classmethod
    def load(cls):
        settings, _ = cls.objects.get_or_create(pk=1)
        return settings
