from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import exceptions, status as http_status
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
    throttle_classes,
)
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from apps.common.exceptions import BusinessError, business_error_response
from apps.common.permissions import IsAdmin
from apps.common.throttling import (
    LoginThrottle,
    PasswordResetThrottle,
    RegisterThrottle,
    TwoFactorThrottle,
)
from apps.accounts.models import UserRole
from apps.accounts.serializers import (
    AdminUserListSerializer,
    AdminUserUpdateSerializer,
    DeleteAccountSerializer,
    EmailVerificationResendSerializer,
    LoginSerializer,
    PasswordChangeSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    ProfileSerializer,
    PublicProfileSerializer,
    RegistrationSerializer,
    TwoFADisableSerializer,
    TwoFAEnableSerializer,
    TwoFAVerifySerializer,
)
from apps.accounts.services import auth as auth_service
from apps.accounts.services.friends import (
    accept_friend_request,
    decline_friend_request,
    friend_user_ids,
    incoming_requests,
    list_friends,
    remove_friend,
    send_friend_request,
)

User = get_user_model()


def _handle(fn):
    """Decorator converting BusinessError into the standard error envelope."""

    def wrapper(request, *args, **kwargs):
        try:
            return fn(request, *args, **kwargs)
        except BusinessError as error:
            return business_error_response(error, request)

    return wrapper


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([RegisterThrottle])
@_handle
def register(request):
    serializer = RegistrationSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        with transaction.atomic():
            user = serializer.save()
            auth_service.send_email_verification(user)
    except Exception as exc:
        raise BusinessError(
            "VERIFICATION_EMAIL_FAILED",
            "We could not send the verification email. Please try again shortly.",
            503,
        ) from exc
    response = Response(
        {
            "message": "Registration successful. Check your email to verify your account, then log in.",
            "username": user.username,
            "email": user.email,
        },
        status=http_status.HTTP_201_CREATED,
    )
    return response


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
@_handle
def verify_email(request):
    token = request.query_params.get("code", "")
    if not token:
        raise BusinessError("VERIFICATION_TOKEN_REQUIRED", "Verification token is required.")
    auth_service.verify_email(token)
    return Response({"message": "Email verified successfully. You can now log in."})


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([PasswordResetThrottle])
def resend_email_verification(request):
    serializer = EmailVerificationResendSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    auth_service.resend_email_verification(serializer.validated_data["email"])
    return Response(
        {"message": "If that account still needs verification, a new email has been sent."}
    )


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([LoginThrottle])
def login(request):
    serializer = LoginSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = auth_service.authenticate_login(
        serializer.validated_data["email"], serializer.validated_data["password"]
    )
    if user.totp_enabled:
        response = Response(
            {"two_factor_required": True, "message": "Enter your TOTP code or a recovery code."}
        )
        auth_service.set_two_fa_challenge_cookie(response, user)
        return response
    response = Response({"message": "Login successful.", "username": user.username})
    auth_service.set_auth_cookies(response, user)
    response["X-CSRFToken"] = get_token(request)
    return response


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([TwoFactorThrottle])
def verify_two_fa(request):
    serializer = TwoFAVerifySerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    challenge = request.COOKIES.get(auth_service.TWO_FA_CHALLENGE_COOKIE)
    user = auth_service.consume_two_fa_challenge(challenge) if challenge else None
    if user is None:
        raise BusinessError("TWO_FA_CHALLENGE_EXPIRED", "Login session expired. Log in again.", 401)
    auth_service.verify_two_fa_challenge(
        user, serializer.validated_data["code"], serializer.validated_data["recovery"]
    )
    response = Response({"message": "Login successful."})
    auth_service.set_auth_cookies(response, user)
    auth_service.clear_auth_cookies(response)
    auth_service.set_auth_cookies(response, user)
    response["X-CSRFToken"] = get_token(request)
    return response


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([LoginThrottle])
def refresh(request):
    refresh_value = request.COOKIES.get(settings.SIMPLE_JWT["REFRESH_COOKIE"])
    if not refresh_value:
        raise BusinessError("NOT_AUTHENTICATED", "Refresh token missing.", 401)
    try:
        refresh_token = RefreshToken(refresh_value)
        refresh_token.blacklist()
        user = User.objects.get(pk=refresh_token["user_id"], is_active=True)
        new_refresh = RefreshToken.for_user(user)
    except (InvalidToken, TokenError, User.DoesNotExist, KeyError):
        raise BusinessError("TOKEN_NOT_VALID", "Invalid or expired refresh token.", 401)
    response = Response({"message": "Tokens refreshed."})
    response.set_cookie(
        settings.SIMPLE_JWT["ACCESS_COOKIE"],
        str(new_refresh.access_token),
        max_age=settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"].total_seconds(),
        path=settings.SIMPLE_JWT["ACCESS_COOKIE_PATH"],
        secure=settings.SIMPLE_JWT["COOKIE_SECURE"],
        httponly=True,
        samesite=settings.SIMPLE_JWT["COOKIE_SAMESITE"],
    )
    response.set_cookie(
        settings.SIMPLE_JWT["REFRESH_COOKIE"],
        str(new_refresh),
        max_age=settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds(),
        path=settings.SIMPLE_JWT["REFRESH_COOKIE_PATH"],
        secure=settings.SIMPLE_JWT["COOKIE_SECURE"],
        httponly=True,
        samesite=settings.SIMPLE_JWT["COOKIE_SAMESITE"],
    )
    return response


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout(request):
    refresh_value = request.COOKIES.get(settings.SIMPLE_JWT["REFRESH_COOKIE"])
    if refresh_value:
        auth_service.blacklist_refresh(refresh_value)
    response = Response({"message": "Logged out."})
    auth_service.clear_auth_cookies(response)
    return response


