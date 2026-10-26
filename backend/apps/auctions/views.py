from django.db import transaction
from django.db.models import Count, DecimalField, Exists, F, OuterRef, Q
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import filters as drf_filters
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.common.exceptions import BusinessError, business_error_response
from apps.common.pagination import StandardResultsSetPagination
from apps.common.permissions import (
    IsAdmin,
    IsAuctionParticipant,
    IsAuctionParticipantOrReadOnly,
)
from apps.common.throttling import BidThrottle
from .models import (
    AuctionEvent,
    AuctionEventStatus,
    AuctionCancellationRequest,
    AuctionLot,
    AuctionLotStatus,
    Bid,
    BidStatus,
    RejectionReason,
    SavedLot,
)
from .serializers import (
    AdminBidTrackingFilterSerializer,
    AdminBidTrackingSerializer,
    BidSerializer,
    EventSerializer,
    EventWriteSerializer,
    CancellationRequestSerializer,
    LotDetailSerializer,
    LotSummarySerializer,
    MyBidSerializer,
    LotWriteSerializer,
)
from .services import bids as bid_service
from .services import cancellations as cancellation_service
from .services import closing as closing_service
from .services import events as event_service
from .services import lots as lot_service


def _handle(fn):
    def wrapper(request, *args, **kwargs):
        try:
            return fn(request, *args, **kwargs)
        except BusinessError as error:
            return business_error_response(error, request)

    return wrapper


def _annotate_lots(queryset, user):
    """Common annotations used across browse/detail endpoints."""
    if user.is_authenticated:
        queryset = queryset.annotate(
            saved_by_me=Exists(
                SavedLot.objects.filter(lot=OuterRef("pk"), user=user)
            )
        )
    else:
        queryset = queryset.annotate(saved_by_me=Count("id", filter=Q(pk=None)))
    return queryset.annotate(
        accepted_bid_count=Count(
            "bids", filter=Q(bids__status=BidStatus.ACCEPTED), distinct=True
        ),
        current_price_value=Coalesce(
            F("highest_bid__amount"),
            F("starting_price"),
            output_field=DecimalField(max_digits=10, decimal_places=2),
        ),
    )


def _lot_queryset(user):
    return _annotate_lots(
        AuctionLot.objects.select_related(
            "auction_event", "product", "product__owner", "product__category", "highest_bid"
        ).prefetch_related("product__images", "saved_by"),
        user,
    )


def _public_lot_queryset(user):
    """Only expose lots belonging to auctions approved for public viewing."""
    return _lot_queryset(user).filter(
        auction_event__status__in=[
            AuctionEventStatus.SCHEDULED,
            AuctionEventStatus.ACTIVE,
            AuctionEventStatus.AWAITING_ORDERS,
            AuctionEventStatus.ENDED,
        ],
        status__in=[
            AuctionLotStatus.SCHEDULED,
            AuctionLotStatus.ACTIVE,
            AuctionLotStatus.AWAITING_ORDER,
            AuctionLotStatus.SOLD,
            AuctionLotStatus.UNSOLD,
        ],
    )


# ---------------------------------------------------------------------------
# Public browse
# ---------------------------------------------------------------------------

@api_view(["GET"])
@permission_classes([AllowAny])
def browse_events(request):
    queryset = (
        AuctionEvent.objects.filter(
            status__in=[
                AuctionEventStatus.SCHEDULED,
                AuctionEventStatus.ACTIVE,
                AuctionEventStatus.ENDED,
            ]
        )
        .select_related("organizer", "reviewed_by")
        .prefetch_related("lots", "lots__product", "lots__product__images")
        .order_by("start_time", "pk")
    )
    paginator = StandardResultsSetPagination()
    page = paginator.paginate_queryset(queryset, request)
    return paginator.get_paginated_response(
        EventSerializer(page, many=True, context={"request": request}).data
    )

