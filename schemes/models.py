import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models, transaction
from django.utils import timezone

from .eligibility import is_redemption_eligible

from .bonuses import CASH_BONUS_POLICY_VERSION


class Customer(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="customer_profile",
    )
    customer_number = models.CharField(max_length=20, unique=True)
    full_name = models.CharField(max_length=200)
    mobile_number = models.CharField(max_length=20)
    email = models.EmailField(unique=True)
    address = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["full_name", "customer_number"]

    def __str__(self):
        return f"{self.customer_number} — {self.full_name}"

    def save(self, *args, **kwargs):
        with transaction.atomic():
            stored = type(self).objects.select_for_update().filter(pk=self.pk).first() if self.pk else None
            if stored is not None and stored.user.privacy_erased_at:
                raise ValidationError("A removed customer's profile requires the privacy workflow, not ordinary editing.")
            return super().save(*args, **kwargs)


class MetalGrade(models.Model):
    class Metal(models.TextChoices):
        GOLD = "GOLD", "Gold"
        SILVER = "SILVER", "Silver"

    GOLD_22K_916 = "GOLD_22K_916"
    GOLD_24K_9999 = "GOLD_24K_9999"
    SILVER_999 = "SILVER_999"

    code = models.CharField(max_length=30, unique=True)
    metal = models.CharField(max_length=10, choices=Metal.choices)
    display_name = models.CharField(max_length=80)
    fineness = models.DecimalField(max_digits=7, decimal_places=6)
    display_order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["display_order", "code"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(metal__in=["GOLD", "SILVER"]),
                name="metal_grade_valid_metal",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    fineness__gt=Decimal("0"),
                    fineness__lte=Decimal("1"),
                ),
                name="metal_grade_valid_fineness",
            ),
        ]

    def clean(self):
        super().clean()
        if not self.pk:
            return
        stored = type(self).objects.filter(pk=self.pk).first()
        if stored is None:
            return
        immutable_fields = ("code", "metal", "display_name", "fineness")
        if any(getattr(stored, field) != getattr(self, field) for field in immutable_fields):
            raise ValidationError("Financial metal-grade definitions are immutable.")

    def delete(self, *args, **kwargs):
        raise ValidationError("Financial metal-grade definitions cannot be deleted.")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.display_name


class SchemePlanConfiguration(models.Model):
    """Immutable typed policy versions. Preparation-only until the full journey ships."""

    class AmountPolicy(models.TextChoices):
        PLAN_FIXED = "PLAN_FIXED", "Amount fixed by the showroom"
        CUSTOMER_FIXED = "CUSTOMER_FIXED", "Customer chooses once at enrolment"
        VARIABLE = "VARIABLE", "Variable amount within limits"

    family_id = models.UUIDField(default=uuid.uuid4, editable=False)
    version = models.PositiveIntegerField(default=1, editable=False)
    policy_schema_version = models.PositiveSmallIntegerField(default=1, editable=False)
    previous = models.OneToOneField(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="successor",
    )
    name = models.CharField(max_length=120)
    amount_policy = models.CharField(max_length=20, choices=AmountPolicy.choices)
    minimum_amount = models.DecimalField(max_digits=14, decimal_places=2)
    maximum_amount = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    fixed_amount = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    amount_step = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        help_text="Optional increment from the minimum, e.g. minimum 500 and step 100 permits 500, 600, 700.",
    )
    frequency_rule = models.CharField(max_length=20, choices=[
        ("ONCE_PER_MONTH", "At most once per calendar month"), ("FLEXIBLE", "Flexible frequency"),
        ("ONCE_PER_PERIOD", "At most one qualifying contribution per selected monthly period"),
    ])
    minimum_months = models.PositiveSmallIntegerField(default=12, null=True, blank=True, validators=[MinValueValidator(12)])
    default_months = models.PositiveSmallIntegerField(default=12, null=True, blank=True, validators=[MinValueValidator(12)])
    duration_months = models.PositiveSmallIntegerField(null=True, blank=True, validators=[MinValueValidator(1)])
    required_count = models.PositiveSmallIntegerField(null=True, blank=True, validators=[MinValueValidator(1)])
    allow_contributions_after_eligibility = models.BooleanField(default=False)
    # Explicit typed dimensions; persisted compatibility is distinct from runtime support.
    accumulation = models.CharField(max_length=20, default="EXACT_METAL", choices=[("EXACT_METAL", "One exact metal grade"), ("INR_PURCHASE_CREDIT", "INR jewellery purchase credit")])
    instalment_policy = models.CharField(max_length=20, default="NONE", choices=[("NONE", "No mandatory instalments"), ("MONTHLY_COMPLETION", "Required monthly completion")])
    eligibility_policy = models.CharField(max_length=20, default="CALENDAR", choices=[("CALENDAR", "Agreed calendar duration"), ("CALENDAR_AND_COUNT", "Calendar duration and qualifying instalments"), ("COUNT", "Qualifying instalment count only"), ("ANYTIME", "Anytime full settlement")])
    missed_payment_policy = models.CharField(max_length=32, default="NONE", choices=[("NONE", "No mandatory-payment penalty"), ("EXTEND_THEN_REVIEW", "Extend, then discontinuation review"), ("LOSE_UNEARNED_BENEFIT", "Loss of specified unearned benefit")])
    period_basis = models.CharField(max_length=20, null=True, blank=True, choices=[("ANNIVERSARY", "Agreement-anniversary month (India time)"), ("CALENDAR_MONTH", "Calendar month, including enrolment month (India time)")])
    grace_days = models.PositiveSmallIntegerField(null=True, blank=True)
    catch_up_policy = models.CharField(max_length=20, null=True, blank=True, choices=[("NONE", "No bulk catch-up or advance instalments")])
    max_extension_months = models.PositiveSmallIntegerField(null=True, blank=True)
    benefit_policy = models.CharField(max_length=20, default="NONE", choices=[("NONE", "No bonus or discount"), ("INR_PURCHASE_BONUS", "INR jewellery purchase bonus"), ("VA_DISCOUNT", "Value-addition discount")])
    benefit_percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    benefit_cap_inr = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    benefit_qualification = models.CharField(max_length=24, default="NONE", choices=[("NONE", "No benefit"), ("NORMAL_ELIGIBILITY", "Normal eligibility"), ("REQUIRED_SCHEDULE", "Required schedule")])
    benefit_on_miss = models.CharField(max_length=24, default="NONE", choices=[("NONE", "No benefit consequence"), ("PRESERVE_ON_COMPLETION", "Preserve on extended completion"), ("DISQUALIFY_UNEARNED", "Disqualify unearned benefit")])
    eligible_charge_definition = models.TextField(blank=True, default="")
    settlement_policy = models.CharField(max_length=20, default="FULL_ONLY", choices=[("FULL_ONLY", "Full jewellery settlement and agreement closure")])
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    actor_label = models.CharField(max_length=254)
    reason = models.TextField()

    class Meta:
        ordering = ["name", "-version"]
        constraints = [
            models.UniqueConstraint(fields=["family_id", "version"], name="plan_config_family_version_unique"),
            models.CheckConstraint(condition=(models.Q(version=1, previous__isnull=True) | models.Q(version__gt=1, previous__isnull=False)), name="plan_config_version_shape"),
            models.CheckConstraint(condition=models.Q(minimum_amount__gt=0), name="plan_config_min_positive"),
            models.CheckConstraint(condition=(models.Q(maximum_amount__isnull=True) | models.Q(maximum_amount__gte=models.F("minimum_amount"))), name="plan_config_max_gte_min"),
            models.CheckConstraint(condition=(models.Q(amount_step__isnull=True) | models.Q(amount_step__gt=0)), name="plan_config_step_positive"),
            models.CheckConstraint(condition=(
                models.Q(amount_policy="PLAN_FIXED", fixed_amount__isnull=False, fixed_amount__gt=0, minimum_amount=models.F("fixed_amount"), maximum_amount=models.F("fixed_amount"), maximum_amount__isnull=False, amount_step__isnull=True)
                | models.Q(amount_policy__in=["CUSTOMER_FIXED", "VARIABLE"], fixed_amount__isnull=True)
            ), name="plan_config_amount_shape"),
            models.CheckConstraint(condition=(
                models.Q(policy_schema_version=1, minimum_months__isnull=False, default_months__isnull=False,
                         minimum_months__gte=12, default_months__gte=models.F("minimum_months"),
                         duration_months__isnull=True, required_count__isnull=True,
                         benefit_percentage__isnull=True, benefit_cap_inr__isnull=True,
                         benefit_qualification="NONE", benefit_on_miss="NONE", eligible_charge_definition="")
                | models.Q(policy_schema_version=2, minimum_months__isnull=True, default_months__isnull=True)
            ), name="plan_config_schema_shape"),
            models.CheckConstraint(condition=(
                models.Q(policy_schema_version=1, accumulation="EXACT_METAL", benefit_policy="NONE", settlement_policy="FULL_ONLY")
                & (
                    models.Q(instalment_policy="NONE", eligibility_policy="CALENDAR", missed_payment_policy="NONE",
                             frequency_rule__in=["ONCE_PER_MONTH", "FLEXIBLE"], period_basis__isnull=True,
                             grace_days__isnull=True, catch_up_policy__isnull=True, max_extension_months__isnull=True)
                    | models.Q(instalment_policy="MONTHLY_COMPLETION", eligibility_policy="CALENDAR_AND_COUNT",
                               missed_payment_policy="EXTEND_THEN_REVIEW", amount_policy="CUSTOMER_FIXED",
                               frequency_rule="ONCE_PER_PERIOD", allow_contributions_after_eligibility=False,
                               period_basis__in=["ANNIVERSARY", "CALENDAR_MONTH"], period_basis__isnull=False,
                               grace_days=0, grace_days__isnull=False, catch_up_policy="NONE", catch_up_policy__isnull=False,
                               max_extension_months=3, max_extension_months__isnull=False)
                )
                | models.Q(policy_schema_version=2, accumulation__in=["EXACT_METAL", "INR_PURCHASE_CREDIT"],
                           settlement_policy="FULL_ONLY", grace_days=0, grace_days__isnull=False,
                           catch_up_policy="NONE", catch_up_policy__isnull=False)
            ), name="plan_config_supported_family"),
            models.CheckConstraint(condition=(
                models.Q(policy_schema_version=1)
                | ((models.Q(eligibility_policy__in=["CALENDAR", "CALENDAR_AND_COUNT"],
                             duration_months__isnull=False, duration_months__gte=1)
                    | models.Q(eligibility_policy__in=["COUNT", "ANYTIME"], duration_months__isnull=True))
                   & (models.Q(frequency_rule="FLEXIBLE", period_basis__isnull=True)
                      | models.Q(frequency_rule="ONCE_PER_PERIOD", period_basis__isnull=False,
                                 period_basis__in=["CALENDAR_MONTH", "ANNIVERSARY"])))
            ), name="plan_config_v2_period_duration"),
            models.CheckConstraint(condition=(
                models.Q(policy_schema_version=1)
                | models.Q(instalment_policy="NONE", eligibility_policy__in=["CALENDAR", "ANYTIME"],
                           required_count__isnull=True, missed_payment_policy="NONE",
                           max_extension_months__isnull=True, benefit_on_miss="NONE")
                | (models.Q(instalment_policy="MONTHLY_COMPLETION", amount_policy__in=["PLAN_FIXED", "CUSTOMER_FIXED"],
                            frequency_rule="ONCE_PER_PERIOD", required_count__isnull=False, required_count__gte=1)
                   & (models.Q(eligibility_policy__in=["COUNT", "CALENDAR_AND_COUNT"],
                               missed_payment_policy="EXTEND_THEN_REVIEW", max_extension_months=3,
                               max_extension_months__isnull=False, allow_contributions_after_eligibility=False)
                      | models.Q(eligibility_policy="CALENDAR", missed_payment_policy="LOSE_UNEARNED_BENEFIT",
                                 max_extension_months__isnull=True, benefit_policy__in=["INR_PURCHASE_BONUS", "VA_DISCOUNT"],
                                 benefit_on_miss="DISQUALIFY_UNEARNED")))
            ), name="plan_config_v2_obligations"),
            models.CheckConstraint(condition=(
                models.Q(policy_schema_version=1)
                | models.Q(benefit_policy="NONE", benefit_percentage__isnull=True, benefit_cap_inr__isnull=True,
                           benefit_qualification="NONE", benefit_on_miss="NONE", eligible_charge_definition="")
                | (models.Q(benefit_percentage__isnull=False, benefit_percentage__gt=0, benefit_percentage__lte=100,
                            benefit_cap_inr__isnull=False, benefit_cap_inr__gt=0)
                   & (models.Q(benefit_policy="INR_PURCHASE_BONUS", accumulation="INR_PURCHASE_CREDIT", eligible_charge_definition="")
                      | (models.Q(benefit_policy="VA_DISCOUNT") & ~models.Q(eligible_charge_definition="")))
                   & (models.Q(instalment_policy="NONE", benefit_qualification="NORMAL_ELIGIBILITY", benefit_on_miss="NONE")
                      | models.Q(instalment_policy="MONTHLY_COMPLETION", benefit_qualification="REQUIRED_SCHEDULE",
                                 benefit_on_miss__in=["PRESERVE_ON_COMPLETION", "DISQUALIFY_UNEARNED"])))
            ), name="plan_config_v2_benefits"),
            models.CheckConstraint(condition=models.Q(benefit_cap_inr__isnull=True) | models.Q(
                benefit_cap_inr__lte=Decimal("999999999999.99")
            ), name="plan_config_benefit_cap_finite"),
            models.CheckConstraint(condition=~models.Q(actor_label="") & ~models.Q(reason=""), name="plan_config_evidence_required"),
        ]

    def clean(self):
        super().clean()
        if self.policy_schema_version == 2:
            from .plan_policies import policy_from_configuration, validate_plan_policy

            validate_plan_policy(policy_from_configuration(self))
        if self.previous_id:
            previous = type(self).objects.get(pk=self.previous_id)
            if self.family_id != previous.family_id or self.version != previous.version + 1:
                raise ValidationError("A new version must immediately follow its previous family version.")
            if self.policy_schema_version < previous.policy_schema_version:
                raise ValidationError("A configuration cannot downgrade its policy schema.")

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("Configuration versions are immutable; create a new version.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Configuration versions cannot be deleted.")

    def __str__(self):
        return f"{self.name} / v{self.version}"


