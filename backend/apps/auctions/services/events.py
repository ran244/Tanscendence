from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.common.exceptions import BusinessError, ErrorCodes
from apps.common.permissions import ensure_auction_participant
from apps.notifications.services import notify, notify_admins
from ..models import (
    AuctionEvent,
    AuctionEventStatus,
    AuctionLot,
    AuctionLotStatus,
)


class EventValidation:
    """Shared event/lot time validations."""

    @staticmethod
    def validate_event_window(start_time, end_time):
        now = timezone.now()
        if end_time <= start_time:
            raise BusinessError("INVALID_TIMES", "End time must be after start time.")
        if start_time <= now + timedelta(seconds=settings.AUCTION_MIN_START_DELAY):
            raise BusinessError(
                "START_TOO_SOON",
                f"Events must start at least {settings.AUCTION_MIN_START_DELAY // 60} minutes in the future.",
            )
        duration = end_time - start_time
        min_duration = getattr(settings, "MIN_EVENT_DURATION", timedelta(minutes=30))
        max_duration = getattr(settings, "MAX_EVENT_DURATION", timedelta(hours=24))
        if duration < min_duration:
            raise BusinessError("EVENT_TOO_SHORT", "Event duration must be at least 30 minutes.")
        if duration > max_duration:
            raise BusinessError("EVENT_TOO_LONG", "Event duration cannot exceed 24 hours.")


def create_event(organizer, title, description, start_time, end_time):
    ensure_auction_participant(organizer)
    EventValidation.validate_event_window(start_time, end_time)
    with transaction.atomic():
        return AuctionEvent.objects.create(
            organizer=organizer,
            title=title,
            description=description,
            start_time=start_time,
            end_time=end_time,
        )


def update_event(event, organizer, data):
    ensure_auction_participant(organizer)
    if not event.organizer_can_edit:
        raise BusinessError(
            ErrorCodes.EVENT_LOCKED,
            "The event is locked. Only draft or rejected events can be edited.",
        )
    if timezone.now() > event.editing_deadline:
        raise BusinessError(
            "EDITING_CLOSED",
            "An auction can only be updated/edited at least 24 hours before it starts.",
        )
    if event.organizer_id != organizer.id:
        raise BusinessError(ErrorCodes.NOT_OWNER, "You do not own this event.", 403)
    if "start_time" in data or "end_time" in data:
        start = data.get("start_time", event.start_time)
        end = data.get("end_time", event.end_time)
        EventValidation.validate_event_window(start, end)
    with transaction.atomic():
        old_start, old_end = event.start_time, event.end_time
        for field in ("title", "description", "start_time", "end_time"):
            if field in data:
                setattr(event, field, data[field])
        event.save()
        # Lots commonly use the full event window. Move those boundaries with
        # the event so an organizer can edit the schedule in one operation.
        if "start_time" in data:
            event.lots.filter(start_time=old_start).update(start_time=event.start_time)
        if "end_time" in data:
            event.lots.filter(end_time=old_end).update(end_time=event.end_time)
        _revalidate_lots(event)
    return event


def create_revision(event, organizer):
    """Create an editable snapshot without changing the approved record."""
    ensure_auction_participant(organizer)
    if event.organizer_id != organizer.id:
        raise BusinessError(ErrorCodes.NOT_OWNER, "You do not own this event.", 403)
    if event.status not in (
        AuctionEventStatus.APPROVED,
        AuctionEventStatus.SCHEDULED,
    ):
        raise BusinessError(
            ErrorCodes.INVALID_TRANSITION,
            "Only an approved or scheduled event can be revised.",
        )
    root = event.revision_of or event
    if root.revisions.filter(
        status__in=[
            AuctionEventStatus.DRAFT,
            AuctionEventStatus.REJECTED,
            AuctionEventStatus.PENDING_APPROVAL,
        ]
    ).exists():
        raise BusinessError(
            "REVISION_EXISTS",
            "This event already has an editable or pending revision.",
        )
    with transaction.atomic():
        revision = AuctionEvent.objects.create(
            revision_of=root,
            revision_number=max(
                [root.revision_number, *root.revisions.values_list("revision_number", flat=True)]
            ) + 1,
            organizer=event.organizer,
            title=event.title,
            description=event.description,
            start_time=event.start_time,
            end_time=event.end_time,
        )
        AuctionLot.objects.bulk_create(
            [
                AuctionLot(
                    auction_event=revision,
                    product=lot.product,
                    lot_number=lot.lot_number,
                    starting_price=lot.starting_price,
                    minimum_increment=lot.minimum_increment,
                    start_time=lot.start_time,
                    end_time=lot.end_time,
                )
                for lot in event.lots.all()
            ]
        )
    return revision


