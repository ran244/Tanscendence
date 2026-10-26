import logging

from django.core.exceptions import PermissionDenied, ValidationError as DjangoValidationError
from django.http import Http404
from rest_framework import exceptions, status
from rest_framework.views import exception_handler

logger = logging.getLogger("apps.common")

# Map DRF exception codes to the stable machine-readable codes exposed in the
# API envelope. Codes are documented in docs/API_AND_WEBSOCKETS.md.
CODE_MAP = {
    "not_found": "NOT_FOUND",
    "permission_denied": "PERMISSION_DENIED",
    "authentication_failed": "AUTHENTICATION_FAILED",
    "invalid": "VALIDATION_ERROR",
    "not_authenticated": "NOT_AUTHENTICATED",
    "throttled": "RATE_LIMITED",
    "method_not_allowed": "METHOD_NOT_ALLOWED",
    "parse_error": "PARSE_ERROR",
    "token_not_valid": "TOKEN_NOT_VALID",
    "bad_request": "BAD_REQUEST",
}


def api_exception_handler(exc, context):
    """Consistent error envelope: {code, message, errors, detail}."""

    if isinstance(exc, BusinessError):
        return business_error_response(exc, context.get("request"))

    if isinstance(exc, Http404):
        exc = exceptions.NotFound()
    elif isinstance(exc, PermissionDenied):
        exc = exceptions.PermissionDenied()
    elif isinstance(exc, DjangoValidationError):
        exc = exceptions.ValidationError(exc.messages)

    response = exception_handler(exc, context)
    if response is None:
        logger.error(
            "unhandled_api_error %s: %s",
            type(exc).__name__,
            str(exc)[:500],
        )
        return response

    detail = response.data
    message = None
    errors = None
    code = CODE_MAP.get(getattr(exc, "default_code", "invalid"), "VALIDATION_ERROR")

    if isinstance(detail, dict):
        message = detail.pop("message", None)
        errors = detail.pop("errors", detail)
        if "detail" in detail:
            message = message or detail["detail"]
    elif isinstance(detail, list) and detail and isinstance(detail[0], dict):
        message = str(detail[0].get("detail", ""))
        errors = detail
    else:
        message = str(detail) if detail else None

    if message is None:
        message = _default_message(exc)

    response.data = {
        "code": code,
        "message": message,
        "errors": errors if errors not in (None, {}, [], "") else None,
        "status": response.status_code,
    }
    if hasattr(context, "request") and hasattr(context.request, "request_id"):
        response.data["request_id"] = context.request.request_id
    return response


def _default_message(exc):
    if isinstance(exc, exceptions.Throttled):
        return f"Rate limit exceeded. Try again in {exc.wait} seconds."
    return getattr(exc, "detail", "An unexpected error occurred.")


class ErrorCodes:
    """Stable error codes used by business services (documented in API docs)."""

    AUTHENTICATION_FAILED = "AUTHENTICATION_FAILED"
    AUCTION_NOT_ACTIVE = "AUCTION_NOT_ACTIVE"
    LOT_NOT_ACTIVE = "LOT_NOT_ACTIVE"
    LOWER_THAN_CURRENT = "LOWER_THAN_CURRENT"
    MINIMUM_INCREMENT_NOT_MET = "MINIMUM_INCREMENT_NOT_MET"
    SELLER_BIDDING = "SELLER_BIDDING"
    BLOCKED_USER = "BLOCKED_USER"
    INVALID_AMOUNT = "INVALID_AMOUNT"
    EVENT_LOCKED = "EVENT_LOCKED"
    EVENT_NOT_EDITABLE = "EVENT_NOT_EDITABLE"
    PRODUCT_ALREADY_LISTED = "PRODUCT_ALREADY_LISTED"
    LOT_TIME_OUTSIDE_EVENT = "LOT_TIME_OUTSIDE_EVENT"
    LOT_NUMBER_TAKEN = "LOT_NUMBER_TAKEN"
    NOT_OWNER = "NOT_OWNER"
    ALREADY_ACTIVE_LOT = "ALREADY_ACTIVE_LOT"
    ORDER_NOT_PAYABLE = "ORDER_NOT_PAYABLE"
    INVALID_TRANSITION = "INVALID_TRANSITION"
    TWO_FA_REQUIRED = "TWO_FA_REQUIRED"
    TWO_FA_INVALID = "TWO_FA_INVALID"
    IDEMPOTENCY_CONFLICT = "IDEMPOTENCY_CONFLICT"
    INVALID_FILE = "INVALID_FILE"
    NOT_FRIENDS = "NOT_FRIENDS"


class BusinessError(Exception):
    """Raised by services; converted to a 4xx response by the view layer."""

    def __init__(self, code, message, status_code=status.HTTP_400_BAD_REQUEST, field_errors=None):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.field_errors = field_errors or {}
        super().__init__(message)


def business_error_response(error, request):
    """Turn a BusinessError into the standard envelope."""
    from rest_framework.response import Response

    data = {
        "code": error.code,
        "message": error.message,
        "errors": error.field_errors or None,
        "status": error.status_code,
    }
    if hasattr(request, "request_id"):
        data["request_id"] = request.request_id
    return Response(data, status=error.status_code)