class SchemePlan(models.Model):
    class AmountRule(models.TextChoices):
        FIXED = "FIXED", "Fixed"
        VARIABLE = "VARIABLE", "Variable"

    class FrequencyRule(models.TextChoices):
        ONCE_PER_MONTH = "ONCE_PER_MONTH", "Once per month"
        FLEXIBLE = "FLEXIBLE", "Flexible"

    name = models.CharField(max_length=120)
    code = models.CharField(max_length=30, unique=True)
    description = models.TextField(blank=True)
    configuration = models.ForeignKey(
        SchemePlanConfiguration, null=True, blank=True, on_delete=models.PROTECT, related_name="plans",
    )
    publication_revision = models.ForeignKey(
        "SchemePlanRevision", null=True, blank=True, on_delete=models.PROTECT,
        related_name="published_plans", editable=False,
    )
    minimum_months = models.PositiveSmallIntegerField(
        default=12, validators=[MinValueValidator(12)]
    )
    default_months = models.PositiveSmallIntegerField(
        default=12, validators=[MinValueValidator(12)]
    )
    amount_rule = models.CharField(max_length=10, choices=AmountRule.choices)
    frequency_rule = models.CharField(max_length=20, choices=FrequencyRule.choices)
    fixed_contribution_amount = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True
    )
    minimum_contribution = models.DecimalField(max_digits=14, decimal_places=2)
    maximum_contribution = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True
    )
    allow_contributions_after_eligibility = models.BooleanField(default=False)
    cash_bonus_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[
            MinValueValidator(Decimal("0")),
            MaxValueValidator(Decimal("100")),
        ],
    )
    cash_bonus_minimum_months = models.PositiveSmallIntegerField(
        default=12,
        validators=[MinValueValidator(12)],
    )
    active = models.BooleanField(default=True)
    publicly_listed = models.BooleanField(
        default=False,
        help_text=(
            "Show this plan on the public plans and pricing page when it is active."
        ),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.CheckConstraint(
                condition=(models.Q(configuration__isnull=True)
                           | models.Q(active=False, publicly_listed=False)
                           | models.Q(active=True, publication_revision__isnull=False)),
                name="configured_plan_publication_required",
            ),
            models.CheckConstraint(
                condition=models.Q(minimum_months__gte=12),
                name="plan_minimum_months_gte_12",
            ),
            models.CheckConstraint(
                condition=models.Q(default_months__gte=models.F("minimum_months")),
                name="plan_default_months_gte_minimum",
            ),
            models.CheckConstraint(
                condition=models.Q(minimum_contribution__gt=0),
                name="plan_minimum_contribution_positive",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(maximum_contribution__isnull=True)
                    | models.Q(maximum_contribution__gte=models.F("minimum_contribution"))
                ),
                name="plan_maximum_gte_minimum",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(amount_rule="VARIABLE")
                    | models.Q(fixed_contribution_amount__gt=0)
                ),
                name="plan_fixed_amount_positive_when_fixed",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    cash_bonus_percentage__gte=Decimal("0"),
                    cash_bonus_percentage__lte=Decimal("100"),
                ),
                name="plan_cash_bonus_percentage_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(cash_bonus_minimum_months__gte=12),
                name="plan_cash_bonus_months_gte_12",
            ),
        ]

    def clean(self):
        errors = {}
        if self.configuration_id:
            from .plan_configuration import configuration_plan_values
            if self.active or self.publicly_listed:
                from .plan_publication import validate_publication_evidence
                try:
                    validate_publication_evidence(self)
                except ValidationError as error:
                    errors["active"] = error.messages
            for field, value in configuration_plan_values(self.configuration).items():
                if getattr(self, field) != value:
                    errors[field] = "This value is pinned to an immutable configuration version."
        if self.default_months < self.minimum_months:
            errors["default_months"] = "Default duration cannot be below the minimum."
        if self.amount_rule == self.AmountRule.FIXED:
            if not self.fixed_contribution_amount or self.fixed_contribution_amount <= 0:
                errors["fixed_contribution_amount"] = "A positive fixed amount is required."
            elif self.minimum_contribution != self.fixed_contribution_amount:
                errors["minimum_contribution"] = "For a fixed plan, minimum must equal fixed amount."
        elif self.fixed_contribution_amount is not None:
            errors["fixed_contribution_amount"] = "Variable plans must not define a fixed amount."
        if (
            self.maximum_contribution is not None
            and self.maximum_contribution < self.minimum_contribution
        ):
            errors["maximum_contribution"] = "Maximum cannot be below minimum."
        if (
            self.cash_bonus_percentage is not None
            and not 0 <= self.cash_bonus_percentage <= 100
        ):
            errors["cash_bonus_percentage"] = (
                "Cash bonus percentage must be between 0 and 100."
            )
        if (
            self.cash_bonus_minimum_months is not None
            and self.cash_bonus_minimum_months < 12
        ):
            errors["cash_bonus_minimum_months"] = (
                "Cash bonus qualifying duration must be at least 12 months."
            )
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.name} ({self.code})"


class SchemePlanRevision(models.Model):
    """Observed plan terms, not a replacement for a customer's agreement snapshot."""

    plan = models.ForeignKey(SchemePlan, on_delete=models.PROTECT, related_name="revisions")
    number = models.PositiveIntegerField()
    terms = models.JSONField()
    recorded_at = models.DateTimeField(auto_now_add=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True)
    actor_label = models.CharField(max_length=254)
    reason = models.TextField()

    class Meta:
        ordering = ["-number"]
        constraints = [
            models.UniqueConstraint(fields=["plan", "number"], name="plan_revision_number_unique"),
            models.CheckConstraint(condition=models.Q(number__gte=1), name="plan_revision_number_positive"),
            models.CheckConstraint(condition=~models.Q(actor_label="") & ~models.Q(reason=""), name="plan_revision_evidence_required"),
        ]

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("Plan revisions are immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Plan revisions are immutable.")

    def __str__(self):
        return f"{self.plan_id} / revision {self.number}"


class SchemePlanOffering(models.Model):
    plan = models.ForeignKey(
        SchemePlan,
        on_delete=models.PROTECT,
        related_name="metal_offerings",
    )
    metal_grade = models.ForeignKey(
        MetalGrade,
        on_delete=models.PROTECT,
        related_name="plan_offerings",
    )
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["plan__name", "metal_grade__display_order", "metal_grade__code"]
        constraints = [
            models.UniqueConstraint(
                fields=["plan", "metal_grade"],
                name="plan_offering_unique_grade",
            ),
        ]

    def __str__(self):
        return f"{self.plan.name} — {self.metal_grade.display_name}"


class SchemeAccount(models.Model):
    class SavingsMode(models.TextChoices):
        CASH = "CASH", "Cash Savings"
        INR_CREDIT = "INR_CREDIT", "INR jewellery purchase credit (not activated)"
        GOLD = "GOLD", "Gold Savings"
        SILVER = "SILVER", "Silver Savings"

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        REDEMPTION_ELIGIBLE = "REDEMPTION_ELIGIBLE", "Redemption eligible"
        REDEEMED = "REDEEMED", "Redeemed"
        CANCELLED = "CANCELLED", "Cancelled unused agreement"
        CLOSURE_PENDING = "CLOSURE_PENDING", "Closure accepted — settlement pending"

    scheme_number = models.CharField(max_length=24, unique=True)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="scheme_accounts")
    plan = models.ForeignKey(SchemePlan, on_delete=models.PROTECT, related_name="scheme_accounts")
    plan_name_snapshot = models.CharField(max_length=120, blank=True, default="")
    plan_code_snapshot = models.CharField(max_length=30, blank=True, default="")
    plan_revision = models.ForeignKey(
        SchemePlanRevision, on_delete=models.PROTECT, related_name="scheme_accounts",
        null=True, blank=True,
    )
    configuration_snapshot = models.ForeignKey(
        SchemePlanConfiguration, on_delete=models.PROTECT, related_name="agreements",
        null=True, blank=True,
    )
    contribution_step_snapshot = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    agreement_schema_version = models.PositiveSmallIntegerField(default=1, editable=False)
    eligibility_policy_snapshot = models.CharField(max_length=24, blank=True, default="", editable=False)
    required_count_snapshot = models.PositiveSmallIntegerField(null=True, blank=True, editable=False)
    start_date = models.DateField()
    agreed_months = models.PositiveSmallIntegerField(null=True, blank=True, validators=[MinValueValidator(1)])
    eligible_from = models.DateField(null=True, blank=True)
    savings_mode = models.CharField(max_length=10, choices=SavingsMode.choices)
    metal_grade = models.ForeignKey(
        MetalGrade,
        on_delete=models.PROTECT,
        related_name="scheme_accounts",
        null=True,
        blank=True,
    )
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.ACTIVE)
    amount_rule_snapshot = models.CharField(max_length=10, choices=SchemePlan.AmountRule.choices)
    frequency_rule_snapshot = models.CharField(
        max_length=20, choices=[*SchemePlan.FrequencyRule.choices, ("ONCE_PER_PERIOD", "Once per agreed period")]
    )
    fixed_amount_snapshot = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True
    )
    minimum_amount_snapshot = models.DecimalField(max_digits=14, decimal_places=2)
    maximum_amount_snapshot = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True
    )
    allow_post_eligibility_contributions_snapshot = models.BooleanField(default=False)
    cash_bonus_policy_version_snapshot = models.CharField(
        max_length=30,
        default=CASH_BONUS_POLICY_VERSION,
    )
    cash_bonus_percentage_snapshot = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    cash_bonus_minimum_months_snapshot = models.PositiveSmallIntegerField(default=12)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-start_date", "scheme_number"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(agreement_schema_version=1, agreed_months__isnull=False, agreed_months__gte=12,
                             eligible_from__isnull=False, eligibility_policy_snapshot="", required_count_snapshot__isnull=True)
                    | (models.Q(agreement_schema_version=2, configuration_snapshot__isnull=False, plan_revision__isnull=False)
                       & (models.Q(eligibility_policy_snapshot="DURATION", agreed_months__isnull=False,
                                   agreed_months__gte=1, eligible_from__isnull=False)
                          | models.Q(eligibility_policy_snapshot="DURATION_AND_COUNT", agreed_months__isnull=False,
                                     agreed_months__gte=1, eligible_from__isnull=False, required_count_snapshot__isnull=False)
                          | models.Q(eligibility_policy_snapshot="COUNT", agreed_months__isnull=True,
                                     eligible_from__isnull=True, required_count_snapshot__isnull=False)
                          | models.Q(eligibility_policy_snapshot="ANYTIME", agreed_months__isnull=True,
                                     eligible_from__isnull=True, required_count_snapshot__isnull=True)))
                ), name="account_eligibility_shape",
            ),
            models.CheckConstraint(condition=models.Q(required_count_snapshot__isnull=True) | models.Q(
                required_count_snapshot__gte=1), name="account_required_count_positive"),
            models.CheckConstraint(condition=models.Q(agreement_schema_version=2,
                frequency_rule_snapshot__in=["FLEXIBLE", "ONCE_PER_PERIOD"]) | models.Q(agreement_schema_version=1,
                frequency_rule_snapshot__in=["FLEXIBLE", "ONCE_PER_MONTH"]), name="account_frequency_shape"),
            models.CheckConstraint(
                condition=models.Q(minimum_amount_snapshot__gt=Decimal("0")),
                name="account_minimum_amount_positive",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(maximum_amount_snapshot__isnull=True)
                    | models.Q(maximum_amount_snapshot__gte=models.F("minimum_amount_snapshot"))
                ),
                name="account_maximum_gte_minimum",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    cash_bonus_percentage_snapshot__gte=Decimal("0"),
                    cash_bonus_percentage_snapshot__lte=Decimal("100"),
                ),
                name="account_cash_bonus_percentage_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(cash_bonus_minimum_months_snapshot__gte=12),
                name="account_cash_bonus_months_gte_12",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(savings_mode__in=["CASH", "INR_CREDIT"], metal_grade__isnull=True)
                    | models.Q(
                        savings_mode__in=["GOLD", "SILVER"],
                        metal_grade__isnull=False,
                    )
                ),
                name="account_metal_grade_required",
            ),
            models.CheckConstraint(
                condition=(models.Q(plan_revision__isnull=True)
                           | (~models.Q(plan_name_snapshot="") & ~models.Q(plan_code_snapshot=""))),
                name="account_revision_identity_required",
            ),
            models.CheckConstraint(condition=(
                models.Q(configuration_snapshot__isnull=True, contribution_step_snapshot__isnull=True)
                | (models.Q(configuration_snapshot__isnull=False, plan_revision__isnull=False,
                            savings_mode__in=["GOLD", "SILVER", "INR_CREDIT"], cash_bonus_percentage_snapshot=0)
                   & (models.Q(contribution_step_snapshot__isnull=True) | models.Q(contribution_step_snapshot__gt=0))
                   & (models.Q(amount_rule_snapshot="VARIABLE", fixed_amount_snapshot__isnull=True)
                      | models.Q(amount_rule_snapshot="FIXED", fixed_amount_snapshot__isnull=False,
                                 fixed_amount_snapshot__gt=0, minimum_amount_snapshot=models.F("fixed_amount_snapshot"),
                                 maximum_amount_snapshot=models.F("fixed_amount_snapshot"), maximum_amount_snapshot__isnull=False,
                                 contribution_step_snapshot__isnull=True)))
            ), name="account_configuration_shape"),
            models.CheckConstraint(condition=(~models.Q(savings_mode="INR_CREDIT") | models.Q(
                configuration_snapshot__isnull=False, plan_revision__isnull=False,
                metal_grade__isnull=True, cash_bonus_percentage_snapshot=0,
            )), name="account_inr_credit_contract"),
            models.CheckConstraint(
                condition=~models.Q(status="CANCELLED") | models.Q(configuration_snapshot__isnull=False),
                name="cancelled_account_configured",
            ),
            models.CheckConstraint(
                condition=~models.Q(status="CLOSURE_PENDING") | models.Q(configuration_snapshot__isnull=False),
                name="pending_closure_configured",
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}
        from .plan_configuration import validate_agreement_configuration
        if self.configuration_snapshot_id:
            from .plan_policies import require_operational_configuration
            require_operational_configuration(self.configuration_snapshot)
        validate_agreement_configuration(self)
        if self.plan_revision_id and self.plan_revision.plan_id != self.plan_id:
            errors["plan_revision"] = "The recorded revision must belong to this agreement's plan."
        if self.savings_mode == self.SavingsMode.CASH:
            if self.metal_grade_id is not None:
                errors["metal_grade"] = "Cash accounts cannot have a metal grade."
        elif self.savings_mode in {self.SavingsMode.GOLD, self.SavingsMode.SILVER}:
            if self.metal_grade_id is None:
                errors["metal_grade"] = "Metal accounts require an exact metal grade."
            elif self.metal_grade.metal != self.savings_mode:
                errors["metal_grade"] = "The metal grade must match the savings mode."
        if self.pk:
            stored = type(self).objects.filter(pk=self.pk).only("metal_grade_id").first()
            if stored is not None and stored.metal_grade_id != self.metal_grade_id:
                errors["metal_grade"] = "An enrolled account's metal grade is immutable."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields")
        stored_status = type(self).objects.filter(pk=self.pk).values_list("status", flat=True).first() if self.pk else None
        if (self.status == "CANCELLED" or stored_status == "CANCELLED") and self.status != stored_status:
            raise ValidationError("Use the unused-agreement cancellation service; cancellation cannot be reopened.")
        if self.configuration_snapshot_id and self.status != stored_status and (
            self.status in ("REDEEMED", "CLOSURE_PENDING") or stored_status in ("REDEEMED", "CLOSURE_PENDING")
        ):
            raise ValidationError("Use the configured full-settlement or controlled reversal service.")
        if self.pk:
            stored = type(self).objects.filter(pk=self.pk).first()
            if stored and (stored.configuration_snapshot_id or self.configuration_snapshot_id):
                from .plan_configuration import AGREEMENT_CONFIGURATION_FIELDS
                protected = (*AGREEMENT_CONFIGURATION_FIELDS,
                             "start_date", "agreed_months", "eligible_from", "cash_bonus_policy_version_snapshot")
                if any(getattr(stored, field) != getattr(self, field) for field in protected):
                    raise ValidationError("Configured agreement terms are immutable.")
        if self.configuration_snapshot_id:
            from .plan_configuration import validate_agreement_configuration
            from .plan_policies import require_operational_configuration
            require_operational_configuration(self.configuration_snapshot)
            validate_agreement_configuration(self)
        identity_fields = ("plan_id", "plan_name_snapshot", "plan_code_snapshot", "plan_revision_id")
        if self.pk and (update_fields is None or set(update_fields).intersection(
            {*identity_fields, "plan", "plan_revision"}
        )):
            stored_identity = type(self).objects.filter(pk=self.pk).values(*identity_fields).first()
            if stored_identity and any(stored_identity[field] != getattr(self, field) for field in identity_fields):
                raise ValidationError("An enrolled account's plan identity and revision are immutable.")
        protected_fields_are_written = update_fields is None or bool(
            {"savings_mode", "metal_grade"}.intersection(update_fields)
        )
        if self.pk and protected_fields_are_written:
            stored = (
                type(self)
                .objects.filter(pk=self.pk)
                .only("savings_mode", "metal_grade_id")
                .first()
            )
            if stored is not None and (
                stored.savings_mode != self.savings_mode
                or stored.metal_grade_id != self.metal_grade_id
            ):
                raise ValidationError(
                    "An enrolled account's savings mode and metal grade are immutable."
                )
        return super().save(*args, **kwargs)

    @property
    def display_plan_name(self):
        return self.plan_name_snapshot or self.plan.name

    @property
    def display_plan_code(self):
        return self.plan_code_snapshot or self.plan.code

    @property
    def monthly_eligibility(self):
        if self.agreement_schema_version == 2:
            raise ValidationError("Independent agreement eligibility workflows are not activated.")
        from .instalments import has_monthly_instalments
        from .instalment_selectors import get_monthly_eligibility
        return get_monthly_eligibility(self) if has_monthly_instalments(self) else None

    @property
    def effective_status(self):
        if self.status in (self.Status.REDEEMED, self.Status.CANCELLED, self.Status.CLOSURE_PENDING):
            return self.status
        monthly = self.monthly_eligibility
        if monthly is not None:
            return self.Status.REDEMPTION_ELIGIBLE if monthly.policy_eligible else self.Status.ACTIVE
        if is_redemption_eligible(
            eligible_from=self.eligible_from,
            as_of=timezone.localdate(),
        ):
            return self.Status.REDEMPTION_ELIGIBLE
        return self.Status.ACTIVE

    @property
    def effective_status_label(self):
        if self.status == self.Status.CANCELLED:
            return self.Status.CANCELLED.label
        if self.status == self.Status.REDEEMED:
            return self.Status.REDEEMED.label
        from .closure_selectors import accepted_closure
        if accepted_closure(self):
            return "Closure accepted — settlement pending"
        if self.status != self.Status.REDEEMED:
            monthly = self.monthly_eligibility
            if monthly is not None:
                return "Requirements met — showroom settlement review" if monthly.policy_eligible else "Monthly completion — " + monthly.state.replace("_", " ").lower()
            if self.configuration_snapshot_id and self.effective_status == self.Status.REDEMPTION_ELIGIBLE:
                return "Calendar date reached — showroom settlement review"
        if self.effective_status == self.Status.ACTIVE:
            return "Active — not yet eligible"
        return self.Status(self.effective_status).label

    @property
    def entitlement_name(self):
        if self.metal_grade_id:
            return self.metal_grade.display_name
        return self.get_savings_mode_display()

    def __str__(self):
        return f"{self.scheme_number} — {self.customer.full_name}"


