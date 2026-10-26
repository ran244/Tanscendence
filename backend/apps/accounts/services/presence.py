"""
Online presence backed by Redis.

For each user we keep a counter of open authenticated WebSocket connections
(`presence:{user_id}`) with a TTL. A heartbeat from any open connection
refreshes the TTL, so stale entries (crashed tabs, lost networks) expire
automatically without manual cleanup.
"""
import json
import logging

from channels.layers import get_channel_layer
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger("apps.accounts")

PRESENCE_TTL = 150  # seconds
HEARTBEAT_INTERVAL = 45  # seconds (must be < PRESENCE_TTL)

KEY_PREFIX = "presence:"


def _key(user_id):
    return f"{KEY_PREFIX}{user_id}"


def connection_opened(user):
    key = _key(user.id)
    data = cache.get(key)
    if data is None:
        data = {"connections": 0, "last_seen": timezone.now().isoformat()}
    data["connections"] = int(data.get("connections", 0)) + 1
    data["last_seen"] = timezone.now().isoformat()
    cache.set(key, data, timeout=PRESENCE_TTL)
    return data


def connection_closed(user):
    key = _key(user.id)
    data = cache.get(key)
    if data is None:
        return None
    data["connections"] = max(0, int(data.get("connections", 0)) - 1)
    data["last_seen"] = timezone.now().isoformat()
    if data["connections"] == 0:
        cache.delete(key)
        return {"connections": 0}
    cache.set(key, data, timeout=PRESENCE_TTL)
    return data


def heartbeat(user):
    key = _key(user.id)
    data = cache.get(key)
    if data is None:
        data = {"connections": 1, "last_seen": timezone.now().isoformat()}
    data["last_seen"] = timezone.now().isoformat()
    cache.set(key, data, timeout=PRESENCE_TTL)
    return data


def is_user_online(user):
    data = cache.get(_key(user.id))
    if not data:
        return False
    return int(data.get("connections", 0)) > 0


def online_status_for(users):
    """Bulk status lookup; returns {user_id: bool}."""
    return {u.id: is_user_online(u) for u in users}


async def broadcast_presence(user, online):
    """Notify the user's friends about a presence change (best effort)."""
    from apps.accounts.services.friends import friend_user_ids

    friend_ids = friend_user_ids(user)
    if not friend_ids:
        return
    channel_layer = get_channel_layer()
    payload = {"type": "presence.change", "user_id": user.id, "online": online}
    for other_id in friend_ids:
        await channel_layer.group_send(f"user_{other_id}", payload)