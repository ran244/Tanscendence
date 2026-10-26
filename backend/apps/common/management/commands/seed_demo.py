"""
Idempotent demo-data seeding. Runs only when SEED_DEMO=true and the
SEED_DEMO_ADMIN_* environment variables are provided. Creates an admin,
demo users, friends, categories, products, events/lots at useful statuses,
bids, notifications and orders. Safe to run repeatedly.
"""
import os
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

User = get_user_model()


class Command(BaseCommand):
    help = "Seed deterministic demo data (requires SEED_DEMO=true and SEED_DEMO_ADMIN_* env vars)."

    def handle(self, *args, **options):
        if not settings.SEED_DEMO:
            self.stdout.write(self.style.WARNING(
                "SEED_DEMO is not enabled. Set SEED_DEMO=true and SEED_DEMO_ADMIN_EMAIL/PASSWORD."
            ))
            return
        admin_email = os.getenv("SEED_DEMO_ADMIN_EMAIL", "")
        admin_password = os.getenv("SEED_DEMO_ADMIN_PASSWORD", "")
        if not admin_email or not admin_password or len(admin_password) < 12:
            self.stdout.write(self.style.ERROR(
                "SEED_DEMO_ADMIN_EMAIL and a strong SEED_DEMO_ADMIN_PASSWORD (>=12 chars) are required."
            ))
            return

        admin, _ = User.objects.get_or_create(
            email=admin_email.lower(),
            defaults={"username": "admin", "role": "ADMIN", "is_staff": True, "is_superuser": True},
        )
        admin.role = "ADMIN"
        admin.is_staff = True
        admin.is_superuser = True
        admin.is_active = True
        if not admin.check_password(admin_password):
            admin.set_password(admin_password)
        admin.save()

        now = timezone.now()
        from apps.accounts.models import Friendship, FriendshipStatus

        users = {}
        for username, email in (
            ("seller", "seller@mystery.test"),
            ("bidder_a", "biddera@mystery.test"),
            ("bidder_b", "bidderb@mystery.test"),
        ):
            user, created = User.objects.get_or_create(
                email=email, defaults={"username": username}
            )
            if not user.check_password("Demo_Password_123!"):
                user.set_password("Demo_Password_123!")
                user.save()
            users[username] = user

        if not Friendship.objects.filter(
            requester=users["bidder_a"], addressee=users["bidder_b"]
        ).exists():
            Friendship.objects.create(
                requester=users["bidder_a"], addressee=users["bidder_b"],
                status=FriendshipStatus.ACCEPTED,
            )

        from apps.products.models import Category, Product

        categories = {}
        for name in ("Antiquities", "Paintings", "Coins", "Jewellery"):
            category, _ = Category.objects.get_or_create(name=name)
            categories[name] = category

        products = {}
        for name, category_name in (
            ("Bronze Roman Lamp", "Antiquities"),
            ("Ottoman Silk Rug", "Antiquities"),
            ("19th Century Oil Portrait", "Paintings"),
            ("Rare Silver Dirham Hoard", "Coins"),
            ("Amber Pendant Necklace", "Jewellery"),
        ):
            product, created = Product.objects.get_or_create(
                owner=users["seller"], name=name,
                defaults={"description": f"A curated {category_name.lower()} item for demo purposes.", "category": categories[category_name]},
            )
            if not created:
                product.category = categories[category_name]
                product.available = True
                product.save()
            products[name] = product

        from apps.auctions.models import (
            AuctionEvent,
            AuctionEventStatus,
            AuctionLot,
            AuctionLotStatus,
            Bid,
            BidStatus,
        )
        from apps.orders.models import Order, OrderStatus, Payment, PaymentStatus

        # --- Live event (active, bidding possible) -------------------------
        live_event, _ = AuctionEvent.objects.get_or_create(
            title="Mystery Antiques Live — Demo Session",
            defaults={
                "description": "A live demo session of curated antiquities.",
                "organizer": users["seller"],
                "start_time": now - timedelta(hours=1),
                "end_time": now + timedelta(hours=6),
                "status": AuctionEventStatus.ACTIVE,
                "submitted_at": now - timedelta(days=2),
                "reviewed_by": admin,
                "reviewed_at": now - timedelta(days=1),
            },
        )
        live_lot, _ = AuctionLot.objects.get_or_create(
            auction_event=live_event, lot_number=1,
            defaults={
                "product": products["Bronze Roman Lamp"],
                "starting_price": "50.00",
                "minimum_increment": "5.00",
                "start_time": now - timedelta(hours=1),
                "end_time": now + timedelta(hours=6),
                "status": AuctionLotStatus.ACTIVE,
            },
        )
        if not Bid.objects.filter(auction_lot=live_lot).exists():
            bid_a = Bid.objects.create(
                auction_lot=live_lot, bidder=users["bidder_a"], amount="55.00"
            )
            Bid.objects.create(auction_lot=live_lot, bidder=users["bidder_b"], amount="60.00")
            live_lot.highest_bid = Bid.objects.get(
                auction_lot=live_lot, bidder=users["bidder_b"], amount="60.00"
            )
            live_lot.save(update_fields=["highest_bid"])
            bid_a.created_at = now - timedelta(minutes=10)
            bid_a.save()

        second_lot, _ = AuctionLot.objects.get_or_create(
            auction_event=live_event, lot_number=2,
            defaults={
                "product": products["Ottoman Silk Rug"],
                "starting_price": "200.00",
                "minimum_increment": "10.00",
                "start_time": now - timedelta(hours=1),
                "end_time": now + timedelta(hours=6),
                "status": AuctionLotStatus.ACTIVE,
            },
        )

        # --- Ended event with a sale (order + payments) ---------------------
        ended_event, _ = AuctionEvent.objects.get_or_create(
            title="Past Session — Sold Lots",
            defaults={
                "description": "A past demo session with a completed sale.",
                "organizer": users["seller"],
                "start_time": now - timedelta(days=3),
                "end_time": now - timedelta(days=2),
                "status": AuctionEventStatus.ENDED,
                "submitted_at": now - timedelta(days=5),
                "reviewed_by": admin,
                "reviewed_at": now - timedelta(days=4),
            },
        )
        sold_lot, _ = AuctionLot.objects.get_or_create(
            auction_event=ended_event, lot_number=1,
            defaults={
                "product": products["Rare Silver Dirham Hoard"],
                "starting_price": "300.00",
                "minimum_increment": "10.00",
                "start_time": now - timedelta(days=3),
                "end_time": now - timedelta(days=2),
                "status": AuctionLotStatus.SOLD,
            },
        )
        if sold_lot.highest_bid_id is None:
            winner_bid = Bid.objects.create(
                auction_lot=sold_lot, bidder=users["bidder_a"], amount="320.00"
            )
            sold_lot.highest_bid = winner_bid
            sold_lot.save(update_fields=["highest_bid"])
        order, order_created = Order.objects.get_or_create(
            auction_lot=sold_lot,
            defaults={
                "buyer": users["bidder_a"],
                "seller": users["seller"],
                "final_price": "320.00",
                "shipping_address": "Demo Street 12, Amman, Jordan",
                "status": OrderStatus.DELIVERED,
            },
        )
        if order_created:
            Payment.objects.create(
                order=order,
                amount="320.00",
                status=PaymentStatus.COLLECTED,
                collection_note="Cash collected on delivery for the demo order.",
                collected_at=now - timedelta(days=2),
            )

        # --- Pending approval event (for admin demo) ------------------------
        pending_event, _ = AuctionEvent.objects.get_or_create(
            title="Pending Review — Demo Event",
            defaults={
                "description": "An event awaiting admin approval.",
                "organizer": users["seller"],
                "start_time": now + timedelta(days=3),
                "end_time": now + timedelta(days=4),
                "status": AuctionEventStatus.PENDING_APPROVAL,
                "submitted_at": now - timedelta(hours=1),
            },
        )
        AuctionLot.objects.get_or_create(
            auction_event=pending_event, lot_number=1,
            defaults={
                "product": products["19th Century Oil Portrait"],
                "starting_price": "150.00",
                "minimum_increment": "10.00",
                "start_time": now + timedelta(days=3),
                "end_time": now + timedelta(days=4),
                "status": AuctionLotStatus.SCHEDULED,
            },
        )

        from apps.notifications.models import Notification

        Notification.objects.get_or_create(
            recipient=users["bidder_a"],
            verb="OUTBID",
            dedupe_key="seed-outbid-biddera",
            defaults={
                "actor": users["bidder_b"],
                "target": live_lot,
                "message_key": "notifications.outbid",
            },
        )
        Notification.objects.get_or_create(
            recipient=users["seller"],
            verb="EVENT_APPROVED",
            dedupe_key="seed-event-approved",
            defaults={
                "actor": admin,
                "target": live_event,
                "message_key": "notifications.event_approved",
            },
        )

        self.stdout.write(self.style.SUCCESS(
            f"Demo data ready: admin={admin.email}, seller/2 bidders, "
            f"{len(products)} products, live/pending/ended events, bids, order and COD collection."
        ))
