from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.common.exceptions import BusinessError, ErrorCodes
from apps.common.permissions import ensure_auction_participant
from apps.notifications.models import NotificationVerb
from apps.notifications.services import notify, notify_admins
from ..models import (
    AuctionCancellationRequest,
    AuctionEvent,
    AuctionEventStatus,
    AuctionLotStatus,
    CancellationRequestStatus,
)


CANCELLABLE_EVENT_STATUSES = (
    AuctionEventStatus.APPROVED,
    AuctionEventStatus.SCHEDULED,
)


def _validate_request_window(event, now, *, review=False):
    if event.status not in CANCELLABLE_EVENT_STATUSES:
        raise BusinessError(
            "EVENT_NOT_CANCELLABLE",
            "Only an approved, scheduled auction can use the cancellation request process.",
        )
    if now > event.editing_deadline:
        raise BusinessError(
            "CANCELLATION_REQUEST_TOO_LATE",
            "Cancellation must be requested and approved at least 24 hours before the auction starts.",
            409 if review else 400,
        )


def request_cancellation(event, requester, reason):
    ensure_auction_participant(requester)
    reason = str(reason or "").strip()
    if not reason:
        raise BusinessError("REASON_REQUIRED", "A cancellation reason is required.")

    try:
        with transaction.atomic():
            event = AuctionEvent.objects.select_for_update().get(pk=event.pk)
            if event.organizer_id != requester.id:
                raise BusinessError(ErrorCodes.NOT_OWNER, "You do not own this event.", 403)
            _validate_request_window(event, timezone.now())
            if event.cancellation_requests.filter(
                status=CancellationRequestStatus.PENDING
            ).exists():
                raise BusinessError(
                    "CANCELLATION_REQUEST_PENDING",
                    "A cancellation request for this auction is already awaiting review.",
                    409,
                )
            cancellation_request = AuctionCancellationRequest.objects.create(
                auction_event=event,
                requester=requester,
                reason=reason,
            )
    except IntegrityError:
        raise BusinessError(
            "CANCELLATION_REQUEST_PENDING",
            "A cancellation request for this auction is already awaiting review.",
            409,
        )

    notify_admins(
        actor=requester,
        verb=NotificationVerb.EVENT_CANCELLATION_REQUESTED,
        target=cancellation_request,
        message_key="notifications.event_cancellation_requested",
        dedupe_key=f"event_cancel_request_{cancellation_request.pk}",
    )
    return cancellation_request


def approve_cancellation(cancellation_request, admin):
    now = timezone.now()
    with transaction.atomic():
        cancellation_request = (
            # Requesters are nullable once an account has been deleted. Lock
            # the request row without locking the nullable joined user row.
            AuctionCancellationRequest.objects.select_for_update(of=("self",))
            .select_related("auction_event", "requester")
            .get(pk=cancellation_request.pk)
        )
        event = AuctionEvent.objects.select_for_update().get(
            pk=cancellation_request.auction_event_id
        )
        if cancellation_request.status != CancellationRequestStatus.PENDING:
            raise BusinessError(
                ErrorCodes.INVALID_TRANSITION,
                "Only a pending cancellation request can be approved.",
            )
        _validate_request_window(event, now, review=True)
        event.lots.exclude(
            status__in=[AuctionLotStatus.SOLD, AuctionLotStatus.UNSOLD]
        ).update(status=AuctionLotStatus.CANCELLED, updated_at=now)
        event.status = AuctionEventStatus.CANCELLED
        event.save(update_fields=["status", "updated_at"])
        cancellation_request.status = CancellationRequestStatus.APPROVED
        cancellation_request.reviewed_by = admin
        cancellation_request.reviewed_at = now
        cancellation_request.review_reason = ""
        cancellation_request.save(
            update_fields=[
                "status",
                "reviewed_by",
                "reviewed_at",
                "review_reason",
                "updated_at",
            ]
        )

    notify(
        recipient=cancellation_request.requester,
        actor=admin,
        verb=NotificationVerb.EVENT_CANCELLATION_APPROVED,
        target=event,
        message_key="notifications.event_cancellation_approved",
        dedupe_key=f"event_cancel_approved_{cancellation_request.pk}",
    )
    return cancellation_request


def reject_cancellation(cancellation_request, admin, reason):
    reason = str(reason or "").strip()
    if not reason:
        raise BusinessError("REASON_REQUIRED", "A rejection reason is required.")
    with transaction.atomic():
        cancellation_request = (
            AuctionCancellationRequest.objects.select_for_update(of=("self",))
            .select_related("auction_event", "requester")
            .get(pk=cancellation_request.pk)
        )
        if cancellation_request.status != CancellationRequestStatus.PENDING:
            raise BusinessError(
                ErrorCodes.INVALID_TRANSITION,
                "Only a pending cancellation request can be rejected.",
            )
        cancellation_request.status = CancellationRequestStatus.REJECTED
        cancellation_request.reviewed_by = admin
        cancellation_request.reviewed_at = timezone.now()
        cancellation_request.review_reason = reason
        cancellation_request.save(
            update_fields=[
                "status",
                "reviewed_by",
                "reviewed_at",
                "review_reason",
                "updated_at",
            ]
        )

    notify(
        recipient=cancellation_request.requester,
        actor=admin,
        verb=NotificationVerb.EVENT_CANCELLATION_REJECTED,
        target=cancellation_request.auction_event,
        message_key="notifications.event_cancellation_rejected",
        dedupe_key=f"event_cancel_rejected_{cancellation_request.pk}",
    )
    return cancellation_request
