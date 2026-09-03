import uuid
from decimal import Decimal

from django import forms
from django.contrib.auth import get_user_model

from .models import (
    MetalGrade,
    PaymentOperationsControl,
    PaymentScheduleWindow,
    Redemption,
    SchemeAccount,
    SchemePlan,
    SchemePlanOffering,
    SchemeRate,
)
from .services import cash_scheme_activity_is_enabled, validate_contribution_allowed


class CustomerCreateForm(forms.Form):
    full_name = forms.CharField(max_length=200)
    email = forms.EmailField(max_length=150)
    mobile_number = forms.CharField(max_length=20)
    address = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), required=False)

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if get_user_model().objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("A user with this email already exists.")
        return email

class SchemePlanForm(forms.ModelForm):
    metal_grades = forms.ModelMultipleChoiceField(
        queryset=MetalGrade.objects.none(),
        label="Metal grades offered for new enrolment",
        widget=forms.CheckboxSelectMultiple,
        help_text=(
            "Each new scheme account is permanently tied to one selected grade. "
            "Existing accounts are unaffected when an offering is disabled."
        ),
    )

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
        self.fields["metal_grades"].queryset = MetalGrade.objects.all()
        if self.instance.pk:
            self.fields["metal_grades"].initial = MetalGrade.objects.filter(
                plan_offerings__plan=self.instance,
                plan_offerings__active=True,
            )
        elif not self.is_bound:
            self.fields["metal_grades"].initial = MetalGrade.objects.filter(
                code__in=[MetalGrade.GOLD_22K_916, MetalGrade.SILVER_999]
            )
        if not cash_scheme_activity_is_enabled():
            self.fields.pop("cash_bonus_percentage", None)
            self.fields.pop("cash_bonus_minimum_months", None)

    def save_offerings(self):
        selected_ids = set(self.cleaned_data["metal_grades"].values_list("pk", flat=True))
        existing = {
            offering.metal_grade_id: offering
            for offering in self.instance.metal_offerings.all()
        }
        for grade in MetalGrade.objects.all():
            active = grade.pk in selected_ids
            offering = existing.get(grade.pk)
            if offering is None:
                SchemePlanOffering.objects.create(
                    plan=self.instance,
                    metal_grade=grade,
                    active=active,
                )
            elif offering.active != active:
                offering.active = active
                offering.save(update_fields=["active", "updated_at"])


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
    metal_grade = forms.ModelChoiceField(
        queryset=MetalGrade.objects.none(),
        label="Metal grade",
    )
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
        self.fields["metal_grade"].queryset = MetalGrade.objects.filter(
            plan_offerings__active=True,
            plan_offerings__plan__active=True,
        ).distinct()

    def clean(self):
        cleaned = super().clean()
        plan = cleaned.get("plan")
        metal_grade = cleaned.get("metal_grade")
        agreed_months = cleaned.get("agreed_months")
        if plan and metal_grade and not SchemePlanOffering.objects.filter(
            plan=plan,
            metal_grade=metal_grade,
            active=True,
        ).exists():
            self.add_error(
                "metal_grade",
                "This metal grade is not offered by the selected plan.",
            )
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


