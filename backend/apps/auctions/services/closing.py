import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction
from django.utils import timezone

from apps.notifications.services import notify
from ..models import (
    AuctionEventStatus,
    AuctionLot,
    AuctionLotStatus,
    BidStatus,
)

logger = logging.getLogger("apps.auctions")


def close_lot(lot_id, force=False):
    """
    Idempotent lot closure.

    - Zero accepted bids  -> UNSOLD
    - One or more accepted bids -> AWAITING_ORDER and exactly one Order created
      (Order.auction_lot is OneToOne; get_or_create makes retries safe).
    """
    with transaction.atomic():
        lot = (
            # The joined organizer may be a deleted (NULL) account. Restrict
            # the lock to the lot instead of attempting to lock an outer join.
            AuctionLot.objects.select_for_update(of=("self",))
            .select_related("auction_event", "auction_event__organizer")
            .get(pk=lot_id)
        )
        if lot.is_terminal or lot.status == AuctionLotStatus.AWAITING_ORDER:
            return {"status": lot.status, "created_order": False, "skipped": True}
        if not force and timezone.now() < lot.end_time:
            return {"status": lot.status, "created_order": False, "skipped": True}
        highest = lot.highest_bid
        created_order = False
        if highest is not None:
            from apps.orders.models import Order, OrderStatus

            order, created = Order.objects.get_or_create(
                auction_lot=lot,
                defaults={
                    "buyer": highest.bidder,
                    "seller": lot.auction_event.organizer,
                    "final_price": highest.amount,
                    "shipping_address": "",
                    "status": OrderStatus.AWAITING_CONFIRMATION,
                },
            )
            created_order = created
            # A winning bid is not a completed sale.  The buyer must submit
            # delivery details and the seller must accept them first.
            lot.status = AuctionLotStatus.AWAITING_ORDER
        else:
            lot.status = AuctionLotStatus.UNSOLD
        lot.save(update_fields=["status", "updated_at"])
        lot_id = lot.pk
        event = lot.auction_event

        event_bidding_finished = not AuctionLot.objects.filter(
            auction_event=event
        ).filter(status__in=[AuctionLotStatus.SCHEDULED, AuctionLotStatus.ACTIVE]).exists()
        event_ended = False
        if event_bidding_finished and event.status == AuctionEventStatus.ACTIVE:
            has_pending_orders = AuctionLot.objects.filter(
                auction_event=event, status=AuctionLotStatus.AWAITING_ORDER
            ).exists()
            event.status = (
                AuctionEventStatus.AWAITING_ORDERS
                if has_pending_orders
                else AuctionEventStatus.ENDED
            )
            event.save(update_fields=["status", "updated_at"])
            event_ended = event.status == AuctionEventStatus.ENDED
        winner_id = highest.bidder_id if highest else None
        winner_name = highest.bidder.username if highest and highest.bidder else None
        order_id = order.pk if highest else None

    # ---- after commit ----------------------------------------------------
    if highest and highest.bidder:
        notify(
            recipient=highest.bidder,
            verb="LOT_WINNER",
            actor=None,
            target=lot,
            message_key="notifications.lot_winner",
            dedupe_key=f"lot_winner_{lot.pk}",
        )
        async_to_sync(_send_user_alert)(highest.bidder.id, {
            "event": "winner",
            "lot_id": lot.pk,
            "order_id": order_id,
            "message_key": "notifications.lot_winner",
        })
    notify(
        recipient=event.organizer,
        verb="LOT_ENDED",
        actor=None,
        target=lot,
        message_key="notifications.lot_ended",
        dedupe_key=f"lot_ended_{lot.pk}",
    )
    async_to_sync(_send_lot_broadcast)(lot.pk, {
        "type": "lot.ended",
        "lot_id": lot.pk,
        "status": lot.status,
        "winner_id": winner_id,
        "winner_username": winner_name,
        "event_ended": event_ended,
    })
    async_to_sync(_send_browse_update)(lot.pk, {"status": lot.status})
    return {"status": lot.status, "created_order": created_order, "skipped": False}


