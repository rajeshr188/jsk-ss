from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def preserve_system_receipts(apps, schema_editor):
    receipt = apps.get_model("schemes", "InrPrincipalReceipt")
    if receipt.objects.using(schema_editor.connection.alias).filter(recorded_by__isnull=True).exists():
        raise RuntimeError("Cannot reverse 0041 with system-recorded INR principal; use compatible forward recovery.")


class Migration(migrations.Migration):
    dependencies = [("schemes", "0040_independent_agreement_storage"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.AlterField(model_name="inrprincipalreceipt", name="recorded_by",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                                    to=settings.AUTH_USER_MODEL)),
        migrations.AddConstraint(model_name="inrprincipalreceipt", constraint=models.CheckConstraint(
            condition=(models.Q(recorded_by__isnull=False) | models.Q(cash_receipt__isnull=True,
                webhook_event__isnull=False, actor_label="system:razorpay-capture")),
            name="inr_principal_actor_shape")),
        migrations.RunPython(migrations.RunPython.noop, preserve_system_receipts),
    ]
