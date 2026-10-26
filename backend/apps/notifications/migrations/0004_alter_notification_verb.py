from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0003_alter_notification_verb"),
    ]

    operations = [
        migrations.AlterField(
            model_name="notification",
            name="verb",
            field=models.CharField(
                choices=[
                    ("BID_ACCEPTED", "Bid accepted"),
                    ("OUTBID", "Outbid"),
                    ("EVENT_SUBMITTED", "Event submitted"),
                    ("EVENT_APPROVED", "Event approved"),
                    ("EVENT_REJECTED", "Event rejected"),
                    ("EVENT_ACTIVATED", "Event activated"),
                    ("EVENT_CANCELLED", "Event cancelled"),
                    ("EVENT_CANCELLATION_REQUESTED", "Event cancellation requested"),
                    ("EVENT_CANCELLATION_APPROVED", "Event cancellation approved"),
                    ("EVENT_CANCELLATION_REJECTED", "Event cancellation rejected"),
                    ("EVENT_UPDATED", "Event updated"),
                    ("LOT_CREATED", "Lot created"),
                    ("LOT_UPDATED", "Lot updated"),
                    ("LOT_REMOVED", "Lot removed"),
                    ("LOT_ENDED", "Lot ended"),
                    ("LOT_WINNER", "Lot won"),
                    ("CLOSING_SOON", "Closing soon"),
                    ("FRIEND_REQUEST", "Friend request"),
                    ("FRIEND_ACCEPTED", "Friend request accepted"),
                    ("COD_CONFIRMED", "Cash on delivery confirmed"),
                    ("ORDER_CREATED", "Order created"),
                    ("ORDER_CANCELLED", "Order cancelled"),
                    ("ORDER_SHIPPED", "Order shipped"),
                    ("ORDER_DELIVERED", "Order delivered"),
                    ("SUPPORT_REPLY", "Support reply"),
                    ("SUPPORT_TICKET_CREATED", "Support ticket created"),
                    ("TICKET_STATUS_CHANGED", "Ticket status changed"),
                    ("PRODUCT_CREATED", "Product created"),
                    ("PRODUCT_UPDATED", "Product updated"),
                    ("PRODUCT_REMOVED", "Product removed"),
                ],
                max_length=32,
            ),
        ),
    ]
