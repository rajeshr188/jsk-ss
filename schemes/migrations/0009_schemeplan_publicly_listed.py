from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("schemes", "0008_auditevent_redemptionreversal"),
    ]

    operations = [
        migrations.AddField(
            model_name="schemeplan",
            name="publicly_listed",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Show this plan on the public plans and pricing page when it is active."
                ),
            ),
        ),
    ]
