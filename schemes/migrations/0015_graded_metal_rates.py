from decimal import Decimal

from django.db import migrations, models
import django.db.models.deletion


def seed_and_backfill_grades(apps, schema_editor):
    MetalGrade = apps.get_model("schemes", "MetalGrade")
    MetalAllocation = apps.get_model("schemes", "MetalAllocation")
    Redemption = apps.get_model("schemes", "Redemption")
    SchemeAccount = apps.get_model("schemes", "SchemeAccount")
    SchemePlan = apps.get_model("schemes", "SchemePlan")
    SchemePlanOffering = apps.get_model("schemes", "SchemePlanOffering")
    SchemeRate = apps.get_model("schemes", "SchemeRate")

    gold_22, _ = MetalGrade.objects.get_or_create(
        code="GOLD_22K_916",
        defaults={
            "metal": "GOLD",
            "display_name": "22K Gold",
            "fineness": Decimal("0.916000"),
            "display_order": 10,
        },
    )
    gold_24, _ = MetalGrade.objects.get_or_create(
        code="GOLD_24K_9999",
        defaults={
            "metal": "GOLD",
            "display_name": "24K Gold",
            "fineness": Decimal("0.999900"),
            "display_order": 20,
        },
    )
    silver_999, _ = MetalGrade.objects.get_or_create(
        code="SILVER_999",
        defaults={
            "metal": "SILVER",
            "display_name": "999 Silver",
            "fineness": Decimal("0.999000"),
            "display_order": 30,
        },
    )

    # Historical GOLD meant 24K and historical SILVER meant 999 silver. Never
    # relabel or numerically convert those contracts, rates, or allocations.
    SchemeAccount.objects.filter(savings_mode="GOLD").update(metal_grade=gold_24)
    SchemeAccount.objects.filter(savings_mode="SILVER").update(metal_grade=silver_999)
    SchemeRate.objects.filter(metal="GOLD").update(metal_grade=gold_24)
    SchemeRate.objects.filter(metal="SILVER").update(metal_grade=silver_999)
    MetalAllocation.objects.filter(metal="GOLD").update(metal_grade=gold_24)
    MetalAllocation.objects.filter(metal="SILVER").update(metal_grade=silver_999)
    Redemption.objects.filter(gold_quantity__isnull=False).update(metal_grade=gold_24)
    Redemption.objects.filter(silver_quantity__isnull=False).update(
        metal_grade=silver_999
    )

    # New gold enrolment moves to 22K. Legacy 24K remains serviceable but is not
    # offered to new accounts unless an owner explicitly enables it later.
    for plan in SchemePlan.objects.all().iterator():
        SchemePlanOffering.objects.get_or_create(
            plan=plan,
            metal_grade=gold_22,
            defaults={"active": True},
        )
        SchemePlanOffering.objects.get_or_create(
            plan=plan,
            metal_grade=gold_24,
            defaults={"active": False},
        )
        SchemePlanOffering.objects.get_or_create(
            plan=plan,
            metal_grade=silver_999,
            defaults={"active": True},
        )

    if SchemeRate.objects.filter(metal_grade__isnull=True).exists():
        raise RuntimeError("Every Scheme Rate must map to a seeded metal grade.")
    if MetalAllocation.objects.filter(metal_grade__isnull=True).exists():
        raise RuntimeError("Every metal allocation must map to a seeded metal grade.")
    if SchemeAccount.objects.filter(
        savings_mode__in=["GOLD", "SILVER"], metal_grade__isnull=True
    ).exists():
        raise RuntimeError("Every metal scheme account must map to a seeded grade.")


class Migration(migrations.Migration):
    dependencies = [
        ("schemes", "0014_paymentwebhookevent_failure_code_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="MetalGrade",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("code", models.CharField(max_length=30, unique=True)),
                (
                    "metal",
                    models.CharField(
                        choices=[("GOLD", "Gold"), ("SILVER", "Silver")],
                        max_length=10,
                    ),
                ),
                ("display_name", models.CharField(max_length=80)),
                ("fineness", models.DecimalField(decimal_places=6, max_digits=7)),
                ("display_order", models.PositiveSmallIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ["display_order", "code"]},
        ),
        migrations.CreateModel(
            name="SchemePlanOffering",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "metal_grade",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="plan_offerings",
                        to="schemes.metalgrade",
                    ),
                ),
                (
                    "plan",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="metal_offerings",
                        to="schemes.schemeplan",
                    ),
                ),
            ],
            options={
                "ordering": [
                    "plan__name",
                    "metal_grade__display_order",
                    "metal_grade__code",
                ]
            },
        ),
        migrations.AddField(
            model_name="schemeaccount",
            name="metal_grade",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="scheme_accounts",
                to="schemes.metalgrade",
            ),
        ),
        migrations.AddField(
            model_name="schemerate",
            name="metal_grade",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="scheme_rates",
                to="schemes.metalgrade",
            ),
        ),
        migrations.AddField(
            model_name="metalallocation",
            name="metal_grade",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="metal_allocations",
                to="schemes.metalgrade",
            ),
        ),
        migrations.AddField(
            model_name="redemption",
            name="metal_grade",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="redemptions",
                to="schemes.metalgrade",
            ),
        ),
        migrations.RunPython(seed_and_backfill_grades, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="schemerate",
            name="metal_grade",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="scheme_rates",
                to="schemes.metalgrade",
            ),
        ),
        migrations.AlterField(
            model_name="metalallocation",
            name="metal_grade",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="metal_allocations",
                to="schemes.metalgrade",
            ),
        ),
        migrations.RemoveIndex(
            model_name="schemerate",
            name="scheme_rate_metal_time_idx",
        ),
        migrations.AddIndex(
            model_name="schemerate",
            index=models.Index(
                fields=["metal_grade", "effective_from"],
                name="scheme_rate_grade_time_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="metalgrade",
            constraint=models.CheckConstraint(
                condition=models.Q(("metal__in", ["GOLD", "SILVER"])),
                name="metal_grade_valid_metal",
            ),
        ),
        migrations.AddConstraint(
            model_name="metalgrade",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("fineness__gt", Decimal("0")),
                    ("fineness__lte", Decimal("1")),
                ),
                name="metal_grade_valid_fineness",
            ),
        ),
        migrations.AddConstraint(
            model_name="schemeplanoffering",
            constraint=models.UniqueConstraint(
                fields=("plan", "metal_grade"),
                name="plan_offering_unique_grade",
            ),
        ),
        migrations.AddConstraint(
            model_name="schemeaccount",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(("metal_grade__isnull", True), ("savings_mode", "CASH"))
                    | models.Q(
                        ("metal_grade__isnull", False),
                        ("savings_mode__in", ["GOLD", "SILVER"]),
                    )
                ),
                name="account_metal_grade_required",
            ),
        ),
        migrations.AddConstraint(
            model_name="redemption",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(("cash_amount__isnull", False), ("metal_grade__isnull", True))
                    | models.Q(("cash_amount__isnull", True), ("metal_grade__isnull", False))
                ),
                name="redemption_metal_grade_required",
            ),
        ),
    ]