def discard_draft(event, organizer):
    """Permanently discard private work that was never submitted."""
    ensure_auction_participant(organizer)
    if event.organizer_id != organizer.id:
        raise BusinessError(ErrorCodes.NOT_OWNER, "You do not own this event.", 403)
    if event.status != AuctionEventStatus.DRAFT:
        raise BusinessError(
            ErrorCodes.INVALID_TRANSITION,
            "Only a draft can be discarded. Submitted auctions must use cancellation.",
        )
    with transaction.atomic():
        product_ids = list(event.lots.values_list("product_id", flat=True))
        event.lots.all().delete()
        event.delete()
        # Products created solely for this private draft are implementation
        # details too; remove them when no other auction references them.
        from apps.products.models import Product

        Product.objects.filter(pk__in=product_ids, owner=organizer).filter(
            auction_lots__isnull=True
        ).delete()


def _revalidate_lots(event):
    """Ensure lot windows still fit inside the (possibly changed) event window."""
    for lot in event.lots.select_related("auction_event"):
        if lot.start_time < event.start_time or lot.end_time > event.end_time:
            raise BusinessError(
                ErrorCodes.LOT_TIME_OUTSIDE_EVENT,
                f"Lot {lot.lot_number} time window no longer fits inside the event.",
            )


def submit_event(event, organizer):
    ensure_auction_participant(organizer)
    if event.organizer_id != organizer.id:
        raise BusinessError(ErrorCodes.NOT_OWNER, "You do not own this event.", 403)
    if event.status not in (AuctionEventStatus.DRAFT, AuctionEventStatus.REJECTED):
        raise BusinessError(
            ErrorCodes.INVALID_TRANSITION, "Only draft or rejected events can be submitted."
        )
    lots = list(event.lots.select_related("product"))
    if not lots:
        raise BusinessError("NO_LOTS", "Add at least one lot before submitting the event.")
    EventValidation.validate_event_window(event.start_time, event.end_time)
    for lot in lots:
        if lot.start_time < event.start_time or lot.end_time > event.end_time:
            raise BusinessError(
                ErrorCodes.LOT_TIME_OUTSIDE_EVENT,
                f"Lot {lot.lot_number} time window is outside the event window.",
            )
        if lot.starting_price <= 0 or lot.minimum_increment <= 0:
            raise BusinessError("INVALID_PRICE", f"Lot {lot.lot_number} has an invalid price.")
    with transaction.atomic():
        event.status = AuctionEventStatus.PENDING_APPROVAL
        event.submitted_at = timezone.now()
        event.rejection_reason = ""
        event.save(update_fields=["status", "submitted_at", "rejection_reason", "updated_at"])
    notify(
        recipient=event.organizer,
        verb="EVENT_SUBMITTED",
        actor=event.organizer,
        target=event,
        message_key="notifications.event_submitted",
        dedupe_key=f"event_submitted_{event.pk}",
    )
    notify_admins(
        actor=event.organizer,
        verb="EVENT_SUBMITTED",
        target=event,
        message_key="notifications.admin_event_submitted",
        dedupe_key=f"admin_event_submitted_{event.pk}",
    )
    return event


