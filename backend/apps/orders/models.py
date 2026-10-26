from django.conf import settings
from django.db import models


class OrderStatus(models.TextChoices):
    AWAITING_CONFIRMATION = "AWAITING_CONFIRMATION", "Awaiting delivery confirmation"
    CONFIRMED = "CONFIRMED", "Cash on delivery confirmed"
    PROCESSING = "PROCESSING", "Processing"
    SHIPPED = "SHIPPED", "Shipped"
    DELIVERED = "DELIVERED", "Delivered"
    CANCELLED = "CANCELLED", "Cancelled"


class Order(models.Model):
    auction_lot = models.OneToOneField(
        "auctions.AuctionLot",
        on_delete=models.PROTECT,
        related_name="order",
    )
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="auction_purchases",
    )
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="auction_sales",
    )
    final_price = models.DecimalField(max_digits=10, decimal_places=2)
    shipping_address = models.TextField(blank=True, default="")
    delivery_full_name = models.CharField(max_length=200, blank=True, default="")
    delivery_city = models.CharField(max_length=120, blank=True, default="")
    delivery_phone = models.CharField(max_length=40, blank=True, default="")
    preferred_delivery_at = models.DateTimeField(null=True, blank=True)
    delivery_notes = models.TextField(blank=True, default="")
    status = models.CharField(
        max_length=24,
        choices=OrderStatus.choices,
        default=OrderStatus.AWAITING_CONFIRMATION,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Order #{self.pk} - Lot {self.auction_lot.lot_number}"


class PaymentStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    COLLECTED = "COLLECTED", "Collected on delivery"
    NOT_COLLECTED = "NOT_COLLECTED", "Not collected"


class PaymentMethod(models.TextChoices):
    CASH_ON_DELIVERY = "CASH_ON_DELIVERY", "Cash on delivery"


class Payment(models.Model):
    order = models.OneToOneField(
        Order,
        on_delete=models.PROTECT,
        related_name="cash_on_delivery",
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING,
    )
    method = models.CharField(
        max_length=20,
        choices=PaymentMethod.choices,
        default=PaymentMethod.CASH_ON_DELIVERY,
    )
    collection_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    collected_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gte=0),
                name="payment_amount_non_negative",
            ),
        ]

    def __str__(self):
        return f"{self.status} cash on delivery for Order #{self.order_id}"
