from datetime import timedelta

from django.db import migrations, models
from django.db.models import F, Q


def backfill_pending_razorpay_expiry(apps, schema_editor):
    Contribution = apps.get_model("schemes", "Contribution")
    Contribution.objects.filter(
        payment_gateway="razorpay",
        status="PENDING",
        checkout_expires_at__isnull=True,
    ).update(checkout_expires_at=F("created_at") + timedelta(minutes=10))


class Migration(migrations.Migration):
    dependencies = [
        ("schemes", "0016_graded_rate_precision_labels"),
    ]

    operations = [
        migrations.AddField(
            model_name="contribution",
            name="checkout_expires_at",
            field=models.DateTimeField(
                blank=True,
                help_text=(
                    "Application deadline for opening or resuming this Razorpay "
                    "Checkout. It does not cancel the provider order or reject a "
                    "captured payment."
                ),
                null=True,
            ),
        ),
        migrations.RunPython(
            backfill_pending_razorpay_expiry,
            migrations.RunPython.noop,
        ),
        migrations.AddConstraint(
            model_name="contribution",
            constraint=models.CheckConstraint(
                condition=(
                    ~Q(payment_gateway="razorpay", status="PENDING")
                    | Q(checkout_expires_at__isnull=False)
                ),
                name="pending_rzp_checkout_expiry",
            ),
        ),
        migrations.AddIndex(
            model_name="contribution",
            index=models.Index(
                fields=["status", "checkout_expires_at"],
                name="contrib_status_expiry_idx",
            ),
        ),
    ]
