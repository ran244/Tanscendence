from django.db import transaction
from django.utils import timezone

from apps.common.exceptions import BusinessError, ErrorCodes
from apps.notifications.services import notify
from .models import Order, OrderStatus, Payment, PaymentStatus


FULFILLMENT_TRANSITIONS = {
    OrderStatus.CONFIRMED: {OrderStatus.PROCESSING, OrderStatus.DELIVERED},
    OrderStatus.PROCESSING: {OrderStatus.SHIPPED},
    OrderStatus.SHIPPED: {OrderStatus.DELIVERED, OrderStatus.CANCELLED},
}


def confirm_cash_on_delivery(order, buyer, delivery_details):
    """Confirm the winner's address and create the single COD collection record."""
    if order.buyer_id != buyer.id:
        raise BusinessError(ErrorCodes.NOT_OWNER, "Not your order.", 403)
    address = (delivery_details.get("shipping_address") or "").strip()
    if not address:
        raise BusinessError("ADDRESS_REQUIRED", "A shipping address is required.")
    if order.status == OrderStatus.CONFIRMED:
        return order.cash_on_delivery
    if order.status != OrderStatus.AWAITING_CONFIRMATION:
        raise BusinessError("ORDER_NOT_CONFIRMABLE", "This order cannot be confirmed for cash on delivery.")

    with transaction.atomic():
        locked = Order.objects.select_for_update().get(pk=order.pk)
        if locked.status == OrderStatus.CONFIRMED:
            return locked.cash_on_delivery
        if locked.status != OrderStatus.AWAITING_CONFIRMATION:
            raise BusinessError("ORDER_NOT_CONFIRMABLE", "This order cannot be confirmed for cash on delivery.")
        locked.shipping_address = address
        locked.delivery_full_name = delivery_details.get("delivery_full_name", "").strip()
        locked.delivery_city = delivery_details.get("delivery_city", "").strip()
        locked.delivery_phone = delivery_details.get("delivery_phone", "").strip()
        locked.preferred_delivery_at = delivery_details.get("preferred_delivery_at")
        locked.delivery_notes = delivery_details.get("delivery_notes", "").strip()
        locked.status = OrderStatus.CONFIRMED
        locked.save(update_fields=[
            "shipping_address", "delivery_full_name", "delivery_city",
            "delivery_phone", "preferred_delivery_at", "delivery_notes",
            "status", "updated_at",
        ])
        collection, _ = Payment.objects.get_or_create(
            order=locked,
            defaults={"amount": locked.final_price, "status": PaymentStatus.PENDING},
        )

    notify(
        recipient=locked.seller,
        actor=buyer,
        verb="COD_CONFIRMED",
        target=locked,
        message_key="notifications.cod_confirmed",
        dedupe_key=f"cod_confirmed_{locked.pk}",
    )
    return collection


def update_fulfillment(order, seller, new_status, collection_note=""):
    if order.seller_id != seller.id:
        raise BusinessError(ErrorCodes.NOT_OWNER, "Not your sale.", 403)
    allowed = FULFILLMENT_TRANSITIONS.get(order.status, set())
    if new_status not in allowed:
        raise BusinessError(ErrorCodes.INVALID_TRANSITION, f"Cannot move order from {order.status} to {new_status}.")
    collection_note = (collection_note or "").strip()
    if new_status == OrderStatus.CANCELLED and not collection_note:
        raise BusinessError("COLLECTION_NOTE_REQUIRED", "Explain why cash could not be collected.")
    with transaction.atomic():
        order.status = new_status
        order.save(update_fields=["status", "updated_at"])
        if new_status in (OrderStatus.DELIVERED, OrderStatus.CANCELLED):
            collection = Payment.objects.select_for_update().get(order=order)
            collection.status = (
                PaymentStatus.COLLECTED
                if new_status == OrderStatus.DELIVERED
                else PaymentStatus.NOT_COLLECTED
            )
            collection.collected_at = (
                timezone.now() if new_status == OrderStatus.DELIVERED else None
            )
            collection.collection_note = collection_note
            collection.save(update_fields=["status", "collected_at", "collection_note"])
        if new_status in (OrderStatus.DELIVERED, OrderStatus.CANCELLED):
            _resolve_auction_order(order, completed=new_status == OrderStatus.DELIVERED)
    verb = {
        OrderStatus.SHIPPED: "ORDER_SHIPPED",
        OrderStatus.DELIVERED: "ORDER_DELIVERED",
        OrderStatus.CANCELLED: "ORDER_CANCELLED",
    }.get(new_status)
    if verb is None:
        return order
    notify(
        recipient=order.buyer,
        actor=seller,
        verb=verb,
        target=order,
        message_key=f"notifications.{verb.lower()}",
        dedupe_key=f"order_{order.pk}_{new_status}",
    )
    return order


def cancel_order(order, buyer):
    if order.buyer_id != buyer.id:
        raise BusinessError(ErrorCodes.NOT_OWNER, "Not your order.", 403)
    if order.status != OrderStatus.AWAITING_CONFIRMATION:
        raise BusinessError(ErrorCodes.INVALID_TRANSITION, "Only an unconfirmed order can be cancelled.")
    with transaction.atomic():
        order.status = OrderStatus.CANCELLED
        order.save(update_fields=["status", "updated_at"])
        _resolve_auction_order(order, completed=False)
    notify(
        recipient=order.seller,
        actor=buyer,
        verb="ORDER_CANCELLED",
        target=order,
        message_key="notifications.order_cancelled",
        dedupe_key=f"order_cancelled_{order.pk}",
    )
    return order


def _resolve_auction_order(order, completed):
    """Resolve the lot, then end its event once every winning order is resolved."""
    from apps.auctions.models import (
        AuctionEvent,
        AuctionEventStatus,
        AuctionLot,
        AuctionLotStatus,
    )

    lot = AuctionLot.objects.select_for_update().get(pk=order.auction_lot_id)
    lot.status = AuctionLotStatus.SOLD if completed else AuctionLotStatus.UNSOLD
    lot.save(update_fields=["status", "updated_at"])
    event = AuctionEvent.objects.select_for_update().get(pk=lot.auction_event_id)
    unresolved = event.lots.filter(
        status__in=[
            AuctionLotStatus.SCHEDULED,
            AuctionLotStatus.ACTIVE,
            AuctionLotStatus.AWAITING_ORDER,
        ]
    ).exists()
    event.status = (
        AuctionEventStatus.AWAITING_ORDERS if unresolved else AuctionEventStatus.ENDED
    )
    event.save(update_fields=["status", "updated_at"])
