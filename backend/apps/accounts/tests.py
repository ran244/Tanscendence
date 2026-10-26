import io
from urllib.parse import parse_qs, urlparse

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TransactionTestCase
from rest_framework import status as http_status

from apps.common.tests_base import BaseTestCase, make_event, make_lot, make_product

User = get_user_model()


class RegistrationTests(BaseTestCase):
    def test_registration_creates_user_and_normalizes_email(self):
        response = self.client.post(
            "/api/accounts/auth/register/",
            {
                "email": "  Mixed@Example.COM ",
                "username": "newuser",
                "password": "Str0ng-Pass!",
                "password_confirm": "Str0ng-Pass!",
            },
            format="json",
        )
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        user = User.objects.get(username="newuser")
        self.assertEqual(user.email, "mixed@example.com")
        self.assertTrue(user.check_password("Str0ng-Pass!"))
        self.assertFalse(user.is_active)
        self.assertFalse(user.email_verified)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Verify your Mystery Auctions email", mail.outbox[0].subject)

    def test_email_verification_activates_account_and_allows_login(self):
        registration = self.client.post(
            "/api/accounts/auth/register/",
            {
                "email": "verify@example.com",
                "username": "verifyme",
                "password": "Str0ng-Pass!",
                "password_confirm": "Str0ng-Pass!",
            },
            format="json",
        )
        self.assertEqual(registration.status_code, http_status.HTTP_201_CREATED)
        blocked_login = self.client.post(
            "/api/accounts/auth/login/",
            {"email": "verify@example.com", "password": "Str0ng-Pass!"},
            format="json",
        )
        self.assertEqual(blocked_login.status_code, http_status.HTTP_403_FORBIDDEN)
        self.assertEqual(blocked_login.data["code"], "EMAIL_NOT_VERIFIED")

        verification_url = next(
            line for line in mail.outbox[-1].body.splitlines() if line.startswith("https://")
        )
        token = parse_qs(urlparse(verification_url).query)["code"][0]
        verified = self.client.get(
            "/api/accounts/auth/email/verify/", {"code": token}
        )
        self.assertEqual(verified.status_code, http_status.HTTP_200_OK)
        user = User.objects.get(username="verifyme")
        self.assertTrue(user.is_active)
        self.assertTrue(user.email_verified)

        login = self.client.post(
            "/api/accounts/auth/login/",
            {"email": "verify@example.com", "password": "Str0ng-Pass!"},
            format="json",
        )
        self.assertEqual(login.status_code, http_status.HTTP_200_OK)

    def test_verification_resend_does_not_disclose_accounts(self):
        response = self.client.post(
            "/api/accounts/auth/email/resend/",
            {"email": "unknown@example.com"},
            format="json",
        )
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

    def test_registration_rejects_mismatched_passwords(self):
        response = self.client.post(
            "/api/accounts/auth/register/",
            {
                "email": "a@example.com",
                "username": "newuser",
                "password": "Str0ng-Pass!",
                "password_confirm": "Different-Pass!",
            },
            format="json",
        )
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "VALIDATION_ERROR")

    def test_registration_rejects_weak_password(self):
        response = self.client.post(
            "/api/accounts/auth/register/",
            {
                "email": "a@example.com",
                "username": "newuser",
                "password": "12345678",
                "password_confirm": "12345678",
            },
            format="json",
        )
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)

    def test_registration_duplicate_email_and_username(self):
        self.create_user(username="existing", email="dup@example.com")
        for payload in (
            {"email": "dup@example.com", "username": "other"},
            {"email": "other@example.com", "username": "existing"},
        ):
            response = self.client.post(
                "/api/accounts/auth/register/",
                {**payload, "password": "Str0ng-Pass!", "password_confirm": "Str0ng-Pass!"},
                format="json",
            )
            self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)


