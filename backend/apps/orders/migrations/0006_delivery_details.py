from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("orders", "0005_alter_order_buyer_alter_order_seller")]

    operations = [
        migrations.AddField(
            model_name="order", name="delivery_full_name",
            field=models.CharField(blank=True, default="", max_length=200),
        ),
        migrations.AddField(
            model_name="order", name="delivery_city",
            field=models.CharField(blank=True, default="", max_length=120),
        ),
        migrations.AddField(
            model_name="order", name="delivery_phone",
            field=models.CharField(blank=True, default="", max_length=40),
        ),
        migrations.AddField(
            model_name="order", name="preferred_delivery_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="order", name="delivery_notes",
            field=models.TextField(blank=True, default=""),
        ),
    ]
