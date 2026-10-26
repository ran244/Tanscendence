from django.core.validators import RegexValidator
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0002_customuser_avatar_customuser_bio_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="customuser",
            name="phone_number",
            field=models.CharField(
                blank=True,
                max_length=20,
                validators=[
                    RegexValidator(
                        message="Enter digits only, optionally beginning with +.",
                        regex=r"^\+?[0-9]+$",
                    )
                ],
            ),
        ),
    ]
