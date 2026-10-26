from decimal import Decimal

from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone
from rest_framework import serializers

from apps.products.models import Product
from apps.products.serializers import CategorySerializer, ProductSerializer
from .models import (
    AuctionCancellationRequest,
    AuctionEvent,
    AuctionLot,
    Bid,
    BidStatus,
    RejectionReason,
    SavedLot,
)


class BidSerializer(serializers.ModelSerializer):
    bidder_id = serializers.SerializerMethodField()
    bidder_username = serializers.SerializerMethodField()
    rejection_code = serializers.SerializerMethodField()

    class Meta:
        model = Bid
        fields = [
            "id",
            "auction_lot",
            "bidder_id",
            "bidder_username",
            "amount",
            "created_at",
            "status",
            "rejection_reason",
            "rejection_code",
        ]
        read_only_fields = fields

    def get_rejection_code(self, obj):
        if obj.rejection_reason:
            return obj.rejection_reason
        return None

    def get_bidder_id(self, obj):
        return obj.bidder_id

    def get_bidder_username(self, obj):
        return obj.bidder.username if obj.bidder else "Deleted user"


class AdminBidTrackingSerializer(serializers.ModelSerializer):
    event_id = serializers.IntegerField(
        source="auction_lot.auction_event_id", read_only=True
    )
    event_title = serializers.CharField(
        source="auction_lot.auction_event.title", read_only=True
    )
    event_status = serializers.CharField(
        source="auction_lot.auction_event.status", read_only=True
    )
    lot_id = serializers.IntegerField(source="auction_lot_id", read_only=True)
    lot_number = serializers.IntegerField(
        source="auction_lot.lot_number", read_only=True
    )
    lot_status = serializers.CharField(
        source="auction_lot.status", read_only=True
    )
    product_id = serializers.IntegerField(
        source="auction_lot.product_id", read_only=True
    )
    product_name = serializers.CharField(
        source="auction_lot.product.name", read_only=True
    )
    bidder_id = serializers.IntegerField(read_only=True, allow_null=True)
    bidder_username = serializers.SerializerMethodField()
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    rejection_reason_display = serializers.SerializerMethodField()
    is_highest = serializers.SerializerMethodField()

    class Meta:
        model = Bid
        fields = [
            "id",
            "event_id",
            "event_title",
            "event_status",
            "lot_id",
            "lot_number",
            "lot_status",
            "product_id",
            "product_name",
            "bidder_id",
            "bidder_username",
            "amount",
            "status",
            "status_display",
            "rejection_reason",
            "rejection_reason_display",
            "created_at",
            "is_highest",
        ]
        read_only_fields = fields

    def get_bidder_username(self, obj):
        return obj.bidder.username if obj.bidder else "Deleted user"

    def get_rejection_reason_display(self, obj):
        return obj.get_rejection_reason_display() if obj.rejection_reason else None

    def get_is_highest(self, obj):
        return obj.auction_lot.highest_bid_id == obj.pk


class AdminBidTrackingFilterSerializer(serializers.Serializer):
    event = serializers.IntegerField(required=False, min_value=1)
    lot = serializers.IntegerField(required=False, min_value=1)
    status = serializers.CharField(required=False)

    def validate_status(self, value):
        normalized = value.strip().upper()
        if normalized not in BidStatus.values:
            raise serializers.ValidationError("Choose ACCEPTED or REJECTED.")
        return normalized


class LotSummarySerializer(serializers.ModelSerializer):
    event_title = serializers.CharField(source="auction_event.title", read_only=True)
    event_status = serializers.CharField(source="auction_event.status", read_only=True)
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_image = serializers.SerializerMethodField()
    current_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    minimum_next_bid = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    bid_count = serializers.SerializerMethodField()
    is_saved = serializers.SerializerMethodField()
    winner_username = serializers.SerializerMethodField()
    order_status = serializers.SerializerMethodField()
    order_status_display = serializers.SerializerMethodField()

    class Meta:
        model = AuctionLot
        fields = [
            "id",
            "auction_event",
            "event_title",
            "event_status",
            "product",
            "product_name",
            "product_image",
            "lot_number",
            "starting_price",
            "minimum_increment",
            "current_price",
            "minimum_next_bid",
            "bid_count",
            "status",
            "start_time",
            "end_time",
            "winner_username",
            "order_status",
            "order_status_display",
            "is_saved",
            "created_at",
        ]
        read_only_fields = fields

    def get_bid_count(self, obj):
        value = getattr(obj, "accepted_bid_count", None)
        if value is not None:
            return value
        if (
            hasattr(obj, "_prefetched_objects_cache")
            and "accepted_bids" in obj._prefetched_objects_cache
        ):
            return len(obj._prefetched_objects_cache["accepted_bids"])
        return obj.bids.filter(status=BidStatus.ACCEPTED).count()

    def _order(self, obj):
        try:
            return obj.order
        except (AttributeError, ObjectDoesNotExist):
            return None

    def get_order_status(self, obj):
        order = self._order(obj)
        return order.status if order else None

    def get_order_status_display(self, obj):
        order = self._order(obj)
        return order.get_status_display() if order else None

    def get_product_image(self, obj):
        request = self.context.get("request")
        cached_images = getattr(
            obj.product, "_prefetched_objects_cache", {}
        ).get("images")
        if cached_images is not None:
            images = list(cached_images)
            image = next((candidate for candidate in images if candidate.is_primary), None)
            image = image or next(iter(images), None)
        else:
            image = obj.product.images.filter(is_primary=True).first() or obj.product.images.first()
        if image and image.image:
            url = request.build_absolute_uri(image.image.url) if request else image.image.url
            return url
        return None

    def get_is_saved(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        value = getattr(obj, "saved_by_me", None)
        if value is not None:
            return value
        if (
            hasattr(obj, "_prefetched_objects_cache")
            and "saved_by" in obj._prefetched_objects_cache
        ):
            return any(s.user_id == request.user.id for s in obj._prefetched_objects_cache["saved_by"])
        return obj.saved_by.filter(user=request.user).exists()

    def get_winner_username(self, obj):
        bid = obj.highest_bid
        if bid and bid.bidder:
            return bid.bidder.username
        return None


class LotDetailSerializer(LotSummarySerializer):
    description = serializers.CharField(source="product.description", read_only=True)
    category = CategorySerializer(source="product.category", read_only=True)
    seller = serializers.SerializerMethodField()
    server_time = serializers.SerializerMethodField()

    class Meta(LotSummarySerializer.Meta):
        fields = LotSummarySerializer.Meta.fields + [
            "description",
            "category",
            "seller",
            "server_time",
        ]

    def get_seller(self, obj):
        from apps.accounts.serializers import PublicProfileSerializer

        if obj.product.owner is None:
            return None
        return PublicProfileSerializer(
            obj.product.owner, context=self.context
        ).data

    def get_server_time(self, obj):
        return timezone.now().isoformat()


class MyBidSerializer(BidSerializer):
    lot = LotSummarySerializer(source="auction_lot", read_only=True)
    outcome = serializers.SerializerMethodField()

    class Meta(BidSerializer.Meta):
        fields = BidSerializer.Meta.fields + ["lot", "outcome"]

    def get_outcome(self, obj):
        # Only the exact bid selected as highest can be the winning bid. This
        # deliberately marks a winner's earlier bids as lost.
        return "winning" if obj.auction_lot.highest_bid_id == obj.pk else "lost"


class LotWriteSerializer(serializers.Serializer):
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())
    lot_number = serializers.IntegerField(min_value=1)
    starting_price = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal("0.01")
    )
    minimum_increment = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal("0.01"),
        required=False,
    )
    start_time = serializers.DateTimeField()
    end_time = serializers.DateTimeField()


