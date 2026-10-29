import uuid

import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("schemes", "0021_plan_agreement_governance"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="SchemePlanConfiguration",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("family_id", models.UUIDField(default=uuid.uuid4, editable=False)),
                ("version", models.PositiveIntegerField(default=1, editable=False)),
                ("name", models.CharField(max_length=120)),
                ("amount_policy", models.CharField(max_length=20, choices=[("PLAN_FIXED", "Amount fixed by the showroom"), ("CUSTOMER_FIXED", "Customer chooses once at enrolment"), ("VARIABLE", "Variable amount within limits")])),
                ("minimum_amount", models.DecimalField(max_digits=14, decimal_places=2)),
                ("maximum_amount", models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)),
                ("fixed_amount", models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)),
                ("amount_step", models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True, help_text="Optional increment from the minimum, e.g. minimum 500 and step 100 permits 500, 600, 700.")),
                ("frequency_rule", models.CharField(max_length=20, choices=[("ONCE_PER_MONTH", "At most once per calendar month"), ("FLEXIBLE", "Flexible frequency")])),
                ("minimum_months", models.PositiveSmallIntegerField(default=12, validators=[django.core.validators.MinValueValidator(12)])),
                ("default_months", models.PositiveSmallIntegerField(default=12, validators=[django.core.validators.MinValueValidator(12)])),
                ("allow_contributions_after_eligibility", models.BooleanField(default=False)),
                ("accumulation", models.CharField(max_length=20, default="EXACT_METAL", choices=[("EXACT_METAL", "One exact metal grade")])),
                ("instalment_policy", models.CharField(max_length=20, default="NONE", choices=[("NONE", "No mandatory instalments")])),
                ("eligibility_policy", models.CharField(max_length=20, default="CALENDAR", choices=[("CALENDAR", "Agreed calendar duration")])),
                ("missed_payment_policy", models.CharField(max_length=20, default="NONE", choices=[("NONE", "No mandatory-payment penalty")])),
                ("benefit_policy", models.CharField(max_length=20, default="NONE", choices=[("NONE", "No bonus or discount")])),
                ("settlement_policy", models.CharField(max_length=20, default="FULL_ONLY", choices=[("FULL_ONLY", "Full jewellery settlement and agreement closure")])),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("actor_label", models.CharField(max_length=254)),
                ("reason", models.TextField()),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ("previous", models.OneToOneField(null=True, blank=True, on_delete=django.db.models.deletion.PROTECT, related_name="successor", to="schemes.schemeplanconfiguration")),
            ],
            options={"ordering": ["name", "-version"]},
        ),
        migrations.AddField(
            model_name="schemeplan", name="configuration",
            field=models.ForeignKey(null=True, blank=True, on_delete=django.db.models.deletion.PROTECT, related_name="plans", to="schemes.schemeplanconfiguration"),
        ),
        migrations.AddConstraint(model_name="schemeplan", constraint=models.CheckConstraint(condition=models.Q(configuration__isnull=True) | models.Q(active=False, publicly_listed=False), name="configured_plan_preparation_only")),
        migrations.AddConstraint(model_name="schemeplanconfiguration", constraint=models.UniqueConstraint(fields=["family_id", "version"], name="plan_config_family_version_unique")),
        migrations.AddConstraint(model_name="schemeplanconfiguration", constraint=models.CheckConstraint(condition=models.Q(version=1, previous__isnull=True) | models.Q(version__gt=1, previous__isnull=False), name="plan_config_version_shape")),
        migrations.AddConstraint(model_name="schemeplanconfiguration", constraint=models.CheckConstraint(condition=models.Q(minimum_amount__gt=0), name="plan_config_min_positive")),
        migrations.AddConstraint(model_name="schemeplanconfiguration", constraint=models.CheckConstraint(condition=models.Q(maximum_amount__isnull=True) | models.Q(maximum_amount__gte=models.F("minimum_amount")), name="plan_config_max_gte_min")),
        migrations.AddConstraint(model_name="schemeplanconfiguration", constraint=models.CheckConstraint(condition=models.Q(amount_step__isnull=True) | models.Q(amount_step__gt=0), name="plan_config_step_positive")),
        migrations.AddConstraint(model_name="schemeplanconfiguration", constraint=models.CheckConstraint(condition=(
            models.Q(amount_policy="PLAN_FIXED", fixed_amount__isnull=False, fixed_amount__gt=0, minimum_amount=models.F("fixed_amount"), maximum_amount=models.F("fixed_amount"), maximum_amount__isnull=False, amount_step__isnull=True)
            | models.Q(amount_policy__in=["CUSTOMER_FIXED", "VARIABLE"], fixed_amount__isnull=True)
        ), name="plan_config_amount_shape")),
        migrations.AddConstraint(model_name="schemeplanconfiguration", constraint=models.CheckConstraint(condition=models.Q(minimum_months__gte=12, default_months__gte=models.F("minimum_months")), name="plan_config_calendar_duration")),
        migrations.AddConstraint(model_name="schemeplanconfiguration", constraint=models.CheckConstraint(condition=models.Q(accumulation="EXACT_METAL", instalment_policy="NONE", eligibility_policy="CALENDAR", missed_payment_policy="NONE", benefit_policy="NONE", settlement_policy="FULL_ONLY", frequency_rule__in=["ONCE_PER_MONTH", "FLEXIBLE"]), name="plan_config_initial_family_only")),
        migrations.AddConstraint(model_name="schemeplanconfiguration", constraint=models.CheckConstraint(condition=~models.Q(actor_label="") & ~models.Q(reason=""), name="plan_config_evidence_required")),
    ]
