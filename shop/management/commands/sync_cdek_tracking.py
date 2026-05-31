from django.core.management.base import BaseCommand, CommandError

from shop.cdek_tracking import CdekTrackingError, sync_order_cdek_tracking
from shop.models import Order, OrderStatus


class Command(BaseCommand):
    help = 'Sync CDEK tracking statuses for orders with track numbers.'

    def add_arguments(self, parser):
        parser.add_argument('--order', default='', help='Sync only one site order number, for example DT-000123.')
        parser.add_argument('--limit', type=int, default=50, help='Maximum orders to sync.')
        parser.add_argument('--fail-fast', action='store_true', help='Stop on first CDEK error.')

    def handle(self, *args, **options):
        queryset = Order.objects.exclude(track_number='').exclude(status__in=[OrderStatus.COMPLETED, OrderStatus.CANCELED])
        if options['order']:
            queryset = queryset.filter(number=options['order'])

        orders = list(queryset.order_by('cdek_tracking_checked_at', 'updated_at')[:max(1, options['limit'])])
        synced = 0
        failed = 0

        for order in orders:
            try:
                sync_order_cdek_tracking(order)
            except CdekTrackingError as exc:
                failed += 1
                message = f'{order.number}: {exc}'
                if options['fail_fast']:
                    raise CommandError(message)
                self.stderr.write(self.style.WARNING(f'WARN: {message}'))
                continue

            synced += 1
            self.stdout.write(self.style.SUCCESS(f'OK: {order.number} -> {order.cdek_status_name or order.cdek_status_code}'))

        self.stdout.write(f'Synced: {synced}. Failed: {failed}.')
