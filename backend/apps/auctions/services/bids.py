import logging
from decimal import Decimal, InvalidOperation

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction
from django.utils import timezone

from apps.common.exceptions import BusinessError, ErrorCodes
from apps.common.permissions import ensure_auction_participant
from apps.notifications.services import notify
from ..models import (
    AuctionLot,
    AuctionLotStatus,
    AuctionEventStatus,
    Bid,
    BidStatus,
    RejectionReason,
)

logger = logging.getLogger("apps.auctions")

REJECTION_CODE_MAP = {
    RejectionReason.AUCTION_NOT_ACTIVE: ErrorCodes.AUCTION_NOT_ACTIVE,
    RejectionReason.LOWER_THAN_CURRENT: ErrorCodes.LOWER_THAN_CURRENT,
    RejectionReason.MINIMUM_INCREMENT_NOT_MET: ErrorCodes.MINIMUM_INCREMENT_NOT_MET,
    RejectionReason.SELLER_BIDDING: ErrorCodes.SELLER_BIDDING,
    RejectionReason.BLOCKED_USER: ErrorCodes.BLOCKED_USER,
    RejectionReason.INVALID_AMOUNT: ErrorCodes.INVALID_AMOUNT,
}


class BidRejected(BusinessError):
    """A rejected bid attempt that must still be recorded in the audit trail."""

    def __init__(self, code, message, rejection_reason, field_errors=None):
        super().__init__(code, message, 422, field_errors)
        self.rejection_reason = rejection_reason


def _to_amount(value):
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise BidRejected(
            ErrorCodes.INVALID_AMOUNT,
            "Bid amount must be a positive decimal with at most two decimal places.",
            RejectionReason.INVALID_AMOUNT,
            field_errors={"amount": "Invalid amount."},
        )
    if not amount.is_finite() or amount <= 0 or amount > Decimal("99999999.99"):
        raise BidRejected(
            ErrorCodes.INVALID_AMOUNT,
            "Bid amount must be positive.",
            RejectionReason.INVALID_AMOUNT,
            field_errors={"amount": "Must be positive."},
        )
    if amount.as_tuple().exponent < -2:
        raise BidRejected(
            ErrorCodes.INVALID_AMOUNT,
            "Bid amount supports at most two decimal places.",
            RejectionReason.INVALID_AMOUNT,
            field_errors={"amount": "At most two decimal places."},
        )
    return amount


