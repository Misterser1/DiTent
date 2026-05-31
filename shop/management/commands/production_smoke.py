from django.conf import settings
from django.core.checks import ERROR, WARNING
from django.core.mail import send_mail
from django.core.management.base import BaseCommand, CommandError

from shop.alfa_acquiring import AlfaAcquiringError, get_payment_status
from shop.checks import production_external_service_checks
from shop.location_services import cdek_get


class Command(BaseCommand):
    help = 'Runs safe production smoke checks for DiTent external integrations.'

    def add_arguments(self, parser):
        parser.add_argument('--email-to', default='', help='Recipient email for SMTP smoke test.')
        parser.add_argument('--skip-email', action='store_true', help='Skip SMTP send test.')
        parser.add_argument('--skip-cdek', action='store_true', help='Skip CDEK pickup point API test.')
        parser.add_argument('--skip-alfa', action='store_true', help='Skip Alfa acquiring status test.')
        parser.add_argument('--cdek-city-code', default='', help='CDEK city code for pickup point smoke test.')
        parser.add_argument('--alfa-order-id', default='', help='Existing Alfa mdOrder/orderId for a read-only status check.')

    def handle(self, *args, **options):
        failures = []
        warnings = []

        self.check_deploy_settings(failures, warnings)

        if options['skip_email']:
            self.warn(warnings, 'SMTP check skipped by --skip-email.')
        else:
            self.check_email(options['email_to'], failures)

        if options['skip_cdek']:
            self.warn(warnings, 'CDEK check skipped by --skip-cdek.')
        else:
            self.check_cdek(options['cdek_city_code'], failures)

        if options['skip_alfa']:
            self.warn(warnings, 'Alfa acquiring check skipped by --skip-alfa.')
        else:
            self.check_alfa(options['alfa_order_id'], failures, warnings)

        for message in warnings:
            self.stdout.write(self.style.WARNING(f'WARN: {message}'))

        if failures:
            for message in failures:
                self.stderr.write(self.style.ERROR(f'FAIL: {message}'))
            raise CommandError('Production smoke checks failed.')

        self.stdout.write(self.style.SUCCESS('Production smoke checks passed.'))

    def check_deploy_settings(self, failures, warnings):
        messages = production_external_service_checks(None)
        for message in messages:
            text = f'{message.id}: {message.msg}'
            if message.level >= ERROR:
                failures.append(text)
            elif message.level >= WARNING:
                warnings.append(text)

        if not messages:
            self.stdout.write(self.style.SUCCESS('OK: deploy settings checks passed.'))

    def check_email(self, recipient, failures):
        if not recipient:
            failures.append('SMTP recipient is not set. Pass --email-to manager@company.ru.')
            return

        try:
            sent = send_mail(
                'DiTent production smoke',
                'SMTP smoke test from DiTent production environment.',
                settings.DEFAULT_FROM_EMAIL,
                [recipient],
                fail_silently=False,
            )
        except Exception as exc:
            failures.append(f'SMTP send failed: {exc}')
            return

        if sent != 1:
            failures.append(f'SMTP send returned unexpected count: {sent}')
            return

        self.stdout.write(self.style.SUCCESS(f'OK: SMTP sent test email to {recipient}.'))

    def check_cdek(self, city_code, failures):
        city_code = city_code or str(getattr(settings, 'CDEK_ORIGIN_CITY_CODE', '') or '')
        if not city_code:
            failures.append('CDEK city code is not set. Pass --cdek-city-code.')
            return

        try:
            points = cdek_get('/v2/deliverypoints', {
                'city_code': city_code,
                'type': 'PVZ',
                'is_handout': 'true',
                'size': 1,
            })
        except Exception as exc:
            failures.append(f'CDEK pickup point request failed: {exc}')
            return

        if not points:
            failures.append(f'CDEK returned no pickup points for city_code={city_code}.')
            return

        self.stdout.write(self.style.SUCCESS(f'OK: CDEK returned pickup points for city_code={city_code}.'))

    def check_alfa(self, payment_order_id, failures, warnings):
        if not payment_order_id:
            self.warn(warnings, 'Alfa status check skipped: pass --alfa-order-id with an existing bank order id for full payment smoke.')
            return

        try:
            status = get_payment_status(payment_order_id)
        except AlfaAcquiringError as exc:
            failures.append(f'Alfa status request failed: {exc}')
            return

        order_status = status.get('orderStatus')
        self.stdout.write(self.style.SUCCESS(f'OK: Alfa returned orderStatus={order_status} for {payment_order_id}.'))

    def warn(self, warnings, message):
        warnings.append(message)
