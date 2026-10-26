from datetime import timedelta

from django.utils import timezone

from apps.auctions.models import AuctionEvent, AuctionLot, AuctionLotStatus
from apps.common.tests_base import BaseTestCase
from apps.products.models import Category, Product


class ProductApiTests(BaseTestCase):
    def setUp(self):
        self.admin = self.create_admin()
        self.seller = self.create_user(username="seller")
        self.other = self.create_user(username="other")
        self.category = Category.objects.create(name="Antiques")

    def test_products_are_owner_scoped(self):
        product = Product.objects.create(
            owner=self.seller, name="Private draft item", category=self.category
        )
        self.api_login(self.other)
        self.assertEqual(self.client.get(f"/api/products/{product.pk}/").status_code, 404)
        self.api_login(self.seller)
        response = self.client.get(f"/api/products/{product.pk}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["owner"], self.seller.pk)

    def test_default_categories_are_available_to_sellers(self):
        self.api_login(self.seller)
        response = self.client.get("/api/products/categories/")
        self.assertEqual(response.status_code, 200)
        names = {row["name"] for row in response.data["results"]}
        self.assertTrue({"Toys & Games", "Other", "Coins"}.issubset(names))

    def test_seller_creates_and_soft_deletes_unlisted_product(self):
        self.api_login(self.seller)
        created = self.api_post(
            "/api/products/",
            {"name": "Bronze Compass", "description": "Old compass", "category": self.category.pk},
        )
        self.assertEqual(created.status_code, 201)
        product = Product.objects.get(pk=created.data["id"])
        self.assertEqual(product.owner, self.seller)
        deleted = self.api_delete(f"/api/products/{product.pk}/")
        self.assertEqual(deleted.status_code, 204)
        product.refresh_from_db()
        self.assertFalse(product.available)

    def test_product_in_nonterminal_lot_cannot_be_removed(self):
        product = Product.objects.create(owner=self.seller, name="Listed item", category=self.category)
        now = timezone.now()
        event = AuctionEvent.objects.create(
            organizer=self.seller,
            title="Scheduled sale",
            status="SCHEDULED",
            start_time=now + timedelta(hours=2),
            end_time=now + timedelta(hours=4),
        )
        AuctionLot.objects.create(
            auction_event=event,
            product=product,
            lot_number=1,
            starting_price="10.00",
            minimum_increment="1.00",
            start_time=event.start_time,
            end_time=event.end_time,
            status=AuctionLotStatus.SCHEDULED,
        )
        self.api_login(self.seller)
        response = self.api_delete(f"/api/products/{product.pk}/")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "PRODUCT_ALREADY_LISTED")
        product.refresh_from_db()
        self.assertTrue(product.available)

    def test_category_mutations_are_admin_only_and_in_use_delete_is_clean_error(self):
        self.api_login(self.seller)
        denied = self.api_post("/api/products/categories/", {"name": "Coins"})
        self.assertEqual(denied.status_code, 403)
        Product.objects.create(owner=self.seller, name="Vase", category=self.category)
        self.api_login(self.admin)
        response = self.api_delete(f"/api/products/categories/{self.category.pk}/")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "CATEGORY_IN_USE")

    def test_admin_cannot_delete_the_last_category(self):
        Category.objects.exclude(pk=self.category.pk).delete()
        self.api_login(self.admin)
        response = self.api_delete(f"/api/products/categories/{self.category.pk}/")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "LAST_CATEGORY")