class SchemeClosureRequest(models.Model):
    """Closure intent and checked lifecycle projection, never a settlement record."""
    class Status(models.TextChoices):
        PENDING = "PENDING", "Awaiting owner review"
        ACCEPTED = "ACCEPTED", "Accepted — awaiting resolution and settlement"
        WITHDRAWN = "WITHDRAWN", "Withdrawn before acceptance"
        REJECTED = "REJECTED", "Rejected before acceptance"
        CANCELLED = "CANCELLED", "Unused agreement cancelled"
        SETTLED = "SETTLED", "Full jewellery settlement completed"

    class Source(models.TextChoices):
        CUSTOMER = "CUSTOMER", "Customer request"
        OWNER_ASSISTED = "OWNER_ASSISTED", "Owner assisted with customer authorization"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    scheme_account = models.ForeignKey(SchemeAccount, on_delete=models.PROTECT, related_name="closure_requests")
    source = models.CharField(max_length=20, choices=Source.choices)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    actor_label = models.CharField(max_length=254)
    reason = models.TextField()
    authorization_reference = models.CharField(max_length=254, blank=True)
    requested_at = models.DateTimeField(default=timezone.now)
    idempotency_key = models.UUIDField(unique=True)

    class Meta:
        ordering = ["-requested_at", "pk"]
        constraints = [
            models.UniqueConstraint(fields=["scheme_account"], condition=models.Q(status__in=["PENDING", "ACCEPTED"]), name="closure_one_open_per_account"),
            models.CheckConstraint(condition=models.Q(status__in=["PENDING", "ACCEPTED", "WITHDRAWN", "REJECTED", "CANCELLED", "SETTLED"]), name="closure_status_valid"),
            models.CheckConstraint(condition=(models.Q(source="CUSTOMER", authorization_reference="") | (models.Q(source="OWNER_ASSISTED") & ~models.Q(authorization_reference=""))), name="closure_authorization_shape"),
            models.CheckConstraint(condition=~models.Q(reason="") & ~models.Q(actor_label=""), name="closure_actor_reason_required"),
        ]

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("Use the closure service; request evidence is immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Closure request history must be retained.")


class SchemeClosureEvent(models.Model):
    class Action(models.TextChoices):
        REQUESTED = "REQUESTED", "Requested"
        NOTE = "NOTE", "Owner review note"
        ACCEPT = "ACCEPT", "Accepted for resolution and settlement"
        WITHDRAW = "WITHDRAW", "Withdrawn"
        REJECT = "REJECT", "Rejected"
        CANCEL = "CANCEL", "Unused agreement cancelled"
        SETTLE = "SETTLE", "Full jewellery settlement"
        REVERSE = "REVERSE", "Settlement reversed — closure remains accepted"

    request = models.ForeignKey(SchemeClosureRequest, on_delete=models.PROTECT, related_name="events")
    sequence = models.PositiveIntegerField()
    action = models.CharField(max_length=12, choices=Action.choices)
    resulting_status = models.CharField(max_length=12, choices=SchemeClosureRequest.Status.choices)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    actor_label = models.CharField(max_length=254)
    reason = models.TextField()
    authorization_reference = models.CharField(max_length=254, blank=True)
    idempotency_key = models.UUIDField(unique=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["sequence", "pk"]
        constraints = [
            models.UniqueConstraint(fields=["request", "sequence"], name="closure_event_sequence_unique"),
            models.CheckConstraint(condition=models.Q(sequence__gte=1), name="closure_event_sequence_positive"),
            models.CheckConstraint(condition=~models.Q(actor_label="") & ~models.Q(reason=""), name="closure_event_actor_reason"),
            models.CheckConstraint(condition=(
                models.Q(action="REQUESTED", resulting_status="PENDING", sequence=1)
                | models.Q(action="NOTE", resulting_status__in=["PENDING", "ACCEPTED"], sequence__gt=1)
                | models.Q(action="ACCEPT", resulting_status="ACCEPTED", sequence__gt=1)
                | models.Q(action="WITHDRAW", resulting_status="WITHDRAWN", sequence__gt=1)
                | models.Q(action="REJECT", resulting_status="REJECTED", sequence__gt=1)
                | models.Q(action="CANCEL", resulting_status="CANCELLED", sequence__gt=1)
                | models.Q(action="SETTLE", resulting_status="SETTLED", sequence__gt=1)
                | models.Q(action="REVERSE", resulting_status="ACCEPTED", sequence__gt=1)
            ), name="closure_event_action_shape"),
        ]

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("Closure events are append-only.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Closure events must be retained.")


class ConfiguredSettlement(models.Model):
    """Immutable authorization/proof; Redemption remains the financial source."""
    closure = models.ForeignKey(SchemeClosureRequest, on_delete=models.PROTECT, related_name="settlements")
    event = models.OneToOneField(SchemeClosureEvent, on_delete=models.PROTECT, related_name="settlement")
    redemption = models.OneToOneField("Redemption", on_delete=models.PROTECT, related_name="configured_settlement")
    basis = models.CharField(max_length=10, choices=[("NORMAL", "Policy eligible"), ("EARLY", "Customer-authorized early closure")])
    authorization_reference = models.CharField(max_length=254)
    evidence = models.JSONField()
    evidence_digest = models.CharField(max_length=64)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(basis__in=["NORMAL", "EARLY"]), name="configured_settlement_basis"),
            models.CheckConstraint(condition=~models.Q(authorization_reference="") & ~models.Q(evidence_digest=""), name="configured_settlement_proof"),
        ]

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("Configured settlement evidence is immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Configured settlement evidence must be retained.")


class ConfiguredSettlementReversal(models.Model):
    settlement = models.OneToOneField(ConfiguredSettlement, on_delete=models.PROTECT, related_name="correction")
    event = models.OneToOneField(SchemeClosureEvent, on_delete=models.PROTECT, related_name="settlement_correction")
    reversal = models.OneToOneField("RedemptionReversal", on_delete=models.PROTECT, related_name="configured_correction")

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("Configured settlement corrections are immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Configured settlement corrections must be retained.")


