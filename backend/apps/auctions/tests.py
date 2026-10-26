from datetime import timedelta
import threading
from unittest.mock import patch

from django.db import close_old_connections, connections
from django.test import TransactionTestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.auctions.models import (
    AuctionCancellationRequest,
    AuctionEvent,
    AuctionEventStatus,
    AuctionLot,
    AuctionLotStatus,
    Bid,
    BidStatus,
    CancellationRequestStatus,
    RejectionReason,
)
from apps.auctions.services.closing import activate_due_events, close_lot
from apps.auctions.services.bids import BidRejected, place_bid
from apps.common.tests_base import BaseTestCase
from apps.notifications.models import Notification
from apps.orders.models import Order, OrderStatus
from apps.products.models import Category, Product


class AuctionLifecycleApiTests(BaseTestCase):
    def setUp(self):
        self.admin = self.create_admin()
        self.seller = self.create_user(username="seller")
        self.other = self.create_user(username="other")
        self.category = Category.objects.create(name="Collectibles")
        self.product = Product.objects.create(
            owner=self.seller, name="Rare Coin", category=self.category
        )
        self.other_product = Product.objects.create(
            owner=self.other, name="Other Coin", category=self.category
        )
        self.start = timezone.now() + timedelta(hours=2)
        self.end = self.start + timedelta(hours=2)

    def _create_event(self, title="Sunday Auction"):
        self.api_login(self.seller)
        response = self.api_post(
            "/api/auctions/events/",
            {
                "title": title,
                "description": "A curated sale",
                "start_time": self.start.isoformat(),
                "end_time": self.end.isoformat(),
            },
        )
        self.assertEqual(response.status_code, 201, response.data)
        return AuctionEvent.objects.get(pk=response.data["id"])

    def _add_lot(self, event, product=None, lot_number=1):
        response = self.api_post(
            f"/api/auctions/events/{event.pk}/lots/",
            {
                "product": (product or self.product).pk,
                "lot_number": lot_number,
                "starting_price": "100.00",
                "minimum_increment": "5.00",
                "start_time": self.start.isoformat(),
                "end_time": self.end.isoformat(),
            },
        )
        return response

    def test_complete_draft_submit_approve_schedule_activate_flow(self):
        event = self._create_event()
        lot_response = self._add_lot(event)
        self.assertEqual(lot_response.status_code, 201, lot_response.data)

        submitted = self.api_post(f"/api/auctions/events/{event.pk}/submit/")
        self.assertEqual(submitted.status_code, 200)
        self.assertEqual(submitted.data["status"], AuctionEventStatus.PENDING_APPROVAL)
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.admin,
                actor=self.seller,
                verb="EVENT_SUBMITTED",
                target_object_id=event.pk,
            ).exists()
        )

        locked = self.api_patch(
            f"/api/auctions/events/{event.pk}/", {"title": "Too late"}
        )
        self.assertEqual(locked.status_code, 400)
        self.assertEqual(locked.data["code"], "EVENT_LOCKED")

        self.api_login(self.other)
        denied = self.api_post(f"/api/auctions/admin/events/{event.pk}/approve/")
        self.assertEqual(denied.status_code, 403)

        self.api_login(self.admin)
        approved = self.api_post(f"/api/auctions/admin/events/{event.pk}/approve/")
        self.assertEqual(approved.status_code, 200)
        self.assertEqual(approved.data["status"], AuctionEventStatus.SCHEDULED)

        public = self.client.get("/api/auctions/lots/")
        self.assertEqual(public.status_code, 200)
        self.assertEqual([row["id"] for row in public.data["results"]], [event.lots.get().pk])

        event.start_time = timezone.now() - timedelta(minutes=1)
        event.end_time = timezone.now() + timedelta(hours=1)
        event.save(update_fields=["start_time", "end_time"])
        event.lots.update(start_time=event.start_time, end_time=event.end_time)
        activated = activate_due_events()
        self.assertEqual(activated, [event.pk])
        event.refresh_from_db()
        self.assertEqual(event.status, AuctionEventStatus.ACTIVE)
        self.assertEqual(event.lots.get().status, AuctionLotStatus.ACTIVE)

    def test_public_endpoints_hide_draft_and_rejected_lots(self):
        event = self._create_event()
        lot = AuctionLot.objects.create(
            auction_event=event,
            product=self.product,
            lot_number=1,
            starting_price="10.00",
            minimum_increment="1.00",
            start_time=self.start,
            end_time=self.end,
        )
        self.assertEqual(self.client.get("/api/auctions/lots/").data["count"], 0)
        self.assertEqual(self.client.get(f"/api/auctions/lots/{lot.pk}/").status_code, 404)
        self.assertEqual(self.client.get(f"/api/auctions/lots/{lot.pk}/bids/").status_code, 404)

    def test_cannot_list_another_users_product(self):
        event = self._create_event()
        response = self._add_lot(event, product=self.other_product)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["code"], "NOT_OWNER")

    def test_event_rejects_past_and_too_soon_start_times(self):
        self.api_login(self.seller)
        for start in (
            timezone.now() - timedelta(hours=1),
            timezone.now() + timedelta(minutes=30),
        ):
            response = self.api_post(
                "/api/auctions/events/",
                {
                    "title": "Invalid schedule",
                    "description": "Must not be persisted",
                    "start_time": start.isoformat(),
                    "end_time": (start + timedelta(hours=2)).isoformat(),
                },
            )
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.data["code"], "START_TOO_SOON")
        self.assertFalse(AuctionEvent.objects.filter(title="Invalid schedule").exists())

    def test_lot_rejects_zero_prices(self):
        event = self._create_event()
        for field in ("starting_price", "minimum_increment"):
            payload = {
                "product": self.product.pk,
                "lot_number": 1,
                "starting_price": "10.00",
                "minimum_increment": "1.00",
                "start_time": self.start.isoformat(),
                "end_time": self.end.isoformat(),
            }
            payload[field] = "0.00"
            response = self.api_post(
                f"/api/auctions/events/{event.pk}/lots/", payload
            )
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.data["code"], "VALIDATION_ERROR")
        self.assertEqual(event.lots.count(), 0)

    def test_submit_requires_a_lot_and_rejection_requires_reason(self):
        event = self._create_event()
        empty = self.api_post(f"/api/auctions/events/{event.pk}/submit/")
        self.assertEqual(empty.status_code, 400)
        self.assertEqual(empty.data["code"], "NO_LOTS")
        self.assertEqual(self._add_lot(event).status_code, 201)
        self.assertEqual(self.api_post(f"/api/auctions/events/{event.pk}/submit/").status_code, 200)
        self.api_login(self.admin)
        missing = self.api_post(
            f"/api/auctions/admin/events/{event.pk}/reject/", {"reason": ""}
        )
        self.assertEqual(missing.status_code, 400)
        rejected = self.api_post(
            f"/api/auctions/admin/events/{event.pk}/reject/",
            {"reason": "The provenance document is missing."},
        )
        self.assertEqual(rejected.status_code, 200)
        self.assertEqual(rejected.data["status"], AuctionEventStatus.REJECTED)

    def test_current_price_ordering_does_not_crash(self):
        event = self._create_event()
        first = self._add_lot(event)
        self.assertEqual(first.status_code, 201)
        second_product = Product.objects.create(
            owner=self.seller, name="Old Stamp", category=self.category
        )
        second = self._add_lot(event, second_product, lot_number=2)
        self.assertEqual(second.status_code, 201)
        event.status = AuctionEventStatus.SCHEDULED
        event.save(update_fields=["status"])
        response = self.client.get("/api/auctions/lots/?ordering=current_price")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 2)

    def test_promotion_immediately_blocks_seller_mutations_for_existing_session(self):
        participant_client = APIClient()
        admin_client = APIClient()
        self.api_login(self.seller, client=participant_client)
        created = self.api_post(
            "/api/auctions/events/",
            {
                "title": "Created before promotion",
                "description": "Historical seller record",
                "start_time": self.start.isoformat(),
                "end_time": self.end.isoformat(),
            },
            client=participant_client,
        )
        self.assertEqual(created.status_code, 201, created.data)
        event = AuctionEvent.objects.get(pk=created.data["id"])

        self.api_login(self.admin, client=admin_client)
        promoted = self.api_patch(
            f"/api/accounts/admin/users/{self.seller.pk}/",
            {"role": "ADMIN"},
            client=admin_client,
        )
        self.assertEqual(promoted.status_code, 200, promoted.data)

        attempts = [
            self.api_post(
                "/api/products/",
                {"name": "Forbidden item", "category": self.category.pk},
                client=participant_client,
            ),
            self.api_post(
                "/api/auctions/events/",
                {
                    "title": "Forbidden event",
                    "start_time": self.start.isoformat(),
                    "end_time": self.end.isoformat(),
                },
                client=participant_client,
            ),
            self.api_patch(
                f"/api/auctions/events/{event.pk}/",
                {"title": "Forbidden edit"},
                client=participant_client,
            ),
            self.api_post(
                f"/api/auctions/events/{event.pk}/lots/",
                {
                    "product": self.product.pk,
                    "lot_number": 1,
                    "starting_price": "100.00",
                    "minimum_increment": "5.00",
                    "start_time": self.start.isoformat(),
                    "end_time": self.end.isoformat(),
                },
                client=participant_client,
            ),
            self.api_post(
                f"/api/auctions/events/{event.pk}/submit/",
                client=participant_client,
            ),
        ]
        for response in attempts:
            self.assertEqual(response.status_code, 403, response.data)
            self.assertEqual(response.data["code"], "ADMIN_MARKETPLACE_RESTRICTED")

        self.assertFalse(Product.objects.filter(name="Forbidden item").exists())
        self.assertFalse(AuctionEvent.objects.filter(title="Forbidden event").exists())
        event.refresh_from_db()
        self.assertEqual(event.title, "Created before promotion")
        self.assertFalse(event.lots.exists())

        # Cancellation remains an administrator moderation action, not seller
        # participation, and still requires a reason.
        cancelled = self.api_post(
            f"/api/auctions/events/{event.pk}/cancel/",
            {"reason": "Cancelled during administrator review"},
            client=participant_client,
        )
        self.assertEqual(cancelled.status_code, 200, cancelled.data)
        self.assertEqual(cancelled.data["status"], AuctionEventStatus.CANCELLED)


    def test_event_can_be_created_with_multiple_lots_atomically(self):
        second_product = Product.objects.create(
            owner=self.seller, name="Rare Stamp", category=self.category
        )
        self.api_login(self.seller)
        response = self.api_post(
            "/api/auctions/events/",
            {
                "title": "Collection event",
                "start_time": self.start.isoformat(),
                "end_time": self.end.isoformat(),
                "lots": [
                    {"product": self.product.pk, "lot_number": 1, "starting_price": "10.00", "minimum_increment": "1.00", "start_time": self.start.isoformat(), "end_time": self.end.isoformat()},
                    {"product": second_product.pk, "lot_number": 2, "starting_price": "20.00", "minimum_increment": "2.00", "start_time": self.start.isoformat(), "end_time": self.end.isoformat()},
                ],
            },
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(len(response.data["lots"]), 2)

    def test_discarding_private_draft_deletes_event_lots_and_draft_products(self):
        event = self._create_event("Private work")
        self.assertEqual(self._add_lot(event).status_code, 201)
        response = self.api_delete(f"/api/auctions/events/{event.pk}/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(AuctionEvent.objects.filter(pk=event.pk).exists())
        self.assertFalse(AuctionLot.objects.filter(auction_event_id=event.pk).exists())
        self.assertFalse(Product.objects.filter(pk=self.product.pk).exists())

    def test_private_draft_never_changes_admin_totals_or_history(self):
        self.api_login(self.admin)
        before_totals = self.client.get("/api/analytics/dashboard/").data["totals"]
        before_history = self.client.get("/api/auctions/admin/events/history/").data["count"]

        event = self._create_event("Invisible private draft")
        self.assertEqual(self._add_lot(event).status_code, 201)

        self.api_login(self.admin)
        during_totals = self.client.get("/api/analytics/dashboard/").data["totals"]
        during_history = self.client.get("/api/auctions/admin/events/history/").data["count"]
        self.assertEqual(during_totals["events"], before_totals["events"])
        self.assertEqual(during_totals["lots"], before_totals["lots"])
        self.assertEqual(during_history, before_history)

        self.api_login(self.seller)
        self.assertEqual(self.api_delete(f"/api/auctions/events/{event.pk}/").status_code, 200)
        self.api_login(self.admin)
        after_totals = self.client.get("/api/analytics/dashboard/").data["totals"]
        after_history = self.client.get("/api/auctions/admin/events/history/").data["count"]
        self.assertEqual(after_totals["events"], before_totals["events"])
        self.assertEqual(after_totals["lots"], before_totals["lots"])
        self.assertEqual(after_history, before_history)

    def test_approved_event_revision_preserves_then_supersedes_original(self):
        event = self._create_event()
        self.assertEqual(self._add_lot(event).status_code, 201)
        self.api_post(f"/api/auctions/events/{event.pk}/submit/")
        self.api_login(self.admin)
        self.api_post(f"/api/auctions/admin/events/{event.pk}/approve/")
        self.api_login(self.seller)
        created = self.api_post(f"/api/auctions/events/{event.pk}/revise/")
        self.assertEqual(created.status_code, 201, created.data)
        revision = AuctionEvent.objects.get(pk=created.data["id"])
        self.assertEqual(revision.lots.count(), 1)
        event.refresh_from_db()
        self.assertEqual(event.status, AuctionEventStatus.SCHEDULED)
        self.api_patch(f"/api/auctions/events/{revision.pk}/", {"title": "Edited collection"})
        self.api_post(f"/api/auctions/events/{revision.pk}/submit/")
        self.api_login(self.admin)
        approved = self.api_post(f"/api/auctions/admin/events/{revision.pk}/approve/")
        self.assertEqual(approved.status_code, 200, approved.data)
        event.refresh_from_db()
        self.assertEqual(event.status, AuctionEventStatus.SUPERSEDED)
        self.assertTrue(AuctionEvent.objects.filter(pk=event.pk, title="Sunday Auction").exists())


class AdminAuctionHistoryApiTests(BaseTestCase):
    def setUp(self):
        self.admin = self.create_admin("history_admin")
        self.seller = self.create_user("history_seller")
        self.now = timezone.now()
        self.events_by_status = {}

        for index, event_status in enumerate(AuctionEventStatus.values):
            event = AuctionEvent.objects.create(
                organizer=self.seller,
                title=f"{event_status} auction",
                status=event_status,
                submitted_at=(self.now if event_status != AuctionEventStatus.DRAFT else None),
                start_time=self.now + timedelta(days=2),
                end_time=self.now + timedelta(days=2, hours=1),
            )
            AuctionEvent.objects.filter(pk=event.pk).update(
                updated_at=self.now + timedelta(minutes=index)
            )
            self.events_by_status[event_status] = event

    def test_history_contains_every_post_approval_and_cancelled_status_with_pagination(self):
        self.api_login(self.admin)

        first_page = self.client.get(
            "/api/auctions/admin/events/history/?page=1&page_size=2"
        )
        second_page = self.client.get(
            "/api/auctions/admin/events/history/?page=2&page_size=2"
        )
        third_page = self.client.get(
            "/api/auctions/admin/events/history/?page=3&page_size=2"
        )

        for response in (first_page, second_page, third_page):
            self.assertEqual(response.status_code, 200, response.data)
            self.assertEqual(response.data["count"], 7)
            self.assertEqual(response.data["total_pages"], 4)

        rows = (
            first_page.data["results"]
            + second_page.data["results"]
            + third_page.data["results"]
        )
        expected_statuses = [
            AuctionEventStatus.SUPERSEDED,
            AuctionEventStatus.REJECTED,
            AuctionEventStatus.CANCELLED,
            AuctionEventStatus.ENDED,
            AuctionEventStatus.ACTIVE,
            AuctionEventStatus.SCHEDULED,
            AuctionEventStatus.APPROVED,
        ]
        self.assertEqual([row["status"] for row in rows], expected_statuses)
        self.assertTrue(first_page.data["next"])
        self.assertIsNone(first_page.data["previous"])
        self.assertIsNone(third_page.data["next"])
        self.assertTrue(third_page.data["previous"])

        returned_ids = {row["id"] for row in rows}
        for excluded_status in (
            AuctionEventStatus.DRAFT,
            AuctionEventStatus.PENDING_APPROVAL,
        ):
            self.assertNotIn(self.events_by_status[excluded_status].pk, returned_ids)
        self.assertIn(self.events_by_status[AuctionEventStatus.REJECTED].pk, returned_ids)

    def test_history_requires_an_administrator(self):
        self.api_login(self.seller)
        response = self.client.get("/api/auctions/admin/events/history/")
        self.assertEqual(response.status_code, 403, response.data)


class AdminActiveBidTrackingApiTests(BaseTestCase):
    def setUp(self):
        self.admin = self.create_admin("bid_audit_admin")
        self.seller = self.create_user("bid_audit_seller")
        self.bidder_a = self.create_user("bidder_a")
        self.bidder_b = self.create_user("bidder_b")
        category = Category.objects.create(name="Bid audit items")
        product = Product.objects.create(
            owner=self.seller, name="Tracked watch", category=category
        )
        now = timezone.now()
        self.active_event = AuctionEvent.objects.create(
            organizer=self.seller,
            title="Active tracked auction",
            status=AuctionEventStatus.ACTIVE,
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=1),
        )
        self.active_lot = AuctionLot.objects.create(
            auction_event=self.active_event,
            product=product,
            lot_number=1,
            starting_price="100.00",
            minimum_increment="5.00",
            status=AuctionLotStatus.ACTIVE,
            start_time=self.active_event.start_time,
            end_time=self.active_event.end_time,
        )
        self.non_active_lot = AuctionLot.objects.create(
            auction_event=self.active_event,
            product=product,
            lot_number=2,
            starting_price="50.00",
            minimum_increment="5.00",
            status=AuctionLotStatus.SCHEDULED,
            start_time=now + timedelta(minutes=10),
            end_time=self.active_event.end_time,
        )
        ended_event = AuctionEvent.objects.create(
            organizer=self.seller,
            title="Ended auction",
            status=AuctionEventStatus.ENDED,
            start_time=now - timedelta(hours=2),
            end_time=now - timedelta(hours=1),
        )
        ended_lot = AuctionLot.objects.create(
            auction_event=ended_event,
            product=product,
            lot_number=1,
            starting_price="20.00",
            minimum_increment="1.00",
            status=AuctionLotStatus.SOLD,
            start_time=ended_event.start_time,
            end_time=ended_event.end_time,
        )

        self.first_bid = Bid.objects.create(
            auction_lot=self.active_lot,
            bidder=self.bidder_a,
            amount="105.00",
        )
        self.highest_bid = Bid.objects.create(
            auction_lot=self.active_lot,
            bidder=self.bidder_b,
            amount="110.00",
        )
        self.rejected_bid = Bid.objects.create(
            auction_lot=self.active_lot,
            bidder=self.bidder_a,
            amount="112.00",
            status=BidStatus.REJECTED,
            rejection_reason=RejectionReason.MINIMUM_INCREMENT_NOT_MET,
        )
        self.inactive_lot_attempt = Bid.objects.create(
            auction_lot=self.non_active_lot,
            bidder=self.bidder_b,
            amount="55.00",
            status=BidStatus.REJECTED,
            rejection_reason=RejectionReason.AUCTION_NOT_ACTIVE,
        )
        self.ended_bid = Bid.objects.create(
            auction_lot=ended_lot,
            bidder=self.bidder_a,
            amount="25.00",
        )
        self.active_lot.highest_bid = self.highest_bid
        self.active_lot.save(update_fields=["highest_bid", "updated_at"])

        ordered_bids = [
            self.first_bid,
            self.highest_bid,
            self.rejected_bid,
            self.inactive_lot_attempt,
        ]
        for index, bid in enumerate(ordered_bids):
            Bid.objects.filter(pk=bid.pk).update(
                created_at=now + timedelta(seconds=index)
            )

    def test_admin_sees_complete_active_auction_bid_audit_with_pagination(self):
        self.api_login(self.admin)
        first_page = self.client.get(
            "/api/auctions/admin/bids/?page=1&page_size=2"
        )
        second_page = self.client.get(
            "/api/auctions/admin/bids/?page=2&page_size=2"
        )

        for response in (first_page, second_page):
            self.assertEqual(response.status_code, 200, response.data)
            self.assertEqual(response.data["count"], 4)
            self.assertEqual(response.data["total_pages"], 2)

        rows = first_page.data["results"] + second_page.data["results"]
        self.assertEqual(
            [row["id"] for row in rows],
            [
                self.inactive_lot_attempt.pk,
                self.rejected_bid.pk,
                self.highest_bid.pk,
                self.first_bid.pk,
            ],
        )
        self.assertNotIn(self.ended_bid.pk, {row["id"] for row in rows})

        highest = next(row for row in rows if row["id"] == self.highest_bid.pk)
        self.assertEqual(highest["event_id"], self.active_event.pk)
        self.assertEqual(highest["event_title"], self.active_event.title)
        self.assertEqual(highest["lot_id"], self.active_lot.pk)
        self.assertEqual(highest["lot_number"], 1)
        self.assertEqual(highest["product_name"], "Tracked watch")
        self.assertEqual(highest["bidder_id"], self.bidder_b.pk)
        self.assertEqual(highest["bidder_username"], self.bidder_b.username)
        self.assertEqual(highest["amount"], "110.00")
        self.assertEqual(highest["status_display"], "Accepted")
        self.assertTrue(highest["is_highest"])
        self.assertNotIn("email", highest)

        rejected = next(row for row in rows if row["id"] == self.rejected_bid.pk)
        self.assertEqual(rejected["status"], BidStatus.REJECTED)
        self.assertEqual(
            rejected["rejection_reason_display"], "Minimum increment not met"
        )
        self.assertFalse(rejected["is_highest"])

    def test_filters_intersect_and_keep_inactive_lot_attempts_in_active_event(self):
        self.api_login(self.admin)
        accepted = self.client.get(
            "/api/auctions/admin/bids/",
            {
                "event": self.active_event.pk,
                "lot": self.active_lot.pk,
                "status": "accepted",
            },
        )
        self.assertEqual(accepted.status_code, 200, accepted.data)
        self.assertEqual(
            {row["id"] for row in accepted.data["results"]},
            {self.first_bid.pk, self.highest_bid.pk},
        )

        inactive_lot = self.client.get(
            "/api/auctions/admin/bids/",
            {"lot": self.non_active_lot.pk, "status": "REJECTED"},
        )
        self.assertEqual(inactive_lot.status_code, 200, inactive_lot.data)
        self.assertEqual(
            [row["id"] for row in inactive_lot.data["results"]],
            [self.inactive_lot_attempt.pk],
        )

        invalid = self.client.get(
            "/api/auctions/admin/bids/", {"status": "UNKNOWN"}
        )
        self.assertEqual(invalid.status_code, 400, invalid.data)

    def test_bid_tracking_requires_admin_and_anonymizes_deleted_bidder(self):
        self.api_login(self.bidder_a)
        forbidden = self.client.get("/api/auctions/admin/bids/")
        self.assertEqual(forbidden.status_code, 403, forbidden.data)

        anonymous = APIClient()
        self.assertIn(
            anonymous.get("/api/auctions/admin/bids/").status_code,
            (401, 403),
        )

        self.bidder_b.delete()
        self.api_login(self.admin)
        response = self.client.get(
            "/api/auctions/admin/bids/", {"lot": self.active_lot.pk}
        )
        self.assertEqual(response.status_code, 200, response.data)
        deleted_rows = [
            row for row in response.data["results"] if row["bidder_id"] is None
        ]
        self.assertTrue(deleted_rows)
        self.assertTrue(
            all(row["bidder_username"] == "Deleted user" for row in deleted_rows)
        )


class AuctionCancellationRequestApiTests(BaseTestCase):
    def setUp(self):
        self.admin = self.create_admin("cancellation_admin")
        self.seller = self.create_user("cancellation_seller")
        self.other = self.create_user("cancellation_other")
        category = Category.objects.create(name="Cancellation tests")
        product = Product.objects.create(
            owner=self.seller, name="Scheduled item", category=category
        )
        self.now = timezone.now()
        self.event = AuctionEvent.objects.create(
            organizer=self.seller,
            title="Scheduled auction",
            status=AuctionEventStatus.SCHEDULED,
            start_time=self.now + timedelta(days=2),
            end_time=self.now + timedelta(days=2, hours=2),
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

    def _request(self, reason="The item is no longer available."):
        return self.api_post(
            f"/api/auctions/events/{self.event.pk}/cancellation-request/",
            {"reason": reason},
        )

    def test_scheduled_auction_requires_request_and_admin_can_approve(self):
        self.api_login(self.seller)
        direct = self.api_post(
            f"/api/auctions/events/{self.event.pk}/cancel/",
            {"reason": "Trying to bypass review"},
        )
        self.assertEqual(direct.status_code, 400, direct.data)
        self.assertEqual(direct.data["code"], "CANCELLATION_REVIEW_REQUIRED")

        requested = self._request()
        self.assertEqual(requested.status_code, 201, requested.data)
        request_id = requested.data["id"]
        duplicate = self._request("A second reason")
        self.assertEqual(duplicate.status_code, 409, duplicate.data)
        self.assertEqual(duplicate.data["code"], "CANCELLATION_REQUEST_PENDING")
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.admin,
                actor=self.seller,
                verb="EVENT_CANCELLATION_REQUESTED",
                target_object_id=request_id,
            ).exists()
        )

        self.api_login(self.admin)
        approved = self.api_post(
            f"/api/auctions/admin/cancellation-requests/{request_id}/approve/"
        )
        self.assertEqual(approved.status_code, 200, approved.data)
        self.event.refresh_from_db()
        self.lot.refresh_from_db()
        cancellation = AuctionCancellationRequest.objects.get(pk=request_id)
        self.assertEqual(self.event.status, AuctionEventStatus.CANCELLED)
        self.assertEqual(self.lot.status, AuctionLotStatus.CANCELLED)
        self.assertEqual(cancellation.status, CancellationRequestStatus.APPROVED)
        self.assertEqual(cancellation.reviewed_by, self.admin)
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.seller,
                actor=self.admin,
                verb="EVENT_CANCELLATION_APPROVED",
            ).exists()
        )

    def test_request_window_boundary_and_ownership_are_enforced(self):
        self.event.start_time = self.now + timedelta(hours=24)
        self.event.end_time = self.event.start_time + timedelta(hours=2)
        self.event.save(update_fields=["start_time", "end_time"])
        self.lot.start_time = self.event.start_time
        self.lot.end_time = self.event.end_time
        self.lot.save(update_fields=["start_time", "end_time"])

        self.api_login(self.other)
        denied = self._request()
        self.assertEqual(denied.status_code, 403, denied.data)
        self.assertEqual(denied.data["code"], "NOT_OWNER")

        self.api_login(self.seller)
        with patch(
            "apps.auctions.services.cancellations.timezone.now",
            return_value=self.now,
        ):
            boundary = self._request()
        self.assertEqual(boundary.status_code, 201, boundary.data)

    def test_too_late_review_is_blocked_but_admin_can_reject(self):
        self.api_login(self.seller)
        requested = self._request()
        request_id = requested.data["id"]
        review_time = self.event.start_time - timedelta(hours=24) + timedelta(seconds=1)

        self.api_login(self.admin)
        with patch(
            "apps.auctions.services.cancellations.timezone.now",
            return_value=review_time,
        ):
            too_late = self.api_post(
                f"/api/auctions/admin/cancellation-requests/{request_id}/approve/"
            )
        self.assertEqual(too_late.status_code, 409, too_late.data)
        self.assertEqual(too_late.data["code"], "CANCELLATION_REQUEST_TOO_LATE")
        self.event.refresh_from_db()
        self.assertEqual(self.event.status, AuctionEventStatus.SCHEDULED)

        missing_reason = self.api_post(
            f"/api/auctions/admin/cancellation-requests/{request_id}/reject/"
        )
        self.assertEqual(missing_reason.status_code, 400, missing_reason.data)
        rejected = self.api_post(
            f"/api/auctions/admin/cancellation-requests/{request_id}/reject/",
            {"reason": "The auction is now too close to its start time."},
        )
        self.assertEqual(rejected.status_code, 200, rejected.data)
        self.assertEqual(rejected.data["status"], CancellationRequestStatus.REJECTED)
        self.event.refresh_from_db()
        self.assertEqual(self.event.status, AuctionEventStatus.SCHEDULED)
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.seller,
                verb="EVENT_CANCELLATION_REJECTED",
            ).exists()
        )