@api_view(["GET"])
@permission_classes([AllowAny])
def browse_lots(request):
    queryset = _public_lot_queryset(request.user)
    status_param = request.query_params.get("status")
    if status_param:
        statuses = [s.strip().upper() for s in status_param.split(",") if s.strip()]
        queryset = queryset.filter(status__in=statuses)
    category = request.query_params.get("category")
    if category:
        queryset = queryset.filter(product__category_id=category)
    search = request.query_params.get("search")
    if search:
        queryset = queryset.filter(
            Q(product__name__icontains=search)
            | Q(auction_event__title__icontains=search)
            | Q(product__description__icontains=search)
        )
    price_min = request.query_params.get("price_min")
    if price_min:
        try:
            queryset = queryset.filter(highest_bid__amount__gte=price_min) | queryset.filter(
                highest_bid__isnull=True, starting_price__gte=price_min
            )
        except ValueError:
            pass
    price_max = request.query_params.get("price_max")
    if price_max:
        try:
            queryset = queryset.filter(highest_bid__amount__lte=price_max) | queryset.filter(
                highest_bid__isnull=True, starting_price__lte=price_max
            )
        except ValueError:
            pass
    ordering = request.query_params.get("ordering", "-created_at")
    allowed_ordering = {
        "current_price",
        "-current_price",
        "end_time",
        "-end_time",
        "bid_count",
        "-bid_count",
        "start_time",
        "-start_time",
        "created_at",
        "-created_at",
        "lot_number",
        "-lot_number",
    }
    if ordering in allowed_ordering:
        if ordering in ("bid_count", "-bid_count"):
            queryset = queryset.order_by(ordering.replace("bid_count", "accepted_bid_count"))
        else:
            queryset = queryset.order_by(
                ordering.replace("current_price", "current_price_value")
            )
    paginator = StandardResultsSetPagination()
    page = paginator.paginate_queryset(queryset, request)
    return paginator.get_paginated_response(
        LotSummarySerializer(page, many=True, context={"request": request}).data
    )


@api_view(["GET"])
@permission_classes([AllowAny])
def lot_detail(request, lot_id):
    lot = get_object_or_404(_public_lot_queryset(request.user), pk=lot_id)
    accepted_bids = (
        lot.bids.filter(status=BidStatus.ACCEPTED)
        .select_related("bidder")
        .order_by("-created_at")[:20]
    )
    data = LotDetailSerializer(lot, context={"request": request}).data
    data["recent_bids"] = BidSerializer(accepted_bids, many=True).data
    return Response(data)


@api_view(["GET"])
@permission_classes([AllowAny])
def lot_bids(request, lot_id):
    lot = get_object_or_404(_public_lot_queryset(request.user), pk=lot_id)
    accepted = lot.bids.filter(status=BidStatus.ACCEPTED).select_related("bidder").order_by("-created_at")
    paginator = StandardResultsSetPagination()
    page = paginator.paginate_queryset(accepted, request)
    return paginator.get_paginated_response(BidSerializer(page, many=True).data)


# ---------------------------------------------------------------------------
# Bidding
# ---------------------------------------------------------------------------

