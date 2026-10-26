from datetime import timedelta

from django.conf import settings
from django.db import models


class AuctionEventStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    PENDING_APPROVAL = "PENDING_APPROVAL", "Pending approval"
    REJECTED = "REJECTED", "Rejected"
    APPROVED = "APPROVED", "Approved"
    SCHEDULED = "SCHEDULED", "Scheduled"
    ACTIVE = "ACTIVE", "Active"
    AWAITING_ORDERS = "AWAITING_ORDERS", "Waiting for order completion"
    ENDED = "ENDED", "Ended"
    CANCELLED = "CANCELLED", "Cancelled"
    SUPERSEDED = "SUPERSEDED", "Superseded"


class AuctionLotStatus(models.TextChoices):
    SCHEDULED = "SCHEDULED", "Scheduled"
    ACTIVE = "ACTIVE", "Active"
    AWAITING_ORDER = "AWAITING_ORDER", "Waiting for order completion"
    CANCELLED = "CANCELLED", "Cancelled"
    SOLD = "SOLD", "Sold"
    UNSOLD = "UNSOLD", "Unsold"


class CancellationRequestStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    APPROVED = "APPROVED", "Approved"
    REJECTED = "REJECTED", "Rejected"


class AuctionEvent(models.Model):
    revision_of = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="revisions",
    )
    revision_number = models.PositiveIntegerField(default=1)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    organizer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="organized_auction_events",
    )
    status = models.CharField(
        max_length=20,
        choices=AuctionEventStatus.choices,
        default=AuctionEventStatus.DRAFT,
    )
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_auction_events",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end_time__gt=models.F("start_time")),
                name="event_end_after_start",
            ),
        ]

    def __str__(self):
        return self.title

    @property
    def editing_deadline(self):
        return self.start_time - timedelta(minutes=settings.AUCTION_EDITABLE_LEAD_MINUTES)

    @property
    def organizer_can_edit(self):
        return self.status in (
            AuctionEventStatus.DRAFT,
            AuctionEventStatus.REJECTED,
        )

    @property
    def is_revision(self):
        return self.revision_of_id is not None


class AuctionCancellationRequest(models.Model):
    auction_event = models.ForeignKey(
        AuctionEvent,
        on_delete=models.PROTECT,
        related_name="cancellation_requests",
    )
    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="auction_cancellation_requests",
    )
    reason = models.TextField()
    status = models.CharField(
        max_length=16,
        choices=CancellationRequestStatus.choices,
        default=CancellationRequestStatus.PENDING,
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_auction_cancellation_requests",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["auction_event"],
                condition=models.Q(status=CancellationRequestStatus.PENDING),
                name="one_pending_cancellation_request_per_event",
            )
        ]

    def __str__(self):
        return f"Cancellation request for {self.auction_event} ({self.status})"


class AuctionLot(models.Model):
    auction_event = models.ForeignKey(
        AuctionEvent,
        on_delete=models.PROTECT,
        related_name="lots",
    )
    product = models.ForeignKey(
        "products.Product",
        on_delete=models.PROTECT,
        related_name="auction_lots",
    )
    lot_number = models.PositiveIntegerField()
    starting_price = models.DecimalField(max_digits=10, decimal_places=2)
    minimum_increment = models.DecimalField(max_digits=10, decimal_places=2, default=1.00)
    highest_bid = models.ForeignKey(
        "Bid",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    status = models.CharField(
        max_length=20,
        choices=AuctionLotStatus.choices,
        default=AuctionLotStatus.SCHEDULED,
    )
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["auction_event", "lot_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["auction_event", "lot_number"],
                name="unique_lot_number_per_event",
            ),
            models.CheckConstraint(
                condition=models.Q(starting_price__gt=0),
                name="lot_starting_price_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(minimum_increment__gt=0),
                name="lot_minimum_increment_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(end_time__gt=models.F("start_time")),
                name="lot_end_after_start",
            ),
        ]

    def __str__(self):
        return f"Lot {self.lot_number}: {self.product.name}"

    @property
    def winner(self):
        return self.highest_bid.bidder if self.highest_bid else None

    @property
    def current_price(self):
        return self.highest_bid.amount if self.highest_bid else self.starting_price

    @property
    def minimum_next_bid(self):
        return self.current_price + self.minimum_increment

    @property
    def is_terminal(self):
        return self.status in (AuctionLotStatus.SOLD, AuctionLotStatus.UNSOLD, AuctionLotStatus.CANCELLED)


class BidStatus(models.TextChoices):
    ACCEPTED = "ACCEPTED", "Accepted"
    REJECTED = "REJECTED", "Rejected"


class RejectionReason(models.TextChoices):
    LOWER_THAN_CURRENT = "LOWER_THAN_CURRENT", "Lower than current bid"
    AUCTION_NOT_ACTIVE = "AUCTION_NOT_ACTIVE", "Auction not active"
    SELLER_BIDDING = "SELLER_BIDDING", "Seller bidding"
    BLOCKED_USER = "BLOCKED_USER", "Blocked user"
    MINIMUM_INCREMENT_NOT_MET = "MINIMUM_INCREMENT_NOT_MET", "Minimum increment not met"
    INVALID_AMOUNT = "INVALID_AMOUNT", "Invalid amount"


class Bid(models.Model):
    auction_lot = models.ForeignKey(
        AuctionLot,
        on_delete=models.PROTECT,
        related_name="bids",
    )
    bidder = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="auction_bids",
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=20,
        choices=BidStatus.choices,
        default=BidStatus.ACCEPTED,
    )
    rejection_reason = models.CharField(
        max_length=50,
        choices=RejectionReason.choices,
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gte=0),
                name="bid_amount_non_negative",
            ),
        ]

    def __str__(self):
        return f"{self.bidder} bid ${self.amount} on lot {self.auction_lot.lot_number}"


class SavedLot(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="saved_lots",
    )
    lot = models.ForeignKey(
        AuctionLot,
        on_delete=models.CASCADE,
        related_name="saved_by",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "lot"], name="unique_saved_lot_per_user"),
        ]

    def __str__(self):
        return f"{self.user} saved lot {self.lot_id}"
