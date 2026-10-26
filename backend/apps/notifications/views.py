from django.db.models import Prefetch, Q
from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.common.pagination import StandardResultsSetPagination
from apps.common.permissions import IsAdmin
from apps.notifications.models import (
    Notification,
    NotificationVerb,
    DirectMessage,
    SupportMessage,
    SupportTicket,
    TicketStatus,
)
from apps.notifications.services import mark_all_read, mark_read, notify, notify_admins
from apps.accounts.models import UserRole
from apps.accounts.services.friends import friend_user_ids


class NotificationSerializer(serializers.ModelSerializer):
    actor_username = serializers.CharField(source="actor.username", read_only=True, default=None)
    target_type = serializers.SerializerMethodField()
    target_id = serializers.IntegerField(source="target_object_id", read_only=True)
    details = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = [
            "id",
            "verb",
            "message_key",
            "actor_id",
            "actor_username",
            "target_type",
            "target_id",
            "details",
            "read_at",
            "is_read",
            "created_at",
        ]
        read_only_fields = fields

    def get_target_type(self, obj):
        return obj.target_content_type.model if obj.target_content_type else None

    def get_details(self, obj):
        target = obj.target
        if target is None:
            return {}
        target_type = self.get_target_type(obj)
        if target_type == "auctionlot":
            highest = target.highest_bid
            try:
                order_id = target.order.id
            except (AttributeError, ObjectDoesNotExist):
                order_id = None
            return {
                "auction_title": target.auction_event.title,
                "product_name": target.product.name,
                "winner_username": (
                    highest.bidder.username if highest and highest.bidder else None
                ),
                "winning_price": str(highest.amount) if highest else None,
                "has_winner": highest is not None,
                "order_id": order_id,
            }
        if target_type == "order":
            return {
                "product_name": target.auction_lot.product.name,
                "buyer_username": target.buyer.username if target.buyer else "Deleted user",
                "final_price": str(target.final_price),
                "shipping_address": target.shipping_address,
                "delivery_full_name": target.delivery_full_name,
                "delivery_city": target.delivery_city,
                "delivery_phone": target.delivery_phone,
                "preferred_delivery_at": target.preferred_delivery_at,
                "delivery_notes": target.delivery_notes,
                "order_status": target.status,
            }
        return {}


class TicketMessageSerializer(serializers.ModelSerializer):
    author_username = serializers.CharField(source="author.username", read_only=True)

    class Meta:
        model = SupportMessage
        fields = ["id", "message", "author_username", "created_at"]
        read_only_fields = ["id", "author_username", "created_at"]


class TicketSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    reporter_username = serializers.CharField(
        source="reporter.username", read_only=True, default=None
    )
    messages = TicketMessageSerializer(many=True, read_only=True)

    class Meta:
        model = SupportTicket
        fields = [
            "id",
            "subject",
            "message",
            "status",
            "status_display",
            "reporter_username",
            "messages",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "status_display",
            "reporter_username",
            "messages",
            "created_at",
            "updated_at",
        ]


