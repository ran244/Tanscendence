from apps.common.tests_base import BaseTestCase, make_event, make_lot, make_product
from apps.orders.models import Order, OrderStatus, Payment, PaymentStatus


class CashOnDeliveryOrderTests(BaseTestCase):
    def setUp(self):
        self.seller = self.create_user(username="seller")
        self.buyer = self.create_user(username="buyer")
        self.other = self.create_user(username="other")
        product = make_product(self.seller)
        event = make_event(self.seller, start_delta=-3600, end_delta=-60, status="ENDED")
        self.lot = make_lot(event, product, start_delta=-3600, end_delta=-60, status="SOLD")
        self.order = Order.objects.create(
            auction_lot=self.lot,
            buyer=self.buyer,
            seller=self.seller,
            final_price="125.00",
        )

    def test_buyer_confirms_cod_and_repeat_is_idempotent(self):
        self.api_login(self.buyer)
        response = self.api_post(
            f"/api/orders/{self.order.pk}/confirm-cod/",
            {"shipping_address": "12 Auction Street, Amman"},
        )
        self.assertEqual(response.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, OrderStatus.CONFIRMED)
        self.assertEqual(self.order.shipping_address, "12 Auction Street, Amman")
        collection = Payment.objects.get(order=self.order)
        self.assertEqual(collection.status, PaymentStatus.PENDING)
        self.assertEqual(collection.amount, self.order.final_price)

        repeated = self.api_post(
            f"/api/orders/{self.order.pk}/confirm-cod/",
            {"shipping_address": "12 Auction Street, Amman"},
        )
        self.assertEqual(repeated.status_code, 200)
        self.assertEqual(Payment.objects.filter(order=self.order).count(), 1)

    def test_cod_confirmation_requires_buyer_and_address(self):
        self.api_login(self.other)
        forbidden = self.api_post(
            f"/api/orders/{self.order.pk}/confirm-cod/", {"shipping_address": "Somewhere"}
        )
        self.assertEqual(forbidden.status_code, 403)
        self.api_login(self.buyer)
        missing = self.api_post(
            f"/api/orders/{self.order.pk}/confirm-cod/", {"shipping_address": "   "}
        )
        self.assertEqual(missing.status_code, 400)

    def test_seller_fulfills_in_order_and_delivery_collects_cash(self):
        self.api_login(self.buyer)
        self.api_post(
            f"/api/orders/{self.order.pk}/confirm-cod/",
            {"shipping_address": "12 Auction Street, Amman"},
        )
        self.api_login(self.seller)
        for status in (OrderStatus.PROCESSING, OrderStatus.SHIPPED, OrderStatus.DELIVERED):
            response = self.api_patch(
                f"/api/orders/{self.order.pk}/fulfill/",
                {"status": status, "collection_note": "Collected in cash"},
            )
            self.assertEqual(response.status_code, 200)
        collection = Payment.objects.get(order=self.order)
        self.assertEqual(collection.status, PaymentStatus.COLLECTED)
        self.assertIsNotNone(collection.collected_at)
        self.assertEqual(collection.collection_note, "Collected in cash")

    def test_seller_can_accept_and_complete_confirmed_order(self):
        self.api_login(self.buyer)
        self.api_post(
            f"/api/orders/{self.order.pk}/confirm-cod/",
            {"shipping_address": "12 Auction Street, Amman"},
        )
        self.api_login(self.seller)
        response = self.api_patch(
            f"/api/orders/{self.order.pk}/fulfill/", {"status": OrderStatus.DELIVERED}
        )
        self.assertEqual(response.status_code, 200)
        self.order.refresh_from_db()
        self.lot.refresh_from_db()
        self.assertEqual(self.order.status, OrderStatus.DELIVERED)
        self.assertEqual(self.lot.status, "SOLD")

    def test_unconfirmed_order_can_be_cancelled(self):
        self.api_login(self.buyer)
        response = self.api_post(f"/api/orders/{self.order.pk}/cancel/")
        self.assertEqual(response.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, OrderStatus.CANCELLED)

    def test_failed_delivery_records_cash_not_collected(self):
        self.api_login(self.buyer)
        self.api_post(
            f"/api/orders/{self.order.pk}/confirm-cod/",
            {"shipping_address": "12 Test Street"},
        )
        self.api_login(self.seller)
        for status in (OrderStatus.PROCESSING, OrderStatus.SHIPPED):
            response = self.api_patch(
                f"/api/orders/{self.order.pk}/fulfill/", {"status": status}
            )
            self.assertEqual(response.status_code, 200)
        missing_reason = self.api_patch(
            f"/api/orders/{self.order.pk}/fulfill/", {"status": OrderStatus.CANCELLED}
        )
        self.assertEqual(missing_reason.status_code, 400)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, OrderStatus.SHIPPED)
        response = self.api_patch(
            f"/api/orders/{self.order.pk}/fulfill/",
            {"status": OrderStatus.CANCELLED, "collection_note": "Recipient unavailable"},
        )
        self.assertEqual(response.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, OrderStatus.CANCELLED)
        self.assertEqual(self.order.cash_on_delivery.status, PaymentStatus.NOT_COLLECTED)
        self.assertEqual(self.order.cash_on_delivery.collection_note, "Recipient unavailable")
