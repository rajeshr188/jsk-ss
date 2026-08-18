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
        return self.Status(self.effective_status).label

    def __str__(self):
        return f"{self.scheme_number} — {self.customer.full_name}"

