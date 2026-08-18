import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


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
    active = models.BooleanField(default=True)
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
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.name} ({self.code})"


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
        ]

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

    def __str__(self):
        return f"{self.scheme_number} — {self.customer.full_name}"


class Contribution(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        PAID = "PAID", "Paid"
        PAID_UNALLOCATED = "PAID_UNALLOCATED", "Paid — allocation pending"
        FAILED = "FAILED", "Failed"

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
    gateway_order_id = models.CharField(max_length=120, null=True, blank=True, unique=True)
    gateway_reference = models.CharField(max_length=120, null=True, blank=True, unique=True)
    gateway_signature = models.CharField(max_length=128, blank=True)
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
                    models.Q(
                        status__in=["PAID", "PAID_UNALLOCATED"],
                        paid_at__isnull=False,
                        gateway_reference__isnull=False,
                    )
                    | models.Q(status__in=["PENDING", "FAILED"], paid_at__isnull=True)
                ),
                name="paid_contribution_has_confirmation",
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
        ]

    def __str__(self):
        return f"{self.scheme_account.scheme_number} — ₹{self.amount} — {self.status}"


class PaymentWebhookEvent(models.Model):
    class Status(models.TextChoices):
        RECEIVED = "RECEIVED", "Received"
        PROCESSED = "PROCESSED", "Processed"
        IGNORED = "IGNORED", "Ignored"
        FAILED = "FAILED", "Failed"

    gateway = models.CharField(max_length=30)
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
    error = models.TextField(blank=True)
    received_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-received_at", "-pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["gateway", "event_id"],
                name="unique_gateway_webhook_event",
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


class RateSnapshot(models.Model):
    class Metal(models.TextChoices):
        GOLD = "GOLD", "24K Gold"
        SILVER = "SILVER", "Silver"

    metal = models.CharField(max_length=10, choices=Metal.choices)
    provider = models.CharField(max_length=50)
    provider_timestamp = models.DateTimeField()
    fetched_at = models.DateTimeField(auto_now_add=True)
    provider_rate = models.DecimalField(max_digits=14, decimal_places=4)
    applied_rate = models.DecimalField(max_digits=14, decimal_places=4)
    purity = models.DecimalField(max_digits=6, decimal_places=4)

    class Meta:
        ordering = ["-fetched_at", "-pk"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(metal__in=["GOLD", "SILVER"]),
                name="rate_snapshot_valid_metal",
            ),
            models.CheckConstraint(
                condition=models.Q(provider_rate__gt=Decimal("0")),
                name="provider_rate_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(applied_rate__gt=Decimal("0")),
                name="applied_rate_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(purity__gt=Decimal("0"), purity__lte=Decimal("1")),
                name="rate_snapshot_valid_purity",
            ),
        ]

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("Historical rate snapshots are immutable.")
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.get_metal_display()} at ₹{self.applied_rate}/g ({self.provider})"


class MetalAllocation(models.Model):
    contribution = models.OneToOneField(
        Contribution,
        on_delete=models.PROTECT,
        related_name="metal_allocation",
    )
    rate_snapshot = models.OneToOneField(
        RateSnapshot,
        on_delete=models.PROTECT,
        related_name="metal_allocation",
    )
    metal = models.CharField(max_length=10, choices=RateSnapshot.Metal.choices)
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

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("Historical metal allocations are immutable.")
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.quantity} g {self.get_metal_display()}"


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
    gold_quantity = models.DecimalField(
        max_digits=18, decimal_places=6, null=True, blank=True
    )
    silver_quantity = models.DecimalField(
        max_digits=18, decimal_places=6, null=True, blank=True
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
            if self.cash_amount is None:
                errors["cash_amount"] = "Cash schemes must redeem a cash entitlement."
            if self.settlement_type == self.SettlementType.METAL:
                errors["settlement_type"] = "Cash schemes cannot use metal settlement."
        elif mode == SchemeAccount.SavingsMode.GOLD:
            if self.gold_quantity is None:
                errors["gold_quantity"] = "Gold schemes must redeem a gold entitlement."
            if self.settlement_type == self.SettlementType.CASH:
                errors["settlement_type"] = (
                    "Gold-to-cash conversion is not defined in the MVP."
                )
        elif mode == SchemeAccount.SavingsMode.SILVER:
            if self.silver_quantity is None:
                errors["silver_quantity"] = "Silver schemes must redeem a silver entitlement."
            if self.settlement_type == self.SettlementType.CASH:
                errors["settlement_type"] = (
                    "Silver-to-cash conversion is not defined in the MVP."
                )
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
        if self.gold_quantity is not None:
            return "g gold"
        return "g silver"

    def __str__(self):
        return f"{self.redemption_number} — {self.scheme_account.scheme_number}"
