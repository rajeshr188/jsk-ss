import uuid
from decimal import Decimal

from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import signing
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import (
    Contribution,
    InStoreCashContributionReversal,
    MetalGrade,
    PaymentOperationsControl,
    PaymentScheduleWindow,
    Redemption,
    SchemeAccount,
    SchemePlan,
    SchemePlanConfiguration,
    SchemePlanOffering,
    SchemeRate,
)
from .services import cash_scheme_activity_is_enabled, validate_contribution_allowed


class OwnerPaymentFilterForm(forms.Form):
    q = forms.CharField(label="Customer, plan or payment reference", max_length=100, required=False)
    status = forms.ChoiceField(label="Status", required=False, choices=[("", "All statuses"), *((value, "Checkout closed after review" if value == "ABANDONED" else label) for value, label in Contribution.Status.choices)])
    method = forms.ChoiceField(label="Method", required=False, choices=[("", "All methods"), ("razorpay", "Razorpay"), ("in_store_cash", "In-store cash"), ("mock", "Practice")])
    mode = forms.ChoiceField(label="Online mode", required=False, choices=[("", "All modes"), ("live", "Live"), ("test", "Test")])
    start = forms.DateField(label="Created from", required=False, widget=forms.DateInput(attrs={"type": "date"}))
    end = forms.DateField(label="Created through", required=False, widget=forms.DateInput(attrs={"type": "date"}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-select" if isinstance(field.widget, forms.Select) else "form-control"

    def clean(self):
        values = super().clean()
        if values.get("start") and values.get("end") and values["end"] < values["start"]:
            raise forms.ValidationError("The to date must be on or after the from date.")
        return values


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
    # This is the existing-style editor; independent drafts have a separate form.
    minimum_months = forms.IntegerField(min_value=12, max_value=32767, initial=12)
    default_months = forms.IntegerField(min_value=12, max_value=32767, initial=12)
    audit_reason = forms.CharField(
        label="Reason for change", widget=forms.Textarea(attrs={"rows": 2}),
        help_text="Recorded with your identity in the plan revision and audit log.",
    )
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
            "description": "Internal plan notes; this text is not published on the public plans page.",
            "active": "Allow new enrolments. Disabling this does not close existing agreements or stop their contributions.",
            "frequency_rule": "A frequency limit, not an instalment-completion or benefit-qualification rule.",
            "cash_bonus_percentage": (
                "Applies only to cash schemes. Use 0 to disable cash bonus."
            ),
            "cash_bonus_minimum_months": (
                "The customer's agreed duration must meet this minimum."
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["frequency_rule"].choices = [
            choice for choice in SchemePlan.FrequencyRule.choices if choice[0] != "ONCE_PER_PERIOD"
        ]
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
        if self.instance.configuration_id:
            from .plan_configuration import configuration_plan_values
            for name in (*configuration_plan_values(self.instance.configuration), "active", "publicly_listed"):
                if name in self.fields:
                    self.fields[name].disabled = True


class SchemePlanChangeForm(SchemePlanForm):
    expected_digest = forms.CharField(widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound:
            from .plan_governance import plan_edit_digest
            self.fields["expected_digest"].initial = plan_edit_digest(self.instance)

    class Meta(SchemePlanForm.Meta):
        fields = [*SchemePlanForm.Meta.fields, "publicly_listed"]
        help_texts = {
            **SchemePlanForm.Meta.help_texts,
            "publicly_listed": (
                "Publishes this savings plan's name, contribution amounts, "
                "frequency, and duration when the plan is active."
            ),
        }

    audit_reason = forms.CharField(
        label="Reason for change",
        widget=forms.Textarea(attrs={"rows": 2}),
        help_text="Recorded in the immutable owner audit log.",
    )


class PlanConfigurationForm(forms.ModelForm):
    minimum_months = forms.IntegerField(min_value=12, max_value=32767, initial=12)
    default_months = forms.IntegerField(min_value=12, max_value=32767, initial=12)
    field_order = ["name", "amount_policy", "minimum_amount", "maximum_amount", "fixed_amount",
        "amount_step", "schedule_family", "schedule_period", "frequency_rule", "minimum_months",
        "default_months", "completion_rule", "missed_outcome", "allow_contributions_after_eligibility", "reason"]
    reason = forms.CharField(label="Reason for this version", widget=forms.Textarea(attrs={"rows": 2}))
    schedule_family = forms.ChoiceField(required=False, label="Contribution obligation", choices=[
        ("CALENDAR", "Optional contributions"),
        ("MONTHLY_COMPLETION", "Required monthly instalments"),
    ], initial="CALENDAR", help_text="An obligation is different from a payment limit. Required instalments currently use a customer-selected fixed amount; no advance or bulk catch-up.")
    schedule_period = forms.ChoiceField(required=False, label="Instalment period basis", choices=[
        ("", "Not applicable — optional contributions"),
        ("ANNIVERSARY", "Agreement-anniversary month (India time)"),
        ("CALENDAR_MONTH", "Calendar month, including enrolment month (India time)"),
    ], help_text="Calendar month: joining on 30 January requires January's instalment before 1 February. Enrolment-day payment counts. No extra grace.")
    completion_rule = forms.ChoiceField(required=False, label="Normal redemption eligibility", choices=[
        ("CALENDAR", "Agreed duration — optional contributions"),
        ("CALENDAR_AND_COUNT", "Agreed duration AND qualifying instalment count"),
    ], initial="CALENDAR", help_text="Both means the later of the minimum-duration date and final qualifying period end. Count-only and anytime plans are not yet supported.")
    missed_outcome = forms.ChoiceField(required=False, label="Missed-payment outcome", choices=[
        ("NONE", "No required instalment — no missed-payment consequence"),
        ("EXTEND_THEN_REVIEW", "Up to three extension periods, then discontinuation review"),
    ], initial="NONE", help_text="Paid entitlement is never forfeited. Benefit-loss rules are unavailable because this release offers no bonus or discount. Outage compensation is separately reviewed.")

    class Meta:
        model = SchemePlanConfiguration
        fields = [
            "name", "amount_policy", "minimum_amount", "maximum_amount", "fixed_amount",
            "amount_step", "frequency_rule", "minimum_months", "default_months",
            "allow_contributions_after_eligibility",
        ]
        help_texts = {
            "fixed_amount": "For a showroom-fixed amount, also set both minimum and maximum to exactly this amount. Leave the increment empty.",
            "frequency_rule": "Required instalments use one qualifying contribution per selected period. For optional contributions, a calendar-month limit is only a ceiling, not an obligation.",
        }
        labels = {"frequency_rule": "Payment limit"}

    def clean(self):
        values = super().clean()
        # Do not silently accept forged future policy fields that this editor cannot support.
        from .plan_configuration import CONFIGURATION_FIELDS, EDITABLE_CONFIGURATION_FIELDS, INDEPENDENT_CONFIGURATION_FIELDS
        if any(name in self.data for name in set(CONFIGURATION_FIELDS + INDEPENDENT_CONFIGURATION_FIELDS) - set(EDITABLE_CONFIGURATION_FIELDS)):
            raise forms.ValidationError("Advanced policy dimensions are not available in this release.")
        if values.get("schedule_family") == "MONTHLY_COMPLETION":
            from .plan_configuration import MONTHLY_COMPLETION_POLICY
            if values.get("amount_policy") != "CUSTOMER_FIXED":
                self.add_error("amount_policy", "Monthly completion requires a customer-selected fixed amount.")
            if values.get("frequency_rule") != "ONCE_PER_PERIOD":
                self.add_error("frequency_rule", "Choose one qualifying contribution per selected monthly period.")
            if not values.get("schedule_period"):
                self.add_error("schedule_period", "Choose calendar month or agreement-anniversary month.")
            if values.get("completion_rule") != "CALENDAR_AND_COUNT":
                self.add_error("completion_rule", "Required instalments currently require both duration and qualifying count.")
            if values.get("missed_outcome") != "EXTEND_THEN_REVIEW":
                self.add_error("missed_outcome", "Required instalments currently use bounded extension followed by review.")
            if values.get("allow_contributions_after_eligibility"):
                self.add_error("allow_contributions_after_eligibility", "Extension payments are separate from payments after completed eligibility. Leave this off.")
            for field, value in MONTHLY_COMPLETION_POLICY.items():
                setattr(self.instance, field, value)
            self.instance.period_basis = values.get("schedule_period") or "ANNIVERSARY"
        else:
            if values.get("schedule_period"):
                self.add_error("schedule_period", "Optional contributions have no instalment periods; their payment limit is selected separately.")
            if values.get("completion_rule") not in (None, "", "CALENDAR"):
                self.add_error("completion_rule", "Optional contributions use duration eligibility, not a compulsory count.")
            if values.get("missed_outcome") not in (None, "", "NONE"):
                self.add_error("missed_outcome", "Optional contributions cannot have a missed-instalment consequence.")
        return values

    def configuration_values(self):
        from .plan_configuration import EDITABLE_CONFIGURATION_FIELDS, MONTHLY_COMPLETION_POLICY
        values = {field: self.cleaned_data[field] for field in EDITABLE_CONFIGURATION_FIELDS}
        if self.cleaned_data.get("schedule_family") == "MONTHLY_COMPLETION":
            values.update(MONTHLY_COMPLETION_POLICY)
            values["period_basis"] = self.cleaned_data["schedule_period"]
        return values


class ConfigurationPreviewForm(forms.Form):
    amount = forms.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0.01"))
    months = forms.IntegerField(min_value=12, max_value=32767)
    metal_grade = forms.ModelChoiceField(queryset=MetalGrade.objects.all())
    start_date = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}), help_text="Monthly scenario start date; defaults to today. No agreement is created.")
    missed_periods = forms.CharField(required=False, max_length=200, help_text="Scenario only: comma-separated missed period numbers, for example 2,5. Leave empty for all payments on time.")

    def clean_missed_periods(self):
        raw = self.cleaned_data.get("missed_periods", "").strip()
        if not raw:
            return ()
        try:
            numbers = tuple(int(part.strip()) for part in raw.split(","))
        except ValueError:
            raise forms.ValidationError("Use comma-separated whole period numbers.") from None
        if len(numbers) != len(set(numbers)) or any(number < 1 for number in numbers):
            raise forms.ValidationError("Use positive, distinct period numbers.")
        return numbers


class ConfiguredPlanDraftForm(forms.Form):
    name = forms.CharField(max_length=120)
    code = forms.CharField(max_length=30)
    metal_grades = forms.ModelMultipleChoiceField(queryset=MetalGrade.objects.all(), widget=forms.CheckboxSelectMultiple)
    reason = forms.CharField(widget=forms.Textarea(attrs={"rows": 2}))


class ConfiguredPlanPublicationForm(forms.Form):
    expected_digest = forms.CharField(widget=forms.HiddenInput)
    confirmed = forms.BooleanField(label="I reviewed this offer and the effect on new applications; existing agreements are unchanged.")
    reason = forms.CharField(max_length=1000, widget=forms.Textarea(attrs={"rows": 3}))


class EnrolmentForm(forms.Form):
    selected_contribution_amount = forms.DecimalField(required=False, max_digits=14, decimal_places=2, min_value=Decimal("0.01"), label="Customer's agreed contribution amount")
    selected_amount_confirmed = forms.BooleanField(required=False, label="I reviewed the configuration and individual amount with the customer.")
    configuration_token = forms.CharField(required=False, widget=forms.HiddenInput)
    plan = forms.ModelChoiceField(queryset=SchemePlan.objects.none())
    metal_grade = forms.ModelChoiceField(
        queryset=MetalGrade.objects.none(),
        label="Metal grade",
        required=False,
    )
    start_date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}),
        help_text=(
            "Calendar dates and any required instalment windows are anchored to this date."
        ),
    )
    agreed_months = forms.IntegerField(
        min_value=1, required=False,
        help_text=(
            "Use the published duration for an independent plan; leave blank for count-only "
            "or anytime eligibility. Required payment count is a separate condition."
        ),
    )
    audit_reason = forms.CharField(
        label="Reason for enrolment",
        widget=forms.Textarea(attrs={"rows": 2}),
        help_text="Recorded with your identity and timestamp.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from .selectors import get_enrollable_scheme_plans
        self.fields["plan"].queryset = get_enrollable_scheme_plans()
        self.fields["metal_grade"].queryset = MetalGrade.objects.filter(
            plan_offerings__active=True,
            plan_offerings__plan__in=self.fields["plan"].queryset,
        ).distinct()
        configured = self.fields["plan"].queryset.filter(configuration__isnull=False)
        if not configured.exists():
            for name in ("selected_contribution_amount", "selected_amount_confirmed", "configuration_token"):
                self.fields.pop(name)
        elif not self.is_bound:
            from .plan_governance import plan_edit_digest
            self.fields["configuration_token"].initial = signing.dumps(
                {str(plan.pk): plan_edit_digest(plan) for plan in configured}, salt="owner-enrolment-configuration",
            )

    def clean(self):
        cleaned = super().clean()
        plan = cleaned.get("plan")
        metal_grade = cleaned.get("metal_grade")
        agreed_months = cleaned.get("agreed_months")
        if plan and plan.configuration_id:
            from .plan_governance import plan_edit_digest
            try:
                offers = signing.loads(cleaned.get("configuration_token", ""), salt="owner-enrolment-configuration", max_age=7200)
                if offers.get(str(plan.pk)) != plan_edit_digest(plan):
                    raise signing.BadSignature
                cleaned["expected_configuration_id"] = plan.configuration_id
                cleaned["expected_plan_digest"] = offers[str(plan.pk)]
            except signing.BadSignature:
                self.add_error(None, "The displayed configuration changed or expired. Reload and review it again.")
            if not cleaned.get("selected_amount_confirmed"):
                self.add_error(None, "Confirm the individual amount with the customer.")
            try:
                if plan.configuration.policy_schema_version == 2:
                    from .enrolment_contracts import independent_request_values
                    independent_request_values(configuration_id=plan.configuration_id,
                        metal_grade_id=metal_grade.pk if metal_grade else None,
                        amount=cleaned.get("selected_contribution_amount"), months=agreed_months)
                else:
                    from .plan_configuration import agreement_snapshot_values
                    agreement_snapshot_values(plan=plan, selected_amount=cleaned.get("selected_contribution_amount"))
            except ValidationError as error:
                self.add_error(None, error)
        if plan and metal_grade and not SchemePlanOffering.objects.filter(
            plan=plan,
            metal_grade=metal_grade,
            active=True,
        ).exists():
            self.add_error(
                "metal_grade",
                "This metal grade is not offered by the selected plan.",
            )
        independent = plan and plan.configuration_id and plan.configuration.policy_schema_version == 2
        if plan and not independent:
            if not metal_grade:
                self.add_error("metal_grade", "Choose the agreed metal grade.")
            if agreed_months is None or agreed_months < max(12, plan.minimum_months):
                self.add_error("agreed_months", f"This plan requires at least {max(12, plan.minimum_months)} months.")
        return cleaned


class SchemeEnrolmentRequestForm(forms.Form):
    offer_token = forms.CharField(required=False, widget=forms.HiddenInput)
    metal_grade = forms.ModelChoiceField(
        queryset=MetalGrade.objects.none(),
        label="Metal grade",
    )
    requested_contribution_amount = forms.DecimalField(
        label="Preferred contribution amount",
        max_digits=14,
        decimal_places=2,
        min_value=Decimal("0.01"),
    )
    requested_months = forms.IntegerField(
        label="Preferred duration (months)",
        min_value=12,
        help_text="This preference is reviewed before an agreement is created.",
    )
    customer_message = forms.CharField(
        label="Message for the showroom",
        required=False,
        max_length=1000,
        widget=forms.Textarea(attrs={"rows": 3}),
    )
    disclosure_accepted = forms.BooleanField(
        label=(
            "I understand this is a non-binding request. It does not create a scheme "
            "account or payment access, and the showroom must review the current terms "
            "with me before enrolment."
        ),
    )

    def __init__(self, *args, plan, **kwargs):
        self.plan = plan
        super().__init__(*args, **kwargs)
        self.fields["metal_grade"].queryset = MetalGrade.objects.filter(
            plan_offerings__plan=plan,
            plan_offerings__active=True,
        ).order_by("display_order", "code")
        self.independent_terms = ()
        if plan.configuration_id and plan.configuration.policy_schema_version == 2:
            from .enrolment_contracts import policy_description
            from .plan_governance import plan_edit_digest
            from .plan_policies import policy_from_configuration
            policy = policy_from_configuration(plan.configuration)
            self.independent_terms = policy_description(plan.configuration)
            self.fields["metal_grade"].required = policy.accumulation != "INR_PURCHASE_CREDIT"
            if not self.fields["metal_grade"].required:
                self.fields["metal_grade"].queryset = MetalGrade.objects.none()
                self.fields["metal_grade"].help_text = "INR purchase credit has no metal grade."
            self.fields["requested_months"] = forms.IntegerField(required=False, min_value=1,
                initial=policy.duration_months, label="Agreed duration (months)",
                help_text="Use the exact published duration; leave blank when no duration condition applies. Required payment count is separate.")
            amount = self.fields["requested_contribution_amount"]
            configuration = plan.configuration
            amount.initial = configuration.fixed_amount if policy.amount_policy == "PLAN_FIXED" else configuration.minimum_amount
            amount.disabled = policy.amount_policy == "PLAN_FIXED"
            amount.label = "Your fixed contribution amount" if policy.amount_policy == "CUSTOMER_FIXED" else "Requested contribution amount"
            amount.help_text = "Within the published bounds and step. Customer-fixed amounts are fixed on the agreement; variable amounts remain a preference."
            if not self.is_bound:
                self.fields["offer_token"].initial = signing.dumps(
                    {"digest": plan_edit_digest(plan), "disclosure": settings.CUSTOMER_ENROLMENT_REQUEST_DISCLOSURE_VERSION},
                    salt="customer-enrolment-offer")
            return
        self.fields.pop("offer_token")
        self.fields["requested_months"].min_value = plan.minimum_months
        self.fields["requested_months"].initial = plan.default_months
        if plan.amount_rule == SchemePlan.AmountRule.FIXED:
            self.fields["requested_contribution_amount"].initial = (
                plan.fixed_contribution_amount
            )
            self.fields["requested_contribution_amount"].disabled = True
            self.fields["requested_contribution_amount"].help_text = (
                "This plan uses the displayed fixed contribution amount."
            )
        else:
            self.fields["requested_contribution_amount"].initial = (
                plan.minimum_contribution
            )
            if plan.maximum_contribution is None:
                self.fields["requested_contribution_amount"].help_text = (
                    f"Choose ₹{plan.minimum_contribution:.2f} or more."
                )
            else:
                self.fields["requested_contribution_amount"].help_text = (
                    f"Choose ₹{plan.minimum_contribution:.2f}–"
                    f"₹{plan.maximum_contribution:.2f}."
                )
        if plan.configuration_id:
            configuration = plan.configuration
            if configuration.amount_policy == "CUSTOMER_FIXED":
                self.fields["requested_contribution_amount"].label = "Your fixed contribution amount"
                self.fields["requested_contribution_amount"].help_text += " Choose once: this amount becomes fixed on your agreement after confirmation and approval."
            if configuration.amount_step:
                self.fields["requested_contribution_amount"].help_text += f" Use increments of ₹{configuration.amount_step:.2f} from the minimum."

    def clean(self):
        cleaned = super().clean()
        grade = cleaned.get("metal_grade")
        amount = cleaned.get("requested_contribution_amount")
        months = cleaned.get("requested_months")
        if self.plan.configuration_id and self.plan.configuration.policy_schema_version == 2:
            from .enrolment_contracts import independent_request_values
            from .plan_governance import plan_edit_digest
            from .plan_publication import require_configured_offer
            try:
                offer = signing.loads(cleaned.get("offer_token", ""), salt="customer-enrolment-offer", max_age=7200)
                if (offer.get("digest") != plan_edit_digest(self.plan)
                        or offer.get("disclosure") != settings.CUSTOMER_ENROLMENT_REQUEST_DISCLOSURE_VERSION):
                    raise signing.BadSignature
                cleaned["expected_plan_digest"] = offer["digest"]
            except signing.BadSignature:
                self.add_error(None, "The displayed offer changed or expired. Reload and review it again.")
            try:
                require_configured_offer(self.plan)
                independent_request_values(configuration_id=self.plan.configuration_id,
                    metal_grade_id=grade.pk if grade else None, amount=amount, months=months)
            except ValidationError as error:
                self.add_error(None, error)
            return cleaned
        if grade and not SchemePlanOffering.objects.filter(
            plan=self.plan,
            metal_grade=grade,
            active=True,
        ).exists():
            self.add_error("metal_grade", "This grade is no longer offered.")
        if amount is not None:
            if self.plan.configuration_id:
                from .plan_configuration import validate_configuration_amount
                try:
                    validate_configuration_amount(self.plan.configuration, amount)
                except ValidationError as error:
                    self.add_error("requested_contribution_amount", error)
            if self.plan.amount_rule == SchemePlan.AmountRule.FIXED:
                if amount != self.plan.fixed_contribution_amount:
                    self.add_error(
                        "requested_contribution_amount",
                        "Use the displayed fixed contribution amount.",
                    )
            elif amount < self.plan.minimum_contribution or (
                self.plan.maximum_contribution is not None
                and amount > self.plan.maximum_contribution
            ):
                self.add_error(
                    "requested_contribution_amount",
                    "Choose an amount within the displayed range.",
                )
        if months is not None and months < self.plan.minimum_months:
            self.add_error(
                "requested_months",
                f"This plan requires at least {self.plan.minimum_months} months.",
            )
        return cleaned


class EnrolmentRequestDecisionForm(forms.Form):
    reason = forms.CharField(
        label="Decision reason",
        max_length=500,
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Retained with the request and immutable audit record.",
    )


class EnrolmentRequestConversionForm(EnrolmentForm):
    current_terms_confirmed = forms.BooleanField(
        label=(
            "I reviewed the current plan, accumulation, amount, independent eligibility and benefit rules, and start date "
            "with the customer."
        ),
    )

    def __init__(self, *args, enrolment_request, **kwargs):
        self.enrolment_request = enrolment_request
        initial = kwargs.setdefault("initial", {})
        initial.setdefault("plan", enrolment_request.plan)
        initial.setdefault("metal_grade", enrolment_request.metal_grade)
        initial.setdefault("start_date", timezone.localdate())
        initial.setdefault("agreed_months", enrolment_request.requested_months)
        super().__init__(*args, **kwargs)
        self.fields["plan"].queryset = SchemePlan.objects.filter(
            pk=enrolment_request.plan_id
        )
        self.fields["metal_grade"].queryset = MetalGrade.objects.filter(
            pk=enrolment_request.metal_grade_id
        )
        self.fields["plan"].disabled = True
        self.fields["metal_grade"].disabled = True
        self.fields["agreed_months"].disabled = True
        if enrolment_request.configuration_snapshot_id and "selected_contribution_amount" in self.fields:
            self.fields["selected_contribution_amount"].initial = enrolment_request.requested_contribution_amount
            self.fields["selected_contribution_amount"].disabled = True
            self.fields["selected_contribution_amount"].help_text = "Uses the customer's requested amount. Changing it requires a fresh confirmed request."
        self.fields["agreed_months"].help_text = "Uses the customer's confirmed duration. A different duration requires a new customer request."
        self.fields["audit_reason"].label = "Confirmation and enrolment reason"
        self.fields["audit_reason"].help_text = (
            "Record how the current terms were confirmed with the customer."
        )


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
            if scheme_account.contribution_step_snapshot:
                boundary += f"; increments of ₹{scheme_account.contribution_step_snapshot} from the minimum"
            self.fields["amount"].help_text = boundary

    def clean_amount(self):
        amount = self.cleaned_data["amount"]
        validated_amount, _ = validate_contribution_allowed(self.scheme_account, amount)
        return validated_amount


class InStoreCashContributionForm(ContributionForm):
    idempotency_key = forms.UUIDField(widget=forms.HiddenInput)
    expected_scheme_rate_id = forms.IntegerField(
        required=False,
        widget=forms.HiddenInput,
    )
    paper_receipt_number = forms.CharField(
        required=False,
        max_length=80,
        label="Paper receipt number (optional)",
        help_text="If entered, this number must be unique.",
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
        help_text="Optional internal note; do not record sensitive payment data.",
    )
    audit_reason = forms.CharField(
        label="Reason for recording",
        initial="Cash received at the showroom.",
        widget=forms.Textarea(attrs={"rows": 2}),
        help_text="Recorded with your identity and timestamp.",
    )
    confirm_cash_received = forms.BooleanField(
        required=False,
        label="I confirm the showroom has physically received this cash amount.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("amount", "paper_receipt_number", "notes", "audit_reason"):
            self.fields[name].widget.attrs["class"] = "form-control"
        self.fields["confirm_cash_received"].widget.attrs["class"] = (
            "form-check-input"
        )

    def clean_paper_receipt_number(self):
        return self.cleaned_data["paper_receipt_number"].strip()


class InStoreCashContributionReversalForm(forms.Form):
    reason_code = forms.ChoiceField(
        label="Correction reason",
        choices=InStoreCashContributionReversal.ReasonCode.choices,
    )
    reason = forms.CharField(
        label="Bookkeeping error details",
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text=(
            "This is not a customer cancellation or cash refund. Explain the "
            "incorrect record and any replacement entry required."
        ),
    )
    confirm_reversal = forms.BooleanField(
        label=(
            "I confirm this is a bookkeeping correction and the original metal "
            "entitlement must be removed."
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["reason_code"].widget.attrs["class"] = "form-select"
        self.fields["reason"].widget.attrs["class"] = "form-control"
        self.fields["confirm_reversal"].widget.attrs["class"] = "form-check-input"


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