def approve_event(event, admin):
    if event.status != AuctionEventStatus.PENDING_APPROVAL:
        raise BusinessError(
            ErrorCodes.INVALID_TRANSITION, "Only pending events can be approved."
        )
    if timezone.now() >= event.start_time:
        raise BusinessError("EVENT_STARTED", "The event start time has already passed.")
    with transaction.atomic():
        if event.revision_of_id:
            previous = (
                AuctionEvent.objects.select_for_update()
                .filter(
                    Q(pk=event.revision_of_id) | Q(revision_of_id=event.revision_of_id),
                    status__in=[AuctionEventStatus.APPROVED, AuctionEventStatus.SCHEDULED],
                )
                .exclude(pk=event.pk)
                .order_by("-revision_number")
                .first()
            )
            if previous and previous.status in (
                AuctionEventStatus.APPROVED,
                AuctionEventStatus.SCHEDULED,
            ):
                previous.status = AuctionEventStatus.SUPERSEDED
                previous.save(update_fields=["status", "updated_at"])
                previous.lots.exclude(
                    status__in=[AuctionLotStatus.SOLD, AuctionLotStatus.UNSOLD]
                ).update(status=AuctionLotStatus.CANCELLED, updated_at=timezone.now())
        # The event already has its start time, so approval schedules it.
        event.status = AuctionEventStatus.SCHEDULED
        event.reviewed_by = admin
        event.reviewed_at = timezone.now()
        event.rejection_reason = ""
        event.save(
            update_fields=["status", "reviewed_by", "reviewed_at", "rejection_reason", "updated_at"]
        )
    notify(
        recipient=event.organizer,
        verb="EVENT_APPROVED",
        actor=admin,
        target=event,
        message_key="notifications.event_approved",
        dedupe_key=f"event_approved_{event.pk}",
    )
    return event


def reject_event(event, admin, reason):
    if event.status != AuctionEventStatus.PENDING_APPROVAL:
        raise BusinessError(
            ErrorCodes.INVALID_TRANSITION, "Only pending events can be rejected."
        )
    if not reason or not reason.strip():
        raise BusinessError("REASON_REQUIRED", "A rejection reason is required.")
    with transaction.atomic():
        event.status = AuctionEventStatus.REJECTED
        event.reviewed_by = admin
        event.reviewed_at = timezone.now()
        event.rejection_reason = reason.strip()
        event.save(
            update_fields=["status", "reviewed_by", "reviewed_at", "rejection_reason", "updated_at"]
        )
    notify(
        recipient=event.organizer,
        verb="EVENT_REJECTED",
        actor=admin,
        target=event,
        message_key="notifications.event_rejected",
        dedupe_key=f"event_rejected_{event.pk}",
    )
    return event


def cancel_event(event, user, reason=""):
    """Explicit cancel transitions.

    - Drafts are discarded through the delete workflow and never cancelled.
    - Organizer may directly cancel REJECTED/PENDING_APPROVAL events.
    - APPROVED/SCHEDULED events use the 24-hour cancellation request workflow.
    - Admin may cancel any event that has not ended, and must provide a reason.
    """
    now = timezone.now()
    is_admin = user.is_admin
    if event.status in (
        AuctionEventStatus.ENDED,
        AuctionEventStatus.CANCELLED,
        AuctionEventStatus.SUPERSEDED,
    ):
        raise BusinessError(
            ErrorCodes.INVALID_TRANSITION,
            "Ended or already-cancelled events cannot be cancelled.",
        )
    if not is_admin:
        if event.organizer_id != user.id:
            raise BusinessError(ErrorCodes.NOT_OWNER, "You do not own this event.", 403)
        if event.status == AuctionEventStatus.DRAFT:
            raise BusinessError(
                ErrorCodes.INVALID_TRANSITION,
                "Drafts are private work. Discard the draft instead of cancelling it.",
            )
        if event.status in (AuctionEventStatus.APPROVED, AuctionEventStatus.SCHEDULED):
            raise BusinessError(
                "CANCELLATION_REVIEW_REQUIRED",
                "Approved auctions require an administrator-reviewed cancellation request.",
            )
        if event.status not in (
            AuctionEventStatus.REJECTED,
            AuctionEventStatus.PENDING_APPROVAL,
        ):
            raise BusinessError(
                ErrorCodes.INVALID_TRANSITION,
                "This auction can no longer be cancelled by its organizer.",
            )
    else:
        if not reason.strip():
            raise BusinessError("REASON_REQUIRED", "An admin cancellation reason is required.")
    with transaction.atomic():
        lots = event.lots.exclude(status__in=[AuctionLotStatus.SOLD, AuctionLotStatus.UNSOLD])
        lots.update(status=AuctionLotStatus.CANCELLED, updated_at=now)
        event.status = AuctionEventStatus.CANCELLED
        event.save(update_fields=["status", "updated_at"])
    notify(
        recipient=event.organizer,
        verb="EVENT_CANCELLED",
        actor=user,
        target=event,
        message_key="notifications.event_cancelled",
        dedupe_key=f"event_cancelled_{event.pk}",
    )
    return event
