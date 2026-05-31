from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0013_order_payment_ready_at'),
    ]

    operations = [
        migrations.AddField(
            model_name='sitesettings',
            name='manager_emails',
            field=models.TextField(blank=True, default='', verbose_name='Email менеджеров для уведомлений'),
        ),
    ]
