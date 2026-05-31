from datetime import datetime, timezone as dt_timezone

from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .location_services import cdek_enabled, cdek_get
from .models import OrderStatus


DELIVERED_CODES = {'DELIVERED'}
IN_DELIVERY_CODES = {
    'ACCEPTED',
    'CREATED',
    'RECEIVED_AT_SHIPMENT_WAREHOUSE',
    'READY_FOR_SHIPMENT_IN_SENDER_CITY',
    'TAKEN_BY_TRANSPORTER',
    'SENT_TO_TRANSIT_CITY',
    'ACCEPTED_IN_TRANSIT_CITY',
    'READY_FOR_SHIPMENT_IN_TRANSIT_CITY',
    'SENT_TO_DESTINATION_CITY',
    'ARRIVED_AT_DESTINATION_CITY',
    'ACCEPTED_AT_RECIPIENT_CITY_WAREHOUSE',
    'ACCEPTED_AT_PICK_UP_POINT',
}


class CdekTrackingError(RuntimeError):
    pass


def latest_status(statuses):
    if not isinstance(statuses, list) or not statuses:
        return {}

    def status_date(status):
        value = status.get('date_time') or status.get('dateTime') or ''
        parsed = parse_datetime(value) if isinstance(value, str) else None
        return parsed or datetime.min.replace(tzinfo=dt_timezone.utc)

    return max((status for status in statuses if isinstance(status, dict)), key=status_date, default={})


def tracking_entity(response):
    if isinstance(response, dict):
        entity = response.get('entity')
        if isinstance(entity, dict):
            return entity
        if response.get('statuses'):
            return response

    return {}


def fetch_cdek_order(identifier, order_uuid=''):
    if not cdek_enabled():
        raise CdekTrackingError('CDEK API credentials are not configured.')

    identifier = (identifier or '').strip()
    order_uuid = (order_uuid or '').strip()
    if not identifier and not order_uuid:
        raise CdekTrackingError('CDEK tracking number is empty.')

    errors = []
    requests = []
    if order_uuid:
        requests.append((f'/v2/orders/{order_uuid}', {}))
    if identifier:
        requests.extend([
            ('/v2/orders', {'cdek_number': identifier}),
            ('/v2/orders', {'im_number': identifier}),
        ])

    for path, params in requests:
        try:
            response = cdek_get(path, params)
        except Exception as error:
            errors.append(str(error))
            continue

        entity = tracking_entity(response)
        if entity:
            return entity

    message = '; '.join(error for error in errors if error) or 'CDEK order was not found.'
    raise CdekTrackingError(message)


def parse_cdek_tracking(entity):
    status = latest_status(entity.get('statuses'))
    status_date = parse_datetime(status.get('date_time') or status.get('dateTime') or '') if status else None
    if status_date and timezone.is_naive(status_date):
        status_date = timezone.make_aware(status_date, timezone.get_current_timezone())

    return {
        'uuid': entity.get('uuid') or '',
        'cdek_number': entity.get('cdek_number') or entity.get('cdekNumber') or '',
        'status_code': status.get('code') or '',
        'status_name': status.get('name') or '',
        'status_date': status_date,
    }


def apply_tracking_to_order(order, tracking):
    update_fields = [
        'cdek_order_uuid',
        'cdek_status_code',
        'cdek_status_name',
        'cdek_status_updated_at',
        'cdek_tracking_checked_at',
        'updated_at',
    ]
    status_code = tracking.get('status_code') or ''

    if tracking.get('uuid'):
        order.cdek_order_uuid = tracking['uuid']
    if tracking.get('cdek_number') and not order.track_number:
        order.track_number = tracking['cdek_number']
        update_fields.append('track_number')

    order.cdek_status_code = status_code
    order.cdek_status_name = tracking.get('status_name') or status_code
    order.cdek_status_updated_at = tracking.get('status_date')
    order.cdek_tracking_checked_at = timezone.now()

    if status_code in DELIVERED_CODES and order.status != OrderStatus.CANCELED:
        order.status = OrderStatus.COMPLETED
        update_fields.append('status')
    elif (
        status_code in IN_DELIVERY_CODES
        and order.status not in {OrderStatus.WAITING_MANAGER, OrderStatus.WAITING_PAYMENT, OrderStatus.COMPLETED, OrderStatus.CANCELED}
    ):
        order.status = OrderStatus.IN_DELIVERY
        update_fields.append('status')

    order.save(update_fields=sorted(set(update_fields)))
    return order


def sync_order_cdek_tracking(order):
    entity = fetch_cdek_order(order.track_number, order.cdek_order_uuid)
    tracking = parse_cdek_tracking(entity)
    return apply_tracking_to_order(order, tracking)
