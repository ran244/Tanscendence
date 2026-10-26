import logging

from celery import shared_task

logger = logging.getLogger("apps.auctions")


@shared_task(name="apps.auctions.tasks.auction_tick", bind=True, max_retries=3)
def auction_tick(self):
    """Periodic scheduler: activate due events, close due lots, closing-soon alerts."""
    from django.utils import timezone

    from .services.closing import activate_due_events, close_due_lots, closing_soon_alerts

    now = timezone.now()
    try:
        activated = activate_due_events(now)
        closed = close_due_lots(now)
        alerted = closing_soon_alerts(now)
        return {
            "activated_events": activated,
            "closed_lots": closed,
            "closing_soon_alerts": alerted,
        }
    except Exception as exc:
        logger.error("auction_tick failed: %s", exc)
        raise self.retry(exc=exc, countdown=30)


@shared_task(name="apps.auctions.tasks.activate_event")
def activate_event_task(event_id):
    from .models import AuctionEvent, AuctionEventStatus
    from .services.closing import activate_due_events

    if AuctionEvent.objects.filter(pk=event_id, status__in=[
        AuctionEventStatus.APPROVED, AuctionEventStatus.SCHEDULED
    ]).exists():
        return activate_due_events()
    return []


@shared_task(name="apps.auctions.tasks.close_lot_task")
def close_lot_task(lot_id):
    from .services.closing import close_lot

    return close_lot(lot_id)