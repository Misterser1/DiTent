from django.db import migrations, models

import shop.models


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0003_customerprofile'),
    ]

    operations = [
        migrations.CreateModel(
            name='SiteSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Дата обновления')),
                ('company_name', models.CharField(default='ООО "Ваше Название"', max_length=180, verbose_name='Организация')),
                ('inn', models.CharField(blank=True, default='9703149875', max_length=20, verbose_name='ИНН')),
                ('kpp', models.CharField(blank=True, default='770301001', max_length=20, verbose_name='КПП')),
                ('ogrn', models.CharField(blank=True, default='1237700457862', max_length=30, verbose_name='ОГРН')),
                ('registration_date', models.CharField(blank=True, default='07.07.2023', max_length=40, verbose_name='Дата регистрации')),
                ('director', models.CharField(blank=True, default='Иванов Иван Иванович', max_length=180, verbose_name='Руководитель')),
                ('phone', models.CharField(blank=True, default='+7 (222) 222 00-00', max_length=40, verbose_name='Телефон')),
                ('phone_href', models.CharField(blank=True, default='+72222220000', max_length=40, verbose_name='Телефон для ссылки')),
                ('email', models.EmailField(blank=True, default='info@namecompany.ru', max_length=254, verbose_name='Email')),
                ('address', models.CharField(blank=True, default='г. Москва', max_length=255, verbose_name='Адрес')),
                ('whatsapp_url', models.URLField(blank=True, default='https://wa.me/72222220000', verbose_name='WhatsApp')),
                ('telegram_url', models.URLField(blank=True, default='https://t.me/namecompany', verbose_name='Telegram')),
                ('vk_url', models.URLField(blank=True, default='https://vk.com/namecompany', verbose_name='VK')),
                ('map_image', models.ImageField(blank=True, upload_to=shop.models.upload_to, verbose_name='Изображение карты')),
            ],
            options={
                'verbose_name': 'Настройки сайта',
                'verbose_name_plural': 'Настройки сайта',
            },
        ),
    ]
