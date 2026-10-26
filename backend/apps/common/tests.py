from datetime import timedelta

from django.utils import timezone
from rest_framework.test import APIClient

from apps.auctions.models import AuctionEvent, AuctionLot
from apps.common.models import PublicApiKey
from apps.common.tests_base import BaseTestCase
from apps.products.models import Category, Product
from apps.orders.models import Order, OrderStatus, Payment, PaymentStatus


class PublicApiTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.owner = self.create_user("apiowner")
        self.category = Category.objects.create(name="Collectibles")
        self.product = Product.objects.create(owner=self.owner, category=self.category, name="Mystery box")
        now = timezone.now()
        self.event = AuctionEvent.objects.create(
            organizer=self.owner, title="API event",
            start_time=now + timedelta(days=1), end_time=now + timedelta(days=2),
        )

    def test_key_is_shown_once_and_required_by_v1(self):
        self.assertEqual(self.client.get("/api/v1/categories/").status_code, 401)
        self.api_login(self.owner)
        response = self.api_post("/api/common/api-keys/", {"name": "integration"})
        self.assertEqual(response.status_code, 201)
        raw_key = response.data["key"]
        listing = self.client.get("/api/common/api-keys/")
        self.assertNotIn("key", listing.data["results"][0])
        response = self.client.get("/api/v1/categories/", HTTP_X_API_KEY=raw_key)
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "Collectibles", {row["name"] for row in response.data["results"]}
        )

    def test_api_key_owner_can_create_update_and_delete_lot(self):
        _, raw_key = PublicApiKey.issue_key(self.owner, "automation")
        start = self.event.start_time + timedelta(hours=1)
        payload = {
            "event": self.event.pk, "product": self.product.pk, "lot_number": 1,
            "starting_price": "50.00", "minimum_increment": "5.00",
            "start_time": start.isoformat(), "end_time": (start + timedelta(hours=2)).isoformat(),
        }
        response = self.client.post("/api/v1/lots/", payload, format="json", HTTP_X_API_KEY=raw_key)
        self.assertEqual(response.status_code, 201, response.data)
        lot_id = response.data["id"]
        payload["lot_number"] = 2
        response = self.client.put(
            f"/api/v1/lots/{lot_id}/", payload, format="json", HTTP_X_API_KEY=raw_key
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(AuctionLot.objects.get(pk=lot_id).lot_number, 2)
        response = self.client.delete(f"/api/v1/lots/{lot_id}/", HTTP_X_API_KEY=raw_key)
        self.assertEqual(response.status_code, 204)
        self.assertFalse(AuctionLot.objects.filter(pk=lot_id).exists())

    def test_existing_api_key_cannot_write_lots_after_owner_is_promoted(self):
        _, raw_key = PublicApiKey.issue_key(self.owner, "before-promotion")
        admin = self.create_admin(username="api_admin")
        admin_client = APIClient()
        self.api_login(admin, client=admin_client)
        promoted = self.api_patch(
            f"/api/accounts/admin/users/{self.owner.pk}/",
            {"role": "ADMIN"},
            client=admin_client,
        )
        self.assertEqual(promoted.status_code, 200, promoted.data)

        start = self.event.start_time + timedelta(hours=1)
        response = self.client.post(
            "/api/v1/lots/",
            {
                "event": self.event.pk,
                "product": self.product.pk,
                "lot_number": 1,
                "starting_price": "50.00",
                "minimum_increment": "5.00",
                "start_time": start.isoformat(),
                "end_time": (start + timedelta(hours=2)).isoformat(),
            },
            format="json",
            HTTP_X_API_KEY=raw_key,
        )
        self.assertEqual(response.status_code, 403, response.data)
        self.assertEqual(response.data["code"], "ADMIN_MARKETPLACE_RESTRICTED")
        self.assertFalse(AuctionLot.objects.exists())


class ImportTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.owner = self.create_user("importer")
        now = timezone.now()
        self.event = AuctionEvent.objects.create(
            organizer=self.owner, title="Import event",
            start_time=now + timedelta(days=1), end_time=now + timedelta(days=2),
        )
        self.category = Category.objects.create(name="Existing")
        self.product = Product.objects.create(owner=self.owner, category=self.category, name="Import product")
        self.api_login(self.owner)

    def test_product_dry_run_does_not_mutate_database(self):
        response = self.api_post(
            "/api/import/products/",
            {"dry_run": True, "rows": [{"name": "Preview", "description": "", "category": "New"}]},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["valid"], 1)
        self.assertFalse(Category.objects.filter(name="New").exists())
        self.assertFalse(Product.objects.filter(name="Preview").exists())

    def test_lot_dry_run_does_not_mutate_database(self):
        start = self.event.start_time + timedelta(hours=1)
        response = self.api_post(
            f"/api/import/lots/{self.event.pk}/",
            {"dry_run": True, "rows": [{
                "product_id": self.product.pk, "lot_number": 1,
                "starting_price": "25.00", "minimum_increment": "2.00",
                "start_time": start.isoformat(), "end_time": (start + timedelta(hours=1)).isoformat(),
            }]},
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["imported"], 0)
        self.assertFalse(AuctionLot.objects.exists())

    def test_promoted_user_cannot_use_bulk_imports_with_existing_session(self):
        admin = self.create_admin(username="import_admin")
        admin_client = APIClient()
        self.api_login(admin, client=admin_client)
        promoted = self.api_patch(
            f"/api/accounts/admin/users/{self.owner.pk}/",
            {"role": "ADMIN"},
            client=admin_client,
        )
        self.assertEqual(promoted.status_code, 200, promoted.data)

        product_response = self.api_post(
            "/api/import/products/",
            {"rows": [{"name": "Forbidden import", "category": "Existing"}]},
        )
        lot_response = self.api_post(
            f"/api/import/lots/{self.event.pk}/",
            {"rows": []},
        )
        for response in (product_response, lot_response):
            self.assertEqual(response.status_code, 403, response.data)
            self.assertEqual(response.data["code"], "ADMIN_MARKETPLACE_RESTRICTED")
        self.assertFalse(Product.objects.filter(name="Forbidden import").exists())


class AnalyticsPrivacyTests(BaseTestCase):
    def test_seller_revenue_excludes_other_sellers_cash_collections(self):
        seller = self.create_user("seller")
        other = self.create_user("otherseller")
        buyer = self.create_user("buyer")
        category = Category.objects.create(name="Analytics")
        now = timezone.now()
        for index, owner in enumerate((seller, other), start=1):
            product = Product.objects.create(owner=owner, category=category, name=f"Item {index}")
            event = AuctionEvent.objects.create(
                organizer=owner, title=f"Event {index}",
                start_time=now - timedelta(hours=2), end_time=now - timedelta(hours=1),
                status="ENDED",
            )
            lot = AuctionLot.objects.create(
                auction_event=event, product=product, lot_number=1,
                starting_price="100.00", minimum_increment="5.00",
                start_time=event.start_time, end_time=event.end_time, status="SOLD",
            )
            order = Order.objects.create(
                auction_lot=lot, buyer=buyer, seller=owner,
                final_price="100.00", status=OrderStatus.DELIVERED,
            )
            Payment.objects.create(
                order=order, amount="100.00", status=PaymentStatus.COLLECTED,
                collected_at=now,
            )
        self.api_login(seller)
        response = self.client.get("/api/analytics/dashboard/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["totals"]["revenue_paid"], "100.00")
