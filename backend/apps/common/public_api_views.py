"""
Versioned public API (/api/v1/).

- Every endpoint requires an active `X-API-Key` and is rate limited.
- The key identifies its owner; mutations enforce that owner's object-level
  permissions.
"""
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view, authentication_classes, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import serializers
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer

from apps.auctions.models import AuctionEvent, AuctionLot, Bid, BidStatus, SavedLot
from apps.auctions.serializers import LotSummarySerializer, LotWriteSerializer
from apps.auctions.services import lots as lot_service
from apps.common.authentication import ApiKeyAuthentication
from apps.common.pagination import StandardResultsSetPagination
from apps.common.permissions import IsAuctionParticipantOrReadOnly
from apps.common.throttling import PublicApiThrottle
from apps.products.models import Category
from apps.products.serializers import CategorySerializer
from apps.products.serializers import ProductSerializer


api_key_only = authentication_classes([ApiKeyAuthentication])


class PublicLotWriteSerializer(LotWriteSerializer):
    event = serializers.IntegerField()


IdMessageSerializer = inline_serializer(
    name="PublicApiIdMessage",
    fields={"id": serializers.IntegerField(), "message": serializers.CharField()},
)
SavedLotResponseSerializer = inline_serializer(
    name="PublicApiSavedLot",
    fields={"id": serializers.IntegerField(), "lot_id": serializers.IntegerField(), "created": serializers.BooleanField(required=False)},
)


@extend_schema(tags=["Public API"], responses=CategorySerializer(many=True))
@api_view(["GET"])
@api_key_only
@permission_classes([IsAuthenticated])
@throttle_classes([PublicApiThrottle])
def public_categories(request):
    categories = Category.objects.all().order_by("name")
    return Response({"results": CategorySerializer(categories, many=True).data})


@extend_schema(
    tags=["Public API"],
    parameters=[OpenApiParameter("search", str, description="Case-insensitive product name search")],
    responses=ProductSerializer(many=True),
)
@api_view(["GET"])
@api_key_only
@permission_classes([IsAuthenticated])
@throttle_classes([PublicApiThrottle])
def public_products(request):
    from apps.products.models import Product

    queryset = Product.objects.filter(available=True).select_related("category", "owner").order_by("name")
    search = request.query_params.get("search")
    if search:
        queryset = queryset.filter(name__icontains=search)
    paginator = StandardResultsSetPagination()
    page = paginator.paginate_queryset(queryset, request)
    return paginator.get_paginated_response(ProductSerializer(page, many=True, context={"request": request}).data)


@extend_schema(methods=["GET"], tags=["Public API"], responses=LotSummarySerializer(many=True))
@extend_schema(methods=["POST"], tags=["Public API"], request=PublicLotWriteSerializer, responses={201: IdMessageSerializer})
@api_view(["GET", "POST"])
@api_key_only
@permission_classes([IsAuthenticated, IsAuctionParticipantOrReadOnly])
@throttle_classes([PublicApiThrottle])
def public_lots(request):
    from apps.auctions.views import _public_lot_queryset

    if request.method == "POST":
        event = get_object_or_404(
            AuctionEvent, pk=request.data.get("event"), organizer=request.user
        )
        serializer = LotWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        lot = lot_service.add_lot(
            event,
            request.user,
            data["product"],
            data["lot_number"],
            data["starting_price"],
            data.get("minimum_increment", 1),
            data["start_time"],
            data["end_time"],
        )
        return Response({"id": lot.pk, "message": "Lot created."}, status=201)

    queryset = _public_lot_queryset(request.user)
    status = request.query_params.get("status")
    if status:
        queryset = queryset.filter(status=status.upper())
    paginator = StandardResultsSetPagination()
    page = paginator.paginate_queryset(queryset, request)
    return paginator.get_paginated_response(
        LotSummarySerializer(page, many=True, context={"request": request}).data
    )