class LoginSessionTests(BaseTestCase):
    def test_me_returns_no_content_for_anonymous_session(self):
        response = self.client.get("/api/accounts/me/")

        self.assertEqual(response.status_code, http_status.HTTP_204_NO_CONTENT)

    def test_anonymous_user_cannot_update_profile(self):
        response = self.client.patch(
            "/api/accounts/me/", {"bio": "not allowed"}, format="json"
        )

        self.assertIn(
            response.status_code,
            (http_status.HTTP_401_UNAUTHORIZED, http_status.HTTP_403_FORBIDDEN),
        )

    def test_login_sets_cookies_and_me_works(self):
        user = self.create_user()
        response = self.client.post(
            "/api/accounts/auth/login/",
            {"email": user.email, "password": "StrongPass123!"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("access_token", response.cookies)
        self.assertIn("refresh_token", response.cookies)
        self.assertEqual(response.cookies["access_token"]["path"], "/")
        me = self.client.get("/api/accounts/me/")
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.data["username"], user.username)

    def test_login_rejects_wrong_password(self):
        user = self.create_user()
        response = self.client.post(
            "/api/accounts/auth/login/",
            {"email": user.email, "password": "WrongPass123!"},
            format="json",
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["code"], "AUTHENTICATION_FAILED")

    def test_refresh_rotation_and_logout(self):
        user = self.create_user()
        self.client.post(
            "/api/accounts/auth/login/",
            {"email": user.email, "password": "StrongPass123!"},
            format="json",
        )
        old_refresh = self.client.cookies["refresh_token"].value
        response = self.client.post("/api/accounts/auth/refresh/", {}, format="json")
        self.assertEqual(response.status_code, 200)
        new_refresh = response.cookies["refresh_token"].value
        self.assertNotEqual(old_refresh, new_refresh)
        # rotated token must be blacklisted
        logout = self.api_post("/api/accounts/auth/logout/")
        self.assertEqual(logout.status_code, 200)
        self.assertEqual(self.client.cookies["access_token"].value, "")
        self.assertEqual(self.client.cookies["refresh_token"].value, "")

    def test_csrf_enforced_for_cookie_authed_unsafe_requests(self):
        user = self.create_user()
        self.client.post(
            "/api/accounts/auth/login/",
            {"email": user.email, "password": "StrongPass123!"},
            format="json",
        )
        response = self.client.patch(
            "/api/accounts/me/", {"bio": "no csrf"}, format="json"
        )
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["code"], "PERMISSION_DENIED")

        # with CSRF cookie + header it succeeds
        client = self.client
        token = client.cookies["csrftoken"].value
        response = client.patch(
            "/api/accounts/me/",
            {"bio": "with csrf"},
            format="json",
            headers={"X-CSRFToken": token},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["bio"], "with csrf")


