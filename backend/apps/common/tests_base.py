"""Shared test helpers: in-memory channel layer, factories, auth helpers."""
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import override_settings
from rest_framework.test import APITestCase

User = get_user_model()

CHANNEL_LAYER_IN_MEMORY = {
    "default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}
}

# Speed up hashing for tests
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
TEST_REST_FRAMEWORK = {
    **settings.REST_FRAMEWORK,
    "DEFAULT_THROTTLE_RATES": {
        **settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"],
        "login": "10000/min",
        "register": "10000/min",
        "two_fa": "10000/min",
        "password_reset": "10000/min",
        "bids": "10000/min",
        "public_api": "10000/min",
        "imports": "10000/min",
    },
}


@override_settings(
    CHANNEL_LAYERS=CHANNEL_LAYER_IN_MEMORY,
    PASSWORD_HASHERS=PASSWORD_HASHERS,
    REST_FRAMEWORK=TEST_REST_FRAMEWORK,
)
class BaseTestCase(APITestCase):
    """Base TestCase with in-memory channel layer, fast hashing and CSRF-aware
    authenticated API helpers (login via the real cookie-JWT endpoint)."""

    def setUp(self):
        super().setUp()
        cache.clear()

    def create_user(self, username="user", email=None, password="StrongPass123!", **extra):
        email = email or f"{username}@example.com"
        return User.objects.create_user(
            email=email, username=username, password=password, **extra
        )

    def create_admin(self, username="admin"):
        admin = self.create_user(username=username, email=f"{username}@example.com")
        admin.role = "ADMIN"
        admin.is_staff = True
        admin.is_superuser = True
        admin.save(update_fields=["role", "is_staff", "is_superuser"])
        return admin

    # ---- authenticated API helpers (real cookie-JWT + CSRF) ---------------
    def api_login(self, user, client=None):
        """Log in through the real login endpoint; returns the CSRF token."""
        client = client or self.client
        # Test clients all share 127.0.0.1, unlike real users. Keep one test
        # class from consuming another class's anonymous login allowance.
        cache.delete("throttle_login_127.0.0.1")
        response = client.post(
            "/api/accounts/auth/login/",
            {"email": user.email, "password": "StrongPass123!"},
            format="json",
        )
        assert response.status_code == 200, response.content
        return client.cookies["csrftoken"].value

    def api_post(self, path, data=None, format="json", client=None, **kw):
        client = client or self.client
        headers = kw.pop("headers", {})
        headers["X-CSRFToken"] = client.cookies["csrftoken"].value
        return client.post(path, data or {}, format=format, headers=headers, **kw)

    def api_patch(self, path, data, client=None, **kw):
        client = client or self.client
        headers = kw.pop("headers", {})
        headers["X-CSRFToken"] = client.cookies["csrftoken"].value
        return client.patch(path, data, format="json", headers=headers, **kw)

    def api_delete(self, path, client=None, **kw):
        client = client or self.client
        headers = kw.pop("headers", {})
        headers["X-CSRFToken"] = client.cookies["csrftoken"].value
        return client.delete(path, headers=headers, **kw)

    def register_and_login(self, username="newbie", password="StrongPass123!"):
        response = self.client.post(
            "/api/accounts/auth/register/",
            {
                "email": f"{username}@example.com",
                "username": username,
                "password": password,
                "password_confirm": password,
            },
            format="json",
        )
        assert response.status_code == 201, response.content
        user = User.objects.get(username=username)
        return user, response


def make_event(user, *, start_delta, end_delta, status="ACTIVE", title="Test event"):
    from datetime import timedelta

    from django.utils import timezone

    from apps.auctions.models import AuctionEvent

    now = timezone.now()
    return AuctionEvent.objects.create(
        organizer=user,
        title=title,
        start_time=now + timedelta(seconds=start_delta),
        end_time=now + timedelta(seconds=end_delta),
        status=status,
    )


def make_lot(event, product, *, lot_number=1, starting_price="10.00",
             min_increment="1.00", start_delta=-60, end_delta=3600, status="ACTIVE"):
    from datetime import timedelta

    from django.utils import timezone

    from apps.auctions.models import AuctionLot

    now = timezone.now()
    return AuctionLot.objects.create(
        auction_event=event,
        product=product,
        lot_number=lot_number,
        starting_price=starting_price,
        minimum_increment=min_increment,
        start_time=now + timedelta(seconds=start_delta),
        end_time=now + timedelta(seconds=end_delta),
        status=status,
    )


def make_product(owner, name="Antique Vase", category_name="Antiquities"):
    from apps.products.models import Category, Product

    category, _ = Category.objects.get_or_create(name=category_name)
    return Product.objects.create(owner=owner, name=name, category=category)
