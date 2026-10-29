"""Owner preparation of independent policies; no publication or money mutation."""
from django import forms
from django.core.exceptions import ValidationError
from django.forms.models import fields_for_model

from .models import MetalGrade, SchemePlanConfiguration


POLICY_GROUPS = (
    ("Name and accumulation", ("name", "accumulation")),
    ("Contribution amount", ("amount_policy", "minimum_amount", "maximum_amount", "fixed_amount", "amount_step")),
    ("Obligation and timing", ("instalment_policy", "frequency_rule", "period_basis")),
    ("Principal eligibility", ("eligibility_policy", "duration_months", "required_count", "allow_contributions_after_eligibility")),
    ("Missed payments", ("missed_payment_policy", "max_extension_months")),
    ("Conditional purchase benefit", ("benefit_policy", "benefit_percentage", "benefit_cap_inr",
        "benefit_qualification", "benefit_on_miss", "eligible_charge_definition")),
    ("Audit reason", ("reason",)),
)
POLICY_FIELDS = tuple(field for _, fields in POLICY_GROUPS for field in fields if field != "reason")
POLICY_CONSTANTS = dict(policy_schema_version=2, minimum_months=None, default_months=None,
    grace_days=0, catch_up_policy="NONE", settlement_policy="FULL_ONLY")


class IndependentConfigurationForm(forms.Form):
    def __init__(self, *args, previous=None, **kwargs):
        if previous is not None and previous.policy_schema_version != 2:
            raise ValidationError("Use the earlier editor for earlier configuration versions.")
        defaults = SchemePlanConfiguration(**POLICY_CONSTANTS, amount_policy="VARIABLE",
            minimum_amount="100.00", frequency_rule="FLEXIBLE", duration_months=12)
        source = previous or defaults
        kwargs["initial"] = {name: getattr(source, name) for name in POLICY_FIELDS}
        super().__init__(*args, **kwargs)
        self.fields.update(fields_for_model(SchemePlanConfiguration, fields=POLICY_FIELDS))
        self.fields["reason"] = forms.CharField(max_length=1000, label="Reason for this version",
            widget=forms.Textarea(attrs={"rows": 2}))
        self.fields["eligible_charge_definition"] = forms.CharField(required=False, max_length=2000,
            widget=forms.Textarea(attrs={"rows": 3}))
        self.fields["frequency_rule"].choices = [
            ("FLEXIBLE", "Flexible contributions"),
            ("ONCE_PER_PERIOD", "At most one qualifying contribution per selected period"),
        ]
        labels = {"instalment_policy": "Contribution obligation", "frequency_rule": "Payment limit",
            "eligibility_policy": "Normal principal eligibility", "required_count": "Required qualifying payments",
            "max_extension_months": "Ordinary replacement periods", "benefit_policy": "Purchase benefit",
            "benefit_cap_inr": "Benefit cap (INR)", "benefit_on_miss": "Effect of missed payments on the unearned benefit"}
        help_texts = {
            "accumulation": "INR purchase credit has no metal rate or grams. Exact-metal agreements select one offered grade later.",
            "amount_policy": "Required instalments need either a showroom-fixed or customer-selected fixed amount. Variable amounts are optional contributions only.",
            "fixed_amount": "Showroom-fixed: minimum, maximum and fixed amount must match; leave the increment blank. Otherwise leave this blank.",
            "period_basis": "Use a basis only with a monthly payment ceiling. Calendar months include the joining month, even near month-end; anniversary months follow the original joining date.",
            "duration_months": "Required for duration or duration-and-count. Leave blank for count-only and anytime.",
            "required_count": "Required only for compulsory monthly instalments. This is independent of duration months; a benefit-only schedule does not postpone principal maturity.",
            "max_extension_months": "Use 3 only for extend-then-review. Otherwise leave blank. Outage compensation is separately acknowledged, never automatic.",
            "allow_contributions_after_eligibility": "Unavailable for count-based completion. Other payment controls and accepted closure still apply.",
            "benefit_policy": "Purchase bonus requires INR principal. A VA discount requires defined invoice charges. Neither is refundable principal or additional grams.",
            "benefit_percentage": "Positive percentage, at most 100 with two decimals; leave blank for no benefit.",
            "benefit_cap_inr": "A positive cap is required for either benefit; leave blank for no benefit.",
            "benefit_qualification": "Optional contributions: normal eligibility. Required instalments: required schedule. No benefit: none.",
            "eligible_charge_definition": "Define eligible invoice charges for VA only. Leave blank for purchase bonus or no benefit. Plain text, not executable rules.",
        }
        for name, label in labels.items():
            self.fields[name].label = label
        for name, help_text in help_texts.items():
            self.fields[name].help_text = help_text
        self.configuration = None

    @property
    def groups(self):
        return tuple((title, tuple(self[name] for name in names)) for title, names in POLICY_GROUPS)

    def clean(self):
        values = super().clean()
        if set(self.data) - set(self.fields) - {"csrfmiddlewaretoken", "action"}:
            self.add_error(None, "Unsupported policy input. Version, history, grace and full-only settlement are controlled by the service.")
        if self.errors:
            return values
        candidate = SchemePlanConfiguration(**{name: values[name] for name in POLICY_FIELDS},
            **POLICY_CONSTANTS, reason=values["reason"])
        try:
            candidate.full_clean(exclude=["created_by", "actor_label"], validate_unique=False)
        except ValidationError as error:
            aliases = {"eligibility": "eligibility_policy", "payment_limit": "frequency_rule",
                "missed_outcome": "missed_payment_policy", "benefit_kind": "benefit_policy",
                "allow_post_eligibility": "allow_contributions_after_eligibility", "extension_periods": "max_extension_months"}
            for name, errors in getattr(error, "message_dict", {"__all__": error.messages}).items():
                field = aliases.get(name, name)
                for message in errors:
                    self.add_error(field if field in self.fields else None, message)
        else:
            self.configuration = candidate
        return values

    def configuration_values(self):
        if not self.is_valid():
            raise ValidationError("Review the configuration errors before saving.")
        return {name: self.cleaned_data[name] for name in POLICY_FIELDS} | POLICY_CONSTANTS