class SchemeEnrolmentRequest(models.Model):
    class Status(models.TextChoices):
        PENDING_OWNER_REVIEW = "PENDING_OWNER_REVIEW", "Pending owner review"
        WITHDRAWN = "WITHDRAWN", "Withdrawn"
        DECLINED = "DECLINED", "Declined"
        EXPIRED = "EXPIRED", "Expired"
        ENROLLED = "ENROLLED", "Enrolled"

    TERMINAL_STATUSES = {
        Status.WITHDRAWN,
        Status.DECLINED,
        Status.EXPIRED,
        Status.ENROLLED,
    }
    SNAPSHOT_FIELDS = (
        "configuration_snapshot_id",
        "customer_id",
        "plan_id",
        "metal_grade_id",
        "plan_name_snapshot",
        "plan_code_snapshot",
        "requested_contribution_amount",
        "requested_months",
        "customer_message",
        "amount_rule_snapshot",
        "frequency_rule_snapshot",
        "fixed_contribution_amount_snapshot",
        "minimum_contribution_snapshot",
        "maximum_contribution_snapshot",
        "minimum_months_snapshot",
        "default_months_snapshot",
        "allow_post_eligibility_contributions_snapshot",
        "disclosure_version",
        "disclosure_accepted_at",
        "expires_at",
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name="enrolment_requests",
    )
    plan = models.ForeignKey(
        SchemePlan,
        on_delete=models.PROTECT,
        related_name="enrolment_requests",
    )
    metal_grade = models.ForeignKey(
        MetalGrade,
        on_delete=models.PROTECT,
        related_name="enrolment_requests",
    )
    plan_name_snapshot = models.CharField(max_length=120)
    plan_code_snapshot = models.CharField(max_length=30)
    configuration_snapshot = models.ForeignKey(
        SchemePlanConfiguration, null=True, blank=True, on_delete=models.PROTECT, related_name="enrolment_requests",
    )
    requested_contribution_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
    )
    requested_months = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(12)],
    )
    customer_message = models.TextField(blank=True)
    amount_rule_snapshot = models.CharField(
        max_length=10,
        choices=SchemePlan.AmountRule.choices,
    )
    frequency_rule_snapshot = models.CharField(
        max_length=20,
        choices=SchemePlan.FrequencyRule.choices,
    )
    fixed_contribution_amount_snapshot = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
    )
    minimum_contribution_snapshot = models.DecimalField(
        max_digits=14,
        decimal_places=2,
    )
    maximum_contribution_snapshot = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
    )
    minimum_months_snapshot = models.PositiveSmallIntegerField()
    default_months_snapshot = models.PositiveSmallIntegerField()
    allow_post_eligibility_contributions_snapshot = models.BooleanField()
    disclosure_version = models.CharField(max_length=30)
    disclosure_accepted_at = models.DateTimeField()
    status = models.CharField(
        max_length=24,
        choices=Status.choices,
        default=Status.PENDING_OWNER_REVIEW,
    )
    expires_at = models.DateTimeField()
    scheme_account = models.OneToOneField(
        SchemeAccount,
        on_delete=models.PROTECT,
        related_name="enrolment_request",
        null=True,
        blank=True,
    )
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="decided_scheme_enrolment_requests",
        null=True,
        blank=True,
    )
    decided_by_label = models.CharField(max_length=254, blank=True)
    decision_reason = models.TextField(blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["customer", "plan", "metal_grade"],
                condition=models.Q(status="PENDING_OWNER_REVIEW"),
                name="enrol_request_unique_pending_offering",
            ),
            models.CheckConstraint(
                condition=models.Q(requested_months__gte=12),
                name="enrol_request_months_gte_12",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    requested_months__gte=models.F("minimum_months_snapshot")
                ),
                name="enrol_request_months_gte_minimum",
            ),
            models.CheckConstraint(
                condition=models.Q(minimum_contribution_snapshot__gt=Decimal("0")),
                name="enrol_request_minimum_positive",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(maximum_contribution_snapshot__isnull=True)
                    | models.Q(
                        maximum_contribution_snapshot__gte=models.F(
                            "minimum_contribution_snapshot"
                        )
                    )
                ),
                name="enrol_request_maximum_valid",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        requested_contribution_amount__gte=models.F(
                            "minimum_contribution_snapshot"
                        )
                    )
                    & (
                        models.Q(maximum_contribution_snapshot__isnull=True)
                        | models.Q(
                            requested_contribution_amount__lte=models.F(
                                "maximum_contribution_snapshot"
                            )
                        )
                    )
                ),
                name="enrol_request_amount_within_offer",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        amount_rule_snapshot="FIXED",
                        fixed_contribution_amount_snapshot__isnull=False,
                        requested_contribution_amount=models.F(
                            "fixed_contribution_amount_snapshot"
                        ),
                    )
                    | models.Q(
                        amount_rule_snapshot="VARIABLE",
                        fixed_contribution_amount_snapshot__isnull=True,
                    )
                ),
                name="enrol_request_amount_rule_valid",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        status="PENDING_OWNER_REVIEW",
                        scheme_account__isnull=True,
                        decided_by__isnull=True,
                        decided_by_label="",
                        decision_reason="",
                        decided_at__isnull=True,
                    )
                    | (
                        models.Q(
                            status__in=["WITHDRAWN", "DECLINED", "EXPIRED"],
                            scheme_account__isnull=True,
                            decided_at__isnull=False,
                        )
                        & ~models.Q(decided_by_label="")
                        & ~models.Q(decision_reason="")
                    )
                    | (
                        models.Q(
                            status="ENROLLED",
                            scheme_account__isnull=False,
                            decided_at__isnull=False,
                        )
                        & ~models.Q(decided_by_label="")
                        & ~models.Q(decision_reason="")
                    )
                ),
                name="enrol_request_lifecycle_shape_valid",
            ),
            models.CheckConstraint(
                condition=~models.Q(disclosure_version=""),
                name="enrol_request_disclosure_required",
            ),
            models.CheckConstraint(
                condition=(
                    ~models.Q(plan_name_snapshot="")
                    & ~models.Q(plan_code_snapshot="")
                ),
                name="enrol_request_plan_identity",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    expires_at__gt=models.F("disclosure_accepted_at")
                ),
                name="enrol_request_expiry_after_consent",
            ),
        ]
        indexes = [
            models.Index(
                fields=["status", "expires_at"],
                name="enrol_req_status_expiry_idx",
            ),
            models.Index(
                fields=["customer", "created_at"],
                name="enrol_req_customer_time_idx",
            ),
        ]

    @property
    def effective_status(self):
        if (
            self.status == self.Status.PENDING_OWNER_REVIEW
            and self.expires_at <= timezone.now()
        ):
            return self.Status.EXPIRED
        return self.status

    @property
    def effective_status_label(self):
        return self.Status(self.effective_status).label

    def clean(self):
        super().clean()
        errors = {}
        if self.metal_grade_id and self.plan_id:
            if self.metal_grade.metal not in {
                SchemeAccount.SavingsMode.GOLD,
                SchemeAccount.SavingsMode.SILVER,
            }:
                errors["metal_grade"] = "Select a supported gold or silver grade."
        if self.scheme_account_id:
            account = self.scheme_account
            if account.customer_id != self.customer_id:
                errors["scheme_account"] = "The linked account must belong to this customer."
            elif account.plan_id != self.plan_id:
                errors["scheme_account"] = "The linked account must use the requested plan."
            elif account.metal_grade_id != self.metal_grade_id:
                errors["scheme_account"] = "The linked account must use the requested grade."
        if (
            self.expires_at
            and self.disclosure_accepted_at
            and self.expires_at <= self.disclosure_accepted_at
        ):
            errors["expires_at"] = "Expiry must be after disclosure acceptance."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.pk:
            stored = type(self).objects.filter(pk=self.pk).first()
            if stored is not None:
                if stored.status in self.TERMINAL_STATUSES:
                    raise ValidationError("Terminal enrolment requests are immutable.")
                changed_snapshots = [
                    field
                    for field in self.SNAPSHOT_FIELDS
                    if getattr(stored, field) != getattr(self, field)
                ]
                if changed_snapshots:
                    raise ValidationError(
                        "Submitted enrolment request details and offer snapshots are immutable."
                    )
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Enrolment request evidence cannot be deleted.")

    def __str__(self):
        return (
            f"{self.customer.full_name} — {self.plan_name_snapshot} — "
            f"{self.metal_grade.display_name}"
        )


class GatewayMode(models.TextChoices):
    TEST = "test", "Test"
    LIVE = "live", "Live"


class PaymentChannel(models.TextChoices):
    RAZORPAY = "RAZORPAY", "Razorpay online"
    IN_STORE_CASH = "IN_STORE_CASH", "In-store cash"
    MOCK = "MOCK", "Mock payment"


class SchemeInstalmentPeriod(models.Model):
    """Frozen scheduled windows, not proof of payment, eligibility or liability."""

    scheme_account = models.ForeignKey(SchemeAccount, on_delete=models.PROTECT, related_name="instalment_periods")
    number = models.PositiveIntegerField()
    starts_on = models.DateField()
    ends_before = models.DateField(help_text="Exclusive end in Asia/Kolkata; the next period starts on this date.")
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    actor_label = models.CharField(max_length=254)
    reason = models.TextField()

    class Meta:
        ordering = ["scheme_account_id", "number"]
        constraints = [
            models.UniqueConstraint(fields=["scheme_account", "number"], name="inst_period_account_number"),
            models.UniqueConstraint(fields=["scheme_account", "starts_on"], name="inst_period_account_start"),
            models.CheckConstraint(condition=models.Q(number__gt=0, amount__gt=0, ends_before__gt=models.F("starts_on")), name="inst_period_valid_window"),
            models.CheckConstraint(condition=~models.Q(actor_label="") & ~models.Q(reason=""), name="inst_period_evidence_required"),
        ]

    def clean(self):
        super().clean()
        if self.scheme_account_id:
            from .instalments import effective_account_windows
            windows = effective_account_windows(self.scheme_account)
            if not self.number or not 1 <= self.number <= len(windows):
                raise ValidationError("The period number is outside the agreed schedule.")
            expected = windows[self.number - 1]
            if (self.starts_on, self.ends_before, self.amount) != (expected.starts_on, expected.ends_before, expected.amount):
                raise ValidationError("Period dates and amount must match the recorded agreement.")

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("Scheduled periods are immutable; corrections require an explicit workflow.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Scheduled periods cannot be deleted.")


class InstalmentReservation(models.Model):
    """Exclusive period claim. State is a projection of append-only decisions."""

    class State(models.TextChoices):
        RESERVED = "RESERVED", "Reserved"
        ORDERING = "ORDERING", "Provider order request started"
        AWAITING = "AWAITING", "Verified payment awaiting timing evidence"
        QUALIFIED = "QUALIFIED", "Payment qualified"
        REVIEW = "REVIEW", "Timing review required"
        REVERSED = "REVERSED", "Cash entry reversed"
        RELEASED = "RELEASED", "Provider-reconciled release"
        RELEASED_REVIEW = "RELEASED_REVIEW", "Late capture after release"

    period = models.ForeignKey(SchemeInstalmentPeriod, on_delete=models.PROTECT, related_name="reservations")
    contribution = models.OneToOneField("Contribution", on_delete=models.PROTECT, related_name="instalment_reservation")
    reserved_at = models.DateTimeField()
    expires_at = models.DateTimeField(help_text="Checkout deadline, not permission to release the period claim.")
    state = models.CharField(max_length=20, choices=State.choices, default=State.RESERVED)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["period"], condition=~models.Q(state__in=["REVERSED", "RELEASED", "RELEASED_REVIEW"]), name="inst_one_occupied_period"),
            models.CheckConstraint(condition=models.Q(state__in=["RESERVED", "ORDERING", "AWAITING", "QUALIFIED", "REVIEW", "REVERSED", "RELEASED", "RELEASED_REVIEW"]), name="inst_reservation_state_valid"),
            models.CheckConstraint(condition=models.Q(expires_at__gt=models.F("reserved_at")), name="inst_reservation_time_valid"),
        ]

    def clean(self):
        super().clean()
        if self.period_id and self.contribution_id:
            if (self.period.scheme_account_id, self.period.amount) != (self.contribution.scheme_account_id, self.contribution.amount):
                raise ValidationError("The reservation must match the agreement and scheduled amount.")

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("Reservation transitions require the instalment service and decision evidence.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Instalment reservations cannot be deleted.")


class InstalmentPaymentDecision(models.Model):
    """Qualification/correction evidence; never an additional money or metal entry."""

    reservation = models.ForeignKey(InstalmentReservation, on_delete=models.PROTECT, related_name="decisions")
    sequence = models.PositiveIntegerField()
    state = models.CharField(max_length=20, choices=InstalmentReservation.State.choices)
    reason_code = models.CharField(max_length=40)
    request_token = models.UUIDField(null=True, blank=True, unique=True, editable=False)
    actor_label = models.CharField(max_length=254)
    created_at = models.DateTimeField(auto_now_add=True)
    earliest_at = models.DateTimeField(null=True, blank=True)
    latest_at = models.DateTimeField(null=True, blank=True)
    webhook_event = models.ForeignKey("PaymentWebhookEvent", on_delete=models.PROTECT, null=True, blank=True)
    cash_receipt = models.ForeignKey("InStoreCashReceipt", on_delete=models.PROTECT, null=True, blank=True)
    cash_reversal = models.ForeignKey("InStoreCashContributionReversal", on_delete=models.PROTECT, null=True, blank=True)
    reconciliation_audit = models.ForeignKey("AuditEvent", on_delete=models.PROTECT, null=True, blank=True)
    owner_review = models.OneToOneField("InstalmentReview", on_delete=models.PROTECT, null=True, blank=True, related_name="qualification_decision")

    class Meta:
        ordering = ["reservation_id", "sequence"]
        constraints = [
            models.CheckConstraint(condition=models.Q(request_token__isnull=True) | models.Q(state="ORDERING"), name="inst_request_token_intent_only"),
            models.UniqueConstraint(fields=["reservation", "sequence"], name="inst_decision_sequence_unique"),
            models.UniqueConstraint(fields=["reservation", "webhook_event"], name="inst_decision_webhook_unique"),
            models.UniqueConstraint(fields=["reservation", "cash_receipt"], name="inst_decision_cash_unique"),
            models.UniqueConstraint(fields=["reservation", "cash_reversal"], name="inst_decision_reversal_unique"),
            models.UniqueConstraint(fields=["reservation", "reconciliation_audit"], name="inst_decision_release_unique"),
            models.CheckConstraint(condition=models.Q(sequence__gt=0) & ~models.Q(reason_code="") & ~models.Q(actor_label=""), name="inst_decision_evidence_required"),
            models.CheckConstraint(condition=((models.Q(owner_review__isnull=True) & (
                models.Q(state="RESERVED", sequence=1, webhook_event__isnull=True, cash_receipt__isnull=True, cash_reversal__isnull=True, reconciliation_audit__isnull=True)
                | models.Q(state="RESERVED", sequence__gt=1, reason_code__in=["PROVIDER_ORDER_RECORDED", "PROVIDER_ORDER_RECOVERED"], webhook_event__isnull=True, cash_receipt__isnull=True, cash_reversal__isnull=True, reconciliation_audit__isnull=True)
                | models.Q(state="ORDERING", webhook_event__isnull=True, cash_receipt__isnull=True, cash_reversal__isnull=True, reconciliation_audit__isnull=True)
                | models.Q(state="AWAITING", webhook_event__isnull=True, cash_receipt__isnull=True, cash_reversal__isnull=True, reconciliation_audit__isnull=True)
                | (models.Q(state__in=["QUALIFIED", "REVIEW"], cash_reversal__isnull=True, reconciliation_audit__isnull=True) & (
                    models.Q(webhook_event__isnull=False, cash_receipt__isnull=True)
                    | models.Q(webhook_event__isnull=True, cash_receipt__isnull=False)))
                | models.Q(state="REVERSED", cash_reversal__isnull=False, cash_receipt__isnull=True, webhook_event__isnull=True, reconciliation_audit__isnull=True)
                | models.Q(state="RELEASED", reconciliation_audit__isnull=False, cash_reversal__isnull=True, cash_receipt__isnull=True, webhook_event__isnull=True)
                | models.Q(state="RELEASED_REVIEW", reconciliation_audit__isnull=True, cash_reversal__isnull=True, cash_receipt__isnull=True, webhook_event__isnull=False)
            )) | models.Q(state="QUALIFIED", reason_code="OWNER_VERIFIED_TIMING", owner_review__isnull=False,
                webhook_event__isnull=True, cash_receipt__isnull=True, cash_reversal__isnull=True,
                reconciliation_audit__isnull=True)), name="inst_decision_source_valid"),
            models.CheckConstraint(condition=(
                ~models.Q(state="QUALIFIED")
                | models.Q(earliest_at__isnull=False, latest_at__isnull=False, latest_at__gte=models.F("earliest_at"))
            ), name="inst_qualified_time_required"),
        ]

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("Instalment payment decisions are append-only.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Instalment payment decisions cannot be deleted.")