@extend_schema(methods=["GET"], tags=["Public API"], responses=LotSummarySerializer)
@extend_schema(methods=["PUT"], tags=["Public API"], request=LotWriteSerializer, responses=IdMessageSerializer)
@extend_schema(methods=["DELETE"], tags=["Public API"], responses={204: None})
@api_view(["GET", "PUT", "DELETE"])
@api_key_only
@permission_classes([IsAuthenticated, IsAuctionParticipantOrReadOnly])
@throttle_classes([PublicApiThrottle])
def public_lot_detail(request, lot_id):
    lot = get_object_or_404(
        AuctionLot.objects.select_related("auction_event", "product"),
        pk=lot_id,
        auction_event__organizer=request.user,
    )
    if request.method == "GET":
        from apps.auctions.views import _annotate_lots

        annotated = _annotate_lots(
            AuctionLot.objects.filter(pk=lot.pk).select_related(
                "auction_event", "product", "product__owner", "product__category", "highest_bid"
            ).prefetch_related("product__images"),
            request.user,
        ).get()
        return Response(LotSummarySerializer(annotated, context={"request": request}).data)
    if request.method == "DELETE":
        lot_service.remove_lot(lot.auction_event, request.user, lot)
        return Response(status=204)
    serializer = LotWriteSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    updated = lot_service.update_lot(
        lot.auction_event, request.user, lot, serializer.validated_data
    )
    return Response({"id": updated.pk, "message": "Lot updated."})


@extend_schema(
    tags=["Public API"],
    parameters=[OpenApiParameter("lot", int, description="Optional lot identifier")],
    responses={200: inline_serializer(name="PublicApiBidList", fields={"results": serializers.ListField()})},
)
@api_view(["GET"])
@api_key_only
@permission_classes([IsAuthenticated])
@throttle_classes([PublicApiThrottle])
def public_bids(request):
    lot_id = request.query_params.get("lot")
    from apps.auctions.models import AuctionEventStatus, AuctionLotStatus

    queryset = Bid.objects.filter(
        status=BidStatus.ACCEPTED,
        auction_lot__auction_event__status__in=[
            AuctionEventStatus.SCHEDULED,
            AuctionEventStatus.ACTIVE,
            AuctionEventStatus.ENDED,
        ],
        auction_lot__status__in=[
            AuctionLotStatus.SCHEDULED,
            AuctionLotStatus.ACTIVE,
            AuctionLotStatus.SOLD,
            AuctionLotStatus.UNSOLD,
        ],
    ).select_related("bidder", "auction_lot")
    if lot_id:
        queryset = queryset.filter(auction_lot_id=lot_id)
    paginator = StandardResultsSetPagination()
    page = paginator.paginate_queryset(queryset, request)
    from apps.auctions.serializers import BidSerializer

    return paginator.get_paginated_response(BidSerializer(page, many=True).data)


@extend_schema(methods=["GET"], tags=["Public API"], responses={200: inline_serializer(name="PublicApiSavedList", fields={"results": serializers.ListField()})})
@extend_schema(methods=["POST"], tags=["Public API"], request=inline_serializer(name="PublicApiSaveRequest", fields={"lot": serializers.IntegerField()}), responses=SavedLotResponseSerializer)
@api_view(["GET", "POST"])
@api_key_only
@permission_classes([IsAuthenticated])
@throttle_classes([PublicApiThrottle])
def public_saved_lots(request):
    if request.method == "GET":
        queryset = SavedLot.objects.filter(user=request.user).order_by("-created_at")
        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(queryset, request)
        return paginator.get_paginated_response(
            [{"id": s.id, "lot_id": s.lot_id, "created_at": s.created_at} for s in page]
        )
    lot_id = request.data.get("lot")
    from apps.auctions.views import _public_lot_queryset

    lot = get_object_or_404(_public_lot_queryset(request.user), pk=lot_id)
    saved, created = SavedLot.objects.get_or_create(user=request.user, lot=lot)
    return Response({"id": saved.id, "lot_id": lot_id, "created": created}, status=201 if created else 200)


@extend_schema(tags=["Public API"], responses={200: inline_serializer(name="PublicApiDeleted", fields={"deleted": serializers.BooleanField()})})
@api_view(["DELETE"])
@api_key_only
@permission_classes([IsAuthenticated])
@throttle_classes([PublicApiThrottle])
def public_saved_lot_delete(request, saved_id):
    saved = get_object_or_404(SavedLot, pk=saved_id, user=request.user)
    saved.delete()
    return Response({"deleted": True})
