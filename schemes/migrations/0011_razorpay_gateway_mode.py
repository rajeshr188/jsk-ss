from django.db import migrations, models


def backfill_test_mode(apps, schema_editor):
    Contribution = apps.get_model("schemes", "Contribution")
    PaymentWebhookEvent = apps.get_model("schemes", "PaymentWebhookEvent")
    Contribution.objects.filter(payment_gateway="razorpay").update(
        gateway_mode="test"
    )
    PaymentWebhookEvent.objects.filter(gateway="razorpay").update(
        gateway_mode="test"
    )


class Migration(migrations.Migration):
    dependencies = [
        ("schemes", "0010_manual_scheme_rates"),
    ]

    operations = [
        migrations.AddField(
            model_name="contribution",
            name="gateway_mode",
            field=models.CharField(
                blank=True,
                choices=[("test", "Test"), ("live", "Live")],
                help_text="Razorpay environment used to create the provider order.",
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name="paymentwebhookevent",
            name="gateway_mode",
            field=models.CharField(
                blank=True,
                choices=[("test", "Test"), ("live", "Live")],
                help_text="Provider environment that delivered the event.",
                max_length=10,
            ),
        ),
        migrations.RunPython(backfill_test_mode, migrations.RunPython.noop),
        migrations.RemoveConstraint(
            model_name="paymentwebhookevent",
            name="unique_gateway_webhook_event",
        ),
        migrations.AddConstraint(
            model_name="contribution",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(
                        payment_gateway="razorpay",
                        gateway_mode__in=["test", "live"],
                    )
                    | (
                        ~models.Q(payment_gateway="razorpay")
                        & models.Q(gateway_mode="")
                    )
                ),
                name="contribution_razorpay_mode_valid",
            ),
        ),
        migrations.AddConstraint(
            model_name="paymentwebhookevent",
            constraint=models.UniqueConstraint(
                fields=("gateway", "gateway_mode", "event_id"),
                name="unique_gateway_webhook_event",
            ),
        ),
        migrations.AddConstraint(
            model_name="paymentwebhookevent",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(
                        gateway="razorpay",
                        gateway_mode__in=["test", "live"],
                    )
                    | (~models.Q(gateway="razorpay") & models.Q(gateway_mode=""))
                ),
                name="webhook_razorpay_mode_valid",
            ),
        ),
    ]