class CancellationRequestSerializer(serializers.ModelSerializer):
    event_title = serializers.CharField(source="auction_event.title", read_only=True)
    event_status = serializers.CharField(source="auction_event.status", read_only=True)
    event_start_time = serializers.DateTimeField(source="auction_event.start_time", read_only=True)
    requester_username = serializers.SerializerMethodField()
    reviewed_by_username = serializers.CharField(
        source="reviewed_by.username", read_only=True, default=None
    )
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = AuctionCancellationRequest
        fields = [
            "id",
            "auction_event",
            "event_title",
            "event_status",
            "event_start_time",
            "requester",
            "requester_username",
            "reason",
            "status",
            "status_display",
            "reviewed_by",
            "reviewed_by_username",
            "reviewed_at",
            "review_reason",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_requester_username(self, obj):
        return obj.requester.username if obj.requester else "Deleted user"


class EventSerializer(serializers.ModelSerializer):
    lots = LotSummarySerializer(many=True, read_only=True)
    organizer_username = serializers.SerializerMethodField()
    can_edit = serializers.BooleanField(source="organizer_can_edit", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    cancellation_deadline = serializers.DateTimeField(source="editing_deadline", read_only=True)
    cancellation_request = serializers.SerializerMethodField()

    class Meta:
        model = AuctionEvent
        fields = [
            "id",
            "revision_of",
            "revision_number",
            "is_revision",
            "title",
            "description",
            "organizer",
            "organizer_username",
            "status",
            "status_display",
            "start_time",
            "end_time",
            "created_at",
            "updated_at",
            "submitted_at",
            "reviewed_by",
            "reviewed_at",
            "rejection_reason",
            "cancellation_deadline",
            "cancellation_request",
            "lots",
            "can_edit",
        ]
        read_only_fields = [
            "id",
            "revision_of",
            "revision_number",
            "is_revision",
            "organizer",
            "organizer_username",
            "status",
            "status_display",
            "created_at",
            "updated_at",
            "submitted_at",
            "reviewed_by",
            "reviewed_at",
            "rejection_reason",
            "cancellation_deadline",
            "cancellation_request",
            "lots",
            "can_edit",
        ]

    def get_cancellation_request(self, obj):
        requests = getattr(obj, "_prefetched_objects_cache", {}).get("cancellation_requests")
        latest = next(iter(requests), None) if requests is not None else obj.cancellation_requests.first()
        return CancellationRequestSerializer(latest).data if latest else None

    def get_organizer_username(self, obj):
        return obj.organizer.username if obj.organizer else "Deleted user"


class EventWriteSerializer(serializers.ModelSerializer):
    lots = LotWriteSerializer(many=True, required=False, write_only=True)

    class Meta:
        model = AuctionEvent
        fields = ["title", "description", "start_time", "end_time", "lots"]

    def validate(self, attrs):
        attrs = super().validate(attrs)
        lots = attrs.get("lots")
        if lots is None:
            return attrs
        numbers = [lot["lot_number"] for lot in lots]
        if len(numbers) != len(set(numbers)):
            raise serializers.ValidationError({"lots": "Lot numbers must be unique."})
        start = attrs.get("start_time")
        end = attrs.get("end_time")
        for index, lot in enumerate(lots):
            if start and lot["start_time"] < start or end and lot["end_time"] > end:
                raise serializers.ValidationError(
                    {"lots": {index: "Lot times must be inside the event window."}}
                )
        return attrs


class SavedLotSerializer(serializers.ModelSerializer):
    lot = LotSummarySerializer(read_only=True)

    class Meta:
        model = SavedLot
        fields = ["id", "lot", "created_at"]
        read_only_fields = ["id", "lot", "created_at"]