@api_view(["GET", "PATCH"])
@permission_classes([AllowAny])
def me(request):
    if request.method == "GET":
        # The SPA calls this endpoint during startup to discover whether the
        # browser has an authenticated session. Being signed out is a normal
        # state, so avoid turning that probe into a noisy 403 in the browser.
        if not request.user.is_authenticated:
            return Response(status=http_status.HTTP_204_NO_CONTENT)
        return Response(ProfileSerializer(request.user, context={"request": request}).data)
    if not request.user.is_authenticated:
        raise exceptions.NotAuthenticated()
    serializer = ProfileSerializer(
        request.user, data=request.data, partial=True, context={"request": request}
    )
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(ProfileSerializer(request.user, context={"request": request}).data)


@api_view(["POST", "DELETE"])
@permission_classes([IsAuthenticated])
def avatar(request):
    if request.method == "POST":
        serializer = ProfileSerializer(
            request.user, data={"avatar": request.FILES.get("avatar")}, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(ProfileSerializer(request.user, context={"request": request}).data)
    user = request.user
    if user.avatar:
        user.avatar.delete(save=False)
    user.save(update_fields=["avatar"])
    return Response(ProfileSerializer(user, context={"request": request}).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@_handle
def password_change(request):
    serializer = PasswordChangeSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    auth_service.change_password(request.user, data["current_password"], data["new_password"])
    return Response({"message": "Password changed. Log in again with the new password."})


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([PasswordResetThrottle])
def password_reset_request(request):
    serializer = PasswordResetRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    auth_service.send_password_reset_email(serializer.validated_data["email"])
    return Response(
        {
            "message": "If an account exists for this email, a reset link has been sent. "
            "Check your inbox (console backend prints it in the server log in development)."
        }
    )


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([PasswordResetThrottle])
@_handle
def password_reset_confirm(request):
    serializer = PasswordResetConfirmSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    auth_service.confirm_password_reset(data["token"], data["new_password"])
    return Response({"message": "Password reset. You can now log in."})


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def two_fa_setup(request):
    if request.method == "GET":
        user = request.user
        if user.totp_enabled:
            return Response({"enabled": True})
        if not user.totp_secret:
            user.totp_secret = auth_service.generate_totp_secret()
            user.save(update_fields=["totp_secret"])
        return Response(
            {
                "enabled": False,
                "secret": user.totp_secret,
                "provisioning_uri": auth_service.totp_provisioning_uri(user),
                "qr_svg": auth_service.totp_qr_svg(user),
            }
        )
    return Response({"message": "Use /me/2fa/enable to confirm your code."})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@_handle
def two_fa_enable(request):
    serializer = TwoFAEnableSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    codes = auth_service.enable_two_fa(request.user, serializer.validated_data["code"])
    return Response(
        {
            "message": "Two-factor authentication enabled.",
            "recovery_codes": codes,
            "warning": "Store these recovery codes somewhere safe. They are shown only once.",
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@_handle
def two_fa_disable(request):
    serializer = TwoFADisableSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    auth_service.disable_two_fa(request.user, code=data.get("code"), password=data.get("password"))
    return Response({"message": "Two-factor authentication disabled."})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@_handle
def delete_account(request):
    serializer = DeleteAccountSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    auth_service.delete_account(
        request.user, data["password"], code=data.get("code") or None
    )
    response = Response({"message": "Your account was permanently deleted."})
    auth_service.clear_auth_cookies(response)
    return response


@api_view(["GET"])
@permission_classes([AllowAny])
def public_profile(request, user_id):
    user = get_object_or_404(User, pk=user_id, is_active=True)
    return Response(PublicProfileSerializer(user, context={"request": request}).data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def user_search(request):
    search = request.query_params.get("search", "").strip()
    if len(search) < 2:
        return Response({"results": []})
    users = User.objects.filter(is_active=True, role=UserRole.USER, username__icontains=search).exclude(pk=request.user.pk).order_by("username")[:25]
    return Response({"results": PublicProfileSerializer(users, many=True, context={"request": request}).data})


# ---------------------------------------------------------------------------
# Friends
# ---------------------------------------------------------------------------

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def friends_list(request):
    friendships = list_friends(request.user).select_related("requester", "addressee")
    data = []
    for friendship in friendships:
        other = (
            friendship.addressee if friendship.requester_id == request.user.id else friendship.requester
        )
        data.append(PublicProfileSerializer(other, context={"request": request}).data)
    return Response({"results": data})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def friend_requests(request):
    incoming = incoming_requests(request.user).select_related("requester")
    return Response(
        {
            "results": [
                {
                    "id": f.id,
                    "from": PublicProfileSerializer(f.requester, context={"request": request}).data,
                    "created_at": f.created_at,
                }
                for f in incoming
            ]
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@_handle
def friend_request_send(request):
    username = request.data.get("username")
    if not username:
        raise BusinessError("VALIDATION_ERROR", "username is required.")
    addressee = User.objects.filter(username__iexact=username.strip()).first()
    if addressee is None:
        raise BusinessError("USER_NOT_FOUND", "No user with this username.", 404)
    friendship = send_friend_request(request.user, addressee)
    if friendship.status == "ACCEPTED":
        return Response({"message": f"You are now friends with {addressee.username}."})
    from apps.notifications.models import NotificationVerb
    from apps.notifications.services import notify
    notify(recipient=addressee, actor=request.user, verb=NotificationVerb.FRIEND_REQUEST, target=friendship, message_key="notifications.friend_request", dedupe_key=f"friend_request_{friendship.pk}")
    return Response({"message": f"Friend request sent to {addressee.username}."})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@_handle
def friend_request_accept(request, friendship_id):
    friendship = accept_friend_request(request.user, friendship_id)
    from apps.notifications.models import NotificationVerb
    from apps.notifications.services import notify
    notify(recipient=friendship.requester, actor=request.user, verb=NotificationVerb.FRIEND_ACCEPTED, target=friendship, message_key="notifications.friend_accepted", dedupe_key=f"friend_accepted_{friendship.pk}")
    return Response({"message": f"You are now friends with {friendship.requester.username}."})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@_handle
def friend_request_decline(request, friendship_id):
    friendship = decline_friend_request(request.user, friendship_id)
    return Response({"message": "Friend request declined."})


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
@_handle
def friend_remove(request, user_id):
    remove_friend(request.user, user_id)
    return Response({"message": "Friend removed."})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def presence_status(request):
    from apps.accounts.services.presence import online_status_for

    ids = request.query_params.get("ids", "")
    user_ids = [int(i) for i in ids.split(",") if i.strip().isdigit()]
    users = User.objects.filter(id__in=user_ids or [request.user.id])
    return Response({"results": online_status_for(users)})


# ---------------------------------------------------------------------------
# Admin user management
# ---------------------------------------------------------------------------

@api_view(["GET"])
@permission_classes([IsAdmin])
def admin_users(request):
    queryset = User.objects.all().order_by("-date_joined")
    search = request.query_params.get("search")
    role = request.query_params.get("role")
    is_active = request.query_params.get("is_active")
    if search:
        queryset = queryset.filter(
            Q(username__icontains=search) | Q(email__icontains=search)
        )
    if role:
        queryset = queryset.filter(role=role.upper())
    if is_active is not None:
        queryset = queryset.filter(is_active=is_active.lower() in ("1", "true"))
    page = request.query_params.get("page")
    results = list(queryset)
    return Response({"results": AdminUserListSerializer(results, many=True).data})


@api_view(["PATCH"])
@permission_classes([IsAdmin])
@_handle
def admin_user_update(request, user_id):
    target = get_object_or_404(User, pk=user_id)
    serializer = AdminUserUpdateSerializer(data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    is_target_admin = target.role == UserRole.ADMIN
    if is_target_admin:
        # The final active admin cannot remove their own administrative access
        # either; otherwise the platform becomes impossible to administer.
        admin_count = User.objects.filter(role=UserRole.ADMIN, is_active=True).count()
        will_still_be_admin = (
            data.get("role", target.role) == UserRole.ADMIN
            and data.get("is_active", target.is_active) is True
        )
        if admin_count <= 1 and not will_still_be_admin:
            raise BusinessError(
                "LAST_ADMIN", "Cannot demote, deactivate or block the last active admin."
            )
    if (
        target.id == request.user.id
        and "role" in data
        and data["role"] != target.role
    ):
        raise BusinessError("SELF_ROLE_CHANGE", "You cannot change your own administrator role.")
    if target.id == request.user.id and data.get("is_active") is False:
        raise BusinessError("SELF_DEACTIVATION", "You cannot deactivate your own administrator account.")
    if target.id == request.user.id and data.get("is_blocked") is True:
        raise BusinessError("SELF_BLOCK", "You cannot block yourself.")

    if "role" in data:
        target.role = data["role"]
    if "is_active" in data:
        target.is_active = data["is_active"]
    if "is_blocked" in data:
        target.is_blocked = data["is_blocked"]
        target.blocked_at = timezone.now() if data["is_blocked"] else None
        if not data["is_blocked"]:
            target.blocked_reason = ""
    if "blocked_reason" in data:
        target.blocked_reason = data["blocked_reason"]
    target.save()
    return Response(AdminUserListSerializer(target).data)


@api_view(["POST"])
@permission_classes([IsAdmin])
@_handle
def admin_user_block(request, user_id):
    target = get_object_or_404(User, pk=user_id)
    if target.id == request.user.id:
        raise BusinessError("SELF_BLOCK", "You cannot block yourself.")
    reason = request.data.get("reason", "")
    target.is_blocked = True
    target.blocked_reason = reason
    target.blocked_at = timezone.now()
    target.save(update_fields=["is_blocked", "blocked_reason", "blocked_at"])
    return Response({"message": f"User {target.username} blocked from bidding.", "blocked": True})


@api_view(["POST"])
@permission_classes([IsAdmin])
@_handle
def admin_user_unblock(request, user_id):
    target = get_object_or_404(User, pk=user_id)
    target.is_blocked = False
    target.blocked_reason = ""
    target.blocked_at = None
    target.save(update_fields=["is_blocked", "blocked_reason", "blocked_at"])
    return Response({"message": f"User {target.username} unblocked.", "blocked": False})
