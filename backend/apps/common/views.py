import logging

from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.common.models import PublicApiKey

logger = logging.getLogger("apps.common")


@api_view(["GET"])
@permission_classes([AllowAny])
def health_root(request):
    return JsonResponse(
        {
            "status": "ok",
            "service": "mystery-auctions",
            "version": "1.0.0",
        }
    )


@api_view(["GET"])
@permission_classes([AllowAny])
def health_ready(request):
    """Readiness probe: verifies PostgreSQL, Redis, and migrations without
    leaking configuration details."""
    checks = {}
    ready = True
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            checks["database"] = "ok"
    except Exception as exc:
        ready = False
        checks["database"] = f"unavailable ({type(exc).__name__})"
    try:
        cache.set("health_probe", "ok", timeout=5)
        checks["cache"] = "ok" if cache.get("health_probe") == "ok" else "unavailable"
        if checks["cache"] != "ok":
            ready = False
    except Exception as exc:
        ready = False
        checks["cache"] = f"unavailable ({type(exc).__name__})"
    from django.db.migrations.executor import MigrationExecutor

    executor = MigrationExecutor(connection)
    plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
    checks["migrations"] = "ok" if not plan else "pending"
    if plan:
        ready = False
    status = "ready" if ready else "not_ready"
    return JsonResponse({"status": status, "checks": checks})


def _api_key_data(api_key):
    return {
        "id": api_key.pk,
        "name": api_key.name,
        "prefix": api_key.key_prefix,
        "is_active": api_key.is_active,
        "created_at": api_key.created_at,
        "last_used_at": api_key.last_used_at,
    }


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def api_keys(request):
    """List the user's keys or issue a key whose plaintext is shown once."""
    if request.method == "GET":
        keys = PublicApiKey.objects.filter(owner=request.user)
        return Response({"results": [_api_key_data(key) for key in keys]})
    name = str(request.data.get("name", "")).strip()
    if not name or len(name) > 100:
        return Response(
            {"code": "VALIDATION_ERROR", "message": "A name of 1-100 characters is required."},
            status=400,
        )
    api_key, plaintext = PublicApiKey.issue_key(request.user, name)
    return Response({**_api_key_data(api_key), "key": plaintext}, status=201)


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def api_key_delete(request, key_id):
    api_key = get_object_or_404(PublicApiKey, pk=key_id, owner=request.user)
    api_key.delete()
    return Response(status=204)