class InstalmentOrderRecovery(models.Model):
    """Authenticated provider identity recovery, NOT payment verification or release."""

    request_decision = models.OneToOneField(InstalmentPaymentDecision, on_delete=models.PROTECT, related_name="request_recovery")
    decision = models.OneToOneField(InstalmentPaymentDecision, on_delete=models.PROTECT, related_name="order_recovery")
    gateway_order_id = models.CharField(max_length=120, unique=True)
    receipt = models.CharField(max_length=40)
    provider_status = models.CharField(max_length=12, choices=[("created", "Created"), ("attempted", "Attempted"), ("paid", "Paid")])
    provider_created_at = models.DateTimeField()
    amount_subunits = models.PositiveBigIntegerField()
    currency = models.CharField(max_length=3, default="INR")
    observed_at = models.DateTimeField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    actor_label = models.CharField(max_length=254)
    reason = models.TextField(max_length=2000)
    evidence_reference = models.CharField(max_length=254)
    idempotency_key = models.UUIDField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(amount_subunits__gte=100, currency="INR",
                provider_status__in=["created", "attempted", "paid"], observed_at__gte=models.F("provider_created_at")), name="inst_order_recovery_facts"),
            models.CheckConstraint(condition=~models.Q(actor_label="") & ~models.Q(reason="")
                & ~models.Q(evidence_reference="") & ~models.Q(receipt="") & ~models.Q(gateway_order_id=""), name="inst_order_recovery_evidence"),
        ]

    def clean(self):
        super().clean()
        if self.request_decision_id and self.decision_id:
            source, result = self.request_decision, self.decision
            contribution = source.reservation.contribution
            if (source.state != "ORDERING" or source.request_token is None
                or result.state != "RESERVED" or result.reason_code != "PROVIDER_ORDER_RECOVERED"
                or result.reservation_id != source.reservation_id or result.sequence != source.sequence + 1
                or self.receipt != f"inst_{source.request_token.hex}"
                or self.gateway_order_id != contribution.gateway_order_id
                or self.amount_subunits != contribution.amount * 100
                or contribution.gateway_mode != "live" or contribution.payment_gateway != "razorpay"
                or self.provider_created_at < source.created_at.replace(microsecond=0)):
                raise ValidationError("Recovered order identity must match its original durable Live request and decision.")

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("Order recovery evidence is append-only.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Order recovery evidence cannot be deleted.")


class InstalmentReview(models.Model):
    """Append-only owner investigation, never an override of money or agreed terms."""

    class Action(models.TextChoices):
        NOTE = "NOTE", "Record investigation note"
        OUTAGE_HOLD = "OUTAGE_HOLD", "Record outage requiring agreement review"
        ACCEPT_TIMING = "ACCEPT_TIMING", "Accept existing verified timing evidence"

    period = models.ForeignKey(SchemeInstalmentPeriod, on_delete=models.PROTECT, related_name="reviews")
    reservation = models.ForeignKey(InstalmentReservation, on_delete=models.PROTECT, null=True, blank=True, related_name="reviews")
    source_decision = models.ForeignKey(InstalmentPaymentDecision, on_delete=models.PROTECT, null=True, blank=True, related_name="reviews")
    sequence = models.PositiveIntegerField()
    action = models.CharField(max_length=20, choices=Action.choices)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    actor_label = models.CharField(max_length=254)
    reason = models.TextField(max_length=2000)
    evidence_reference = models.CharField(max_length=254, help_text="Internal incident/support reference; never a password, token or raw payload.")
    idempotency_key = models.UUIDField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["period_id", "sequence"]
        constraints = [
            models.UniqueConstraint(fields=["period", "sequence"], name="inst_review_sequence_unique"),
            models.CheckConstraint(condition=models.Q(sequence__gt=0) & ~models.Q(actor_label="") & ~models.Q(reason="") & ~models.Q(evidence_reference=""), name="inst_review_evidence_required"),
            models.CheckConstraint(condition=(
                models.Q(action="ACCEPT_TIMING", reservation__isnull=False, source_decision__isnull=False)
                | models.Q(action="NOTE", source_decision__isnull=True)
                | models.Q(action="OUTAGE_HOLD", reservation__isnull=True, source_decision__isnull=True)
            ), name="inst_review_action_shape"),
        ]

    def clean(self):
        super().clean()
        if self.reservation_id and self.reservation.period_id != self.period_id:
            raise ValidationError("The review must belong to the reservation's recorded period.")
        if self.source_decision_id and self.source_decision.reservation_id != self.reservation_id:
            raise ValidationError("Timing evidence must belong to the reviewed reservation.")

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("Instalment reviews are append-only; record a follow-up instead.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Instalment reviews cannot be deleted.")


class InstalmentOutageResolution(models.Model):
    """Explicit acknowledged amendment/closure; the original hold and terms survive."""

    class Outcome(models.TextChoices):
        COMPENSATE = "COMPENSATE", "Append one compensating month on the agreed period basis"
        RESTORED = "RESTORED", "Restored within the original payable window"
        QUALIFIED = "QUALIFIED", "Original period already has a qualifying payment"

    hold = models.OneToOneField(InstalmentReview, on_delete=models.PROTECT, related_name="outage_resolution")
    period = models.ForeignKey(SchemeInstalmentPeriod, on_delete=models.PROTECT, related_name="outage_resolutions")
    scheme_account = models.ForeignKey(SchemeAccount, on_delete=models.PROTECT, related_name="outage_resolutions")
    outcome = models.CharField(max_length=20, choices=Outcome.choices)
    policy_version = models.CharField(max_length=30, default="OUTAGE_COMPENSATION_V1", editable=False)
    compensation_number = models.PositiveSmallIntegerField(null=True, blank=True)
    compensation_period = models.OneToOneField(SchemeInstalmentPeriod, on_delete=models.PROTECT,
        null=True, blank=True, related_name="outage_amendment")
    qualification_decision = models.ForeignKey(InstalmentPaymentDecision, on_delete=models.PROTECT,
        null=True, blank=True, related_name="outage_resolutions")
    incident_started_at = models.DateTimeField()
    service_restored_at = models.DateTimeField()
    customer_acknowledged_at = models.DateTimeField()
    acknowledgement_reference = models.CharField(max_length=254)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    actor_label = models.CharField(max_length=254)
    reason = models.TextField(max_length=2000)
    evidence_reference = models.CharField(max_length=254)
    idempotency_key = models.UUIDField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["scheme_account_id", "created_at", "pk"]
        constraints = [
            models.UniqueConstraint(fields=["scheme_account", "compensation_number"], name="outage_account_comp_unique"),
            models.UniqueConstraint(fields=["period"], condition=models.Q(outcome="COMPENSATE"), name="outage_period_comp_unique"),
            models.CheckConstraint(condition=(
                models.Q(outcome="COMPENSATE", compensation_number__isnull=False,
                    compensation_number__gte=1, compensation_number__lte=3, compensation_period__isnull=False)
                | models.Q(outcome__in=["RESTORED", "QUALIFIED"], compensation_number__isnull=True, compensation_period__isnull=True)
            ), name="outage_resolution_shape"),
            models.CheckConstraint(condition=(
                models.Q(outcome="QUALIFIED", qualification_decision__isnull=False)
                | (~models.Q(outcome="QUALIFIED") & models.Q(qualification_decision__isnull=True))
            ), name="outage_resolution_proof"),
            models.CheckConstraint(condition=models.Q(policy_version="OUTAGE_COMPENSATION_V1")
                & ~models.Q(actor_label="") & ~models.Q(reason="") & ~models.Q(evidence_reference="")
                & ~models.Q(acknowledgement_reference=""), name="outage_resolution_evidence"),
            models.CheckConstraint(condition=models.Q(service_restored_at__gt=models.F("incident_started_at"),
                customer_acknowledged_at__gte=models.F("service_restored_at")), name="outage_resolution_time_order"),
        ]

    def clean(self):
        super().clean()
        if self.hold_id and (self.hold.action != "OUTAGE_HOLD" or self.hold.period_id != self.period_id):
            raise ValidationError("Resolve an outage hold for this exact affected period.")
        if any(not value.strip() for value in (self.actor_label, self.reason, self.evidence_reference, self.acknowledgement_reference)):
            raise ValidationError("Outage resolution evidence must not be blank.")
        if self.hold_id and self.customer_acknowledged_at and self.customer_acknowledged_at < self.hold.created_at:
            raise ValidationError("Customer acknowledgement must follow the recorded outage review.")
        if self.created_at and self.customer_acknowledged_at and self.customer_acknowledged_at > self.created_at:
            raise ValidationError("Customer acknowledgement cannot postdate the recorded resolution.")
        if self.period_id and self.period.scheme_account_id != self.scheme_account_id:
            raise ValidationError("Outage evidence must belong to the same agreement.")
        if self.qualification_decision_id and (
            self.qualification_decision.state != "QUALIFIED"
            or self.qualification_decision.reservation.period_id != self.period_id
        ):
            raise ValidationError("Closure must link existing qualification evidence for this affected period.")
        if self.compensation_period_id:
            from .instalments import compensation_window
            window = compensation_window(self.scheme_account, self.compensation_number)
            p = self.compensation_period
            if (p.scheme_account_id, p.number, p.starts_on, p.ends_before, p.amount) != (
                self.scheme_account_id, window.number, window.starts_on, window.ends_before, window.amount
            ):
                raise ValidationError("Compensation must append the next window on the original agreed period basis.")

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("Outage resolutions are immutable acknowledged evidence.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Outage resolutions cannot be deleted.")


class Contribution(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        PAID = "PAID", "Paid"
        PAID_UNALLOCATED = "PAID_UNALLOCATED", "Paid — allocation pending"
        FAILED = "FAILED", "Failed"
        ABANDONED = "ABANDONED", "Abandoned"
        REVERSED = "REVERSED", "Reversed"

    scheme_account = models.ForeignKey(
        SchemeAccount,
        on_delete=models.PROTECT,
        related_name="contributions",
    )
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    contribution_period = models.DateField(
        help_text="First calendar day of the contribution month."
    )
    frequency_rule_snapshot = models.CharField(
        max_length=20, choices=SchemePlan.FrequencyRule.choices
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    payment_gateway = models.CharField(max_length=30)
    payment_channel = models.CharField(
        max_length=20,
        choices=PaymentChannel.choices,
        default=PaymentChannel.MOCK,
    )
    gateway_mode = models.CharField(
        max_length=10,
        choices=GatewayMode.choices,
        blank=True,
        help_text="Razorpay environment used to create the provider order.",
    )
    scheme_rate = models.ForeignKey(
        "SchemeRate",
        on_delete=models.PROTECT,
        related_name="locked_contributions",
        null=True,
        blank=True,
    )
    rate_locked_at = models.DateTimeField(null=True, blank=True)
    gateway_order_id = models.CharField(max_length=120, null=True, blank=True, unique=True)
    gateway_reference = models.CharField(max_length=120, null=True, blank=True, unique=True)
    gateway_signature = models.CharField(max_length=128, blank=True)
    checkout_expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=(
            "Application deadline for opening or resuming this Razorpay Checkout. "
            "It does not cancel the provider order or reject a captured payment."
        ),
    )
    allocation_error = models.TextField(blank=True)
    allocation_attempted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=Decimal("0")),
                name="contribution_amount_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(contribution_period__day=1),
                name="contribution_period_first_day",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(scheme_rate__isnull=True, rate_locked_at__isnull=True)
                    | models.Q(scheme_rate__isnull=False, rate_locked_at__isnull=False)
                ),
                name="contribution_scheme_rate_lock_complete",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        status__in=["PAID", "PAID_UNALLOCATED", "REVERSED"],
                        paid_at__isnull=False,
                        gateway_reference__isnull=False,
                    )
                    | models.Q(
                        status__in=["PENDING", "FAILED", "ABANDONED"],
                        paid_at__isnull=True,
                    )
                ),
                name="paid_contribution_has_confirmation",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        payment_gateway="razorpay",
                        gateway_mode__in=[GatewayMode.TEST, GatewayMode.LIVE],
                    )
                    | (
                        ~models.Q(payment_gateway="razorpay")
                        & models.Q(gateway_mode="")
                    )
                ),
                name="contribution_razorpay_mode_valid",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        payment_gateway="razorpay",
                        payment_channel=PaymentChannel.RAZORPAY,
                    )
                    | models.Q(
                        payment_gateway="in_store_cash",
                        payment_channel=PaymentChannel.IN_STORE_CASH,
                    )
                    | (
                        ~models.Q(payment_gateway__in=["razorpay", "in_store_cash"])
                        & models.Q(payment_channel=PaymentChannel.MOCK)
                    )
                ),
                name="contribution_payment_channel_valid",
            ),
            models.CheckConstraint(
                condition=(
                    ~models.Q(payment_channel=PaymentChannel.IN_STORE_CASH)
                    | models.Q(
                        gateway_mode="",
                        gateway_order_id__isnull=True,
                        gateway_signature="",
                        checkout_expires_at__isnull=True,
                        status__in=["PAID", "PAID_UNALLOCATED", "REVERSED"],
                    )
                ),
                name="in_store_cash_fields_valid",
            ),
            models.CheckConstraint(
                condition=(
                    ~models.Q(status="REVERSED")
                    | models.Q(payment_channel=PaymentChannel.IN_STORE_CASH)
                ),
                name="reversed_contribution_is_cash",
            ),
            models.CheckConstraint(
                condition=(
                    ~models.Q(
                        payment_gateway="razorpay",
                        status="PENDING",
                    )
                    | models.Q(checkout_expires_at__isnull=False)
                ),
                name="pending_rzp_checkout_expiry",
            ),
            models.UniqueConstraint(
                fields=["scheme_account", "contribution_period"],
                condition=models.Q(
                    status__in=["PAID", "PAID_UNALLOCATED"],
                    frequency_rule_snapshot="ONCE_PER_MONTH",
                ),
                name="one_paid_contribution_per_account_period",
            ),
            models.UniqueConstraint(
                fields=["scheme_account", "contribution_period"],
                condition=models.Q(
                    status="PENDING",
                    payment_gateway="razorpay",
                    frequency_rule_snapshot="ONCE_PER_MONTH",
                ),
                name="one_pending_razorpay_monthly_payment",
            ),
        ]
        indexes = [
            models.Index(fields=["status", "created_at"], name="contrib_status_created_idx"),
            models.Index(
                fields=["status", "checkout_expires_at"],
                name="contrib_status_expiry_idx",
            ),
        ]

    @property
    def razorpay_checkout_expired(self):
        if self.payment_gateway != "razorpay":
            return False
        return (
            self.checkout_expires_at is None
            or timezone.now() >= self.checkout_expires_at
        )

    @property
    def payment_method_display(self):
        return self.get_payment_channel_display()

    def save(self, *args, **kwargs):
        if self._state.adding:
            if self.payment_gateway == "razorpay":
                self.payment_channel = PaymentChannel.RAZORPAY
            elif self.payment_gateway == "in_store_cash":
                self.payment_channel = PaymentChannel.IN_STORE_CASH
            else:
                self.payment_channel = PaymentChannel.MOCK
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.scheme_account.scheme_number} — ₹{self.amount} — {self.status}"


