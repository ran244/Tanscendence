import hashlib
import logging
import secrets

from django.conf import settings
from django.core.cache import cache
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.db import transaction
from django.utils import timezone
from rest_framework import exceptions
from rest_framework_simplejwt.tokens import RefreshToken

from apps.common.exceptions import BusinessError, ErrorCodes
from apps.accounts.models import TwoFactorRecoveryCode

logger = logging.getLogger("apps.accounts")

User = get_user_model()

TWO_FA_CHALLENGE_COOKIE = "two_fa_challenge"
TWO_FA_CHALLENGE_TTL = 10 * 60  # seconds

RESET_TOKEN_TTL = 30 * 60  # seconds
RESET_TOKEN_SALT = "mystery-auctions-password-reset"
EMAIL_VERIFICATION_TOKEN_TTL = 24 * 60 * 60  # seconds
EMAIL_VERIFICATION_TOKEN_SALT = "mystery-auctions-email-verification"

ACCESS_COOKIE = settings.SIMPLE_JWT["ACCESS_COOKIE"]
REFRESH_COOKIE = settings.SIMPLE_JWT["REFRESH_COOKIE"]


def _access_cookie_path():
    return settings.SIMPLE_JWT["ACCESS_COOKIE_PATH"]


def _refresh_cookie_path():
    return settings.SIMPLE_JWT["REFRESH_COOKIE_PATH"]


def _cookie_kwargs():
    return {
        "secure": settings.SIMPLE_JWT["COOKIE_SECURE"],
        "httponly": settings.SIMPLE_JWT["COOKIE_HTTPONLY"],
        "samesite": settings.SIMPLE_JWT["COOKIE_SAMESITE"],
    }


def set_auth_cookies(response, user):
    """Issue fresh access/refresh cookies for a user."""
    refresh = RefreshToken.for_user(user)
    response.set_cookie(
        ACCESS_COOKIE,
        str(refresh.access_token),
        max_age=settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"].total_seconds(),
        path=_access_cookie_path(),
        **_cookie_kwargs(),
    )
    response.set_cookie(
        REFRESH_COOKIE,
        str(refresh),
        max_age=settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds(),
        path=_refresh_cookie_path(),
        **_cookie_kwargs(),
    )
    return refresh


def clear_auth_cookies(response):
    response.delete_cookie(ACCESS_COOKIE, path=_access_cookie_path())
    response.delete_cookie(REFRESH_COOKIE, path=_refresh_cookie_path())
    response.delete_cookie(TWO_FA_CHALLENGE_COOKIE, path="/")


def blacklist_refresh(refresh_token_value):
    try:
        token = RefreshToken(refresh_token_value)
        token.blacklist()
    except Exception:
        logger.debug("refresh token already blacklisted or invalid")


def set_two_fa_challenge_cookie(response, user):
    challenge = secrets.token_urlsafe(24)
    cache.set(
        f"two_fa_challenge:{challenge}",
        str(user.pk),
        timeout=TWO_FA_CHALLENGE_TTL,
    )
    signer = TimestampSigner()
    signed = signer.sign(f"{user.pk}:{challenge}")
    response.set_cookie(
        TWO_FA_CHALLENGE_COOKIE,
        signed,
        max_age=TWO_FA_CHALLENGE_TTL,
        path="/",
        secure=settings.SIMPLE_JWT["COOKIE_SECURE"],
        httponly=True,
        samesite=settings.SIMPLE_JWT["COOKIE_SAMESITE"],
    )


def consume_two_fa_challenge(cookie_value):
    signer = TimestampSigner()
    try:
        value = signer.unsign(cookie_value, max_age=TWO_FA_CHALLENGE_TTL)
    except (BadSignature, SignatureExpired):
        return None
    user_id, separator, challenge = value.partition(":")
    if not separator or not challenge:
        return None
    cache_key = f"two_fa_challenge:{challenge}"
    cached_user_id = cache.get(cache_key)
    if str(cached_user_id) != user_id:
        return None
    # A login challenge is deliberately single-use, including when the code
    # supplied after consuming it is wrong. The user can start a fresh login.
    cache.delete(cache_key)
    try:
        return User.objects.get(pk=user_id, is_active=True)
    except User.DoesNotExist:
        return None


def authenticate_login(email, password):
    """Return the user or raise BusinessError with the right code."""
    try:
        user = User.objects.get(email__iexact=email.strip())
    except User.DoesNotExist:
        raise BusinessError(ErrorCodes.AUTHENTICATION_FAILED, "Invalid credentials.", 401)
    if not user.check_password(password):
        raise BusinessError(ErrorCodes.AUTHENTICATION_FAILED, "Invalid credentials.", 401)
    if not user.is_active:
        if not user.email_verified:
            raise BusinessError(
                "EMAIL_NOT_VERIFIED",
                "Verify your email address before logging in.",
                403,
            )
        raise BusinessError("ACCOUNT_DEACTIVATED", "This account is deactivated.", 403)
    return user


