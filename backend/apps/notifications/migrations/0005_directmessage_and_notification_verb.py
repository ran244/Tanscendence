from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("notifications", "0004_alter_notification_verb"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]

    operations = [
        migrations.CreateModel(
            name="DirectMessage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("message", models.TextField(max_length=2000)),
                ("read_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("recipient", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="received_direct_messages", to=settings.AUTH_USER_MODEL)),
                ("sender", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="sent_direct_messages", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["created_at"]},
        ),
        migrations.AddIndex(model_name="directmessage", index=models.Index(fields=["sender", "recipient", "created_at"], name="notificatio_sender__044215_idx")),
        migrations.AlterField(
            model_name="notification", name="verb",
            field=models.CharField(choices=[
                ("BID_ACCEPTED", "Bid accepted"), ("OUTBID", "Outbid"), ("EVENT_SUBMITTED", "Event submitted"),
                ("EVENT_APPROVED", "Event approved"), ("EVENT_REJECTED", "Event rejected"), ("EVENT_ACTIVATED", "Event activated"),
                ("EVENT_CANCELLED", "Event cancelled"), ("EVENT_CANCELLATION_REQUESTED", "Event cancellation requested"),
                ("EVENT_CANCELLATION_APPROVED", "Event cancellation approved"), ("EVENT_CANCELLATION_REJECTED", "Event cancellation rejected"),
                ("EVENT_UPDATED", "Event updated"), ("LOT_CREATED", "Lot created"), ("LOT_UPDATED", "Lot updated"),
                ("LOT_REMOVED", "Lot removed"), ("LOT_ENDED", "Lot ended"), ("LOT_WINNER", "Lot won"),
                ("CLOSING_SOON", "Closing soon"), ("FRIEND_REQUEST", "Friend request"), ("FRIEND_ACCEPTED", "Friend request accepted"),
                ("DIRECT_MESSAGE", "Direct message"), ("COD_CONFIRMED", "Cash on delivery confirmed"), ("ORDER_CREATED", "Order created"),
                ("ORDER_CANCELLED", "Order cancelled"), ("ORDER_SHIPPED", "Order shipped"), ("ORDER_DELIVERED", "Order delivered"),
                ("SUPPORT_REPLY", "Support reply"), ("SUPPORT_TICKET_CREATED", "Support ticket created"),
                ("TICKET_STATUS_CHANGED", "Ticket status changed"), ("PRODUCT_CREATED", "Product created"),
                ("PRODUCT_UPDATED", "Product updated"), ("PRODUCT_REMOVED", "Product removed")
            ], max_length=32),
        ),
    ]