class InrPrincipalReceipt(models.Model):
    """Verified purchase-credit principal, never legacy CASH or a metal allocation."""
    scheme_account = models.ForeignKey(SchemeAccount, on_delete=models.PROTECT, related_name="inr_principal_receipts")
    configuration = models.ForeignKey(SchemePlanConfiguration, on_delete=models.PROTECT)
    contribution = models.OneToOneField(Contribution, on_delete=models.PROTECT, related_name="inr_principal_receipt")
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    source_reference = models.CharField(max_length=120)
    verified_at = models.DateTimeField()
    cash_receipt = models.OneToOneField("InStoreCashReceipt", null=True, blank=True, on_delete=models.PROTECT)
    webhook_event = models.OneToOneField("PaymentWebhookEvent", null=True, blank=True, on_delete=models.PROTECT)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    actor_label = models.CharField(max_length=254)
    reason = models.TextField()
    idempotency_key = models.UUIDField(unique=True)
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(amount__gt=0, amount__lte=Decimal("999999999999.99")), name="inr_principal_amount_valid"),
            models.CheckConstraint(condition=(models.Q(cash_receipt__isnull=False, webhook_event__isnull=True)
                | models.Q(cash_receipt__isnull=True, webhook_event__isnull=False)), name="inr_principal_one_source"),
            models.CheckConstraint(condition=~models.Q(source_reference="") & ~models.Q(actor_label="") & ~models.Q(reason=""), name="inr_principal_evidence_required"),
        ]

    def clean(self):
        super().clean()
        from .inr_selectors import validate_principal_receipt
        validate_principal_receipt(self)

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("INR principal receipts are immutable; retain correction evidence.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("INR principal receipts must be retained.")


class InrPrincipalCorrection(models.Model):
    """Full erroneous cash-receipt correction, not a refund or a partial withdrawal."""
    receipt = models.OneToOneField(InrPrincipalReceipt, on_delete=models.PROTECT, related_name="correction")
    cash_reversal = models.OneToOneField("InStoreCashContributionReversal", on_delete=models.PROTECT)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    actor_label = models.CharField(max_length=254)
    reason = models.TextField()
    idempotency_key = models.UUIDField(unique=True)
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=~models.Q(actor_label="") & ~models.Q(reason=""), name="inr_correction_evidence_required")]

    def clean(self):
        super().clean()
        from .inr_selectors import validate_principal_correction
        validate_principal_correction(self)

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("INR principal corrections are append-only.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("INR principal corrections must be retained.")


class InrSettlementProposal(models.Model):
    """Immutable full-principal terms; retirement is a checked service projection."""
    scheme_account = models.ForeignKey(SchemeAccount, on_delete=models.PROTECT, related_name="inr_settlements")
    closure = models.ForeignKey(SchemeClosureRequest, on_delete=models.PROTECT, related_name="inr_proposals")
    previous = models.OneToOneField("self", null=True, blank=True, on_delete=models.PROTECT, related_name="replacement")
    retired = models.BooleanField(default=False, editable=False)
    principal = models.DecimalField(max_digits=14, decimal_places=2)
    invoice_payable = models.DecimalField(max_digits=14, decimal_places=2)
    principal_to_invoice = models.DecimalField(max_digits=14, decimal_places=2)
    principal_refund = models.DecimalField(max_digits=14, decimal_places=2)
    separate_top_up = models.DecimalField(max_digits=14, decimal_places=2)
    invoice_reference = models.CharField(max_length=120, unique=True, null=True, blank=True)
    authorization_reference = models.CharField(max_length=254)
    basis = models.CharField(max_length=10, choices=[("NORMAL", "Policy eligible"), ("EARLY", "Authorized early exit")])
    evidence = models.JSONField()
    evidence_digest = models.CharField(max_length=64)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    actor_label = models.CharField(max_length=254)
    reason = models.TextField()
    idempotency_key = models.UUIDField(unique=True)
    recorded_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["scheme_account"], condition=models.Q(retired=False), name="inr_one_current_disposition"),
            models.UniqueConstraint(fields=["scheme_account"], condition=models.Q(previous__isnull=True), name="inr_one_disposition_root"),
            models.CheckConstraint(condition=models.Q(principal__gt=0, principal__lte=Decimal("999999999999.99"),
                invoice_payable__gte=0, invoice_payable__lte=Decimal("999999999999.99"),
                principal_to_invoice__gte=0, principal_refund__gte=0, separate_top_up__gte=0), name="inr_settlement_amount_bounds"),
            models.CheckConstraint(condition=models.Q(principal=models.F("principal_to_invoice") + models.F("principal_refund"),
                invoice_payable=models.F("principal_to_invoice") + models.F("separate_top_up"))
                & (models.Q(principal_refund=0) | models.Q(separate_top_up=0)), name="inr_settlement_conserves_value"),
            models.CheckConstraint(condition=(models.Q(invoice_payable=0, invoice_reference__isnull=True)
                | (models.Q(invoice_payable__gt=0, invoice_reference__isnull=False) & ~models.Q(invoice_reference=""))), name="inr_settlement_invoice_shape"),
            models.CheckConstraint(condition=models.Q(basis__in=["NORMAL", "EARLY"]) & ~models.Q(authorization_reference="")
                & ~models.Q(actor_label="") & ~models.Q(reason="") & ~models.Q(evidence_digest=""), name="inr_settlement_proof_required"),
        ]

    def clean(self):
        super().clean()
        from .inr_settlement_selectors import validate_inr_proposal
        validate_inr_proposal(self)

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("INR settlement proposals are immutable; corrections require separate review.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("INR settlement evidence must be retained.")


class InrSettlementFulfilment(models.Model):
    """Actual manual discharge of one exact leg; never a promise to pay later."""
    proposal = models.ForeignKey(InrSettlementProposal, on_delete=models.PROTECT, related_name="fulfilments")
    kind = models.CharField(max_length=12, choices=[("JEWELLERY", "Jewellery handed over"), ("REFUND", "Principal returned")])
    receipt = models.ForeignKey(InrPrincipalReceipt, null=True, blank=True, on_delete=models.PROTECT)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    method = models.CharField(max_length=24, choices=[("SHOWROOM", "Showroom jewellery handover"),
        ("CASH_RETURN", "Original cash payment returned"), ("PROVIDER_DASHBOARD", "Manual original-source provider refund")])
    external_reference = models.CharField(max_length=120)
    customer_receipt_reference = models.CharField(max_length=254)
    top_up_reference = models.CharField(max_length=120, blank=True)
    fulfilled_at = models.DateTimeField()
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    actor_label = models.CharField(max_length=254)
    reason = models.TextField()
    idempotency_key = models.UUIDField(unique=True)
    recorded_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["proposal", "receipt"], name="inr_refund_leg_once_per_proposal"),
            models.UniqueConstraint(fields=["proposal"], condition=models.Q(kind="JEWELLERY"), name="inr_one_jewellery_fulfilment"),
            models.UniqueConstraint(fields=["method", "external_reference"], name="inr_fulfilment_reference_unique"),
            models.CheckConstraint(condition=models.Q(amount__gt=0, amount__lte=Decimal("999999999999.99")), name="inr_fulfilment_amount_valid"),
            models.CheckConstraint(condition=(models.Q(kind="JEWELLERY", receipt__isnull=True, method="SHOWROOM")
                | models.Q(kind="REFUND", receipt__isnull=False, method__in=["CASH_RETURN", "PROVIDER_DASHBOARD"], top_up_reference="")), name="inr_fulfilment_source_shape"),
            models.CheckConstraint(condition=~models.Q(external_reference="") & ~models.Q(customer_receipt_reference="")
                & ~models.Q(actor_label="") & ~models.Q(reason=""), name="inr_fulfilment_evidence_required"),
        ]

    def clean(self):
        super().clean()
        from .inr_settlement_selectors import validate_inr_fulfilment
        validate_inr_fulfilment(self)

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("INR fulfilment evidence is append-only.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("INR fulfilment evidence must be retained.")


class InrSettlementCompletion(models.Model):
    proposal = models.OneToOneField(InrSettlementProposal, on_delete=models.PROTECT, related_name="completion")
    event = models.OneToOneField(SchemeClosureEvent, on_delete=models.PROTECT, related_name="inr_completion")

    def clean(self):
        super().clean()
        from .inr_settlement_selectors import validate_inr_completion
        validate_inr_completion(self)

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("INR completion evidence is immutable.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("INR completion evidence must be retained.")


class InrSettlementResolution(models.Model):
    """Append-only retirement proof: unused proposal void or full physical return."""
    proposal = models.OneToOneField(InrSettlementProposal, on_delete=models.PROTECT, related_name="resolution")
    event = models.OneToOneField(SchemeClosureEvent, on_delete=models.PROTECT, related_name="inr_resolution")
    kind = models.CharField(max_length=12, choices=[("VOID", "No fulfilment occurred"), ("FULL_RETURN", "All fulfilled portions returned")])
    evidence = models.JSONField()
    evidence_digest = models.CharField(max_length=64)

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(kind__in=["VOID", "FULL_RETURN"])
            & ~models.Q(evidence_digest=""), name="inr_resolution_proof_required")]

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("INR resolution evidence is immutable.")
        # Full proof includes child returns: the service validates it after inserting
        # the complete set, in the same transaction, before retiring the proposal.
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("INR resolution evidence must be retained.")


class InrFulfilmentReturn(models.Model):
    resolution = models.ForeignKey(InrSettlementResolution, on_delete=models.PROTECT, related_name="returns")
    fulfilment = models.OneToOneField(InrSettlementFulfilment, on_delete=models.PROTECT, related_name="physical_return")
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    method = models.CharField(max_length=16, choices=[("GOODS_RETURN", "Jewellery returned"),
        ("CASH_RECEIPT", "Refund money received back in cash"), ("BANK_CREDIT", "Refund money credited back")])
    external_reference = models.CharField(max_length=120)
    customer_confirmation = models.CharField(max_length=254)
    invoice_correction_reference = models.CharField(max_length=120, blank=True)
    top_up_refund_reference = models.CharField(max_length=120, blank=True)
    returned_at = models.DateTimeField()

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(amount__gt=0, amount__lte=Decimal("999999999999.99")), name="inr_return_amount_valid"),
            models.CheckConstraint(condition=models.Q(method__in=["GOODS_RETURN", "CASH_RECEIPT", "BANK_CREDIT"])
                & ~models.Q(external_reference="") & ~models.Q(customer_confirmation=""), name="inr_return_evidence_required"),
            models.UniqueConstraint(fields=["method", "external_reference"], name="inr_return_reference_unique"),
        ]

    def clean(self):
        super().clean()
        from .inr_correction_selectors import validate_inr_return
        validate_inr_return(self)

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("Physical return records are immutable.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Physical return evidence must be retained.")


class InStoreCashReceipt(models.Model):
    contribution = models.OneToOneField(
        Contribution,
        on_delete=models.PROTECT,
        related_name="cash_receipt",
    )
    receipt_reference = models.CharField(max_length=32, unique=True)
    idempotency_key = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    paper_receipt_number = models.CharField(
        max_length=80,
        null=True,
        blank=True,
        unique=True,
        help_text="Optional unique number from the showroom's paper receipt book.",
    )
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="received_in_store_cash_contributions",
    )
    received_by_label = models.CharField(max_length=254)
    received_at = models.DateTimeField(default=timezone.now)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-received_at", "-pk"]
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(receipt_reference=""),
                name="cash_receipt_reference_required",
            ),
            models.CheckConstraint(
                condition=~models.Q(received_by_label=""),
                name="cash_receipt_actor_label_required",
            ),
        ]
        indexes = [
            models.Index(fields=["received_at"], name="cash_receipt_time_idx"),
        ]

    def clean(self):
        super().clean()
        if self.contribution_id and (
            self.contribution.payment_channel != PaymentChannel.IN_STORE_CASH
            or self.contribution.payment_gateway != "in_store_cash"
        ):
            raise ValidationError(
                {"contribution": "The contribution is not an in-store cash payment."}
            )

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("Historical in-store cash receipts are immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Historical in-store cash receipts cannot be deleted.")

    def __str__(self):
        return f"{self.receipt_reference} — {self.contribution.scheme_account.scheme_number}"


