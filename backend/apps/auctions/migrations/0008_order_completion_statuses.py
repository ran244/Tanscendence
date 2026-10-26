from django.db import migrations, models


def move_open_orders_to_waiting(apps, schema_editor):
    AuctionEvent = apps.get_model("auctions", "AuctionEvent")
    AuctionLot = apps.get_model("auctions", "AuctionLot")
    Order = apps.get_model("orders", "Order")

    open_lot_ids = Order.objects.exclude(status__in=["DELIVERED", "CANCELLED"]).values_list(
        "auction_lot_id", flat=True
    )
    AuctionLot.objects.filter(id__in=open_lot_ids, status="SOLD").update(
        status="AWAITING_ORDER"
    )
    event_ids = AuctionLot.objects.filter(status="AWAITING_ORDER").values_list(
        "auction_event_id", flat=True
    )
    AuctionEvent.objects.filter(id__in=event_ids, status="ENDED").update(
        status="AWAITING_ORDERS"
    )


class Migration(migrations.Migration):
    dependencies = [
        ("auctions", "0007_auctionevent_revisions"),
        ("orders", "0005_alter_order_buyer_alter_order_seller"),
    ]

    operations = [
        migrations.AlterField(
            model_name="auctionevent",
            name="status",
            field=models.CharField(
                choices=[
                    ("DRAFT", "Draft"), ("PENDING_APPROVAL", "Pending approval"),
                    ("REJECTED", "Rejected"), ("APPROVED", "Approved"),
                    ("SCHEDULED", "Scheduled"), ("ACTIVE", "Active"),
                    ("AWAITING_ORDERS", "Waiting for order completion"),
                    ("ENDED", "Ended"), ("CANCELLED", "Cancelled"),
                    ("SUPERSEDED", "Superseded"),
                ],
                default="DRAFT",
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="auctionlot",
            name="status",
            field=models.CharField(
                choices=[
                    ("SCHEDULED", "Scheduled"), ("ACTIVE", "Active"),
                    ("AWAITING_ORDER", "Waiting for order completion"),
                    ("CANCELLED", "Cancelled"), ("SOLD", "Sold"),
                    ("UNSOLD", "Unsold"),
                ],
                default="SCHEDULED",
                max_length=20,
            ),
        ),
        migrations.RunPython(move_open_orders_to_waiting, migrations.RunPython.noop),
    ]
