import hashlib
import hmac

from django.conf import settings
from django.middleware.csrf import get_token
from django.utils import timezone
from rest_framework import exceptions
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken

from apps.accounts.models import CustomUser


class CookieJWTAuthentication(JWTAuthentication):
    """
    Authenticate with the access token stored in the HttpOnly `access_token`
    cookie. Falls back to the Authorization header (used by API-key clients
    and scripts). CSRF is enforced for cookie-authenticated unsafe methods.
    """

    def authenticate(self, request):
        header = self.get_header(request)
        raw_token = self.get_raw_token(header) if header else None
        if raw_token is None:
            raw_token = request.COOKIES.get(settings.SIMPLE_JWT["ACCESS_COOKIE"])
        if raw_token is None:
            return None
        validated_token = self.get_validated_token(raw_token)
        user = self.get_user(validated_token)
        if raw_token == request.COOKIES.get(settings.SIMPLE_JWT["ACCESS_COOKIE"]):
            self.enforce_csrf(request)
        return user, validated_token

    def enforce_csrf(self, request):
        """
        Reject unsafe cookie-authenticated requests without a valid CSRF
        token. Mirrors DRF's SessionAuthentication enforcement.
        """
        if request.method in ("GET", "HEAD", "OPTIONS", "TRACE"):
            return
        request_csrf = request.META.get("HTTP_X_CSRFTOKEN")
        cookie_csrf = request.META.get("CSRF_COOKIE")
        if not request_csrf or not cookie_csrf:
            raise exceptions.PermissionDenied("CSRF token missing.")
        if not hmac.compare_digest(str(request_csrf), str(cookie_csrf)):
            raise exceptions.PermissionDenied("CSRF token mismatch.")


class ApiKeyAuthentication:
    """
    Authenticates requests carrying a valid `X-API-Key` header against the
    PublicApiKey store. Used by the versioned public API (/api/v1/). An API
    key NEVER grants object-level permissions: mutations still require a
    logged-in user and are checked against object ownership.
    """

    keyword = "ApiKey"
    header = "HTTP_X_API_KEY"

    def authenticate(self, request):
        raw_key = request.META.get(self.header)
        if not raw_key:
            return None
        digest = hashlib.sha256(raw_key.encode()).hexdigest()
        from apps.common.models import PublicApiKey

        try:
            api_key = PublicApiKey.objects.select_related("owner").get(key_hash=digest)
        except PublicApiKey.DoesNotExist:
            raise exceptions.AuthenticationFailed("Invalid API key.")
        if not api_key.is_active:
            raise exceptions.AuthenticationFailed("API key is inactive.")
        if not api_key.owner.is_active:
            raise exceptions.AuthenticationFailed("API key owner is inactive.")
        api_key.last_used_at = timezone.now()
        api_key.save(update_fields=["last_used_at"])
        request.api_key = api_key
        return api_key.owner, api_key

    def authenticate_header(self, request):
        return 'ApiKey realm="api"'


def generate_api_key():
    import secrets

    return secrets.token_urlsafe(32)


def hash_api_key(raw_key):
    return hashlib.sha256(raw_key.encode()).hexdigest()