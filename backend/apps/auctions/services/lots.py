from django.db import transaction
from django.utils import timezone

from apps.common.exceptions import BusinessError, ErrorCodes
from apps.common.permissions import ensure_auction_participant
from ..models import AuctionLot, AuctionLotStatus


def _product_binding_lot_exists(product, event, exclude_lot=None):
    """A product may be listed in at most one non-terminal lot."""
    queryset = AuctionLot.objects.filter(
        product=product,
    ).exclude(status__in=[AuctionLotStatus.SOLD, AuctionLotStatus.UNSOLD, AuctionLotStatus.CANCELLED])
    if exclude_lot is not None:
        queryset = queryset.exclude(pk=exclude_lot.pk)
    if queryset.filter(auction_event=event).exists():
        return True
    # An editable revision intentionally points at the same products as its
    # immutable approved snapshot, but never twice within the same revision.
    root_id = event.revision_of_id or event.pk
    queryset = queryset.exclude(
        auction_event_id=root_id
    ).exclude(auction_event__revision_of_id=root_id)
    return queryset.exists()


def validate_lot_data(event, product, lot_number, starting_price, minimum_increment,
                      start_time, end_time, exclude_lot=None):
    now = timezone.now()
    if start_time < event.start_time or end_time > event.end_time:
        raise BusinessError(
            ErrorCodes.LOT_TIME_OUTSIDE_EVENT,
            "Lot times must be inside the event window.",
        )
    if end_time <= start_time:
        raise BusinessError("INVALID_TIMES", "Lot end time must be after its start time.")
    if starting_price <= 0:
        raise BusinessError(ErrorCodes.INVALID_AMOUNT, "Starting price must be positive.")
    if minimum_increment <= 0:
        raise BusinessError(ErrorCodes.INVALID_AMOUNT, "Minimum increment must be positive.")
    if _product_binding_lot_exists(product, event, exclude_lot=exclude_lot):
        raise BusinessError(
            ErrorCodes.PRODUCT_ALREADY_LISTED,
            "This product is already listed in another active lot.",
        )
    duplicate_number = AuctionLot.objects.filter(
        auction_event=event, lot_number=lot_number
    ).exclude(pk=exclude_lot.pk if exclude_lot else -1).exists()
    if duplicate_number:
        raise BusinessError(ErrorCodes.LOT_NUMBER_TAKEN, "Lot number already used in this event.")


def add_lot(event, organizer, product, lot_number, starting_price, minimum_increment,
            start_time, end_time):
    ensure_auction_participant(organizer)
    if not event.organizer_can_edit:
        raise BusinessError(
            ErrorCodes.EVENT_NOT_EDITABLE,
            "Lots can only be added while the event is editable (draft or rejected).",
        )
    if event.organizer_id != organizer.id:
        raise BusinessError(ErrorCodes.NOT_OWNER, "You do not own this event.", 403)
    if product.owner_id != organizer.id:
        raise BusinessError(ErrorCodes.NOT_OWNER, "You can only list products you own.", 403)
    validate_lot_data(
        event, product, lot_number, starting_price, minimum_increment, start_time, end_time
    )
    with transaction.atomic():
        lot = AuctionLot.objects.create(
            auction_event=event,
            product=product,
            lot_number=lot_number,
            starting_price=starting_price,
            minimum_increment=minimum_increment,
            start_time=start_time,
            end_time=end_time,
        )
    return lot


def update_lot(event, organizer, lot, data):
    ensure_auction_participant(organizer)
    if not event.organizer_can_edit:
        raise BusinessError(
            ErrorCodes.EVENT_NOT_EDITABLE,
            "Lots can only be changed while the event is editable.",
        )
    if event.organizer_id != organizer.id:
        raise BusinessError(ErrorCodes.NOT_OWNER, "You do not own this event.", 403)
    product = data.get("product", lot.product)
    if product.owner_id != organizer.id:
        raise BusinessError(ErrorCodes.NOT_OWNER, "You can only list products you own.", 403)
    validate_lot_data(
        event,
        product,
        data.get("lot_number", lot.lot_number),
        data.get("starting_price", lot.starting_price),
        data.get("minimum_increment", lot.minimum_increment),
        data.get("start_time", lot.start_time),
        data.get("end_time", lot.end_time),
        exclude_lot=lot,
    )
    with transaction.atomic():
        for field in ("product", "lot_number", "starting_price", "minimum_increment", "start_time", "end_time"):
            if field in data:
                setattr(lot, field, data[field])
        lot.save()
    return lot


def remove_lot(event, organizer, lot):
    ensure_auction_participant(organizer)
    if not event.organizer_can_edit:
        raise BusinessError(
            ErrorCodes.EVENT_NOT_EDITABLE,
            "Lots can only be removed while the event is editable.",
        )
    if event.organizer_id != organizer.id:
        raise BusinessError(ErrorCodes.NOT_OWNER, "You do not own this event.", 403)
    if lot.bids.exists():
        raise BusinessError(
            ErrorCodes.INVALID_TRANSITION,
            "A lot that already received bids cannot be removed.",
        )
    lot.delete()
    return True
