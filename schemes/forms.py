import uuid
from decimal import Decimal

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password

from .models import Redemption, SchemeAccount, SchemePlan, SchemeRate
from .services import cash_scheme_activity_is_enabled, validate_contribution_allowed


class CustomerCreateForm(forms.Form):
    full_name = forms.CharField(max_length=200)
    email = forms.EmailField(max_length=150)
    mobile_number = forms.CharField(max_length=20)
    address = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), required=False)
    password1 = forms.CharField(label="Temporary password", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Confirm temporary password", widget=forms.PasswordInput)

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if get_user_model().objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("A user with this email already exists.")
        return email

    def clean(self):
        cleaned = super().clean()
        password = cleaned.get("password1")
        if password and password != cleaned.get("password2"):
            self.add_error("password2", "The passwords do not match.")
        if password:
            validate_password(password)
        return cleaned


class SchemePlanForm(forms.ModelForm):
    class Meta:
        model = SchemePlan
        fields = [
            "name",
            "code",
            "description",
            "minimum_months",
            "default_months",
            "amount_rule",
            "frequency_rule",
            "fixed_contribution_amount",
            "minimum_contribution",
            "maximum_contribution",
            "allow_contributions_after_eligibility",
            "cash_bonus_percentage",
            "cash_bonus_minimum_months",
            "active",
        ]

        help_texts = {
            "cash_bonus_percentage": (
                "Applies only to cash schemes. Use 0 to disable cash bonus."
            ),
            "cash_bonus_minimum_months": (
                "The customer's agreed duration must meet this minimum."
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not cash_scheme_activity_is_enabled():
            self.fields.pop("cash_bonus_percentage", None)
            self.fields.pop("cash_bonus_minimum_months", None)


class SchemePlanChangeForm(SchemePlanForm):
    class Meta(SchemePlanForm.Meta):
        fields = [*SchemePlanForm.Meta.fields, "publicly_listed"]
        help_texts = {
            **SchemePlanForm.Meta.help_texts,
            "publicly_listed": (
                "Publishes this savings plan's name, description, contribution amounts, "
                "frequency, and duration when the plan is active."
            ),
        }

    audit_reason = forms.CharField(
        label="Reason for change",
        widget=forms.Textarea(attrs={"rows": 2}),
        help_text="Recorded in the immutable owner audit log.",
    )


class EnrolmentForm(forms.Form):
    plan = forms.ModelChoiceField(queryset=SchemePlan.objects.none())
    savings_mode = forms.ChoiceField(choices=SchemeAccount.SavingsMode.choices)
    start_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    agreed_months = forms.IntegerField(min_value=12)
    audit_reason = forms.CharField(
        label="Reason for enrolment",
        widget=forms.Textarea(attrs={"rows": 2}),
        help_text="Recorded with your identity and timestamp.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["plan"].queryset = SchemePlan.objects.filter(active=True)
        if not cash_scheme_activity_is_enabled():
            self.fields["savings_mode"].choices = [
                choice
                for choice in SchemeAccount.SavingsMode.choices
                if choice[0] != SchemeAccount.SavingsMode.CASH
            ]

    def clean(self):
        cleaned = super().clean()
        plan = cleaned.get("plan")
        agreed_months = cleaned.get("agreed_months")
        if plan and agreed_months and agreed_months < plan.minimum_months:
            self.add_error(
                "agreed_months",
                f"This plan requires at least {plan.minimum_months} months.",
            )
        return cleaned


class ContributionForm(forms.Form):
    amount = forms.DecimalField(
        label="Contribution amount",
        max_digits=14,
        decimal_places=2,
        min_value=0.01,
    )

    def __init__(self, *args, scheme_account, **kwargs):
        super().__init__(*args, **kwargs)
        self.scheme_account = scheme_account
        if scheme_account.amount_rule_snapshot == SchemePlan.AmountRule.FIXED:
            self.fields["amount"].initial = scheme_account.fixed_amount_snapshot
            self.fields["amount"].disabled = True
            self.fields["amount"].help_text = "This scheme has a fixed contribution amount."
        else:
            maximum = scheme_account.maximum_amount_snapshot
            boundary = f"Minimum ₹{scheme_account.minimum_amount_snapshot}"
            if maximum is not None:
                boundary += f"; maximum ₹{maximum}"
            self.fields["amount"].help_text = boundary

    def clean_amount(self):
        amount = self.cleaned_data["amount"]
        validated_amount, _ = validate_contribution_allowed(self.scheme_account, amount)
        return validated_amount


class SchemeRatePublishForm(forms.Form):
    LARGE_CHANGE_PERCENT = Decimal("5.00")

    metal = forms.ChoiceField(choices=SchemeRate.Metal.choices)
    rate_per_gram = forms.DecimalField(
        label="New Scheme Rate per gram",
        max_digits=14,
        decimal_places=4,
        min_value=Decimal("0.0001"),
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
        help_text="Optional operational note recorded with this publication.",
    )
    confirm_large_change = forms.BooleanField(
        required=False,
        label="I have checked and confirm this unusually large rate change.",
    )

    def __init__(self, *args, current_rates=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.current_rates = current_rates or {}
        self.current_rate = None
        self.difference = None
        self.percentage_difference = None
        self.requires_confirmation = False

    def clean(self):
        cleaned = super().clean()
        metal = cleaned.get("metal")
        new_rate = cleaned.get("rate_per_gram")
        self.current_rate = self.current_rates.get(metal)
        if self.current_rate is None or new_rate is None:
            return cleaned

        self.difference = new_rate - self.current_rate.rate_per_gram
        self.percentage_difference = (
            self.difference / self.current_rate.rate_per_gram * Decimal("100")
        ).quantize(Decimal("0.01"))
        self.requires_confirmation = (
            abs(self.percentage_difference) > self.LARGE_CHANGE_PERCENT
        )
        if self.requires_confirmation and not cleaned.get("confirm_large_change"):
            self.add_error(
                "confirm_large_change",
                f"This change exceeds {self.LARGE_CHANGE_PERCENT:.0f}%. "
                "Check the values and confirm before publishing.",
            )
        return cleaned


class RedemptionForm(forms.Form):
    settlement_type = forms.ChoiceField(choices=())
    amount = forms.DecimalField(label="Amount to redeem", min_value=Decimal("0.01"))
    external_reference = forms.CharField(
        label="Invoice / settlement reference",
        max_length=120,
        required=False,
    )
    notes = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), required=False)
    audit_reason = forms.CharField(
        label="Reason for redemption",
        widget=forms.Textarea(attrs={"rows": 2}),
        help_text="Recorded with your identity and timestamp.",
    )
    idempotency_key = forms.UUIDField(widget=forms.HiddenInput)

    def __init__(self, *args, scheme_account, outstanding, **kwargs):
        super().__init__(*args, **kwargs)
        self.scheme_account = scheme_account
        self.outstanding = outstanding
        self.fields["idempotency_key"].initial = uuid.uuid4()
        if scheme_account.savings_mode == SchemeAccount.SavingsMode.CASH:
            self.fields["settlement_type"].choices = [
                choice
                for choice in Redemption.SettlementType.choices
                if choice[0]
                in {
                    Redemption.SettlementType.CASH,
                    Redemption.SettlementType.JEWELLERY_PURCHASE,
                }
            ]
            self.fields["amount"] = forms.DecimalField(
                label="Cash principal to redeem",
                max_digits=14,
                decimal_places=2,
                min_value=Decimal("0.01"),
                max_value=outstanding,
                help_text=f"Outstanding principal: ₹{outstanding:.2f}",
            )
        else:
            metal_name = scheme_account.get_savings_mode_display()
            self.fields["settlement_type"].choices = [
                choice
                for choice in Redemption.SettlementType.choices
                if choice[0]
                in {
                    Redemption.SettlementType.METAL,
                    Redemption.SettlementType.JEWELLERY_PURCHASE,
                }
            ]
            self.fields["amount"] = forms.DecimalField(
                label=f"{metal_name} quantity to redeem (g)",
                max_digits=18,
                decimal_places=6,
                min_value=Decimal("0.000001"),
                max_value=outstanding,
                help_text=f"Outstanding entitlement: {outstanding:.6f} g",
            )

    def clean(self):
        cleaned = super().clean()
        if (
            cleaned.get("settlement_type")
            == Redemption.SettlementType.JEWELLERY_PURCHASE
            and not cleaned.get("external_reference", "").strip()
        ):
            self.add_error(
                "external_reference",
                "Enter the jewellery invoice or sales reference.",
            )
        return cleaned


class AuditReasonForm(forms.Form):
    reason = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 2}),
        help_text="Recorded with your identity and timestamp.",
    )


class RedemptionReversalForm(AuditReasonForm):
    reason = forms.CharField(
        label="Reason for reversal",
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text=(
            "This appends a compensating event and restores the entitlement. "
            "The original redemption remains visible."
        ),
    )