class BiddingAndClosingTests(BaseTestCase):
    def setUp(self):
        self.seller = self.create_user(username="seller")
        self.bidder_a = self.create_user(username="bidder_a")
        self.bidder_b = self.create_user(username="bidder_b")
        category = Category.objects.create(name="Art")
        product = Product.objects.create(owner=self.seller, name="Painting", category=category)
        now = timezone.now()
        self.event = AuctionEvent.objects.create(
            organizer=self.seller,
            title="Live art",
            status=AuctionEventStatus.ACTIVE,
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=1),
        )
        self.lot = AuctionLot.objects.create(
            auction_event=self.event,
            product=product,
            lot_number=1,
            starting_price="100.00",
            minimum_increment="5.00",
            start_time=now - timedelta(minutes=30),
            end_time=now + timedelta(minutes=30),
            status=AuctionLotStatus.ACTIVE,
        )

    def _bid(self, user, amount):
        self.api_login(user)
        return self.api_post(
            f"/api/auctions/lots/{self.lot.pk}/bids/place/", {"amount": amount}
        )

    def test_accepted_bid_updates_winner_and_outbid_notification(self):
        first = self._bid(self.bidder_a, "105.00")
        self.assertEqual(first.status_code, 200)
        second = self._bid(self.bidder_b, "110.00")
        self.assertEqual(second.status_code, 200)
        self.lot.refresh_from_db()
        self.assertEqual(self.lot.highest_bid.bidder, self.bidder_b)
        self.assertEqual(self.lot.highest_bid.amount, 110)
        self.assertTrue(
            Notification.objects.filter(recipient=self.bidder_a, verb="OUTBID").exists()
        )

    def test_each_rejection_is_persisted_without_changing_winner(self):
        cases = [
            (self.bidder_a, "not-a-number", "INVALID_AMOUNT"),
            (self.bidder_a, "100.00", "LOWER_THAN_CURRENT"),
            (self.bidder_a, "103.00", "MINIMUM_INCREMENT_NOT_MET"),
            (self.seller, "105.00", "SELLER_BIDDING"),
        ]
        self.bidder_b.is_blocked = True
        self.bidder_b.save(update_fields=["is_blocked"])
        cases.append((self.bidder_b, "105.00", "BLOCKED_USER"))
        for user, amount, code in cases:
            response = self._bid(user, amount)
            self.assertEqual(response.status_code, 422)
            self.assertEqual(response.data["code"], code)
            self.assertTrue(
                Bid.objects.filter(
                    auction_lot=self.lot,
                    bidder=user,
                    status=BidStatus.REJECTED,
                    rejection_reason=code,
                ).exists()
            )
        self.lot.refresh_from_db()
        self.assertIsNone(self.lot.highest_bid)

    def test_inactive_lot_rejection_is_audited(self):
        self.lot.status = AuctionLotStatus.SCHEDULED
        self.lot.save(update_fields=["status"])
        response = self._bid(self.bidder_a, "105.00")
        self.assertEqual(response.status_code, 422)
        self.assertTrue(
            Bid.objects.filter(
                auction_lot=self.lot,
                status=BidStatus.REJECTED,
                rejection_reason=RejectionReason.AUCTION_NOT_ACTIVE,
            ).exists()
        )

    def test_promotion_immediately_blocks_bidding_without_audit_row(self):
        bidder_client = APIClient()
        admin_client = APIClient()
        admin = self.create_admin(username="role_admin")
        self.api_login(self.bidder_a, client=bidder_client)
        self.api_login(admin, client=admin_client)
        promoted = self.api_patch(
            f"/api/accounts/admin/users/{self.bidder_a.pk}/",
            {"role": "ADMIN"},
            client=admin_client,
        )
        self.assertEqual(promoted.status_code, 200, promoted.data)

        response = self.api_post(
            f"/api/auctions/lots/{self.lot.pk}/bids/place/",
            {"amount": "105.00"},
            client=bidder_client,
        )
        self.assertEqual(response.status_code, 403, response.data)
        self.assertEqual(response.data["code"], "ADMIN_MARKETPLACE_RESTRICTED")
        self.assertFalse(Bid.objects.filter(bidder=self.bidder_a).exists())
        self.lot.refresh_from_db()
        self.assertIsNone(self.lot.highest_bid)

    def test_sold_closure_creates_one_cod_order_and_is_idempotent(self):
        self.assertEqual(self._bid(self.bidder_a, "105.00").status_code, 200)
        result = close_lot(self.lot.pk, force=True)
        self.assertEqual(result["status"], AuctionLotStatus.AWAITING_ORDER)
        order = Order.objects.get(auction_lot=self.lot)
        self.assertEqual(order.buyer, self.bidder_a)
        self.assertEqual(order.status, OrderStatus.AWAITING_CONFIRMATION)
        self.event.refresh_from_db()
        self.assertEqual(self.event.status, AuctionEventStatus.AWAITING_ORDERS)
        repeated = close_lot(self.lot.pk, force=True)
        self.assertTrue(repeated["skipped"])
        self.assertEqual(Order.objects.filter(auction_lot=self.lot).count(), 1)

    def test_bid_history_marks_only_exact_highest_bid_as_winning(self):
        self.assertEqual(self._bid(self.bidder_a, "105.00").status_code, 200)
        self.assertEqual(self._bid(self.bidder_a, "110.00").status_code, 200)
        close_lot(self.lot.pk, force=True)

        history = self.client.get("/api/auctions/bids/mine/?page_size=100")
        self.assertEqual(history.status_code, 200)
        self.assertEqual(len(history.data["results"]), 2)
        self.assertEqual(
            [row["outcome"] for row in history.data["results"]],
            ["winning", "lost"],
        )
        self.assertTrue(all(row["lot"]["id"] == self.lot.pk for row in history.data["results"]))

        detail = self.client.get(f"/api/auctions/lots/{self.lot.pk}/")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.data["winner_username"], self.bidder_a.username)
        self.assertEqual(detail.data["current_price"], "110.00")

    def test_no_bid_closure_is_unsold_and_ends_event(self):
        result = close_lot(self.lot.pk, force=True)
        self.assertEqual(result["status"], AuctionLotStatus.UNSOLD)
        self.assertFalse(Order.objects.filter(auction_lot=self.lot).exists())
        self.event.refresh_from_db()
        self.assertEqual(self.event.status, AuctionEventStatus.ENDED)


