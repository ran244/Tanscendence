"""Create a coherent, non-destructive marketplace dataset for demonstrations."""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone


MOCK_PASSWORD = "MockDemo123!"


class Command(BaseCommand):
    help = "Create or refresh idempotent mock users, auctions, bids, orders and social data."

    @transaction.atomic
    def handle(self, *args, **options):
        from apps.accounts.models import Friendship, FriendshipStatus
        from apps.auctions.models import (
            AuctionEvent, AuctionEventStatus, AuctionLot, AuctionLotStatus,
            Bid, BidStatus,
        )
        from apps.notifications.models import DirectMessage
        from apps.notifications.services import notify
        from apps.orders.models import Order, OrderStatus, Payment, PaymentStatus
        from apps.products.models import Category, Product

        User = get_user_model()
        now = timezone.now()
        admin = User.objects.filter(role="ADMIN", is_active=True).first()

        user_specs = {
            "maya_curator": ("maya.curator@mock.mystery.test", "Maya", "Haddad", "+962790000101", "Collector and seller of regional art and historic objects."),
            "omar_collector": ("omar.collector@mock.mystery.test", "Omar", "Nasser", "+962790000102", "Coin and manuscript collector based in Amman."),
            "lina_arts": ("lina.arts@mock.mystery.test", "Lina", "Khalil", "+962790000103", "Interested in paintings, jewellery and decorative arts."),
            "sami_vintage": ("sami.vintage@mock.mystery.test", "Sami", "Darwish", "+962790000104", "Vintage toy and watch enthusiast."),
        }
        users = {}
        for username, (email, first, last, phone, bio) in user_specs.items():
            user, _ = User.objects.update_or_create(
                email=email,
                defaults={
                    "username": username, "first_name": first, "last_name": last,
                    "phone_number": phone, "bio": bio, "email_verified": True,
                    "is_active": True,
                },
            )
            user.set_password(MOCK_PASSWORD)
            user.save(update_fields=["password"])
            users[username] = user

        Friendship.objects.update_or_create(
            requester=users["omar_collector"], addressee=users["lina_arts"],
            defaults={"status": FriendshipStatus.ACCEPTED},
        )
        Friendship.objects.update_or_create(
            requester=users["sami_vintage"], addressee=users["omar_collector"],
            defaults={"status": FriendshipStatus.PENDING},
        )
        DirectMessage.objects.get_or_create(
            sender=users["omar_collector"], recipient=users["lina_arts"],
            message="The upcoming manuscript lot looks exceptional. Good luck!",
        )

        category_descriptions = {
            "Antiquities": "Historic objects and archaeological-style collectibles.",
            "Books & Manuscripts": "Rare books, letters, maps and handwritten works.",
            "Coins": "Historic coinage, medals and numismatic collections.",
            "Jewellery": "Vintage and contemporary jewellery and precious objects.",
            "Paintings": "Original paintings, drawings and framed works.",
            "Toys & Games": "Collectible toys, board games and childhood memorabilia.",
            "Other": "Distinctive collectibles that do not fit another category.",
        }
        categories = {}
        for name, description in category_descriptions.items():
            category, _ = Category.objects.get_or_create(name=name)
            if not category.description:
                category.description = description
                category.save(update_fields=["description"])
            categories[name] = category

        product_specs = {
            "Nabataean Bronze Oil Lamp": ("Antiquities", "A small bronze lamp with geometric decoration and a naturally aged patina."),
            "Ottoman Brass Coffee Grinder": ("Antiquities", "Hand-engraved cylindrical grinder dating to the late Ottoman period."),
            "1923 Transjordan Postal Cover": ("Books & Manuscripts", "A preserved postal cover with early Transjordan stamps and clear cancellations."),
            "Handwritten Levantine Recipe Book": ("Books & Manuscripts", "A family recipe notebook containing Arabic handwriting from the 1940s."),
            "Abbasid Silver Dirham": ("Coins", "A catalogued silver dirham with legible calligraphy and even toning."),
            "Jordan 1969 Proof Coin Set": ("Coins", "A complete proof set in its original presentation case."),
            "Art Deco Sapphire Brooch": ("Jewellery", "Geometric silver brooch with a central blue sapphire and period clasp."),
            "Amman at Dawn Watercolour": ("Paintings", "Signed watercolour showing the old city hills in warm morning light."),
            "1960s Tin Fire Engine": ("Toys & Games", "Lithographed tin fire engine with working wheels and original ladder."),
            "Swiss Mechanical Desk Clock": ("Other", "Eight-day mechanical clock in a walnut presentation case."),
            "Mother-of-Pearl Jewellery Box": ("Other", "Damascene-style wooden box with detailed mother-of-pearl inlay."),
        }
        products = {}
        seller = users["maya_curator"]
        for name, (category_name, description) in product_specs.items():
            product, _ = Product.objects.update_or_create(
                owner=seller, name=name,
                defaults={"category": categories[category_name], "description": description, "available": True},
            )
            products[name] = product

        def event(title, description, start, end, status, submitted=True):
            obj, _ = AuctionEvent.objects.update_or_create(
                organizer=seller, title=title,
                defaults={
                    "description": description, "start_time": start, "end_time": end,
                    "status": status, "submitted_at": now - timedelta(days=2) if submitted else None,
                    "reviewed_by": admin if status not in (AuctionEventStatus.DRAFT, AuctionEventStatus.PENDING_APPROVAL) else None,
                    "reviewed_at": now - timedelta(days=1) if admin and status not in (AuctionEventStatus.DRAFT, AuctionEventStatus.PENDING_APPROVAL) else None,
                },
            )
            return obj

        def lot(event_obj, number, product_name, start_price, increment, status):
            obj, _ = AuctionLot.objects.update_or_create(
                auction_event=event_obj, lot_number=number,
                defaults={
                    "product": products[product_name], "starting_price": Decimal(start_price),
                    "minimum_increment": Decimal(increment), "start_time": event_obj.start_time,
                    "end_time": event_obj.end_time, "status": status,
                },
            )
            return obj

        def bid(lot_obj, bidder, amount):
            obj, _ = Bid.objects.get_or_create(
                auction_lot=lot_obj, bidder=bidder, amount=Decimal(amount),
                status=BidStatus.ACCEPTED,
            )
            lot_obj.highest_bid = obj
            lot_obj.save(update_fields=["highest_bid"])
            return obj

        live = event(
            "[Mock] Treasures of Amman — Live", "Four curated objects with active competitive bidding.",
            now - timedelta(hours=2), now + timedelta(hours=5), AuctionEventStatus.ACTIVE,
        )
        live_lots = [
            lot(live, 1, "Nabataean Bronze Oil Lamp", "85.00", "5.00", AuctionLotStatus.ACTIVE),
            lot(live, 2, "Ottoman Brass Coffee Grinder", "120.00", "10.00", AuctionLotStatus.ACTIVE),
            lot(live, 3, "Abbasid Silver Dirham", "180.00", "10.00", AuctionLotStatus.ACTIVE),
            lot(live, 4, "1960s Tin Fire Engine", "65.00", "5.00", AuctionLotStatus.ACTIVE),
        ]
        bid(live_lots[0], users["omar_collector"], "90.00")
        bid(live_lots[0], users["lina_arts"], "105.00")
        bid(live_lots[1], users["sami_vintage"], "130.00")
        bid(live_lots[2], users["omar_collector"], "190.00")
        bid(live_lots[2], users["omar_collector"], "210.00")

        upcoming = event(
            "[Mock] Paper, Paint & Memory", "An upcoming sale of manuscripts and Jordanian art.",
            now + timedelta(days=2), now + timedelta(days=2, hours=6), AuctionEventStatus.SCHEDULED,
        )
        lot(upcoming, 1, "1923 Transjordan Postal Cover", "140.00", "10.00", AuctionLotStatus.SCHEDULED)
        lot(upcoming, 2, "Handwritten Levantine Recipe Book", "95.00", "5.00", AuctionLotStatus.SCHEDULED)
        lot(upcoming, 3, "Amman at Dawn Watercolour", "260.00", "20.00", AuctionLotStatus.SCHEDULED)

        waiting = event(
            "[Mock] Jewellery & Timepieces", "Bidding has ended; winners are completing their delivery requests.",
            now - timedelta(days=2), now - timedelta(days=1), AuctionEventStatus.AWAITING_ORDERS,
        )
        waiting_one = lot(waiting, 1, "Art Deco Sapphire Brooch", "300.00", "20.00", AuctionLotStatus.AWAITING_ORDER)
        waiting_two = lot(waiting, 2, "Swiss Mechanical Desk Clock", "220.00", "10.00", AuctionLotStatus.AWAITING_ORDER)
        bid(waiting_one, users["lina_arts"], "360.00")
        bid(waiting_two, users["sami_vintage"], "250.00")
        order_one, _ = Order.objects.update_or_create(
            auction_lot=waiting_one,
            defaults={"buyer": users["lina_arts"], "seller": seller, "final_price": Decimal("360.00"), "status": OrderStatus.AWAITING_CONFIRMATION, "shipping_address": ""},
        )
        order_two, _ = Order.objects.update_or_create(
            auction_lot=waiting_two,
            defaults={
                "buyer": users["sami_vintage"], "seller": seller, "final_price": Decimal("250.00"),
                "status": OrderStatus.CONFIRMED, "delivery_full_name": "Sami Darwish",
                "shipping_address": "18 Rainbow Street", "delivery_city": "Amman",
                "delivery_phone": "+962790000104", "delivery_notes": "Please call before arriving.",
            },
        )
        Payment.objects.update_or_create(order=order_two, defaults={"amount": order_two.final_price, "status": PaymentStatus.PENDING})

        ended = event(
            "[Mock] Jordanian Collectors Archive", "A completed sale containing both sold and unsold lots.",
            now - timedelta(days=12), now - timedelta(days=11), AuctionEventStatus.ENDED,
        )
        sold = lot(ended, 1, "Jordan 1969 Proof Coin Set", "200.00", "10.00", AuctionLotStatus.SOLD)
        lot(ended, 2, "Mother-of-Pearl Jewellery Box", "175.00", "10.00", AuctionLotStatus.UNSOLD)
        bid(sold, users["omar_collector"], "245.00")
        completed, _ = Order.objects.update_or_create(
            auction_lot=sold,
            defaults={
                "buyer": users["omar_collector"], "seller": seller, "final_price": Decimal("245.00"),
                "status": OrderStatus.DELIVERED, "delivery_full_name": "Omar Nasser",
                "shipping_address": "42 University Street", "delivery_city": "Amman",
                "delivery_phone": "+962790000102", "delivery_notes": "Delivered successfully.",
            },
        )
        Payment.objects.update_or_create(
            order=completed,
            defaults={"amount": completed.final_price, "status": PaymentStatus.COLLECTED, "collected_at": now - timedelta(days=10), "collection_note": "Cash received in full."},
        )

        pending = event(
            "[Mock] Weekend Curiosities", "A seller submission ready for administrator review.",
            now + timedelta(days=5), now + timedelta(days=5, hours=4), AuctionEventStatus.PENDING_APPROVAL,
        )
        lot(pending, 1, "Mother-of-Pearl Jewellery Box", "175.00", "10.00", AuctionLotStatus.SCHEDULED)

        notify(recipient=users["lina_arts"], verb="LOT_WINNER", target=waiting_one,
               message_key="notifications.lot_winner", dedupe_key="mock_lina_winner")
        notify(recipient=seller, actor=users["sami_vintage"], verb="COD_CONFIRMED", target=order_two,
               message_key="notifications.cod_confirmed", dedupe_key="mock_sami_delivery")
        if admin:
            notify(recipient=admin, actor=seller, verb="EVENT_SUBMITTED", target=pending,
                   message_key="notifications.admin_event_submitted", dedupe_key="mock_pending_event")

        self.stdout.write(self.style.SUCCESS(
            "Mock data ready: 4 users, 11 products, 5 auction scenarios, 12 lots, "
            "bids with repeat-bid history, 3 order states, friendships and notifications."
        ))
        self.stdout.write(f"Mock login password for all four users: {MOCK_PASSWORD}")