class PaymentOperationsForm(forms.Form):
    schedule_enabled = forms.BooleanField(
        required=False,
        label="Use the weekly payment schedule",
        help_text=(
            "When disabled, the weekly hours do not restrict payments; manual and "
            "environment pauses still apply."
        ),
    )
    require_current_day_rate = forms.BooleanField(
        required=False,
        label="Require a Scheme Rate published today before scheduled opening",
    )
    global_pause = forms.BooleanField(
        required=False,
        label="Pause all new online contributions",
    )
    gold_pause = forms.BooleanField(
        required=False,
        label="Pause new gold contributions",
    )
    silver_pause = forms.BooleanField(
        required=False,
        label="Pause new silver contributions",
    )
    customer_message = forms.CharField(
        required=False,
        max_length=240,
        label="Optional customer message",
        help_text="Shown instead of the standard temporary-closure explanation.",
    )
    audit_reason = forms.CharField(
        label="Reason for change",
        widget=forms.Textarea(attrs={"rows": 2}),
        help_text="Recorded with your identity and the before/after policy.",
    )

    def __init__(self, *args, control: PaymentOperationsControl, **kwargs):
        super().__init__(*args, **kwargs)
        self.control = control
        for name in (
            "schedule_enabled",
            "require_current_day_rate",
            "global_pause",
            "gold_pause",
            "silver_pause",
        ):
            self.fields[name].widget.attrs["class"] = "form-check-input"
        self.fields["customer_message"].widget.attrs["class"] = "form-control"
        self.fields["audit_reason"].widget.attrs["class"] = "form-control"
        windows = {window.weekday: window for window in control.schedule_windows.all()}
        if not self.is_bound:
            for name in (
                "schedule_enabled",
                "require_current_day_rate",
                "global_pause",
                "gold_pause",
                "silver_pause",
                "customer_message",
            ):
                self.initial[name] = getattr(control, name)
        self.schedule_rows = []
        for weekday, label in PaymentScheduleWindow.Weekday.choices:
            window = windows[weekday]
            enabled_name = f"day_{weekday}_enabled"
            opens_name = f"day_{weekday}_opens_at"
            closes_name = f"day_{weekday}_closes_at"
            self.fields[enabled_name] = forms.BooleanField(
                required=False,
                label=f"{label} enabled",
                initial=window.enabled,
                widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
            )
            self.fields[opens_name] = forms.TimeField(
                label=f"{label} opens",
                initial=window.opens_at,
                input_formats=["%H:%M"],
                widget=forms.TimeInput(
                    format="%H:%M",
                    attrs={"type": "time", "class": "form-control"},
                ),
            )
            self.fields[closes_name] = forms.TimeField(
                label=f"{label} closes",
                initial=window.closes_at,
                input_formats=["%H:%M"],
                widget=forms.TimeInput(
                    format="%H:%M",
                    attrs={"type": "time", "class": "form-control"},
                ),
            )
            self.schedule_rows.append(
                {
                    "label": label,
                    "enabled": self[enabled_name],
                    "opens_at": self[opens_name],
                    "closes_at": self[closes_name],
                }
            )

    def clean(self):
        cleaned = super().clean()
        for weekday, label in PaymentScheduleWindow.Weekday.choices:
            opens_at = cleaned.get(f"day_{weekday}_opens_at")
            closes_at = cleaned.get(f"day_{weekday}_closes_at")
            if opens_at is not None and closes_at is not None and opens_at >= closes_at:
                self.add_error(
                    f"day_{weekday}_closes_at",
                    f"{label} closing time must be after its opening time.",
                )
        return cleaned

    def schedule_values(self):
        return {
            weekday: {
                "enabled": self.cleaned_data[f"day_{weekday}_enabled"],
                "opens_at": self.cleaned_data[f"day_{weekday}_opens_at"],
                "closes_at": self.cleaned_data[f"day_{weekday}_closes_at"],
            }
            for weekday, _label in PaymentScheduleWindow.Weekday.choices
        }


class SchemeRatePublishForm(forms.Form):
    LARGE_CHANGE_PERCENT = Decimal("5.00")

    metal_grade = forms.ModelChoiceField(
        queryset=MetalGrade.objects.none(),
        label="Metal grade",
    )
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
        self.fields["metal_grade"].queryset = MetalGrade.objects.all()
        self.current_rates = current_rates or {}
        self.current_rate = None
        self.difference = None
        self.percentage_difference = None
        self.requires_confirmation = False

    def clean(self):
        cleaned = super().clean()
        metal_grade = cleaned.get("metal_grade")
        new_rate = cleaned.get("rate_per_gram")
        self.current_rate = (
            self.current_rates.get(metal_grade.code) if metal_grade else None
        )
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
            metal_name = scheme_account.entitlement_name
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
                help_text=f"Exact outstanding entitlement: {outstanding:.6f} g",
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


class WebhookRecoveryForm(forms.Form):
    class Action:
        INSPECT = "INSPECT"
        APPLY = "APPLY"

    action = forms.ChoiceField(
        choices=[
            (Action.INSPECT, "Check provider"),
            (Action.APPLY, "Apply verified recovery"),
        ]
    )
    reason = forms.CharField(
        label="Reason for recovery check",
        widget=forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
        help_text=(
            "Recorded with your identity and the provider comparison. Checking does "
            "not create entitlement; Apply still requires an exact captured-payment match."
        ),
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
