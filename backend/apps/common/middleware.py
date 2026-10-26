import logging
import uuid

SENSITIVE_KEYWORDS = (
    "password",
    "passwd",
    "secret",
    "token",
    "cookie",
    "authorization",
    "apikey",
    "api_key",
    "card",
    "cvv",
    "totp",
    "otp",
    "secret_key",
)


class RequestIDMiddleware:
    """Attach a request id to every log record and echo it as X-Request-ID."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_id = request.META.get("HTTP_X_REQUEST_ID") or uuid.uuid4().hex[:16]
        request.request_id = request_id
        response = self.get_response(request)
        response["X-Request-ID"] = request_id
        return response


class RedactingFilter(logging.Filter):
    """Redact known sensitive values (cookies, tokens, card data) from logs."""

    def filter(self, record):
        # Framework-generated log records do not pass through our request
        # middleware, so the formatter still needs a safe fallback value.
        if not hasattr(record, "request_id"):
            record.request_id = "-"
        try:
            message = record.getMessage()
            for keyword in SENSITIVE_KEYWORDS:
                low = message.lower()
                idx = low.find(keyword)
                if idx != -1:
                    record.msg = _redact_value(message, idx, keyword)
                    record.args = ()
                    message = record.msg
            record.msg = _redact_jwt_like(message)
            record.args = ()
        except Exception:
            pass
        return True


def _redact_value(message, idx, keyword):
    """Redact the value following `keyword=` or `keyword: "value"` patterns."""
    rest = message[idx + len(keyword):]
    if rest[:1] in ("=", ":", " "):
        parts = [message[:idx + len(keyword)]]
        tail = rest.lstrip("=: ")
        if tail[:1] in ('"', "'"):
            quote = tail[0]
            end = tail.find(quote, 1)
            if end != -1:
                parts.append(tail[:end + 1].replace(tail[1:end], "[REDACTED]"))
                return "".join(parts) + tail[end + 1:]
        # redact up to next whitespace or comma
        end = len(tail)
        for sep in (" ", ",", ")", "]"):
            pos = tail.find(sep)
            if pos != -1:
                end = min(end, pos)
        parts.append("[REDACTED]")
        return "".join(parts) + tail[end:]
    return message


def _redact_jwt_like(message):
    """Redact JWT-shaped tokens in the message."""
    import re

    return re.sub(
        r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}",
        "[REDACTED]",
        message,
    )