class ProfileTests(BaseTestCase):
    def test_profile_update_and_avatar_flow(self):
        user = self.create_user()
        token = self.api_login(user)
        self.assertIsNotNone(token)
        response = self.api_patch(
            "/api/accounts/me/",
            {"bio": "Collector of mysteries", "phone_number": "+96270000000"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["bio"], "Collector of mysteries")

        import io

        from PIL import Image

        buffer = io.BytesIO()
        Image.new("RGB", (4, 4), color=(120, 90, 60)).save(buffer, format="PNG")
        buffer.seek(0)
        upload_file = SimpleUploadedFile(
            "avatar.png", buffer.getvalue(), content_type="image/png"
        )
        upload = self.client.post(
            "/api/accounts/me/avatar/",
            {"avatar": upload_file},
            format="multipart",
            headers={"X-CSRFToken": token},
        )
        self.assertEqual(upload.status_code, 200)
        self.assertTrue(upload.data["avatar"])
        delete = self.api_delete("/api/accounts/me/avatar/")
        self.assertEqual(delete.status_code, 200)
        self.assertFalse(delete.data["avatar"])

    def test_phone_number_accepts_digits_and_optional_leading_plus_only(self):
        user = self.create_user()
        self.api_login(user)

        for valid in ("", "96270000000", "+96270000000"):
            with self.subTest(valid=valid):
                response = self.api_patch(
                    "/api/accounts/me/", {"phone_number": valid}
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.data["phone_number"], valid)

        for invalid in ("+", "++962", "962+700", "962 700", "962-700", "phone"):
            with self.subTest(invalid=invalid):
                response = self.api_patch(
                    "/api/accounts/me/", {"phone_number": invalid}
                )
                self.assertEqual(response.status_code, 400)

    def test_avatar_rejects_non_image(self):
        user = self.create_user()
        token = self.api_login(user)
        response = self.client.post(
            "/api/accounts/me/avatar/",
            {"avatar": io.BytesIO(b"not an image at all")},
            format="multipart",
            headers={"X-CSRFToken": token},
        )
        self.assertEqual(response.status_code, 400)

    def test_public_profile_hides_private_fields(self):
        user = self.create_user(bio="Hello")
        response = self.client.get(f"/api/accounts/users/{user.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["username"], user.username)
        for private in ("email", "phone_number", "totp", "role", "is_blocked"):
            self.assertNotIn(private, response.data)


class PasswordResetTests(BaseTestCase):
    def test_reset_request_never_reveals_email_existence(self):
        response = self.client.post(
            "/api/accounts/auth/password/reset/request/",
            {"email": "ghost@example.com"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        response = self.client.post(
            "/api/accounts/auth/password/reset/request/",
            {"email": "ghost@example.com"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)

    def test_reset_confirm_flow(self):
        from django.core import mail

        user = self.create_user()
        self.client.post(
            "/api/accounts/auth/password/reset/request/",
            {"email": user.email},
            format="json",
        )
        self.assertEqual(len(mail.outbox), 1)
        body = mail.outbox[0].body
        token = body.split("token=", 1)[1].splitlines()[0].strip()
        response = self.client.post(
            "/api/accounts/auth/password/reset/confirm/",
            {"token": token, "new_password": "NewStrongPass123!", "new_password_confirm": "NewStrongPass123!"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        user.refresh_from_db()
        self.assertTrue(user.check_password("NewStrongPass123!"))

    def test_reset_confirm_rejects_bad_token(self):
        response = self.client.post(
            "/api/accounts/auth/password/reset/confirm/",
            {"token": "garbage", "new_password": "NewStrongPass123!", "new_password_confirm": "NewStrongPass123!"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "INVALID_RESET_TOKEN")


class TwoFATests(BaseTestCase):
    def _login_with_2fa(self, user):
        self.client.post(
            "/api/accounts/auth/login/",
            {"email": user.email, "password": "StrongPass123!"},
            format="json",
        )
        # simulate enabling 2FA via direct service (setup/QR tested separately)
        from apps.accounts.services import auth as auth_service

        secret = auth_service.generate_totp_secret()
        user.totp_secret = secret
        user.save(update_fields=["totp_secret"])
        import pyotp

        code = pyotp.TOTP(secret).now()
        response = self.api_post(
            "/api/accounts/me/2fa/enable/",
            {"code": code},
        )
        self.assertEqual(response.status_code, 200)
        user.refresh_from_db()
        self.assertTrue(user.totp_enabled)
        self.assertEqual(len(user.two_factor_recovery_codes.all()), 10)
        return code

    def test_login_requires_2fa_challenge_then_verify(self):
        user = self.create_user()
        self._login_with_2fa(user)
        self.api_post("/api/accounts/auth/logout/")
        response = self.client.post(
            "/api/accounts/auth/login/",
            {"email": user.email, "password": "StrongPass123!"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["two_factor_required"])
        self.assertIn("two_fa_challenge", response.cookies)
        challenge = self.client.cookies["two_fa_challenge"].value

        import pyotp

        code = pyotp.TOTP(user.totp_secret).now()
        verify = self.client.post(
            "/api/accounts/auth/2fa/verify/",
            {"code": code, "recovery": False},
            format="json",
        )
        self.assertEqual(verify.status_code, 200)
        self.assertIn("access_token", verify.cookies)
        # challenge cookie is single-use
        self.api_post("/api/accounts/auth/logout/")
        self.client.post(
            "/api/accounts/auth/login/",
            {"email": user.email, "password": "StrongPass123!"},
            format="json",
        )
        self.client.cookies["two_fa_challenge"] = challenge
        stale = self.client.post(
            "/api/accounts/auth/2fa/verify/", {"code": code}, format="json"
        )
        self.assertEqual(stale.status_code, 401)

    def test_recovery_code_login(self):
        user = self.create_user()
        self._login_with_2fa(user)
        self.api_post("/api/accounts/auth/logout/")
        self.client.post(
            "/api/accounts/auth/login/",
            {"email": user.email, "password": "StrongPass123!"},
            format="json",
        )
        recovery = user.two_factor_recovery_codes.first()
        plaintext = None
        # codes are stored hashed; re-issue to obtain a plaintext for the test
        from apps.accounts.models import TwoFactorRecoveryCode

        TwoFactorRecoveryCode.objects.filter(user=user).delete()
        codes = TwoFactorRecoveryCode.issue_codes(user, count=1)
        plaintext = codes[0]
        response = self.client.post(
            "/api/accounts/auth/2fa/verify/",
            {"code": plaintext, "recovery": True},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        # used code cannot be reused
        self.api_post("/api/accounts/auth/logout/")
        self.client.post(
            "/api/accounts/auth/login/",
            {"email": user.email, "password": "StrongPass123!"},
            format="json",
        )
        response = self.client.post(
            "/api/accounts/auth/2fa/verify/",
            {"code": plaintext, "recovery": True},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_2fa_disable_requires_confirmation(self):
        user = self.create_user()
        self._login_with_2fa(user)
        response = self.api_post(
            "/api/accounts/me/2fa/disable/",
            {"password": "StrongPass123!"},
        )
        self.assertEqual(response.status_code, 200)
        user.refresh_from_db()
        self.assertFalse(user.totp_enabled)


class FriendAndPresenceTests(BaseTestCase):
    def test_friend_flow(self):
        alice = self.create_user(username="alice")
        bob = self.create_user(username="bob")
        self.api_login(alice)
        response = self.api_post(
            "/api/accounts/friends/request/", {"username": "bob"}
        )
        self.assertEqual(response.status_code, 200)
        # bob accepts
        self.api_login(bob)
        incoming = self.client.get("/api/accounts/friends/requests/")
        self.assertEqual(len(incoming.data["results"]), 1)
        friendship_id = incoming.data["results"][0]["id"]
        accepted = self.api_post(
            f"/api/accounts/friends/requests/{friendship_id}/accept/"
        )
        self.assertEqual(accepted.status_code, 200)
        friends = self.client.get("/api/accounts/friends/")
        self.assertEqual(len(friends.data["results"]), 1)
        self.assertEqual(friends.data["results"][0]["username"], "alice")
        # remove
        removed = self.api_delete(f"/api/accounts/friends/{alice.id}/")
        self.assertEqual(removed.status_code, 200)

    def test_friend_request_rejects_self_and_duplicates(self):
        alice = self.create_user(username="alice")
        self.api_login(alice)
        response = self.api_post(
            "/api/accounts/friends/request/", {"username": "alice"}
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "SELF_FRIENDSHIP")

    def test_presence_status_endpoint(self):
        alice = self.create_user(username="alice")
        bob = self.create_user(username="bob")
        self.api_login(alice)
        response = self.client.get(
            f"/api/accounts/presence/?ids={alice.id},{bob.id}"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["results"], {alice.id: False, bob.id: False})


class AccountDeletionTests(BaseTestCase):
    def test_delete_requires_password_removes_user_and_allows_credentials_to_be_reused(self):
        user = self.create_user()
        original_id = user.id
        original_email = user.email
        original_username = user.username
        self.api_login(user)
        response = self.api_post(
            "/api/accounts/me/delete/", {"password": "wrong"}
        )
        self.assertEqual(response.status_code, 400)
        self.assertTrue(User.objects.filter(pk=original_id).exists())

        legacy = self.api_post(
            "/api/accounts/me/deactivate/", {"password": "StrongPass123!"}
        )
        self.assertEqual(legacy.status_code, 404)

        response = self.api_post(
            "/api/accounts/me/delete/", {"password": "StrongPass123!"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(pk=original_id).exists())
        self.assertEqual(response.cookies["access_token"]["max-age"], 0)

        response = self.client.post(
            "/api/accounts/auth/login/", {"email": original_email, "password": "StrongPass123!"},
            format="json",
        )
        self.assertEqual(response.status_code, 401)

        registration = self.client.post(
            "/api/accounts/auth/register/",
            {
                "email": original_email,
                "username": original_username,
                "password": "Str0ng-Reused!",
                "password_confirm": "Str0ng-Reused!",
            },
            format="json",
        )
        self.assertEqual(registration.status_code, 201)
        self.assertTrue(User.objects.filter(email=original_email, username=original_username).exists())

    def test_admin_and_promoted_admin_accounts_cannot_delete_themselves(self):
        for username, extra in (
            ("admin", {"role": "ADMIN"}),
            ("staffmember", {"is_staff": True}),
            ("supermember", {"is_superuser": True}),
        ):
            with self.subTest(username=username):
                user = self.create_user(username=username, **extra)
                self.api_login(user)
                response = self.api_post(
                    "/api/accounts/me/delete/", {"password": "StrongPass123!"}
                )
                self.assertEqual(response.status_code, 403)
                self.assertEqual(response.data["code"], "ADMIN_ACCOUNT_PROTECTED")
                self.assertTrue(User.objects.filter(pk=user.pk).exists())

    def test_delete_accepts_alphanumeric_recovery_code(self):
        from apps.accounts.models import TwoFactorRecoveryCode

        user = self.create_user()
        self.api_login(user)
        user.totp_secret = "JBSWY3DPEHPK3PXP"
        user.totp_enabled = True
        user.save(update_fields=["totp_secret", "totp_enabled"])
        recovery_code = TwoFactorRecoveryCode.issue_codes(user, count=1)[0]

        missing = self.api_post(
            "/api/accounts/me/delete/", {"password": "StrongPass123!"}
        )
        self.assertEqual(missing.status_code, 400)
        deleted = self.api_post(
            "/api/accounts/me/delete/",
            {"password": "StrongPass123!", "code": recovery_code},
        )
        self.assertEqual(deleted.status_code, 200)
        self.assertFalse(User.objects.filter(pk=user.pk).exists())

    def test_delete_preserves_and_anonymizes_historical_records(self):
        from apps.auctions.models import (
            AuctionCancellationRequest,
            Bid,
            BidStatus,
            CancellationRequestStatus,
        )
        from apps.notifications.models import SupportMessage, SupportTicket
        from apps.orders.models import Order, OrderStatus

        owner = self.create_user(username="historical")
        buyer = self.create_user(username="historicalbuyer")
        admin = self.create_admin(username="historyadmin")
        product = make_product(owner, name="History item")
        event = make_event(owner, start_delta=-7200, end_delta=-3600, status="ENDED")
        lot = make_lot(
            event,
            product,
            start_delta=-7200,
            end_delta=-3600,
            status="SOLD",
        )
        bid = Bid.objects.create(
            auction_lot=lot,
            bidder=owner,
            amount="11.00",
            status=BidStatus.REJECTED,
        )
        cancellation_request = AuctionCancellationRequest.objects.create(
            auction_event=event,
            requester=owner,
            reason="Historical request",
            status=CancellationRequestStatus.REJECTED,
        )
        order = Order.objects.create(
            auction_lot=lot,
            buyer=buyer,
            seller=owner,
            final_price="20.00",
            status=OrderStatus.DELIVERED,
        )
        ticket = SupportTicket.objects.create(
            reporter=owner, subject="Historical ticket", message="Please help"
        )
        support_message = SupportMessage.objects.create(
            ticket=ticket, author=owner, message="Please help"
        )

        owner_id = owner.id
        self.api_login(owner)
        response = self.api_post(
            "/api/accounts/me/delete/", {"password": "StrongPass123!"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(pk=owner_id).exists())

        product.refresh_from_db()
        event.refresh_from_db()
        bid.refresh_from_db()
        cancellation_request.refresh_from_db()
        order.refresh_from_db()
        ticket.refresh_from_db()
        support_message.refresh_from_db()
        self.assertIsNone(product.owner_id)
        self.assertIsNone(event.organizer_id)
        self.assertIsNone(bid.bidder_id)
        self.assertIsNone(cancellation_request.requester_id)
        self.assertIsNone(order.seller_id)
        self.assertEqual(order.buyer_id, buyer.id)
        self.assertIsNone(ticket.reporter_id)
        self.assertIsNone(support_message.author_id)

        self.api_login(admin)
        history = self.client.get("/api/auctions/admin/events/history/")
        self.assertEqual(history.status_code, 200)
        record = next(item for item in history.data["results"] if item["id"] == event.id)
        self.assertEqual(record["organizer_username"], "Deleted user")
        users = self.client.get("/api/accounts/admin/users/")
        self.assertNotIn(owner_id, [item["id"] for item in users.data["results"]])

    def test_delete_is_blocked_by_every_active_obligation(self):
        from apps.auctions.models import Bid
        from apps.orders.models import Order

        user = self.create_user(username="obligated")
        other = self.create_user(username="otherparty")
        make_event(user, start_delta=3600, end_delta=7200, status="DRAFT")

        other_product = make_product(other, name="Other lot")
        other_event = make_event(other, start_delta=3600, end_delta=7200, status="SCHEDULED")
        active_lot = make_lot(
            other_event,
            other_product,
            start_delta=3600,
            end_delta=7200,
            status="SCHEDULED",
        )
        highest_bid = Bid.objects.create(auction_lot=active_lot, bidder=user, amount="15.00")
        active_lot.highest_bid = highest_bid
        active_lot.save(update_fields=["highest_bid"])

        order_product = make_product(other, name="Order lot")
        ended_event = make_event(other, start_delta=-7200, end_delta=-3600, status="ENDED")
        sold_lot = make_lot(
            ended_event,
            order_product,
            lot_number=2,
            start_delta=-7200,
            end_delta=-3600,
            status="SOLD",
        )
        Order.objects.create(
            auction_lot=sold_lot,
            buyer=user,
            seller=other,
            final_price="25.00",
        )

        self.api_login(user)
        response = self.api_post(
            "/api/accounts/me/delete/", {"password": "StrongPass123!"}
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["code"], "ACCOUNT_HAS_ACTIVE_OBLIGATIONS")
        self.assertIn("unfinished auctions", response.data["message"])
        self.assertIn("current winning bids", response.data["message"])
        self.assertIn("unfinished orders", response.data["message"])
        self.assertTrue(User.objects.filter(pk=user.pk).exists())


class AdminUserManagementTests(BaseTestCase):
    def test_admin_updates_role_and_blocks(self):
        admin = self.create_admin()
        target = self.create_user(username="target")
        self.api_login(admin)
        response = self.api_patch(
            f"/api/accounts/admin/users/{target.id}/",
            {"role": "ADMIN", "is_blocked": True, "blocked_reason": "spam bidding"},
        )
        self.assertEqual(response.status_code, 200)
        target.refresh_from_db()
        self.assertEqual(target.role, "ADMIN")
        self.assertTrue(target.is_blocked)

    def test_admin_cannot_demote_last_admin(self):
        admin = self.create_admin()
        self.api_login(admin)
        response = self.api_patch(
            f"/api/accounts/admin/users/{admin.id}/",
            {"role": "USER"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "LAST_ADMIN")

    def test_admin_cannot_demote_self_when_another_admin_exists(self):
        admin = self.create_admin(username="firstadmin")
        self.create_admin(username="secondadmin")
        self.api_login(admin)
        response = self.api_patch(
            f"/api/accounts/admin/users/{admin.id}/", {"role": "USER"}
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "SELF_ROLE_CHANGE")
        admin.refresh_from_db()
        self.assertEqual(admin.role, "ADMIN")

    def test_non_admin_cannot_access_admin_users(self):
        user = self.create_user()
        self.api_login(user)
        response = self.client.get("/api/accounts/admin/users/")
        self.assertEqual(response.status_code, 403)