@api_view(["POST"])
@permission_classes([IsAuthenticated, IsAuctionParticipant])
@throttle_classes([BidThrottle])
@_handle
def place_bid(request, lot_id):
    get_object_or_404(AuctionLot, pk=lot_id)
    amount = request.data.get("amount")
    bid, snapshot = bid_service.place_bid(lot_id, request.user, amount)
    return Response(
        {
            "message": "Bid accepted.",
            "bid": BidSerializer(bid).data,
            "current_price": snapshot["current_price"],
            "minimum_next_bid": snapshot["minimum_next_bid"],
            "bid_count": snapshot["bid_count"],
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_bids(request):
    queryset = _annotate_lots(
        AuctionLot.objects.filter(bids__bidder=request.user, bids__status=BidStatus.ACCEPTED),
        request.user,
    )
    lot_ids = queryset.values_list("pk", flat=True)
    bids = (
        Bid.objects.filter(bidder=request.user, status=BidStatus.ACCEPTED)
        .filter(auction_lot_id__in=lot_ids)
        .select_related(
            "auction_lot", "auction_lot__product", "auction_lot__product__category",
            "auction_lot__auction_event", "auction_lot__highest_bid",
            "auction_lot__highest_bid__bidder",
        )
        .prefetch_related("auction_lot__product__images", "auction_lot__saved_by")
        .order_by("-created_at")
    )
    paginator = StandardResultsSetPagination()
    page = paginator.paginate_queryset(bids, request)
    return paginator.get_paginated_response(
        MyBidSerializer(page, many=True, context={"request": request}).data
    )


@api_view(["POST", "DELETE"])
@permission_classes([IsAuthenticated])
def saved_lot(request, lot_id):
    lot = get_object_or_404(AuctionLot, pk=lot_id)
    if request.method == "POST":
        saved, created = SavedLot.objects.get_or_create(user=request.user, lot=lot)
        return Response({"saved": True, "created": created})
    SavedLot.objects.filter(user=request.user, lot=lot).delete()
    return Response({"saved": False})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_saved_lots(request):
    queryset = (
        SavedLot.objects.filter(user=request.user)
        .select_related("lot", "lot__product", "lot__auction_event")
        .order_by("-created_at")
    )
    paginator = StandardResultsSetPagination()
    page = paginator.paginate_queryset(queryset, request)
    lots = [s.lot for s in page]
    annotated = _annotate_lots(AuctionLot.objects.filter(pk__in=[l.pk for l in lots]), request.user)
    by_id = {l.pk: l for l in annotated}
    data = [
        {
            "id": s.id,
            "created_at": s.created_at,
            "lot": LotSummarySerializer(by_id[s.lot_id], context={"request": request}).data,
        }
        for s in page
    ]
    return paginator.get_paginated_response(data)


# ---------------------------------------------------------------------------
# Seller / organizer
# ---------------------------------------------------------------------------

@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated, IsAuctionParticipantOrReadOnly])
@_handle
def events(request):
    if request.method == "GET":
        queryset = (
            AuctionEvent.objects.filter(organizer=request.user)
            .select_related("organizer", "reviewed_by")
            .prefetch_related(
                "lots",
                "lots__product",
                "lots__product__images",
                "cancellation_requests",
            )
            .order_by("-created_at")
        )
        status_filter = request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter.upper())
        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(queryset, request)
        return paginator.get_paginated_response(
            EventSerializer(page, many=True, context={"request": request}).data
        )
    serializer = EventWriteSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    lots = data.pop("lots", [])
    with transaction.atomic():
        event = event_service.create_event(
            request.user,
            data["title"],
            data.get("description", ""),
            data["start_time"],
            data["end_time"],
        )
        for lot_data in lots:
            lot_service.add_lot(
                event, request.user, lot_data["product"], lot_data["lot_number"],
                lot_data["starting_price"], lot_data.get("minimum_increment", 1),
                lot_data["start_time"], lot_data["end_time"],
            )
    return Response(
        EventSerializer(event, context={"request": request}).data, status=201
    )


@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([IsAuthenticated, IsAuctionParticipantOrReadOnly])
@_handle
def event_detail(request, event_id):
    event = get_object_or_404(
        AuctionEvent.objects.select_related("organizer").prefetch_related(
            "lots", "lots__product", "lots__product__images", "cancellation_requests"
        ),
        pk=event_id,
    )
    if request.method == "GET":
        if event.organizer_id != request.user.id and not request.user.is_admin:
            raise BusinessError("NOT_OWNER", "You do not own this event.", 403)
        return Response(EventSerializer(event, context={"request": request}).data)
    if event.organizer_id != request.user.id:
        raise BusinessError("NOT_OWNER", "You do not own this event.", 403)
    if request.method == "DELETE":
        event_service.discard_draft(event, request.user)
        return Response({"message": "Draft deleted."})
    serializer = EventWriteSerializer(data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    event = event_service.update_event(event, request.user, serializer.validated_data)
    return Response(EventSerializer(event, context={"request": request}).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated, IsAuctionParticipant])
@_handle
def event_revision(request, event_id):
    event = get_object_or_404(AuctionEvent.objects.prefetch_related("lots"), pk=event_id)
    revision = event_service.create_revision(event, request.user)
    return Response(
        EventSerializer(revision, context={"request": request}).data,
        status=201,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated, IsAuctionParticipant])
