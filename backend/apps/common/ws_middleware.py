import asyncio
import json

from channels.db import database_sync_to_async
from django.conf import settings
from rest_framework_simplejwt.tokens import AccessToken


async def get_user_from_scope(scope):
    """Resolve the user from the validated access token cookie in the scope."""
    user = None
    for header_name, header_value in scope.get("headers", []):
        if header_name == b"cookie":
            cookies = _parse_cookies(header_value.decode("latin-1"))
            raw_token = cookies.get(settings.SIMPLE_JWT["ACCESS_COOKIE"])
            if raw_token:
                try:
                    access = AccessToken(raw_token)
                    user = await database_sync_to_async(_get_user)(access["user_id"])
                except Exception:
                    user = None
            break
    return user


def _parse_cookies(cookie_header):
    cookies = {}
    for part in cookie_header.split(";"):
        if "=" in part:
            key, _, value = part.strip().partition("=")
            cookies[key] = value
    return cookies


def _get_user(user_id):
    from django.contrib.auth import get_user_model

    User = get_user_model()
    try:
        return User.objects.get(pk=user_id, is_active=True)
    except User.DoesNotExist:
        return None


def is_allowed_origin(scope):
    from django.conf import settings

    origin = None
    for header_name, header_value in scope.get("headers", []):
        if header_name == b"origin":
            origin = header_value.decode("latin-1")
    if origin is None:
        # Non-browser clients (tests, scripts) may omit Origin.
        return True
    if "://" in origin:
        origin = origin.split("://", 1)[1]
    origin_host = origin.split("/", 1)[0].split(":")[0]
    allowed = {h.split(":")[0] for h in settings.ALLOWED_HOSTS}
    return "*" in allowed or origin_host in allowed


class JwtAuthMiddleware:
    """Populate scope['user'] from the access-token cookie."""

    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        scope["user"] = await get_user_from_scope(scope)
        return await self.inner(scope, receive, send)


class OriginValidatorMiddleware:
    """Reject WebSocket handshakes from unknown origins."""

    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        if not is_allowed_origin(scope):
            await send(
                {
                    "type": "websocket.close",
                    "code": 4403,
                }
            )
            return
        return await self.inner(scope, receive, send)
