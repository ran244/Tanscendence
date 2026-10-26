from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("auctions", "0006_alter_auctioncancellationrequest_requester_and_more")]

    operations = [
        migrations.AddField(
            model_name="auctionevent",
            name="revision_number",
            field=models.PositiveIntegerField(default=1),
        ),
        migrations.AddField(
            model_name="auctionevent",
            name="revision_of",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="revisions",
                to="auctions.auctionevent",
            ),
        ),
        migrations.AlterField(
            model_name="auctionevent",
            name="status",
            field=models.CharField(
                choices=[
                    ("DRAFT", "Draft"),
                    ("PENDING_APPROVAL", "Pending approval"),
                    ("REJECTED", "Rejected"),
                    ("APPROVED", "Approved"),
                    ("SCHEDULED", "Scheduled"),
                    ("ACTIVE", "Active"),
                    ("ENDED", "Ended"),
                    ("CANCELLED", "Cancelled"),
                    ("SUPERSEDED", "Superseded"),
                ],
                default="DRAFT",
                max_length=20,
            ),
        ),
    ]
