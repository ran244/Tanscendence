import json

from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async

from apps.accounts.services.presence import (
    connection_closed,
    connection_opened,
    heartbeat,
)
from apps.notifications.models import Notification


class AuthConsumer(AsyncJsonWebsocketConsumer):
    """
    Authenticated channel: personal notifications and presence heartbeats.
    Joined to group `user_<id>` (also used by the notification service).
    """

    async def connect(self):
        user = self.scope.get("user")
        if user is None or not user.is_authenticated:
            await self.close(code=4401)
            return
        self.user = user
        self.group_name = f"user_{user.id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await database_sync_to_async(connection_opened)(user)
        await self.accept()
        await self.send_json(
            {
                "type": "welcome",
                "user_id": user.id,
                "unread_notifications": await database_sync_to_async(self._unread_count)(),
            }
        )

    def _unread_count(self):
        return Notification.objects.filter(recipient_id=self.user.id, read_at__isnull=True).count()

    async def disconnect(self, code):
        if hasattr(self, "user"):
            await database_sync_to_async(connection_closed)(self.user)
            if hasattr(self, "group_name"):
                await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, content, **kwargs):
        kind = content.get("type")
        if kind == "presence.heartbeat":
            await database_sync_to_async(heartbeat)(self.user)
            await self.send_json({"type": "presence.heartbeat_ack"})
        elif kind == "notifications.unread":
            await self.send_json(
                {"type": "notifications.unread", "count": await database_sync_to_async(self._unread_count)()}
            )
        elif kind == "ping":
            from django.utils import timezone

            await self.send_json({"type": "pong", "now": timezone.now().isoformat()})
        else:
            await self.send_json({"type": "error", "code": "UNKNOWN_MESSAGE_TYPE"})

    # -- group broadcast handlers ------------------------------------------
    async def notification_created(self, event):
        payload = dict(event)
        payload.pop("type", None)
        await self.send_json({"type": "notification.created", **payload})

    async def presence_change(self, event):
        payload = dict(event)
        payload.pop("type", None)
        await self.send_json({"type": "presence.change", **payload})

    async def lot_alert(self, event):
        """Personal lot alerts (outbid, closing soon, ended, winner)."""
        payload = dict(event)
        payload.pop("type", None)
        await self.send_json({"type": "lot.alert", **payload})