class IndependentPlanDraftForm(forms.Form):
    name = forms.CharField(max_length=120)
    code = forms.CharField(max_length=30)
    description = forms.CharField(required=False, label="Internal notes", widget=forms.Textarea(attrs={"rows": 3}))
    metal_grades = forms.ModelMultipleChoiceField(queryset=MetalGrade.objects.all(), widget=forms.CheckboxSelectMultiple)
    reason = forms.CharField(max_length=1000, label="Audit reason", widget=forms.Textarea(attrs={"rows": 2}))
    expected_digest = forms.CharField(widget=forms.HiddenInput)

    def __init__(self, *args, configuration, plan=None, **kwargs):
        super().__init__(*args, **kwargs)
        if configuration.policy_schema_version != 2:
            raise ValidationError("This form requires an independent configuration.")
        self.inr = configuration.accumulation == "INR_PURCHASE_CREDIT"
        if self.inr:
            self.fields.pop("metal_grades")
        if plan:
            from .plan_governance import plan_edit_digest
            self.initial.update({name: getattr(plan, name) for name in ("name", "code", "description")})
            self.initial["expected_digest"] = plan_edit_digest(plan)
            if not self.inr:
                self.initial["metal_grades"] = plan.metal_offerings.filter(active=True).values_list("metal_grade_id", flat=True)
        else:
            self.fields.pop("expected_digest")

    def clean(self):
        values = super().clean()
        if set(self.data) - set(self.fields) - {"csrfmiddlewaretoken"}:
            raise ValidationError("Only draft identity, notes and offered grades can be edited; policy and activation are locked.")
        if self.inr:
            values["metal_grades"] = ()
        return values
