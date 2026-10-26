from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


class NotificationVerb(models.TextChoices):
    BID_ACCEPTED = "BID_ACCEPTED", "Bid accepted"
    OUTBID = "OUTBID", "Outbid"
    EVENT_SUBMITTED = "EVENT_SUBMITTED", "Event submitted"
    EVENT_APPROVED = "EVENT_APPROVED", "Event approved"
    EVENT_REJECTED = "EVENT_REJECTED", "Event rejected"
    EVENT_ACTIVATED = "EVENT_ACTIVATED", "Event activated"
    EVENT_CANCELLED = "EVENT_CANCELLED", "Event cancelled"
    EVENT_CANCELLATION_REQUESTED = "EVENT_CANCELLATION_REQUESTED", "Event cancellation requested"
    EVENT_CANCELLATION_APPROVED = "EVENT_CANCELLATION_APPROVED", "Event cancellation approved"
    EVENT_CANCELLATION_REJECTED = "EVENT_CANCELLATION_REJECTED", "Event cancellation rejected"
    EVENT_UPDATED = "EVENT_UPDATED", "Event updated"
    LOT_CREATED = "LOT_CREATED", "Lot created"
    LOT_UPDATED = "LOT_UPDATED", "Lot updated"
    LOT_REMOVED = "LOT_REMOVED", "Lot removed"
    LOT_ENDED = "LOT_ENDED", "Lot ended"
    LOT_WINNER = "LOT_WINNER", "Lot won"
    CLOSING_SOON = "CLOSING_SOON", "Closing soon"
    FRIEND_REQUEST = "FRIEND_REQUEST", "Friend request"
    FRIEND_ACCEPTED = "FRIEND_ACCEPTED", "Friend request accepted"
    DIRECT_MESSAGE = "DIRECT_MESSAGE", "Direct message"
    COD_CONFIRMED = "COD_CONFIRMED", "Cash on delivery confirmed"
    ORDER_CREATED = "ORDER_CREATED", "Order created"
    ORDER_CANCELLED = "ORDER_CANCELLED", "Order cancelled"
    ORDER_SHIPPED = "ORDER_SHIPPED", "Order shipped"
    ORDER_DELIVERED = "ORDER_DELIVERED", "Order delivered"
    SUPPORT_REPLY = "SUPPORT_REPLY", "Support reply"
    SUPPORT_TICKET_CREATED = "SUPPORT_TICKET_CREATED", "Support ticket created"
    TICKET_STATUS_CHANGED = "TICKET_STATUS_CHANGED", "Ticket status changed"
    PRODUCT_CREATED = "PRODUCT_CREATED", "Product created"
    PRODUCT_UPDATED = "PRODUCT_UPDATED", "Product updated"
    PRODUCT_REMOVED = "PRODUCT_REMOVED", "Product removed"


class Notification(models.Model):
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notification_actor",
    )
    verb = models.CharField(max_length=32, choices=NotificationVerb.choices)
    message_key = models.CharField(max_length=100, blank=True)
    target_content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE, null=True, blank=True
    )
    target_object_id = models.PositiveIntegerField(null=True, blank=True)
    target = GenericForeignKey("target_content_type", "target_object_id")
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    # Non-null dedupe keys make task-emitted notifications idempotent.
    dedupe_key = models.CharField(max_length=64, null=True, blank=True, unique=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient", "read_at", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.verb} -> {self.recipient} ({self.created_at:%Y-%m-%d %H:%M})"

    @property
    def is_read(self):
        return self.read_at is not None


class TicketStatus(models.TextChoices):
    OPEN = "OPEN", "Open"
    IN_PROGRESS = "IN_PROGRESS", "In progress"
    RESOLVED = "RESOLVED", "Resolved"
    CLOSED = "CLOSED", "Closed"


class SupportTicket(models.Model):
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="support_tickets",
    )
    subject = models.CharField(max_length=200)
    message = models.TextField()
    status = models.CharField(
        max_length=20, choices=TicketStatus.choices, default=TicketStatus.OPEN
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Ticket #{self.pk}: {self.subject}"


class SupportMessage(models.Model):
    ticket = models.ForeignKey(
        SupportTicket, on_delete=models.CASCADE, related_name="messages"
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="support_messages",
    )
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Message on ticket #{self.ticket_id} by {self.author}"


class DirectMessage(models.Model):
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sent_direct_messages"
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="received_direct_messages"
    )
    message = models.TextField(max_length=2000)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [models.Index(fields=["sender", "recipient", "created_at"], name="notificatio_sender__044215_idx")]

    def __str__(self):
        return f"Message from {self.sender} to {self.recipient}"
