from django import forms
from django.core.files.uploadedfile import UploadedFile

from .models import Accessory, Category, Color, ConstructorGalleryImage, DrawingOrder, Fabric, Fastener, Formula, GalleryItem, Order, Product, Review, SiteSettings
from .validators import validate_uploaded_file


class SafeUploadModelForm(forms.ModelForm):
    def clean(self):
        cleaned_data = super().clean()

        for field_name, value in cleaned_data.items():
            if isinstance(value, UploadedFile):
                validate_uploaded_file(value)

        return cleaned_data


class NonNegativeFieldsMixin:
    non_negative_fields = ()

    def clean(self):
        cleaned_data = super().clean()

        for field_name in self.non_negative_fields:
            value = cleaned_data.get(field_name)
            if value is not None and value < 0:
                self.add_error(field_name, 'Значение не может быть отрицательным.')

        return cleaned_data


class CategoryForm(SafeUploadModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['parent'].queryset = Category.objects.filter(parent__isnull=True).order_by('position', 'title')

    def clean_parent(self):
        parent = self.cleaned_data.get('parent')

        if parent and parent.parent_id is not None:
            raise forms.ValidationError('Категорию можно добавить только в верхний раздел каталога.')

        return parent

    class Meta:
        model = Category
        fields = ('title', 'slug', 'parent', 'image', 'position', 'status')


class ProductForm(NonNegativeFieldsMixin, SafeUploadModelForm):
    non_negative_fields = ('price', 'width_cm', 'depth_cm', 'height_cm', 'stock')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].queryset = Category.objects.filter(parent__isnull=False).order_by('parent__position', 'parent__title', 'position', 'title')

    def clean_category(self):
        category = self.cleaned_data['category']

        if category.parent_id is None:
            raise forms.ValidationError('Товар можно привязать только к вложенной категории, а не к верхнему разделу каталога.')

        return category

    class Meta:
        model = Product
        fields = (
            'title',
            'category',
            'sku',
            'price',
            'width_cm',
            'depth_cm',
            'height_cm',
            'fabric',
            'color',
            'fastener',
            'main_image',
            'purpose',
            'description',
            'stock',
            'status',
        )


class FabricForm(NonNegativeFieldsMixin, SafeUploadModelForm):
    non_negative_fields = ('price_per_square_meter', 'roll_width_cm', 'uv_resistance', 'durability')

    class Meta:
        model = Fabric
        fields = (
            'title',
            'price_per_square_meter',
            'density',
            'roll_width_cm',
            'property_type',
            'uv_resistance',
            'durability',
            'strength',
            'care',
            'purpose',
            'description',
            'status',
        )


class ColorForm(SafeUploadModelForm):
    class Meta:
        model = Color
        fields = ('title', 'fabric', 'image', 'status')


class FastenerForm(NonNegativeFieldsMixin, SafeUploadModelForm):
    non_negative_fields = ('price',)

    class Meta:
        model = Fastener
        fields = ('title', 'calculation_type', 'price', 'compatibility', 'image', 'status')


class AccessoryForm(NonNegativeFieldsMixin, SafeUploadModelForm):
    non_negative_fields = ('price',)

    class Meta:
        model = Accessory
        fields = ('title', 'code', 'price', 'status')


class FormulaForm(NonNegativeFieldsMixin, SafeUploadModelForm):
    non_negative_fields = (
        'coefficient',
        'minimum_price',
        'seam_price_cm',
        'topstitch_price_cm',
        'edging_price_cm',
        'min_size_cm',
        'max_size_cm',
    )

    def clean(self):
        cleaned_data = super().clean()
        min_size = cleaned_data.get('min_size_cm')
        max_size = cleaned_data.get('max_size_cm')

        if min_size is not None and max_size is not None and min_size > max_size:
            self.add_error('max_size_cm', 'Максимальный размер должен быть больше или равен минимальному.')

        return cleaned_data

    class Meta:
        model = Formula
        fields = (
            'title',
            'shape',
            'code',
            'coefficient',
            'minimum_price',
            'seam_price_cm',
            'topstitch_price_cm',
            'edging_price_cm',
            'min_size_cm',
            'max_size_cm',
            'expression',
            'parameters',
            'status',
        )


class OrderForm(NonNegativeFieldsMixin, SafeUploadModelForm):
    non_negative_fields = ('items_total', 'delivery_total', 'discount_total', 'vat_total', 'total')

    class Meta:
        model = Order
        fields = (
            'number',
            'status',
            'payment_status',
            'customer_type',
            'customer_name',
            'phone',
            'email',
            'delivery_method',
            'delivery_city',
            'delivery_address',
            'track_number',
            'cdek_order_uuid',
            'cdek_status_code',
            'cdek_status_name',
            'cdek_status_updated_at',
            'cdek_tracking_checked_at',
            'payment_method',
            'items_total',
            'delivery_total',
            'discount_total',
            'vat_total',
            'total',
            'client_comment',
            'manager_comment',
            'return_terms_accepted',
        )


class DrawingOrderForm(SafeUploadModelForm):
    class Meta:
        model = DrawingOrder
        fields = (
            'status',
            'customer_name',
            'phone',
            'email',
            'comment',
            'manager_comment',
            'return_terms_accepted',
        )


class GalleryItemForm(SafeUploadModelForm):
    class Meta:
        model = GalleryItem
        fields = ('title', 'image', 'video_url', 'description', 'position', 'status')


class ConstructorGalleryImageForm(SafeUploadModelForm):
    class Meta:
        model = ConstructorGalleryImage
        fields = ('title', 'image', 'position', 'status')


class ReviewForm(SafeUploadModelForm):
    class Meta:
        model = Review
        fields = ('title', 'author_name', 'text', 'rating', 'image', 'location', 'image_caption', 'status')


class SiteSettingsForm(SafeUploadModelForm):
    def clean_manager_emails(self):
        value = self.cleaned_data.get('manager_emails') or ''
        emails = [
            email.strip()
            for email in value.replace(';', ',').replace('\n', ',').split(',')
            if email.strip()
        ]

        for email in emails:
            forms.EmailField().clean(email)

        return '\n'.join(emails)

    class Meta:
        model = SiteSettings
        fields = (
            'company_name',
            'inn',
            'kpp',
            'ogrn',
            'registration_date',
            'director',
            'phone',
            'phone_href',
            'email',
            'manager_emails',
            'address',
            'whatsapp_url',
            'telegram_url',
            'vk_url',
            'map_image',
        )