@_handle
def event_lots(request, event_id):
    event = get_object_or_404(AuctionEvent, pk=event_id)
    serializer = LotWriteSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    lot = lot_service.add_lot(
        event,
        request.user,
        data["product"],
        data["lot_number"],
        data["starting_price"],
        data.get("minimum_increment", 1.00),
        data["start_time"],
        data["end_time"],
    )
    from apps.notifications.services import notify

    notify(
        recipient=request.user,
        verb="LOT_CREATED",
        actor=request.user,
        target=lot,
        message_key="notifications.lot_created",
    )
    return Response(
        LotDetailSerializer(
            _annotate_lots(AuctionLot.objects.filter(pk=lot.pk).select_related(
                "auction_event", "product", "product__owner", "product__category", "highest_bid"
            ).prefetch_related("product__images"), request.user).first(),
            context={"request": request},
        ).data,
        status=201,
    )


@api_view(["PATCH", "DELETE"])
@permission_classes([IsAuthenticated, IsAuctionParticipant])
@_handle
def event_lot_detail(request, event_id, lot_id):
    event = get_object_or_404(AuctionEvent, pk=event_id)
    lot = get_object_or_404(AuctionLot, pk=lot_id, auction_event=event)
    if request.method == "DELETE":
        lot_service.remove_lot(event, request.user, lot)
        from apps.notifications.services import notify

        notify(
            recipient=request.user,
            verb="LOT_REMOVED",
            actor=request.user,
            target=event,
            message_key="notifications.lot_removed",
        )
        return Response({"message": "Lot removed."})
    serializer = LotWriteSerializer(data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    lot = lot_service.update_lot(event, request.user, lot, serializer.validated_data)
    from apps.notifications.services import notify

    notify(
        recipient=request.user,
        verb="LOT_UPDATED",
        actor=request.user,
        target=lot,
        message_key="notifications.lot_updated",
    )
    return Response(
        LotDetailSerializer(
            _annotate_lots(AuctionLot.objects.filter(pk=lot.pk).select_related(
                "auction_event", "product", "product__owner", "product__category", "highest_bid"
            ).prefetch_related("product__images"), request.user).first(),
            context={"request": request},
        ).data
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated, IsAuctionParticipant])
@_handle
def event_submit(request, event_id):
    event = get_object_or_404(AuctionEvent, pk=event_id)
    event_service.submit_event(event, request.user)
    return Response(EventSerializer(event, context={"request": request}).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@_handle
def event_cancel(request, event_id):
    event = get_object_or_404(AuctionEvent, pk=event_id)
    event_service.cancel_event(event, request.user, request.data.get("reason", ""))
    return Response(EventSerializer(event, context={"request": request}).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated, IsAuctionParticipant])
@_handle
def event_cancellation_request(request, event_id):
    event = get_object_or_404(AuctionEvent, pk=event_id)
    cancellation_request = cancellation_service.request_cancellation(
        event, request.user, request.data.get("reason", "")
    )
    return Response(CancellationRequestSerializer(cancellation_request).data, status=201)


# ---------------------------------------------------------------------------
# Admin review
# ---------------------------------------------------------------------------

@api_view(["GET"])
@permission_classes([IsAdmin])
def admin_events(request):
    status_filter = request.query_params.get("status", AuctionEventStatus.PENDING_APPROVAL)
    queryset = (
        AuctionEvent.objects.filter(status=status_filter.upper())
        .select_related("organizer", "reviewed_by")
        .prefetch_related("lots", "lots__product", "cancellation_requests")
        .order_by("submitted_at")
    )
    paginator = StandardResultsSetPagination()
    page = paginator.paginate_queryset(queryset, request)
    return paginator.get_paginated_response(
        EventSerializer(page, many=True, context={"request": request}).data
    )