class PaymentWebhookEvent(models.Model):
    class Status(models.TextChoices):
        RECEIVED = "RECEIVED", "Received"
        PROCESSED = "PROCESSED", "Processed"
        IGNORED = "IGNORED", "Ignored"
        FAILED = "FAILED", "Failed"
        REVIEW_REQUIRED = "REVIEW_REQUIRED", "Review required"

    gateway = models.CharField(max_length=30)
    gateway_mode = models.CharField(
        max_length=10,
        choices=GatewayMode.choices,
        blank=True,
        help_text="Provider environment that delivered the event.",
    )
    event_id = models.CharField(max_length=120)
    event_type = models.CharField(max_length=100)
    payload_sha256 = models.CharField(max_length=64)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.RECEIVED
    )
    contribution = models.ForeignKey(
        Contribution,
        on_delete=models.PROTECT,
        related_name="webhook_events",
        null=True,
        blank=True,
    )
    gateway_order_id = models.CharField(max_length=120, blank=True)
    gateway_reference = models.CharField(max_length=120, blank=True)
    failure_code = models.CharField(max_length=60, blank=True)
    error = models.TextField(blank=True)
    received_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-received_at", "-pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["gateway", "gateway_mode", "event_id"],
                name="unique_gateway_webhook_event",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        gateway="razorpay",
                        gateway_mode__in=[GatewayMode.TEST, GatewayMode.LIVE],
                    )
                    | (~models.Q(gateway="razorpay") & models.Q(gateway_mode=""))
                ),
                name="webhook_razorpay_mode_valid",
            ),
        ]
        indexes = [
            models.Index(
                fields=["gateway", "status", "received_at"],
                name="webhook_gateway_status_idx",
            ),
        ]

    def __str__(self):
        return f"{self.gateway} — {self.event_type} — {self.status}"


class WebhookProcessingAttempt(models.Model):
    class Source(models.TextChoices):
        PROVIDER_DELIVERY = "PROVIDER_DELIVERY", "Provider delivery"
        OWNER_RECOVERY = "OWNER_RECOVERY", "Owner recovery"

    class Outcome(models.TextChoices):
        PROCESSED = "PROCESSED", "Processed"
        IGNORED = "IGNORED", "Ignored"
        ALREADY_FINAL = "ALREADY_FINAL", "Already final"
        REVIEW_REQUIRED = "REVIEW_REQUIRED", "Review required"
        TRANSIENT_FAILURE = "TRANSIENT_FAILURE", "Transient failure"
        ELIGIBLE_FOR_RECOVERY = (
            "ELIGIBLE_FOR_RECOVERY",
            "Eligible for recovery",
        )
        ALREADY_PROCESSED = "ALREADY_PROCESSED", "Already processed"

    webhook_event = models.ForeignKey(
        PaymentWebhookEvent,
        on_delete=models.PROTECT,
        related_name="processing_attempts",
    )
    source = models.CharField(max_length=30, choices=Source.choices)
    outcome = models.CharField(max_length=30, choices=Outcome.choices)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="webhook_processing_attempts",
        null=True,
        blank=True,
    )
    actor_label = models.CharField(max_length=254)
    reason = models.TextField()
    error_code = models.CharField(max_length=60, blank=True)
    detail = models.TextField(blank=True)
    provider_snapshot = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(actor_label=""),
                name="webhook_attempt_actor_required",
            ),
            models.CheckConstraint(
                condition=~models.Q(reason=""),
                name="webhook_attempt_reason_required",
            ),
        ]
        indexes = [
            models.Index(
                fields=["webhook_event", "created_at"],
                name="webhook_attempt_event_idx",
            ),
        ]

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("Webhook processing attempts are immutable.")
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.webhook_event.event_id} — {self.get_outcome_display()}"


class SchemeRate(models.Model):
    class Metal(models.TextChoices):
        GOLD = "GOLD", "Gold"
        SILVER = "SILVER", "Silver"

    metal = models.CharField(max_length=10, choices=Metal.choices)
    metal_grade = models.ForeignKey(
        MetalGrade,
        on_delete=models.PROTECT,
        related_name="scheme_rates",
    )
    rate_per_gram = models.DecimalField(max_digits=14, decimal_places=4)
    purity = models.DecimalField(max_digits=7, decimal_places=6)
    effective_from = models.DateTimeField(default=timezone.now)
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="published_scheme_rates",
        null=True,
        blank=True,
        help_text="Null only for rate history migrated from the former provider architecture.",
    )
    published_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-effective_from", "-published_at", "-pk"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(metal__in=["GOLD", "SILVER"]),
                name="scheme_rate_valid_metal",
            ),
            models.CheckConstraint(
                condition=models.Q(rate_per_gram__gt=Decimal("0")),
                name="scheme_rate_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(purity__gt=Decimal("0"), purity__lte=Decimal("1")),
                name="scheme_rate_valid_purity",
            ),
        ]
        indexes = [
            models.Index(
                fields=["metal_grade", "effective_from"],
                name="scheme_rate_grade_time_idx",
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.metal_grade_id:
            if self.metal != self.metal_grade.metal:
                errors["metal"] = "The rate metal must match its metal grade."
            if self.purity != self.metal_grade.fineness:
                errors["purity"] = "The rate purity must match its metal grade."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("Published scheme rates are immutable.")
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.metal_grade.display_name} scheme rate at ₹{self.rate_per_gram}/g"


class PaymentOperationsControl(models.Model):
    """Single-business control plane for creating new payment exposure."""

    SINGLETON_PK = 1

    id = models.PositiveSmallIntegerField(
        primary_key=True,
        default=SINGLETON_PK,
        editable=False,
    )
    schedule_enabled = models.BooleanField(default=False)
    require_current_day_rate = models.BooleanField(default=True)
    global_pause = models.BooleanField(default=False)
    gold_pause = models.BooleanField(default=False)
    silver_pause = models.BooleanField(default=False)
    customer_message = models.CharField(max_length=240, blank=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="payment_operations_changes",
        null=True,
        blank=True,
    )
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        super().clean()
        if self.pk not in {None, self.SINGLETON_PK}:
            raise ValidationError("Only one payment operations control is permitted.")

    def save(self, *args, **kwargs):
        self.pk = self.SINGLETON_PK
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("The payment operations control cannot be deleted.")

    def __str__(self):
        return "Payment operations control"


class PaymentScheduleWindow(models.Model):
    class Weekday(models.IntegerChoices):
        MONDAY = 0, "Monday"
        TUESDAY = 1, "Tuesday"
        WEDNESDAY = 2, "Wednesday"
        THURSDAY = 3, "Thursday"
        FRIDAY = 4, "Friday"
        SATURDAY = 5, "Saturday"
        SUNDAY = 6, "Sunday"

    control = models.ForeignKey(
        PaymentOperationsControl,
        on_delete=models.PROTECT,
        related_name="schedule_windows",
    )
    weekday = models.PositiveSmallIntegerField(choices=Weekday.choices)
    enabled = models.BooleanField(default=True)
    opens_at = models.TimeField()
    closes_at = models.TimeField()

    class Meta:
        ordering = ["weekday"]
        constraints = [
            models.UniqueConstraint(
                fields=["control", "weekday"],
                name="payment_schedule_one_window_per_day",
            ),
            models.CheckConstraint(
                condition=models.Q(weekday__gte=0, weekday__lte=6),
                name="payment_schedule_valid_weekday",
            ),
            models.CheckConstraint(
                condition=models.Q(opens_at__lt=models.F("closes_at")),
                name="payment_schedule_positive_window",
            ),
        ]

    def __str__(self):
        return (
            f"{self.get_weekday_display()} "
            f"{self.opens_at:%H:%M}-{self.closes_at:%H:%M}"
        )


class MetalAllocation(models.Model):
    contribution = models.OneToOneField(
        Contribution,
        on_delete=models.PROTECT,
        related_name="metal_allocation",
    )
    scheme_rate = models.ForeignKey(
        SchemeRate,
        on_delete=models.PROTECT,
        related_name="metal_allocations",
    )
    metal = models.CharField(max_length=10, choices=SchemeRate.Metal.choices)
    metal_grade = models.ForeignKey(
        MetalGrade,
        on_delete=models.PROTECT,
        related_name="metal_allocations",
    )
    quantity = models.DecimalField(max_digits=18, decimal_places=6)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(metal__in=["GOLD", "SILVER"]),
                name="metal_allocation_valid_metal",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gt=Decimal("0")),
                name="metal_allocation_quantity_positive",
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.metal_grade_id and self.metal != self.metal_grade.metal:
            errors["metal"] = "The allocation metal must match its metal grade."
        if self.scheme_rate_id and self.metal_grade_id:
            if self.scheme_rate.metal_grade_id != self.metal_grade_id:
                errors["scheme_rate"] = "The allocation grade must match its locked rate."
        if self.contribution_id and self.metal_grade_id:
            if self.contribution.scheme_account.metal_grade_id != self.metal_grade_id:
                errors["metal_grade"] = "The allocation grade must match the scheme account."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("Historical metal allocations are immutable.")
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.quantity} g {self.metal_grade.display_name}"


class Redemption(models.Model):
    class SettlementType(models.TextChoices):
        JEWELLERY_PURCHASE = "JEWELLERY_PURCHASE", "Jewellery purchase"
        CASH = "CASH", "Cash"
        METAL = "METAL", "Metal"

    class Status(models.TextChoices):
        COMPLETED = "COMPLETED", "Completed"

    redemption_number = models.CharField(max_length=24, unique=True)
    idempotency_key = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    scheme_account = models.ForeignKey(
        SchemeAccount,
        on_delete=models.PROTECT,
        related_name="redemptions",
    )
    settlement_type = models.CharField(max_length=24, choices=SettlementType.choices)
    cash_amount = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True
    )
    cash_principal_amount = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True
    )
    cash_bonus_amount = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True
    )
    gold_quantity = models.DecimalField(
        max_digits=18, decimal_places=6, null=True, blank=True
    )
    silver_quantity = models.DecimalField(
        max_digits=18, decimal_places=6, null=True, blank=True
    )
    metal_grade = models.ForeignKey(
        MetalGrade,
        on_delete=models.PROTECT,
        related_name="redemptions",
        null=True,
        blank=True,
    )
    external_reference = models.CharField(max_length=120, blank=True)
    notes = models.TextField(blank=True)
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="processed_redemptions",
    )
    completed_at = models.DateTimeField(default=timezone.now)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.COMPLETED,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-completed_at", "-pk"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(
                        cash_amount__gt=Decimal("0"),
                        gold_quantity__isnull=True,
                        silver_quantity__isnull=True,
                    )
                    | models.Q(
                        cash_amount__isnull=True,
                        gold_quantity__gt=Decimal("0"),
                        silver_quantity__isnull=True,
                    )
                    | models.Q(
                        cash_amount__isnull=True,
                        gold_quantity__isnull=True,
                        silver_quantity__gt=Decimal("0"),
                    )
                ),
                name="redemption_exactly_one_positive_entitlement",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        cash_amount__isnull=True,
                        cash_principal_amount__isnull=True,
                        cash_bonus_amount__isnull=True,
                    )
                    | models.Q(
                        cash_amount__gt=Decimal("0"),
                        cash_principal_amount__gte=Decimal("0"),
                        cash_bonus_amount__gte=Decimal("0"),
                        cash_amount=(
                            models.F("cash_principal_amount")
                            + models.F("cash_bonus_amount")
                        ),
                    )
                ),
                name="redemption_cash_components_match_total",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(cash_amount__isnull=False, metal_grade__isnull=True)
                    | models.Q(cash_amount__isnull=True, metal_grade__isnull=False)
                ),
                name="redemption_metal_grade_required",
            ),
        ]
        indexes = [
            models.Index(
                fields=["scheme_account", "status", "completed_at"],
                name="redemption_account_status_idx",
            ),
        ]

    def clean(self):
        super().clean()
        if not self.scheme_account_id:
            return
        mode = self.scheme_account.savings_mode
        errors = {}
        if mode == SchemeAccount.SavingsMode.INR_CREDIT:
            raise ValidationError("INR purchase-credit settlement must not use legacy cash or metal redemption records.")
        if mode == SchemeAccount.SavingsMode.CASH:
            if self.metal_grade_id is not None:
                errors["metal_grade"] = "Cash redemptions cannot have a metal grade."
            if self.cash_amount is None:
                errors["cash_amount"] = "Cash schemes must redeem a cash entitlement."
            elif (
                self.cash_principal_amount is None
                or self.cash_bonus_amount is None
                or self.cash_principal_amount < 0
                or self.cash_bonus_amount < 0
                or self.cash_principal_amount + self.cash_bonus_amount
                != self.cash_amount
            ):
                errors["cash_amount"] = (
                    "Cash redemption principal and bonus components must match the total."
                )
            if self.settlement_type == self.SettlementType.METAL:
                errors["settlement_type"] = "Cash schemes cannot use metal settlement."
        elif mode == SchemeAccount.SavingsMode.GOLD:
            if self.metal_grade_id != self.scheme_account.metal_grade_id:
                errors["metal_grade"] = "Redemption grade must match the scheme account."
            if self.gold_quantity is None:
                errors["gold_quantity"] = "Gold schemes must redeem a gold entitlement."
            if self.settlement_type == self.SettlementType.CASH:
                errors["settlement_type"] = (
                    "Gold-to-cash conversion is not defined in the MVP."
                )
            if (
                self.cash_principal_amount is not None
                or self.cash_bonus_amount is not None
            ):
                errors["cash_amount"] = "Metal redemptions cannot contain cash components."
        elif mode == SchemeAccount.SavingsMode.SILVER:
            if self.metal_grade_id != self.scheme_account.metal_grade_id:
                errors["metal_grade"] = "Redemption grade must match the scheme account."
            if self.silver_quantity is None:
                errors["silver_quantity"] = "Silver schemes must redeem a silver entitlement."
            if self.settlement_type == self.SettlementType.CASH:
                errors["settlement_type"] = (
                    "Silver-to-cash conversion is not defined in the MVP."
                )
            if (
                self.cash_principal_amount is not None
                or self.cash_bonus_amount is not None
            ):
                errors["cash_amount"] = "Metal redemptions cannot contain cash components."
        if (
            self.settlement_type == self.SettlementType.JEWELLERY_PURCHASE
            and not self.external_reference.strip()
        ):
            errors["external_reference"] = (
                "An invoice or sales reference is required for a jewellery purchase."
            )
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("Historical redemptions are immutable.")
        return super().save(*args, **kwargs)

    @property
    def entitlement_amount(self):
        return self.cash_amount or self.gold_quantity or self.silver_quantity

    @property
    def entitlement_unit(self):
        if self.cash_amount is not None:
            return "INR"
        return f"g {self.metal_grade.display_name}"

    def __str__(self):
        return f"{self.redemption_number} — {self.scheme_account.scheme_number}"


