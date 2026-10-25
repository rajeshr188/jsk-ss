"""Read-only schema-2 contract resolution, not enrolment or eligibility permission.

The pinned configuration supplies independent policy dimensions. Customer choices
resolve only the exact denomination and amount; they cannot rewrite that policy.
No account, payment, rate lock, persisted schedule or benefit is created here.
"""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError

from .eligibility import add_calendar_months
from .models import MetalGrade, SchemePlanConfiguration, SchemePlanRevision
from .plan_configuration import configuration_evidence, validate_configuration_amount
from .plan_policies import PlanPolicy, policy_from_configuration, validate_plan_policy


@dataclass(frozen=True, kw_only=True)
class IndependentAgreementTerms:
    configuration_id: int
    policy: PlanPolicy
    savings_mode: str
    metal_grade_id: int | None
    metal_grade_code: str | None
    start_date: date
    # A duration floor is not a claim that count/benefit/settlement checks passed.
    duration_not_before: date | None
    amount_rule: str
    fixed_amount: Decimal | None
    minimum_amount: Decimal
    maximum_amount: Decimal | None
    contribution_step: Decimal | None

    def amount_snapshots(self):
        return dict(amount_rule_snapshot=self.amount_rule, fixed_amount_snapshot=self.fixed_amount,
            minimum_amount_snapshot=self.minimum_amount, maximum_amount_snapshot=self.maximum_amount,
            contribution_step_snapshot=self.contribution_step)

    def account_snapshots(self):
        """Storage projection only; never permission to save or enrol an account."""
        return dict(self.amount_snapshots(), agreement_schema_version=2,
            eligibility_policy_snapshot=self.policy.eligibility, required_count_snapshot=self.policy.required_count,
            configuration_snapshot_id=self.configuration_id, savings_mode=self.savings_mode,
            metal_grade_id=self.metal_grade_id, start_date=self.start_date,
            agreed_months=self.policy.duration_months, eligible_from=self.duration_not_before,
            frequency_rule_snapshot=self.policy.payment_limit,
            allow_post_eligibility_contributions_snapshot=self.policy.allow_post_eligibility,
            cash_bonus_percentage_snapshot=Decimal("0.00"), cash_bonus_minimum_months_snapshot=12)


def resolve_independent_agreement_terms(*, configuration_id, start_date, selected_amount=None,
                                        metal_grade_id=None):
    """Resolve persisted policy facts; deliberately independent of release flags.

    COUNT/ANYTIME have no invented duration date. A variable amount preference is
    validated, if supplied, but never converted to a fixed contractual obligation.
    Readiness and owner/customer consent must be checked by future enrolment services.
    """
    configuration = SchemePlanConfiguration.objects.get(pk=configuration_id)
    configuration.full_clean()
    if configuration.policy_schema_version != 2:
        raise ValidationError("Independent agreement terms require policy schema 2.")
    if type(start_date) is not date:
        raise ValidationError("Use an explicit agreement calendar date, not a timestamp.")
    policy = policy_from_configuration(configuration)
    validate_plan_policy(policy)
    if policy.amount_policy == "CUSTOMER_FIXED" and selected_amount is None:
        raise ValidationError("The customer's confirmed fixed contribution amount is required.")
    selected = configuration.fixed_amount
    if selected_amount is not None:
        selected = validate_configuration_amount(configuration, selected_amount)
    if policy.amount_policy == "PLAN_FIXED":
        selected = validate_configuration_amount(configuration, configuration.fixed_amount)
    fixed = policy.amount_policy != "VARIABLE"

    grade = None
    if policy.accumulation == "INR_PURCHASE_CREDIT":
        if metal_grade_id is not None:
            raise ValidationError("INR purchase credit cannot carry a metal grade.")
        mode = "INR_CREDIT"
    else:
        grade = MetalGrade.objects.filter(pk=metal_grade_id, metal__in=["GOLD", "SILVER"]).first()
        if grade is None:
            raise ValidationError("Select an existing exact metal grade.")
        mode = grade.metal
    try:
        duration_date = (add_calendar_months(start_date, policy.duration_months)
                         if policy.duration_months is not None else None)
    except (ValueError, OverflowError):
        raise ValidationError("The agreement duration exceeds the supported calendar range.") from None
    return IndependentAgreementTerms(
        configuration_id=configuration.pk, policy=policy, savings_mode=mode,
        metal_grade_id=grade.pk if grade else None, metal_grade_code=grade.code if grade else None,
        start_date=start_date, duration_not_before=duration_date,
        amount_rule="FIXED" if fixed else "VARIABLE", fixed_amount=selected if fixed else None,
        minimum_amount=selected if fixed else configuration.minimum_amount,
        maximum_amount=selected if fixed else configuration.maximum_amount,
        contribution_step=None if fixed else configuration.amount_step,
    )