class DirectMessageSerializer(serializers.ModelSerializer):
    sender_username = serializers.CharField(source="sender.username", read_only=True)
    recipient_username = serializers.CharField(source="recipient.username", read_only=True)

    class Meta:
        model = DirectMessage
        fields = ["id", "sender", "sender_username", "recipient", "recipient_username", "message", "read_at", "created_at"]
        read_only_fields = ["id", "sender", "sender_username", "recipient", "recipient_username", "read_at", "created_at"]


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def direct_messages(request, user_id):
    from django.contrib.auth import get_user_model

    if user_id not in friend_user_ids(request.user):
        return Response({"code": "NOT_FRIENDS", "message": "You can only message accepted friends."}, status=403)
    other = get_object_or_404(get_user_model(), pk=user_id, is_active=True)
    if request.method == "GET":
        queryset = DirectMessage.objects.filter(
            Q(sender=request.user, recipient=other) | Q(sender=other, recipient=request.user)
        ).select_related("sender", "recipient")
        DirectMessage.objects.filter(sender=other, recipient=request.user, read_at__isnull=True).update(read_at=timezone.now())
        return Response({"results": DirectMessageSerializer(queryset, many=True).data})
    serializer = DirectMessageSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    message = serializer.save(sender=request.user, recipient=other)
    notify(recipient=other, actor=request.user, verb=NotificationVerb.DIRECT_MESSAGE, target=message, message_key="notifications.direct_message", dedupe_key=f"direct_message_{message.pk}")
    return Response(DirectMessageSerializer(message).data, status=201)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def notification_list(request):
    queryset = Notification.objects.filter(recipient=request.user).select_related(
        "actor", "target_content_type"
    )
    unread_only = request.query_params.get("unread") == "true"
    if unread_only:
        queryset = queryset.filter(read_at__isnull=True)
    paginator = StandardResultsSetPagination()
    page = paginator.paginate_queryset(queryset, request)
    data = NotificationSerializer(page, many=True).data
    return paginator.get_paginated_response(data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def notification_unread_count(request):
    from apps.notifications.services import unread_count

    return Response({"count": unread_count(request.user)})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def notification_read(request, notification_id):
    notification = get_object_or_404(Notification, pk=notification_id, recipient=request.user)
    mark_read(notification, request.user)
    return Response({"id": notification.pk, "read": True})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def notification_read_all(request):
    count = mark_all_read(request.user)
    return Response({"read": count})


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def tickets(request):
    if request.method == "GET":
        paginator = StandardResultsSetPagination()
        queryset = SupportTicket.objects.filter(reporter=request.user).prefetch_related(
            Prefetch("messages", queryset=SupportMessage.objects.select_related("author"))
        )
        page = paginator.paginate_queryset(queryset, request)
        return paginator.get_paginated_response(TicketSerializer(page, many=True).data)
    serializer = TicketSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    ticket = serializer.save(reporter=request.user)
    SupportMessage.objects.create(ticket=ticket, author=request.user, message=serializer.validated_data["message"])
    notify_admins(
        actor=request.user,
        verb=NotificationVerb.SUPPORT_TICKET_CREATED,
        target=ticket,
        message_key="notifications.support_ticket_created",
        dedupe_key=f"support_ticket_created_{ticket.pk}",
    )
    return Response(TicketSerializer(ticket).data, status=201)


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def ticket_detail(request, ticket_id):
    ticket = get_object_or_404(SupportTicket, pk=ticket_id)
    if ticket.reporter_id != request.user.id and request.user.role != UserRole.ADMIN:
        return Response({"code": "PERMISSION_DENIED", "message": "Not your ticket."}, status=403)
    if request.method == "GET":
        return Response(TicketSerializer(ticket).data)
    if ticket.status in (TicketStatus.RESOLVED, TicketStatus.CLOSED):
        return Response(
            {"code": "INVALID_TRANSITION", "message": "This ticket is closed for replies."},
            status=409,
        )
    serializer = TicketMessageSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    message = serializer.save(ticket=ticket, author=request.user)
    if request.user.role == UserRole.ADMIN and ticket.status == TicketStatus.OPEN:
        ticket.status = TicketStatus.IN_PROGRESS
        ticket.save(update_fields=["status", "updated_at"])
    if request.user.role == UserRole.ADMIN:
        if ticket.reporter_id and ticket.reporter_id != request.user.id:
            notify(
                recipient_id=ticket.reporter_id,
                actor=request.user,
                verb=NotificationVerb.SUPPORT_REPLY,
                target=ticket,
                message_key="notifications.support_reply",
                dedupe_key=f"support_reply_{message.pk}",
            )
    else:
        notify_admins(
            actor=request.user,
            verb=NotificationVerb.SUPPORT_REPLY,
            target=ticket,
            message_key="notifications.support_user_reply",
            dedupe_key=f"support_user_reply_{message.pk}",
        )
    return Response(TicketMessageSerializer(message).data, status=201)


@api_view(["GET"])
@permission_classes([IsAdmin])
def admin_tickets(request):
    status_filter = request.query_params.get("status")
    queryset = SupportTicket.objects.select_related("reporter").prefetch_related(
        Prefetch("messages", queryset=SupportMessage.objects.select_related("author"))
    )
    if status_filter:
        queryset = queryset.filter(status=status_filter.upper())
    paginator = StandardResultsSetPagination()
    page = paginator.paginate_queryset(queryset, request)
    return paginator.get_paginated_response(TicketSerializer(page, many=True).data)


@api_view(["PATCH"])
@permission_classes([IsAdmin])
def admin_ticket_status(request, ticket_id):
    ticket = get_object_or_404(SupportTicket, pk=ticket_id)
    status_value = request.data.get("status")
    if status_value not in TicketStatus.values:
        return Response({"code": "VALIDATION_ERROR", "message": "Invalid status."}, status=400)
    previous = ticket.status
    ticket.status = status_value
    ticket.save(update_fields=["status", "updated_at"])
    if ticket.reporter_id and previous != status_value:
        notify(
            recipient_id=ticket.reporter_id,
            actor=request.user,
            verb="TICKET_STATUS_CHANGED",
            target=ticket,
            message_key="notifications.ticket_status_changed",
            dedupe_key=f"ticket_status_{ticket.pk}_{status_value}",
        )
    return Response(TicketSerializer(ticket).data)