def send_email_verification(user):
    """Send a signed, expiring activation link to a registered user."""
    token = TimestampSigner(salt=EMAIL_VERIFICATION_TOKEN_SALT).sign(str(user.pk))
    verification_url = f"{settings.EMAIL_VERIFICATION_FRONTEND_URL}?code={token}"
    subject = "Verify your Mystery Auctions email"
    body = (
        f"Hello {user.username},\n\n"
        "Please verify your email address by opening this link:\n\n"
        f"{verification_url}\n\n"
        f"The link expires in {EMAIL_VERIFICATION_TOKEN_TTL // 3600} hours. "
        "If you did not create this account, you can ignore this email.\n\n"
        "Mystery Auctions"
    )
    # Django's console email backend emits MIME quoted-printable output, which
    # turns the query-string '=' into '=3D' and may wrap long URLs. Provide a
    # copy-safe single-line link only in local debug logs.
    if settings.DEBUG:
        logger.info("DEV_EMAIL_VERIFICATION_LINK %s", verification_url)
    try:
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False)
    except Exception as exc:
        logger.error("failed to send email verification: %s", exc)
        raise


def verify_email(token):
    signer = TimestampSigner(salt=EMAIL_VERIFICATION_TOKEN_SALT)
    try:
        value = signer.unsign(token, max_age=EMAIL_VERIFICATION_TOKEN_TTL)
        user = User.objects.get(pk=value)
    except (BadSignature, SignatureExpired, User.DoesNotExist, ValueError):
        raise BusinessError(
            "INVALID_VERIFICATION_TOKEN",
            "This verification link is invalid or has expired.",
            400,
        )
    if not user.email_verified or not user.is_active:
        user.email_verified = True
        user.is_active = True
        user.save(update_fields=["email_verified", "is_active"])
    return user


def resend_email_verification(email):
    """Do not disclose whether an address is registered."""
    try:
        user = User.objects.get(email__iexact=email.strip())
    except User.DoesNotExist:
        return
    if not user.email_verified:
        send_email_verification(user)


def verify_totp(user, code):
    import pyotp

    if not user.totp_secret:
        return False
    totp = pyotp.TOTP(user.totp_secret)
    return totp.verify(code, valid_window=1)


def generate_totp_secret():
    import pyotp

    return pyotp.random_base32()


def totp_provisioning_uri(user):
    import pyotp

    totp = pyotp.TOTP(user.totp_secret)
    return totp.provisioning_uri(name=user.email, issuer_name="Mystery Auctions")


def totp_qr_svg(user):
    import qrcode
    import qrcode.image.svg

    factory = qrcode.image.svg.SvgPathImage
    img = qrcode.make(totp_provisioning_uri(user), image_factory=factory)
    stream = img.to_string()
    return stream.decode("utf-8")


def enable_two_fa(user, code):
    if user.totp_enabled:
        raise BusinessError("TWO_FA_ALREADY_ENABLED", "Two-factor authentication is already enabled.")
    if not user.totp_secret:
        raise BusinessError("TWO_FA_NOT_SETUP", "Request a 2FA setup first.")
    if not verify_totp(user, code):
        raise BusinessError(ErrorCodes.TWO_FA_INVALID, "Invalid TOTP code.")
    user.totp_enabled = True
    user.totp_confirmed_at = timezone.now()
    user.save(update_fields=["totp_enabled", "totp_confirmed_at"])
    return TwoFactorRecoveryCode.issue_codes(user)


def disable_two_fa(user, code=None, password=None):
    if not user.totp_enabled:
        raise BusinessError("TWO_FA_NOT_ENABLED", "Two-factor authentication is not enabled.")
    if password and user.check_password(password):
        pass
    elif code and verify_totp(user, code):
        pass
    else:
        raise BusinessError(ErrorCodes.TWO_FA_INVALID, "Invalid TOTP code or password.")
    user.totp_enabled = False
    user.totp_secret = ""
    user.totp_confirmed_at = None
    user.save(update_fields=["totp_enabled", "totp_secret", "totp_confirmed_at"])
    TwoFactorRecoveryCode.objects.filter(user=user).delete()


def verify_two_fa_challenge(user, code, is_recovery):
    if is_recovery:
        if not TwoFactorRecoveryCode.consume_code(user, code):
            raise BusinessError(ErrorCodes.TWO_FA_INVALID, "Invalid recovery code.")
        return
    if not verify_totp(user, code):
        raise BusinessError(ErrorCodes.TWO_FA_INVALID, "Invalid TOTP code.")


