from django.conf import settings
from django.db import migrations, models
import apps.products.models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("products", "0006_alter_product_owner")]
    operations = [
        migrations.CreateModel(
            name="ProductAttachment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("file", models.FileField(storage=apps.products.models.private_upload_storage, upload_to=apps.products.models.product_attachment_path)),
                ("original_name", models.CharField(max_length=255)),
                ("content_type", models.CharField(max_length=120)),
                ("size", models.PositiveBigIntegerField()),
                ("uploaded_at", models.DateTimeField(auto_now_add=True)),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="attachments", to="products.product")),
            ], options={"ordering": ["uploaded_at"]},
        ),
    ]