class RedemptionReversal(models.Model):
    reversal_number = models.CharField(max_length=24, unique=True)
    redemption = models.OneToOneField(
        Redemption,
        on_delete=models.PROTECT,
        related_name="reversal",
    )
    reason = models.TextField()
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="processed_redemption_reversals",
    )
    reversed_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-reversed_at", "-pk"]
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(reason=""),
                name="redemption_reversal_reason_required",
            ),
        ]

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("Historical redemption reversals are immutable.")
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.reversal_number} — {self.redemption.redemption_number}"


class InStoreCashContributionReversal(models.Model):
    class ReasonCode(models.TextChoices):
        DUPLICATE_ENTRY = "DUPLICATE_ENTRY", "Duplicate entry"
        WRONG_ACCOUNT = "WRONG_ACCOUNT", "Wrong scheme account"
        WRONG_AMOUNT = "WRONG_AMOUNT", "Wrong amount"
        CASH_NOT_RECEIVED = "CASH_NOT_RECEIVED", "Cash was not received"

    contribution = models.OneToOneField(
        Contribution,
        on_delete=models.PROTECT,
        related_name="cash_reversal",
    )
    reversal_number = models.CharField(max_length=32, unique=True)
    reason_code = models.CharField(max_length=24, choices=ReasonCode.choices)
    reason = models.TextField()
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="processed_in_store_cash_reversals",
    )
    processed_by_label = models.CharField(max_length=254)
    reversed_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-reversed_at", "-pk"]
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(reversal_number=""),
                name="cash_reversal_number_required",
            ),
            models.CheckConstraint(
                condition=~models.Q(reason=""),
                name="cash_reversal_reason_required",
            ),
            models.CheckConstraint(
                condition=~models.Q(processed_by_label=""),
                name="cash_reversal_actor_label_required",
            ),
        ]
        indexes = [
            models.Index(fields=["reversed_at"], name="cash_reversal_time_idx"),
        ]

    def clean(self):
        super().clean()
        if self.contribution_id and (
            self.contribution.payment_channel != PaymentChannel.IN_STORE_CASH
        ):
            raise ValidationError(
                {"contribution": "Only an in-store cash contribution can be reversed."}
            )

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError(
                "Historical in-store cash contribution reversals are immutable."
            )
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError(
            "Historical in-store cash contribution reversals cannot be deleted."
        )

    def __str__(self):
        return f"{self.reversal_number} — {self.contribution.gateway_reference}"


class SchemeReminder(models.Model):
    class Kind(models.TextChoices):
        UPCOMING_ELIGIBILITY = (
            "UPCOMING_ELIGIBILITY",
            "Upcoming eligibility",
        )
        UPCOMING_MONTHLY_COMPLETION = (
            "UPCOMING_MONTHLY_COMPLETION",
            "Upcoming monthly completion",
        )
        ALLOCATION_EXCEPTION = (
            "ALLOCATION_EXCEPTION",
            "Allocation exception",
        )
        COMPLETED_REDEMPTION = (
            "COMPLETED_REDEMPTION",
            "Completed redemption",
        )

    class Audience(models.TextChoices):
        CUSTOMER = "CUSTOMER", "Customer"
        OWNER = "OWNER", "Owner"

    idempotency_key = models.CharField(max_length=64, unique=True, editable=False)
    kind = models.CharField(max_length=32, choices=Kind.choices)
    audience = models.CharField(max_length=10, choices=Audience.choices)
    recipient_email = models.EmailField()
    scheme_account = models.ForeignKey(
        SchemeAccount,
        on_delete=models.PROTECT,
        related_name="reminders",
    )
    contribution = models.ForeignKey(
        Contribution,
        on_delete=models.PROTECT,
        related_name="reminders",
        null=True,
        blank=True,
    )
    redemption = models.ForeignKey(
        Redemption,
        on_delete=models.PROTECT,
        related_name="reminders",
        null=True,
        blank=True,
    )
    event_date = models.DateField()
    eligibility_lead_days = models.PositiveSmallIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    kind__in=[
                        "UPCOMING_ELIGIBILITY",
                        "UPCOMING_MONTHLY_COMPLETION",
                        "ALLOCATION_EXCEPTION",
                        "COMPLETED_REDEMPTION",
                    ]
                ),
                name="scheme_reminder_kind_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(audience__in=["CUSTOMER", "OWNER"]),
                name="scheme_reminder_audience_valid",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        kind__in=["UPCOMING_ELIGIBILITY", "UPCOMING_MONTHLY_COMPLETION"],
                        contribution__isnull=True,
                        redemption__isnull=True,
                        eligibility_lead_days__isnull=False,
                    )
                    | models.Q(
                        kind="ALLOCATION_EXCEPTION",
                        contribution__isnull=False,
                        redemption__isnull=True,
                        eligibility_lead_days__isnull=True,
                    )
                    | models.Q(
                        kind="COMPLETED_REDEMPTION",
                        contribution__isnull=True,
                        redemption__isnull=False,
                        eligibility_lead_days__isnull=True,
                    )
                ),
                name="scheme_reminder_target_shape_valid",
            ),
        ]
        indexes = [
            models.Index(
                fields=["kind", "event_date"],
                name="scheme_reminder_kind_date_idx",
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.contribution_id:
            if self.contribution.scheme_account_id != self.scheme_account_id:
                errors["contribution"] = (
                    "The reminder contribution must belong to its scheme account."
                )
        if self.redemption_id:
            if self.redemption.scheme_account_id != self.scheme_account_id:
                errors["redemption"] = (
                    "The reminder redemption must belong to its scheme account."
                )
        if self.kind == self.Kind.UPCOMING_ELIGIBILITY:
            if self.event_date != self.scheme_account.eligible_from:
                errors["event_date"] = (
                    "An eligibility reminder must retain the contractual eligibility date."
                )
        if self.kind == self.Kind.UPCOMING_MONTHLY_COMPLETION:
            from .instalments import has_monthly_instalments
            # Structural validation only: later reversals/holds must not invalidate
            # immutable historical notification evidence. Delivery rechecks policy.
            if not has_monthly_instalments(self.scheme_account):
                errors["kind"] = "Monthly completion requires a recorded monthly agreement."
            periods = self.scheme_account.instalment_periods
            has_boundary = periods.filter(ends_before=self.event_date).exists() if self.event_date else False
            if self.event_date == self.scheme_account.eligible_from:
                has_boundary = periods.filter(ends_before__lte=self.event_date).exists()
            if (not self.event_date or self.event_date < self.scheme_account.eligible_from or not has_boundary):
                errors["event_date"] = "Monthly completion must retain the later of minimum duration and a recorded qualifying-period end."
        if self.kind in (self.Kind.UPCOMING_ELIGIBILITY, self.Kind.UPCOMING_MONTHLY_COMPLETION):
            if not self.eligibility_lead_days:
                errors["eligibility_lead_days"] = (
                    "An upcoming eligibility reminder requires a positive lead time."
                )
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("Historical scheme reminders are immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Historical scheme reminders cannot be deleted.")

    @property
    def delivery_status(self):
        attempts = list(self.delivery_attempts.all())
        if any(
            attempt.outcome == SchemeReminderDeliveryAttempt.Outcome.ACCEPTED
            for attempt in attempts
        ):
            return "Accepted by email provider"
        if attempts:
            return "Delivery failed"
        return "Pending delivery"

    @property
    def latest_delivery_attempt(self):
        attempts = list(self.delivery_attempts.all())
        return attempts[-1] if attempts else None

    def __str__(self):
        return (
            f"{self.get_kind_display()} — {self.scheme_account.scheme_number} "
            f"— {self.recipient_email}"
        )


class SchemeReminderDeliveryAttempt(models.Model):
    class Outcome(models.TextChoices):
        ACCEPTED = "ACCEPTED", "Accepted by email provider"
        FAILED = "FAILED", "Failed"

    reminder = models.ForeignKey(
        SchemeReminder,
        on_delete=models.PROTECT,
        related_name="delivery_attempts",
    )
    outcome = models.CharField(max_length=12, choices=Outcome.choices)
    backend = models.CharField(max_length=200)
    accepted_count = models.PositiveSmallIntegerField(default=0)
    error_code = models.CharField(max_length=100, blank=True)
    attempted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["attempted_at", "pk"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(outcome__in=["ACCEPTED", "FAILED"]),
                name="scheme_reminder_attempt_outcome_valid",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        outcome="ACCEPTED",
                        accepted_count=1,
                        error_code="",
                    )
                    | (
                        models.Q(
                            outcome="FAILED",
                            accepted_count=0,
                        )
                        & ~models.Q(error_code="")
                    )
                ),
                name="scheme_reminder_attempt_result_valid",
            ),
        ]
        indexes = [
            models.Index(
                fields=["reminder", "attempted_at"],
                name="scheme_rem_attempt_time_idx",
            ),
        ]

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("Historical reminder delivery attempts are immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Historical reminder delivery attempts cannot be deleted.")

    def __str__(self):
        return f"{self.reminder} — {self.get_outcome_display()}"


class AuditEvent(models.Model):
    class Action(models.TextChoices):
        CUSTOMER_ENROLMENT = "CUSTOMER_ENROLMENT", "Customer enrolment"
        ENROLMENT_REQUEST_SUBMITTED = (
            "ENROLMENT_REQUEST_SUBMITTED",
            "Enrolment request submitted",
        )
        ENROLMENT_REQUEST_WITHDRAWN = (
            "ENROLMENT_REQUEST_WITHDRAWN",
            "Enrolment request withdrawn",
        )
        ENROLMENT_REQUEST_DECLINED = (
            "ENROLMENT_REQUEST_DECLINED",
            "Enrolment request declined",
        )
        ENROLMENT_REQUEST_EXPIRED = (
            "ENROLMENT_REQUEST_EXPIRED",
            "Enrolment request expired",
        )
        ENROLMENT_REQUEST_ENROLLED = (
            "ENROLMENT_REQUEST_ENROLLED",
            "Enrolment request enrolled",
        )
        SCHEME_CHANGE = "SCHEME_CHANGE", "Scheme change"
        MANUAL_PAYMENT_CORRECTION = (
            "MANUAL_PAYMENT_CORRECTION",
            "Manual payment correction",
        )
        IN_STORE_CASH_RECEIPT = "IN_STORE_CASH_RECEIPT", "In-store cash receipt"
        IN_STORE_CASH_REVERSAL = "IN_STORE_CASH_REVERSAL", "In-store cash reversal"
        SCHEME_RATE_PUBLICATION = "SCHEME_RATE_PUBLICATION", "Scheme rate publication"
        REDEMPTION = "REDEMPTION", "Redemption"
        REVERSAL = "REVERSAL", "Reversal"
        ALLOCATION_RETRY = "ALLOCATION_RETRY", "Allocation retry"
        PAYMENT_ORDER_RECONCILIATION = (
            "PAYMENT_ORDER_RECONCILIATION",
            "Payment order reconciliation",
        )
        PAYMENT_OPERATIONS_CHANGE = (
            "PAYMENT_OPERATIONS_CHANGE",
            "Payment operations change",
        )
        WEBHOOK_RECOVERY = "WEBHOOK_RECOVERY", "Webhook recovery"

    action = models.CharField(max_length=40, choices=Action.choices)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="scheme_audit_events",
        null=True,
        blank=True,
    )
    actor_label = models.CharField(max_length=254)
    reason = models.TextField()
    scheme_plan = models.ForeignKey(
        SchemePlan,
        on_delete=models.PROTECT,
        related_name="audit_events",
        null=True,
        blank=True,
    )
    scheme_account = models.ForeignKey(
        SchemeAccount,
        on_delete=models.PROTECT,
        related_name="audit_events",
        null=True,
        blank=True,
    )
    contribution = models.ForeignKey(
        Contribution,
        on_delete=models.PROTECT,
        related_name="audit_events",
        null=True,
        blank=True,
    )
    scheme_rate = models.ForeignKey(
        SchemeRate,
        on_delete=models.PROTECT,
        related_name="audit_events",
        null=True,
        blank=True,
    )
    redemption = models.ForeignKey(
        Redemption,
        on_delete=models.PROTECT,
        related_name="audit_events",
        null=True,
        blank=True,
    )
    details = models.JSONField(default=dict, blank=True)
    occurred_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-occurred_at", "-pk"]
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(actor_label=""),
                name="audit_event_actor_label_required",
            ),
            models.CheckConstraint(
                condition=~models.Q(reason=""),
                name="audit_event_reason_required",
            ),
        ]
        indexes = [
            models.Index(fields=["action", "occurred_at"], name="audit_action_time_idx"),
        ]

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("Historical audit events are immutable.")
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.get_action_display()} — {self.actor_label}"
