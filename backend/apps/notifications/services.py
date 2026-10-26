import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.utils import timezone

from .models import Notification

logger = logging.getLogger("apps.notifications")


def notify(recipient=None, recipient_id=None, actor=None, verb="", target=None,
           message_key="", dedupe_key=None):
    """
    Create a persistent notification and deliver it in real time.

    Dedupe: notifications with the same `dedupe_key` (used by retried tasks)
    are created only once. Auction-bid notifications pass dedupe_key=None and
    are always unique rows.
    """
    recipient_obj = recipient
    if recipient_id is not None:
        from django.contrib.auth import get_user_model

        recipient_obj = get_user_model().objects.filter(pk=recipient_id).first()
    if recipient_obj is None:
        return None

    if dedupe_key:
        with transaction.atomic():
            notification, created = Notification.objects.get_or_create(
                dedupe_key=dedupe_key,
                defaults={
                    "recipient": recipient_obj,
                    "actor": actor,
                    "verb": verb,
                    "message_key": message_key,
                    "target": target,
                },
            )
    else:
        notification = Notification.objects.create(
            recipient=recipient_obj,
            actor=actor,
            verb=verb,
            message_key=message_key,
            target=target,
        )
        created = True

    if created:
        deliver(notification)
    return notification


def notify_admins(*, actor=None, verb="", target=None, message_key="", dedupe_key=None):
    """Fan out an actionable platform activity to every active administrator."""
    from django.contrib.auth import get_user_model

    administrators = get_user_model().objects.filter(role="ADMIN", is_active=True)
    if actor is not None:
        administrators = administrators.exclude(pk=actor.pk)

    notifications = []
    for administrator in administrators:
        recipient_key = None
        if dedupe_key:
            suffix = f"_{administrator.pk}"
            recipient_key = f"{dedupe_key[:64 - len(suffix)]}{suffix}"
        notifications.append(
            notify(
                recipient=administrator,
                actor=actor,
                verb=verb,
                target=target,
                message_key=message_key,
                dedupe_key=recipient_key,
            )
        )
    return notifications


def deliver(notification):
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    notification = Notification.objects.select_related("actor", "target_content_type").get(pk=notification.pk)
    payload = {
        "notification": {
            "id": notification.pk,
            "verb": notification.verb,
            "message_key": notification.message_key,
            "actor_id": notification.actor_id,
            "actor_username": notification.actor.username if notification.actor else None,
            "target_type": (
                notification.target_content_type.model if notification.target_content_type else None
            ),
            "target_id": notification.target_object_id,
            "created_at": notification.created_at.isoformat(),
            "read": False,
        }
    }
    async_to_sync(channel_layer.group_send)(f"user_{notification.recipient_id}", {
        "type": "notification.created",
        **payload,
    })


def mark_read(notification, user):
    if notification.recipient_id != user.id:
        return False
    if notification.read_at is None:
        notification.read_at = timezone.now()
        notification.save(update_fields=["read_at"])
    return True


def mark_all_read(user):
    return Notification.objects.filter(recipient=user, read_at__isnull=True).update(
        read_at=timezone.now()
    )


def unread_count(user):
    return Notification.objects.filter(recipient=user, read_at__isnull=True).count()
