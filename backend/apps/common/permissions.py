from rest_framework.permissions import BasePermission, SAFE_METHODS

from apps.accounts.models import UserRole
from apps.common.exceptions import BusinessError


ADMIN_MARKETPLACE_MESSAGE = (
    "Administrator accounts can review auctions, but cannot place bids or create or manage auction listings."
)


def ensure_auction_participant(user):
    """Keep administration separate from marketplace participation.

    Authentication resolves the user from the database on every request, so
    this check also takes effect immediately for an existing session or API
    key after a USER is promoted to ADMIN.
    """
    if not user or getattr(user, "role", None) != UserRole.USER:
        raise BusinessError(
            "ADMIN_MARKETPLACE_RESTRICTED",
            ADMIN_MARKETPLACE_MESSAGE,
            403,
        )


class IsAuctionParticipant(BasePermission):
    """Allow only regular USER accounts to perform marketplace actions."""

    def has_permission(self, request, view):
        ensure_auction_participant(request.user)
        return True


class IsAuctionParticipantOrReadOnly(BasePermission):
    """Keep historical/public reads available while blocking admin writes."""

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        ensure_auction_participant(request.user)
        return True


class IsAdmin(BasePermission):
    """Require role ADMIN (the platform-admin role used by the frontend area)."""

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.role == UserRole.ADMIN)


class IsSelfOrAdmin(BasePermission):
    """Allow the resource owner or an admin; reject everyone else."""

    def has_object_permission(self, request, view, obj):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.role == UserRole.ADMIN:
            return True
        owner = getattr(obj, "owner", None) or getattr(obj, "user", None)
        if owner is not None:
            return owner == user
        if hasattr(obj, "id") and hasattr(user, "id"):
            return obj.id == user.id
        return False


class ReadOnly(BasePermission):
    def has_permission(self, request, view):
        return request.method in ("GET", "HEAD", "OPTIONS")
