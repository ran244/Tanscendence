from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.common.exceptions import BusinessError, business_error_response
from apps.common.pagination import StandardResultsSetPagination
from .models import Order, OrderStatus, Payment
from .services import cancel_order, confirm_cash_on_delivery, update_fulfillment


class OrderSerializer(serializers.ModelSerializer):
    lot = serializers.SerializerMethodField()
    buyer_username = serializers.SerializerMethodField()
    seller_username = serializers.SerializerMethodField()
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Order
        fields = [
            "id",
            "auction_lot",
            "lot",
            "buyer",
            "buyer_username",
            "seller",
            "seller_username",
            "final_price",
            "shipping_address",
            "delivery_full_name",
            "delivery_city",
            "delivery_phone",
            "preferred_delivery_at",
            "delivery_notes",
            "status",
            "status_display",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_lot(self, obj):
        from apps.auctions.serializers import LotSummarySerializer

        return LotSummarySerializer(obj.auction_lot, context=self.context).data

    def get_buyer_username(self, obj):
        return obj.buyer.username if obj.buyer else "Deleted user"

    def get_seller_username(self, obj):
        return obj.seller.username if obj.seller else "Deleted user"


class DeliveryDetailsSerializer(serializers.Serializer):
    delivery_full_name = serializers.CharField(max_length=200, required=False, allow_blank=True)
    shipping_address = serializers.CharField(max_length=1000)
    delivery_city = serializers.CharField(max_length=120, required=False, allow_blank=True)
    delivery_phone = serializers.CharField(max_length=40, required=False, allow_blank=True)
    preferred_delivery_at = serializers.DateTimeField(required=False, allow_null=True)
    delivery_notes = serializers.CharField(required=False, allow_blank=True, max_length=2000)


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = [
            "id",
            "order",
            "amount",
            "status",
            "method",
            "collection_note",
            "created_at",
            "collected_at",
        ]
        read_only_fields = fields


def _order_queryset(user, role):
    queryset = (
        Order.objects.select_related(
            "buyer", "seller", "auction_lot", "auction_lot__product", "auction_lot__auction_event"
        )
        .prefetch_related("auction_lot__product__images")
    )
    if role == "buyer":
        return queryset.filter(buyer=user)
    return queryset.filter(seller=user)


def _handle(fn):
    def wrapper(request, *args, **kwargs):
        try:
            return fn(request, *args, **kwargs)
        except BusinessError as error:
            return business_error_response(error, request)

    return wrapper


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def orders_list(request):
    role = request.query_params.get("role", "buyer")
    if role not in ("buyer", "seller"):
        role = "buyer"
    queryset = _order_queryset(request.user, role)
    status_filter = request.query_params.get("status")
    if status_filter:
        queryset = queryset.filter(status=status_filter.upper())
    paginator = StandardResultsSetPagination()
    page = paginator.paginate_queryset(queryset, request)
    return paginator.get_paginated_response(OrderSerializer(page, many=True, context={"request": request}).data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def order_detail(request, order_id):
    order = get_object_or_404(Order, pk=order_id)
    if order.buyer_id != request.user.id and order.seller_id != request.user.id and not request.user.is_admin:
        return Response({"code": "PERMISSION_DENIED", "message": "Not your order."}, status=403)
    data = OrderSerializer(order, context={"request": request}).data
    collection = Payment.objects.filter(order=order).first()
    data["cash_on_delivery"] = PaymentSerializer(collection).data if collection else None
    return Response(data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@_handle
def order_confirm_cod(request, order_id):
    order = get_object_or_404(Order, pk=order_id)
    serializer = DeliveryDetailsSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    collection = confirm_cash_on_delivery(order, request.user, serializer.validated_data)
    order.refresh_from_db()
    return Response(
        {
            "message": "Delivery details submitted. The order completes after the seller accepts them.",
            "order": OrderSerializer(order, context={"request": request}).data,
            "cash_on_delivery": PaymentSerializer(collection).data,
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@_handle
def order_cancel(request, order_id):
    order = get_object_or_404(Order, pk=order_id)
    cancel_order(order, request.user)
    return Response(OrderSerializer(order, context={"request": request}).data)


@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
@_handle
def order_fulfillment(request, order_id):
    order = get_object_or_404(Order, pk=order_id)
    new_status = request.data.get("status", "").upper()
    if new_status not in OrderStatus.values:
        raise BusinessError("VALIDATION_ERROR", "Invalid status.")
    update_fulfillment(order, request.user, new_status, request.data.get("collection_note", ""))
    return Response(OrderSerializer(order, context={"request": request}).data)