def validate_independent_account_terms(account):
    """Validate stored independent facts, not payment/eligibility/benefit readiness."""
    terms = resolve_independent_agreement_terms(configuration_id=account.configuration_snapshot_id,
        start_date=account.start_date, selected_amount=account.fixed_amount_snapshot,
        metal_grade_id=account.metal_grade_id)
    expected = terms.account_snapshots()
    if any(getattr(account, field) != value for field, value in expected.items()):
        raise ValidationError("Agreement amounts, denomination or duration differ from the pinned independent policy.")
    # Reload immutable provenance; current plan edits and caller-mutated cached objects
    # must not change an existing agreement's meaning.
    configuration = SchemePlanConfiguration.objects.get(pk=terms.configuration_id)
    revision = SchemePlanRevision.objects.filter(pk=account.plan_revision_id).first()
    evidence = revision.terms if revision else None
    if (revision is None or revision.plan_id != account.plan_id or not isinstance(evidence, dict)
            or evidence.get("configuration") != configuration_evidence(configuration)
            or evidence.get("name") != account.plan_name_snapshot
            or evidence.get("code") != account.plan_code_snapshot):
        raise ValidationError("The agreement requires matching frozen configuration and revision evidence.")
    grades = evidence.get("metal_grades")
    if (not isinstance(grades, list)
            or (terms.savings_mode == "INR_CREDIT" and grades != [])
            or (terms.metal_grade_code is not None and terms.metal_grade_code not in grades)):
        raise ValidationError("The recorded revision and accumulation denomination must agree.")
    return terms


@dataclass(frozen=True, kw_only=True)
class IndependentAgreementSchedule:
    """Prospective obligations, not persisted periods or payment qualifications."""
    terms: IndependentAgreementTerms
    windows: tuple


def resolve_independent_agreement_schedule(*, configuration_id, start_date,
                                           selected_amount=None, metal_grade_id=None):
    """Prepare schema-2 enrolment's schedule without granting runtime permission.

    Required count, not duration, determines the original monthly windows. Ordinary
    replacement windows exist only for EXTEND_THEN_REVIEW. Outage compensation needs
    separate acknowledged evidence and is never pre-created here. Optional payment
    ceilings are not obligations and therefore produce no required windows.

    A window end is not an eligibility date: COUNT qualification needs verified
    payment evidence, while DURATION_AND_COUNT also needs its duration/period rules.
    This function creates no account, period, payment, benefit or financial record.
    """
    from .instalments import InstalmentWindow, period_boundary

    terms = resolve_independent_agreement_terms(configuration_id=configuration_id,
        start_date=start_date, selected_amount=selected_amount, metal_grade_id=metal_grade_id)
    policy = terms.policy
    if policy.obligation == "OPTIONAL":
        return IndependentAgreementSchedule(terms=terms, windows=())
    required_count = policy.required_count
    replacements = policy.extension_periods if policy.missed_outcome == "EXTEND_THEN_REVIEW" else 0
    total = required_count + replacements
    # The policy bounds required count at 32767; period.number is PositiveInteger,
    # so its separate ordinary replacement periods fit without truncating the count.
    try:
        period_boundary(policy, terms.start_date, total)
        windows = tuple(InstalmentWindow(number=index + 1,
            starts_on=period_boundary(policy, terms.start_date, index),
            ends_before=period_boundary(policy, terms.start_date, index + 1),
            amount=terms.fixed_amount, extension=index >= required_count)
            for index in range(total))
    except (ValueError, OverflowError):
        raise ValidationError("The proposed schedule exceeds supported calendar dates.") from None
    return IndependentAgreementSchedule(terms=terms, windows=windows)
