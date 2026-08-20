from decimal import Decimal

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


def backfill_locked_scheme_rates(apps, schema_editor):
    Contribution = apps.get_model("schemes", "Contribution")
    MetalAllocation = apps.get_model("schemes", "MetalAllocation")
    SchemeRate = apps.get_model("schemes", "SchemeRate")

    SchemeRate.objects.filter(notes="").update(
        notes="Historical rate migrated from the former provider-backed architecture."
    )
    for allocation in MetalAllocation.objects.select_related(
        "contribution", "scheme_rate"
    ).iterator():
        Contribution.objects.filter(pk=allocation.contribution_id).update(
            scheme_rate_id=allocation.scheme_rate_id,
            # The legacy architecture selected its rate during allocation rather than
            # at contribution creation. The former fetched_at value (now published_at)
            # is therefore the closest truthful timestamp for the historical lock.
            rate_locked_at=allocation.scheme_rate.published_at,
        )

    verified_without_allocation = Contribution.objects.filter(
        status__in=["PAID", "PAID_UNALLOCATED"],
        scheme_account__savings_mode__in=["GOLD", "SILVER"],
        metal_allocation__isnull=True,
    ).count()
    open_legacy_orders = Contribution.objects.filter(
        status="PENDING",
        payment_gateway="razorpay",
        gateway_order_id__isnull=False,
        scheme_rate__isnull=True,
        scheme_account__savings_mode__in=["GOLD", "SILVER"],
    ).count()
    if verified_without_allocation or open_legacy_orders:
        raise RuntimeError(
            "Manual Scheme Rate migration blocked: reconcile legacy metal records "
            "before deployment "
            f"(verified_metal_without_allocation={verified_without_allocation}, "
            f"open_razorpay_orders={open_legacy_orders})."
        )


class Migration(migrations.Migration):
    dependencies = [
        ("schemes", "0009_schemeplan_publicly_listed"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="ratesnapshot",
            name="rate_snapshot_valid_metal",
        ),
        migrations.RemoveConstraint(
            model_name="ratesnapshot",
            name="provider_rate_positive",
        ),
        migrations.RemoveConstraint(
            model_name="ratesnapshot",
            name="applied_rate_positive",
        ),
        migrations.RemoveConstraint(
            model_name="ratesnapshot",
            name="rate_snapshot_valid_purity",
        ),
        migrations.RenameModel(
            old_name="RateSnapshot",
            new_name="SchemeRate",
        ),
        migrations.RenameField(
            model_name="schemerate",
            old_name="applied_rate",
            new_name="rate_per_gram",
        ),
        migrations.RenameField(
            model_name="schemerate",
            old_name="provider_timestamp",
            new_name="effective_from",
        ),
        migrations.AlterField(
            model_name="schemerate",
            name="effective_from",
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
        migrations.RenameField(
            model_name="schemerate",
            old_name="fetched_at",
            new_name="published_at",
        ),
        migrations.RenameField(
            model_name="metalallocation",
            old_name="rate_snapshot",
            new_name="scheme_rate",
        ),
        migrations.RenameField(
            model_name="auditevent",
            old_name="rate_snapshot",
            new_name="scheme_rate",
        ),
        migrations.RemoveField(
            model_name="schemerate",
            name="provider",
        ),
        migrations.RemoveField(
            model_name="schemerate",
            name="provider_rate",
        ),
        migrations.AddField(
            model_name="schemerate",
            name="notes",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="schemerate",
            name="published_by",
            field=models.ForeignKey(
                blank=True,
                help_text=(
                    "Null only for rate history migrated from the former provider "
                    "architecture."
                ),
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="published_scheme_rates",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="contribution",
            name="rate_locked_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="contribution",
            name="scheme_rate",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="locked_contributions",
                to="schemes.schemerate",
            ),
        ),
        migrations.AddConstraint(
            model_name="contribution",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(scheme_rate__isnull=True, rate_locked_at__isnull=True)
                    | models.Q(scheme_rate__isnull=False, rate_locked_at__isnull=False)
                ),
                name="contribution_scheme_rate_lock_complete",
            ),
        ),
        migrations.AlterField(
            model_name="metalallocation",
            name="scheme_rate",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="metal_allocations",
                to="schemes.schemerate",
            ),
        ),
        migrations.AlterField(
            model_name="auditevent",
            name="action",
            field=models.CharField(
                choices=[
                    ("CUSTOMER_ENROLMENT", "Customer enrolment"),
                    ("SCHEME_CHANGE", "Scheme change"),
                    ("MANUAL_PAYMENT_CORRECTION", "Manual payment correction"),
                    ("SCHEME_RATE_PUBLICATION", "Scheme rate publication"),
                    ("REDEMPTION", "Redemption"),
                    ("REVERSAL", "Reversal"),
                    ("ALLOCATION_RETRY", "Allocation retry"),
                ],
                max_length=40,
            ),
        ),
        migrations.AlterModelOptions(
            name="schemerate",
            options={"ordering": ["-effective_from", "-published_at", "-pk"]},
        ),
        migrations.AddConstraint(
            model_name="schemerate",
            constraint=models.CheckConstraint(
                condition=models.Q(metal__in=["GOLD", "SILVER"]),
                name="scheme_rate_valid_metal",
            ),
        ),
        migrations.AddConstraint(
            model_name="schemerate",
            constraint=models.CheckConstraint(
                condition=models.Q(rate_per_gram__gt=Decimal("0")),
                name="scheme_rate_positive",
            ),
        ),
        migrations.AddConstraint(
            model_name="schemerate",
            constraint=models.CheckConstraint(
                condition=models.Q(purity__gt=Decimal("0"), purity__lte=Decimal("1")),
                name="scheme_rate_valid_purity",
            ),
        ),
        migrations.AddIndex(
            model_name="schemerate",
            index=models.Index(
                fields=["metal", "effective_from"],
                name="scheme_rate_metal_time_idx",
            ),
        ),
        migrations.RunPython(backfill_locked_scheme_rates, migrations.RunPython.noop),
    ]