def place_bid(lot_id, bidder, raw_amount):
    """
    Place a bid inside a locked transaction.

    Validation order (frozen decision #10):
      1. lot/event active and server time inside the window
      2. positive decimal amount (<= 2 decimal places)
      3. amount beats the current price
      4. amount meets the minimum increment
      5. bidder is not the owner/organizer
      6. bidder is not blocked

    Every rejection is recorded as a REJECTED Bid row (audit trail) without
    touching the current winning bid. The database row lock guarantees that
    concurrent bids cannot corrupt `highest_bid`.
    """
    # Authorization failures are not bids and must not create a rejected-bid
    # audit record. Keep this check outside the BidRejected transaction path.
    ensure_auction_participant(bidder)
    try:
        with transaction.atomic():
            lot = (
                # Lock only the lot row. Organizer/product owners are nullable
                # after account deletion, and PostgreSQL cannot apply an
                # unrestricted FOR UPDATE across those outer joins.
                AuctionLot.objects.select_for_update(of=("self",))
                .select_related("auction_event", "auction_event__organizer", "product", "product__owner")
                .get(pk=lot_id)
            )
            now = timezone.now()

            if (
                lot.status != AuctionLotStatus.ACTIVE
                or lot.auction_event.status != AuctionEventStatus.ACTIVE
                or not (lot.start_time <= now <= lot.end_time)
            ):
                raise BidRejected(
                    ErrorCodes.AUCTION_NOT_ACTIVE,
                    "This lot is not accepting bids right now.",
                    RejectionReason.AUCTION_NOT_ACTIVE,
                )

            amount = _to_amount(raw_amount)
            current_price = lot.current_price
            if amount <= current_price:
                raise BidRejected(
                    ErrorCodes.LOWER_THAN_CURRENT,
                    "Your bid must be higher than the current price.",
                    RejectionReason.LOWER_THAN_CURRENT,
                    field_errors={"amount": "Must exceed the current price."},
                )
            if amount < lot.minimum_next_bid:
                raise BidRejected(
                    ErrorCodes.MINIMUM_INCREMENT_NOT_MET,
                    f"Your bid must be at least the minimum increment above the current price "
                    f"({lot.minimum_next_bid}).",
                    RejectionReason.MINIMUM_INCREMENT_NOT_MET,
                    field_errors={"amount": "Minimum increment not met."},
                )
            if bidder.id in (lot.auction_event.organizer_id, lot.product.owner_id):
                raise BidRejected(
                    ErrorCodes.SELLER_BIDDING,
                    "You cannot bid on your own lot.",
                    RejectionReason.SELLER_BIDDING,
                )
            if bidder.is_blocked:
                raise BidRejected(
                    ErrorCodes.BLOCKED_USER,
                    "Your account is blocked from bidding.",
                    RejectionReason.BLOCKED_USER,
                )

            previous_winner_id = lot.highest_bid.bidder_id if lot.highest_bid else None
            bid = Bid.objects.create(auction_lot=lot, bidder=bidder, amount=amount)
            lot.highest_bid = bid
            lot.save(update_fields=["highest_bid", "updated_at"])
            lot_id = lot.pk
            lot_snapshot = {
                "id": lot.id,
                "current_price": str(bid.amount),
                "minimum_next_bid": str(amount + lot.minimum_increment),
                "bid_count": lot.bids.filter(status=BidStatus.ACCEPTED).count(),
                "status": lot.status,
            }
            event_pk = lot.auction_event_id
    except BidRejected as error:
        # Recording inside the rejected transaction would be rolled back with
        # the exception. Persist the audit row in its own successful transaction.
        Bid.objects.create(
            auction_lot_id=lot_id,
            bidder=bidder,
            amount=_safe_amount(raw_amount),
            status=BidStatus.REJECTED,
            rejection_reason=error.rejection_reason,
        )
        raise

    # ---- after commit: broadcasts + persistent notifications -------------
    if previous_winner_id and previous_winner_id != bidder.id:
        notify(
            recipient_id=previous_winner_id,
            verb="OUTBID",
            actor=bidder,
            target=lot,
            message_key="notifications.outbid",
            dedupe_key=None,
        )
        async_to_sync(_send_user_alert)(previous_winner_id, {
            "event": "outbid",
            "lot_id": lot_id,
            "message_key": "notifications.outbid",
        })
    async_to_sync(_send_lot_broadcast)(lot_id, {
        "type": "bid.accepted",
        "bid": {
            "id": bid.id,
            "bidder_id": bidder.id,
            "bidder_username": bidder.username,
            "amount": str(bid.amount),
            "created_at": bid.created_at.isoformat(),
        },
        "current_price": lot_snapshot["current_price"],
        "minimum_next_bid": lot_snapshot["minimum_next_bid"],
        "bid_count": lot_snapshot["bid_count"],
        "event_id": event_pk,
    })
    async_to_sync(_send_browse_update)(lot_id, lot_snapshot)
    return bid, lot_snapshot


def _safe_amount(raw_amount):
    try:
        amount = Decimal(str(raw_amount))
        if not amount.is_finite() or amount <= 0 or amount > Decimal("99999999.99"):
            return Decimal("0")
        return amount.quantize(Decimal("0.01"))
    except Exception:
        return Decimal("0")


async def _send_lot_broadcast(lot_id, payload):
    channel_layer = get_channel_layer()
    if channel_layer is not None:
        await channel_layer.group_send(f"lot_{lot_id}", payload)


async def _send_browse_update(lot_id, snapshot):
    channel_layer = get_channel_layer()
    if channel_layer is not None:
        await channel_layer.group_send(
            "browse_lots",
            {
                "type": "lot.price_update",
                "lot_id": lot_id,
                "current_price": snapshot["current_price"],
                "minimum_next_bid": snapshot["minimum_next_bid"],
                "bid_count": snapshot["bid_count"],
                "status": snapshot["status"],
            },
        )


async def _send_user_alert(user_id, payload):
    channel_layer = get_channel_layer()
    if channel_layer is not None:
        await channel_layer.group_send(f"user_{user_id}", {"type": "lot.alert", **payload})
