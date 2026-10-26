from datetime import timedelta

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator
from django.test import TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

from apps.auctions.models import AuctionEvent, AuctionEventStatus, AuctionLot, AuctionLotStatus
from apps.common.tests_base import CHANNEL_LAYER_IN_MEMORY
from apps.products.models import Category, Product
from config.asgi import application


@override_settings(CHANNEL_LAYERS=CHANNEL_LAYER_IN_MEMORY)
class WebSocketContractTests(TransactionTestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        self.seller = User.objects.create_user(
            email="seller@example.com", username="seller", password="StrongPass123!"
        )
        self.bidder = User.objects.create_user(
            email="bidder@example.com", username="bidder", password="StrongPass123!"
        )
        category = Category.objects.create(name="Socket Art")
        product = Product.objects.create(owner=self.seller, name="Live Vase", category=category)
        now = timezone.now()
        self.event = AuctionEvent.objects.create(
            organizer=self.seller,
            title="Socket auction",
            status=AuctionEventStatus.SCHEDULED,
            start_time=now + timedelta(minutes=5),
            end_time=now + timedelta(hours=1),
        )
        self.lot = AuctionLot.objects.create(
            auction_event=self.event,
            product=product,
            lot_number=1,
            starting_price="50.00",
            minimum_increment="5.00",
            start_time=self.event.start_time,
            end_time=self.event.end_time,
            status=AuctionLotStatus.SCHEDULED,
        )

    def test_public_lot_socket_snapshot_and_broadcast(self):
        async_to_sync(self._public_lot_socket_snapshot_and_broadcast)()

    async def _public_lot_socket_snapshot_and_broadcast(self):
        communicator = WebsocketCommunicator(
            application,
            f"/ws/lot/{self.lot.pk}/",
            headers=[(b"origin", b"https://localhost")],
        )
        connected, _ = await communicator.connect()
        self.assertTrue(connected)
        snapshot = await communicator.receive_json_from(timeout=2)
        self.assertEqual(snapshot["type"], "snapshot")
        self.assertEqual(snapshot["current_price"], "50.00")

        await get_channel_layer().group_send(
            f"lot_{self.lot.pk}",
            {
                "type": "bid.accepted",
                "bid": {"id": 99, "amount": "55.00"},
                "current_price": "55.00",
            },
        )
        event = await communicator.receive_json_from(timeout=2)
        self.assertEqual(event["type"], "bid.accepted")
        self.assertEqual(event["current_price"], "55.00")
        await communicator.disconnect()

    def test_draft_lot_and_untrusted_origin_are_rejected(self):
        self.event.status = AuctionEventStatus.DRAFT
        self.event.save(update_fields=["status"])
        async_to_sync(self._assert_lot_rejected)("https://localhost", 4404)
        self.event.status = AuctionEventStatus.SCHEDULED
        self.event.save(update_fields=["status"])
        async_to_sync(self._assert_lot_rejected)("https://evil.example", 4403)

    async def _assert_lot_rejected(self, origin, expected_code):
        communicator = WebsocketCommunicator(
            application,
            f"/ws/lot/{self.lot.pk}/",
            headers=[(b"origin", origin.encode())],
        )
        connected, code = await communicator.connect()
        self.assertFalse(connected)
        self.assertEqual(code, expected_code)

    def test_personal_socket_requires_auth_and_delivers_notifications(self):
        access = str(RefreshToken.for_user(self.bidder).access_token)
        async_to_sync(self._personal_socket_requires_auth_and_delivers_notifications)(access)

    async def _personal_socket_requires_auth_and_delivers_notifications(self, access):
        anonymous = WebsocketCommunicator(
            application,
            "/ws/auth/",
            headers=[(b"origin", b"https://localhost")],
        )
        connected, code = await anonymous.connect()
        self.assertFalse(connected)
        self.assertEqual(code, 4401)

        authenticated = WebsocketCommunicator(
            application,
            "/ws/auth/",
            headers=[
                (b"origin", b"https://localhost"),
                (b"cookie", f"access_token={access}".encode()),
            ],
        )
        connected, _ = await authenticated.connect()
        self.assertTrue(connected)
        welcome = await authenticated.receive_json_from(timeout=2)
        self.assertEqual(welcome["type"], "welcome")
        self.assertEqual(welcome["user_id"], self.bidder.pk)

        await get_channel_layer().group_send(
            f"user_{self.bidder.pk}",
            {
                "type": "notification.created",
                "notification": {"id": 1, "verb": "OUTBID"},
            },
        )
        event = await authenticated.receive_json_from(timeout=2)
        self.assertEqual(event["type"], "notification.created")
        self.assertEqual(event["notification"]["verb"], "OUTBID")
        await authenticated.disconnect()