@api_view(["GET"])
@permission_classes([IsAdmin])
def admin_event_history(request):
    """Auction records that are visible in the admin history and rejected filter."""
    history_statuses = [
        AuctionEventStatus.APPROVED,
        AuctionEventStatus.SCHEDULED,
        AuctionEventStatus.ACTIVE,
        AuctionEventStatus.AWAITING_ORDERS,
        AuctionEventStatus.ENDED,
        AuctionEventStatus.CANCELLED,
        AuctionEventStatus.REJECTED,
        AuctionEventStatus.SUPERSEDED,
    ]
    queryset = (
        AuctionEvent.objects.filter(status__in=history_statuses)
        .exclude(status=AuctionEventStatus.CANCELLED, submitted_at__isnull=True)
        .select_related("organizer", "reviewed_by")
        .prefetch_related(
            "lots",
            "lots__product",
            "lots__product__images",
            "lots__highest_bid__bidder",
            "lots__order",
            "lots__saved_by",
            "cancellation_requests",
        )
        .order_by("-updated_at", "-pk")
    )
    paginator = StandardResultsSetPagination()
    page = paginator.paginate_queryset(queryset, request)
    return paginator.get_paginated_response(
        EventSerializer(page, many=True, context={"request": request}).data
    )


@api_view(["GET"])
@permission_classes([IsAdmin])
def admin_active_bids(request):
    """Chronological accepted bids and rejected attempts for active auctions."""
    filters = AdminBidTrackingFilterSerializer(data=request.query_params)
    filters.is_valid(raise_exception=True)

    queryset = (
        Bid.objects.filter(
            auction_lot__auction_event__status=AuctionEventStatus.ACTIVE
        )
        .select_related(
            "bidder",
            "auction_lot",
            "auction_lot__auction_event",
            "auction_lot__product",
        )
        .order_by("-created_at", "-pk")
    )
    selected = filters.validated_data
    if "event" in selected:
        queryset = queryset.filter(
            auction_lot__auction_event_id=selected["event"]
        )
    if "lot" in selected:
        queryset = queryset.filter(auction_lot_id=selected["lot"])
    if "status" in selected:
        queryset = queryset.filter(status=selected["status"])

    paginator = StandardResultsSetPagination()
    page = paginator.paginate_queryset(queryset, request)
    return paginator.get_paginated_response(
        AdminBidTrackingSerializer(page, many=True).data
    )


@api_view(["POST"])
@permission_classes([IsAdmin])
@_handle
def admin_event_approve(request, event_id):
    event = get_object_or_404(AuctionEvent, pk=event_id)
    event_service.approve_event(event, request.user)
    return Response(EventSerializer(event, context={"request": request}).data)


@api_view(["POST"])
@permission_classes([IsAdmin])
@_handle
def admin_event_reject(request, event_id):
    event = get_object_or_404(AuctionEvent, pk=event_id)
    reason = request.data.get("reason", "")
    event_service.reject_event(event, request.user, reason)
    return Response(EventSerializer(event, context={"request": request}).data)


@api_view(["GET"])
@permission_classes([IsAdmin])
def admin_cancellation_requests(request):
    status_filter = request.query_params.get("status", "PENDING").upper()
    queryset = (
        AuctionCancellationRequest.objects.filter(status=status_filter)
        .select_related("auction_event", "requester", "reviewed_by")
        .order_by("created_at")
    )
    paginator = StandardResultsSetPagination()
    page = paginator.paginate_queryset(queryset, request)
    return paginator.get_paginated_response(
        CancellationRequestSerializer(page, many=True).data
    )


@api_view(["POST"])
@permission_classes([IsAdmin])
@_handle
def admin_cancellation_approve(request, request_id):
    cancellation_request = get_object_or_404(AuctionCancellationRequest, pk=request_id)
    cancellation_request = cancellation_service.approve_cancellation(
        cancellation_request, request.user
    )
    return Response(CancellationRequestSerializer(cancellation_request).data)


@api_view(["POST"])
@permission_classes([IsAdmin])
@_handle
def admin_cancellation_reject(request, request_id):
    cancellation_request = get_object_or_404(AuctionCancellationRequest, pk=request_id)
    cancellation_request = cancellation_service.reject_cancellation(
        cancellation_request, request.user, request.data.get("reason", "")
    )
    return Response(CancellationRequestSerializer(cancellation_request).data)
