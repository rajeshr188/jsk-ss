"""Public policy projections and hypothetical examples; never payment authority."""
from decimal import Decimal, ROUND_HALF_UP, localcontext

from django import forms
from django.core.exceptions import ValidationError

from schemes.benefits import calculate_purchase_bonus, calculate_va_discount
from schemes.enrolment_contracts import policy_description
from schemes.models import MetalAllocation
from schemes.plan_configuration import validate_configuration_amount
from schemes.plan_policies import policy_from_configuration
from schemes.selectors import get_public_scheme_plans


def offer_facts(plan):
    """Use recorded structured rules, never internal notes or an invented benefit."""
    configuration = plan.configuration if plan.configuration_id else None
    policy = policy_from_configuration(configuration) if configuration else None
    inr = bool(policy and policy.accumulation == "INR_PURCHASE_CREDIT")
    rows = policy_description(configuration) if configuration else []
    facts = dict(rows)
    grades = tuple(o.metal_grade for o in plan.metal_offerings.all() if o.active)
    return {
        "inr": inr,
        "accumulation": "INR jewellery purchase credit" if inr else "Exact-grade gold or silver grams",
        "grades": grades,
        "amount": facts.get("Amount rule", "Plan-fixed contribution amount" if plan.amount_rule == "FIXED" else "Variable contributions within the recorded bounds"),
        "obligation": facts.get("Required schedule", "Required monthly payments" if policy and policy.obligation == "REQUIRED_MONTHLY" else "No mandatory instalments"),
        "limit": facts.get("Payment limit", "At most once per calendar month" if plan.frequency_rule == "ONCE_PER_MONTH" else "Flexible contribution timing"),
        "eligibility": facts.get("Normal eligibility", f"Agreed calendar duration; minimum {plan.minimum_months} months. A frequency limit does not require twelve paid instalments."),
        "benefit": facts.get("Conditional benefit", facts.get("Benefit", "No additional benefit is promised on this public offer; accepted written terms govern.")),
        "exit": ("One final full settlement. Jewellery purchase credit uses verified INR principal; unused paid principal may be returned through the original-source refund procedure. Benefits are purchase-only, never refundable cash."
            if inr else "Configured agreements use one final full jewellery settlement in the agreed grade. No voluntary metal-to-cash conversion."
            if configuration else "Contact the showroom to review early discontinuation and the settlement rights in your recorded agreement."),
        "rows": rows,
    }


def get_public_offers(*, limit=None):
    plans = get_public_scheme_plans(limit=limit).select_related("configuration")
    result = list(plans)
    for plan in result:
        plan.public_facts = offer_facts(plan)
    return result


class OfferIllustrationForm(forms.Form):
    amount = forms.DecimalField(label="Illustrative contribution (INR)", max_digits=14, decimal_places=2, min_value=Decimal("0.01"))
    grade = forms.ChoiceField(label="Offered metal grade")
    rate = forms.DecimalField(label="Assumed scheme rate (INR per gram)", max_digits=14, decimal_places=4, min_value=Decimal("0.0001"),
        help_text="Your hypothetical assumption, not a current quote or a locked rate.")
    eligible_charges = forms.DecimalField(label="Assumed eligible making/value-addition charges (INR)", max_digits=14, decimal_places=2, min_value=Decimal("0.00"))

    def __init__(self, *args, plan, **kwargs):
        self.plan = plan
        self.facts = offer_facts(plan)
        super().__init__(*args, **kwargs)
        self.fields["amount"].initial = plan.fixed_contribution_amount if plan.amount_rule == "FIXED" else plan.minimum_contribution
        self.fields["amount"].disabled = plan.amount_rule == "FIXED"
        configuration = plan.configuration if plan.configuration_id else None
        self.policy = policy_from_configuration(configuration) if configuration else None
        if self.facts["inr"]:
            del self.fields["grade"], self.fields["rate"]
        else:
            self.fields["grade"].choices = [(g.code, g.display_name) for g in self.facts["grades"]]
            if self.facts["grades"]:
                grade = self.facts["grades"][0]
                self.fields["grade"].initial = grade.code
                self.fields["rate"].initial = Decimal("100.0000") if grade.metal == "SILVER" else Decimal("10000.0000")
        if not self.policy or self.policy.benefit_kind != "VA_DISCOUNT":
            del self.fields["eligible_charges"]
        else:
            self.fields["eligible_charges"].initial = Decimal("1000.00")

    def clean_amount(self):
        amount = self.cleaned_data["amount"]
        plan = self.plan
        if plan.configuration_id:
            return validate_configuration_amount(plan.configuration, amount)
        if amount < plan.minimum_contribution or (plan.maximum_contribution is not None and amount > plan.maximum_contribution):
            raise ValidationError("Use an amount within this offer's recorded contribution limits.")
        return amount


def offer_illustration(form):
    """Call only after validation. No ORM writes, rate lookup or provider request."""
    data = form.cleaned_data
    amount = data["amount"]
    result = {"amount": amount, "inr": form.facts["inr"], "benefit": None}
    if form.facts["inr"]:
        result["principal"] = amount
    else:
        grade = next(g for g in form.facts["grades"] if g.code == data["grade"])
        with localcontext() as context:
            context.prec = 38
            quantity = (amount / data["rate"]).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
            if quantity <= 0:
                raise ValidationError("These assumptions are too small to illustrate an allocation. Choose a larger valid amount or a lower assumed rate.")
            field = MetalAllocation._meta.get_field("quantity")
            if quantity >= Decimal(10) ** (field.max_digits - field.decimal_places):
                raise ValidationError("These assumptions exceed the supported metal quantity. Choose a smaller valid amount or a higher assumed rate.")
            result.update(grade=grade, rate=data["rate"], quantity=quantity,
                display_quantity=quantity.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP))
    policy = form.policy
    if policy and policy.benefit_kind == "INR_PURCHASE_BONUS":
        result["benefit"] = calculate_purchase_bonus(qualifying_principal=amount,
            percentage=policy.benefit_percentage, cap=policy.benefit_cap_inr)
    elif policy and policy.benefit_kind == "VA_DISCOUNT":
        charges = data["eligible_charges"]
        result["eligible_charge_definition"] = policy.eligible_charge_definition
        result["benefit"] = calculate_va_discount(eligible_charges=charges, invoice_payable=charges,
            percentage=policy.benefit_percentage, cap=policy.benefit_cap_inr)
    return result