async def _noop_broadcast(*args, **kwargs):
    return None


class ConcurrentBidTests(TransactionTestCase):
    """Exercise the row lock with separate PostgreSQL connections."""

    def setUp(self):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        self.seller = User.objects.create_user("seller@example.com", "seller", "StrongPass123!")
        self.bidder_a = User.objects.create_user("a@example.com", "bidder_a", "StrongPass123!")
        self.bidder_b = User.objects.create_user("b@example.com", "bidder_b", "StrongPass123!")
        category = Category.objects.create(name="Concurrent Art")
        product = Product.objects.create(owner=self.seller, name="Sculpture", category=category)
        now = timezone.now()
        event = AuctionEvent.objects.create(
            organizer=self.seller,
            title="Concurrent auction",
            status=AuctionEventStatus.ACTIVE,
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=1),
        )
        self.lot = AuctionLot.objects.create(
            auction_event=event,
            product=product,
            lot_number=1,
            starting_price="100.00",
            minimum_increment="5.00",
            start_time=now - timedelta(minutes=10),
            end_time=now + timedelta(minutes=10),
            status=AuctionLotStatus.ACTIVE,
        )

    def test_simultaneous_bids_serialize_and_highest_amount_wins(self):
        barrier = threading.Barrier(2)
        results = []
        result_lock = threading.Lock()

        def submit(user_id, amount):
            from django.contrib.auth import get_user_model

            close_old_connections()
            user = get_user_model().objects.get(pk=user_id)
            barrier.wait(timeout=5)
            try:
                bid, _ = place_bid(self.lot.pk, user, amount)
                outcome = ("accepted", str(bid.amount))
            except BidRejected as error:
                outcome = ("rejected", error.code)
            finally:
                connections.close_all()
            with result_lock:
                results.append(outcome)

        with (
            patch("apps.auctions.services.bids.notify"),
            patch("apps.auctions.services.bids._send_user_alert", new=_noop_broadcast),
            patch("apps.auctions.services.bids._send_lot_broadcast", new=_noop_broadcast),
            patch("apps.auctions.services.bids._send_browse_update", new=_noop_broadcast),
        ):
            threads = [
                threading.Thread(target=submit, args=(self.bidder_a.pk, "105.00")),
                threading.Thread(target=submit, args=(self.bidder_b.pk, "110.00")),
            ]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=10)

        self.assertTrue(all(not thread.is_alive() for thread in threads))
        self.assertEqual(len(results), 2)
        self.lot.refresh_from_db()
        self.assertEqual(self.lot.highest_bid.amount, 110)
        self.assertEqual(self.lot.highest_bid.bidder, self.bidder_b)
        self.assertIn(Bid.objects.filter(auction_lot=self.lot, status=BidStatus.ACCEPTED).count(), (1, 2))