def send_password_reset_email(email):
    """Never reveal whether the email exists."""
    try:
        user = User.objects.get(email__iexact=email.strip())
    except User.DoesNotExist:
        logger.info("password reset requested for unknown email")
        return
    token = TimestampSigner(salt=RESET_TOKEN_SALT).sign(str(user.pk))
    subject = "Reset your Mystery Auctions password"
    reset_url = f"{settings.PASSWORD_RESET_FRONTEND_URL}/reset-password?token={token}"
    body = (
        f"Hello {user.username},\n\n"
        f"Someone requested a password reset for this account. If that was you, open:\n\n"
        f"{reset_url}\n\n"
        f"The link expires in {RESET_TOKEN_TTL // 60} minutes. If you did not request "
        f"this, you can safely ignore this email.\n\n"
        f"Mystery Auctions (educational project — orders use cash on delivery)."
    )
    try:
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False)
    except Exception as exc:  # pragma: no cover - smtp failures must not leak
        logger.error("failed to send password reset email: %s", exc)


def confirm_password_reset(token, new_password):
    signer = TimestampSigner(salt=RESET_TOKEN_SALT)
    try:
        value = signer.unsign(token, max_age=RESET_TOKEN_TTL)
        user = User.objects.get(pk=value, is_active=True)
    except (BadSignature, SignatureExpired, User.DoesNotExist, ValueError):
        raise BusinessError("INVALID_RESET_TOKEN", "Invalid or expired reset token.", 400)
    user.set_password(new_password)
    user.save(update_fields=["password"])
    return user


def delete_account(user, password, code=None):
    """Permanently remove a participant while preserving anonymized history.

    Historical marketplace foreign keys use SET_NULL. Deletion is refused
    while the participant still has an obligation that needs their identity:
    an unfinished auction they organize, a current winning bid, or an
    unfinished order as buyer or seller.
    """
    from django.db.models import Q

    from apps.accounts.models import UserRole
    from apps.auctions.models import (
        AuctionEvent,
        AuctionEventStatus,
        AuctionLot,
        AuctionLotStatus,
        BidStatus,
    )
    from apps.orders.models import Order, OrderStatus

    with transaction.atomic():
        locked = User.objects.select_for_update().get(pk=user.pk)
        if locked.role == UserRole.ADMIN or locked.is_staff or locked.is_superuser:
            raise BusinessError(
                "ADMIN_ACCOUNT_PROTECTED",
                "Administrator accounts cannot delete themselves.",
                403,
            )
        if not locked.check_password(password):
            raise BusinessError("INVALID_PASSWORD", "Incorrect password.", 400)
        if locked.totp_enabled:
            valid_code = bool(code) and (
                verify_totp(locked, code)
                or TwoFactorRecoveryCode.consume_code(locked, code)
            )
            if not valid_code:
                raise BusinessError(
                    ErrorCodes.TWO_FA_INVALID,
                    "A valid TOTP or recovery code is required.",
                )

        unfinished_events = AuctionEvent.objects.filter(organizer=locked).exclude(
            status__in=[AuctionEventStatus.ENDED, AuctionEventStatus.CANCELLED]
        )
        current_winning_bids = AuctionLot.objects.filter(
            status__in=[AuctionLotStatus.SCHEDULED, AuctionLotStatus.ACTIVE],
            highest_bid__bidder=locked,
            highest_bid__status=BidStatus.ACCEPTED,
        )
        unfinished_orders = Order.objects.filter(
            Q(buyer=locked) | Q(seller=locked)
        ).exclude(status__in=[OrderStatus.DELIVERED, OrderStatus.CANCELLED])
        blockers = []
        if unfinished_events.exists():
            blockers.append("unfinished auctions")
        if current_winning_bids.exists():
            blockers.append("current winning bids")
        if unfinished_orders.exists():
            blockers.append("unfinished orders")
        if blockers:
            raise BusinessError(
                "ACCOUNT_HAS_ACTIVE_OBLIGATIONS",
                "Resolve your " + ", ".join(blockers) + " before deleting your account.",
                409,
            )

        # Delivery addresses are personal data and are not needed once an
        # order is terminal. Financial and auction facts remain for history.
        Order.objects.filter(buyer=locked).update(shipping_address="")

        avatar_name = locked.avatar.name if locked.avatar else ""
        avatar_storage = locked.avatar.storage if locked.avatar else None
        deleted_user_id = locked.pk
        locked.delete()

        if avatar_name and avatar_storage:
            transaction.on_commit(lambda: avatar_storage.delete(avatar_name))
        transaction.on_commit(lambda: cache.delete(f"presence:{deleted_user_id}"))

    return deleted_user_id


def change_password(user, current, new):
    if not user.check_password(current):
        raise BusinessError("INVALID_PASSWORD", "Incorrect current password.", 400)
    user.set_password(new)
    user.save(update_fields=["password"])
