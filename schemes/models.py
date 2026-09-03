import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

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
        GOLD = "GOLD", "Gold Savings"
        SILVER = "SILVER", "Silver Savings"

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        REDEMPTION_ELIGIBLE = "REDEMPTION_ELIGIBLE", "Redemption eligible"
        REDEEMED = "REDEEMED", "Redeemed"

    scheme_number = models.CharField(max_length=24, unique=True)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="scheme_accounts")
    plan = models.ForeignKey(SchemePlan, on_delete=models.PROTECT, related_name="scheme_accounts")
    start_date = models.DateField()
    agreed_months = models.PositiveSmallIntegerField(validators=[MinValueValidator(12)])
    eligible_from = models.DateField()
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
        max_length=20, choices=SchemePlan.FrequencyRule.choices
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
                condition=models.Q(agreed_months__gte=12),
                name="account_agreed_months_gte_12",
            ),
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
                    models.Q(savings_mode="CASH", metal_grade__isnull=True)
                    | models.Q(
                        savings_mode__in=["GOLD", "SILVER"],
                        metal_grade__isnull=False,
                    )
                ),
                name="account_metal_grade_required",
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}
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
    def effective_status(self):
        if self.status == self.Status.REDEEMED:
            return self.Status.REDEEMED
        if timezone.localdate() >= self.eligible_from:
            return self.Status.REDEMPTION_ELIGIBLE
        return self.Status.ACTIVE

    @property
    def effective_status_label(self):
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


class GatewayMode(models.TextChoices):
    TEST = "test", "Test"
    LIVE = "live", "Live"


class Contribution(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        PAID = "PAID", "Paid"
        PAID_UNALLOCATED = "PAID_UNALLOCATED", "Paid — allocation pending"
        FAILED = "FAILED", "Failed"
        ABANDONED = "ABANDONED", "Abandoned"

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
                        status__in=["PAID", "PAID_UNALLOCATED"],
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

    def __str__(self):
        return f"{self.scheme_account.scheme_number} — ₹{self.amount} — {self.status}"


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


class AuditEvent(models.Model):
    class Action(models.TextChoices):
        CUSTOMER_ENROLMENT = "CUSTOMER_ENROLMENT", "Customer enrolment"
        SCHEME_CHANGE = "SCHEME_CHANGE", "Scheme change"
        MANUAL_PAYMENT_CORRECTION = (
            "MANUAL_PAYMENT_CORRECTION",
            "Manual payment correction",
        )
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