def close_due_lots(now=None):
    now = now or timezone.now()
    due = AuctionLot.objects.filter(
        status=AuctionLotStatus.ACTIVE,
        end_time__lte=now,
    ).values_list("id", flat=True)
    results = []
    for lot_id in due:
        try:
            results.append(close_lot(lot_id))
        except Exception as exc:  # pragma: no cover - task retries will re-raise
            logger.error("close_lot %s failed: %s", lot_id, exc)
            raise
    return results


def activate_due_events(now=None):
    """Move APPROVED/SCHEDULED events (and their lots) to ACTIVE."""
    now = now or timezone.now()
    from ..models import AuctionEvent

    due = AuctionEvent.objects.filter(
        status__in=[AuctionEventStatus.APPROVED, AuctionEventStatus.SCHEDULED],
        start_time__lte=now,
        end_time__gt=now,
    )
    activated = []
    for event in due:
        with transaction.atomic():
            event.status = AuctionEventStatus.ACTIVE
            event.save(update_fields=["status", "updated_at"])
            AuctionLot.objects.filter(
                auction_event=event, status=AuctionLotStatus.SCHEDULED
            ).update(status=AuctionLotStatus.ACTIVE, updated_at=now)
        notify(
            recipient=event.organizer,
            verb="EVENT_ACTIVATED",
            actor=None,
            target=event,
            message_key="notifications.event_activated",
            dedupe_key=f"event_activated_{event.pk}",
        )
        async_to_sync(_send_event_broadcast)(event.pk, {"type": "event.activated", "event_id": event.pk})
        activated.append(event.pk)
    return activated


def closing_soon_alerts(now=None):
    """Warn bidders/savers of lots that end within the closing-soon window."""
    from datetime import timedelta

    from django.conf import settings

    now = now or timezone.now()
    window = timedelta(minutes=settings.AUCTION_CLOSING_SOON_MINUTES)
    lots = AuctionLot.objects.filter(
        status=AuctionLotStatus.ACTIVE,
        end_time__lte=now + window,
        end_time__gt=now,
    ).select_related("auction_event", "auction_event__organizer")
    alerted = 0
    for lot in lots:
        recipients = set()
        recipients.add(lot.auction_event.organizer_id)
        recipients.update(
            lot.bids.filter(status=BidStatus.ACCEPTED).values_list("bidder_id", flat=True)
        )
        recipients.update(lot.saved_by.values_list("user_id", flat=True))
        for recipient_id in recipients:
            if recipient_id is None:
                continue
            notify(
                recipient_id=recipient_id,
                verb="CLOSING_SOON",
                actor=None,
                target=lot,
                message_key="notifications.closing_soon",
                dedupe_key=f"closing_soon_{lot.pk}_{recipient_id}",
            )
            async_to_sync(_send_user_alert)(recipient_id, {
                "event": "closing_soon",
                "lot_id": lot.pk,
                "ends_at": lot.end_time.isoformat(),
                "message_key": "notifications.closing_soon",
            })
            alerted += 1
    return alerted


async def _send_lot_broadcast(lot_id, payload):
    channel_layer = get_channel_layer()
    if channel_layer is not None:
        await channel_layer.group_send(f"lot_{lot_id}", payload)


async def _send_user_alert(user_id, payload):
    channel_layer = get_channel_layer()
    if channel_layer is not None:
        await channel_layer.group_send(f"user_{user_id}", {"type": "lot.alert", **payload})


async def _send_browse_update(lot_id, payload):
    channel_layer = get_channel_layer()
    if channel_layer is not None:
        await channel_layer.group_send(
            "browse_lots", {"type": "lot.price_update", "lot_id": lot_id, **payload}
        )


async def _send_event_broadcast(event_id, payload):
    channel_layer = get_channel_layer()
    if channel_layer is not None:
        await channel_layer.group_send("browse_lots", payload)
