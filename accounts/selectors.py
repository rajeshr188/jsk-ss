from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount, SocialToken
from django.db.models import Count, Q, OuterRef, Subquery
from django.utils import timezone

from schemes.payment_refund_selectors import unresolved_payment_events

from .models import (
    CustomerAccountDeletionRequest,
    CustomerInvitation,
    CustomerRegistration,
)


def get_owner_registration_applications():
    return CustomerRegistration.objects.select_related(
        "reviewed_by", "approved_user__customer_profile"
    ).order_by("-submitted_at", "-pk")


def get_activation_attention():
    latest = CustomerInvitation.objects.filter(user_id=OuterRef("user_id")).order_by(
        "-created_at", "-pk",
    ).values("pk")[:1]
    return CustomerInvitation.objects.filter(
        pk=Subquery(latest), accepted_at__isnull=True, revoked_at__isnull=True,
        user__is_active=True, user__role="CUSTOMER", user__privacy_erased_at__isnull=True,
        user__password__startswith="!", user__customer_profile__isnull=False,
    ).filter(
        Q(recovery_requested_at__isnull=False) | Q(expires_at__lte=timezone.now())
        | Q(delivery_failed_at__isnull=False) | Q(email_sent_at__isnull=True),
    ).select_related("user__customer_profile").order_by("created_at", "pk")


@dataclass(frozen=True)
class DeletionAccountBalance:
    scheme_number: str
    status: str
    grade: str
    cash_principal: Decimal
    cash_earned_bonus: Decimal
    metal_quantity: Decimal
    purchase_credit_principal: Decimal | None = Decimal("0.00")
    benefit_pending: bool = False


@dataclass(frozen=True)
class DeletionDispositionPreview:
    generated_at: datetime
    account_balances: tuple[DeletionAccountBalance, ...]
    inventory: tuple[tuple[str, int, str], ...]
    review_flags: tuple[str, ...]
    external_checks: tuple[str, ...]
    allocation_exceptions: int
    unresolved_webhooks: int
    has_financial_history: bool
    financial_exceptions: int = 0


def customer_account_deletion_disposition(deletion_request):
    """Read-only inventory, never a decision or proof that erasure is safe.

    Per-account balances use the financial selectors, without summing different
    grades or netting separate agreements. External disputes cannot be inferred
    from local payment status. Completion rechecks this preview under agreement locks.
    """
    from schemes.models import (
        AuditEvent,
        Contribution,
        InStoreCashReceipt,
        MetalAllocation,
        PaymentWebhookEvent,
        Redemption,
        SchemeAccount,
        SchemeEnrolmentRequest,
        SchemeReminder,
    )
    from schemes.selectors import get_cash_bonus_summary, get_metal_balance

    customer = deletion_request.customer
    user = customer.user
    accounts = customer.scheme_accounts.select_related("metal_grade")
    contributions = Contribution.objects.filter(scheme_account__customer=customer)
    enrolments = customer.enrolment_requests.all()
    balances = []
    flags = []
    financial_exceptions = 0
    for account in accounts:
        cash = get_cash_bonus_summary(account)
        quantity = get_metal_balance(account)
        principal = Decimal("0.00")
        from django.core.exceptions import ValidationError
        from schemes.statement_selectors import benefit_document, inr_statement, validate_metal_document_history
        if account.savings_mode == "INR_CREDIT":
            try:
                document = inr_statement(account)
                principal, benefit = document.remaining_entitlement, document.benefit
            except ValidationError:
                benefit = benefit_document(account)
                principal = None  # Unknown is never presented as zero liability.
                financial_exceptions += 1
                flags.append(f"{account.scheme_number}: INR principal/disposition evidence requires reconciliation.")
        else:
            benefit = benefit_document(account)
            try:
                validate_metal_document_history(account)
            except ValidationError:
                financial_exceptions += 1
                flags.append(f"{account.scheme_number}: metal settlement/benefit history requires reconciliation.")
        if benefit and benefit.needs_review:
            financial_exceptions += 1
            flags.append(f"{account.scheme_number}: benefit evidence requires reconciliation; retain the recorded right.")
        balances.append(
            DeletionAccountBalance(
                scheme_number=account.scheme_number,
                status=account.get_status_display(),
                grade=(
                    account.metal_grade.code
                    if account.metal_grade_id else "INR purchase credit" if account.savings_mode == "INR_CREDIT" else "CASH (legacy)"
                ),
                cash_principal=cash.principal_outstanding,
                cash_earned_bonus=cash.earned_bonus,
                metal_quantity=quantity,
                purchase_credit_principal=principal,
                benefit_pending=bool(benefit and (benefit.pending_right or benefit.needs_review)),
            )
        )
    if balances:
        flags.append("Scheme history exists, even if current balances are zero; review contractual and financial retention.")
    if any(
        b.cash_principal != 0 or b.cash_earned_bonus != 0 or b.metal_quantity != 0
        or b.purchase_credit_principal != 0 or b.benefit_pending
        for b in balances
    ):
        flags.append("A non-zero entitlement or balance exception needs settlement/reconciliation review. Deletion never forfeits it.")
    if accounts.exclude(status=SchemeAccount.Status.REDEEMED).exists():
        flags.append("An agreement is still open, including any zero-balance agreement; review its remaining obligations.")
    pending = contributions.filter(status=Contribution.Status.PENDING).count()
    if pending:
        flags.append(f"Pending contributions: {pending}. Inspect provider state using the existing reconciliation workflow; expiry is not provider cancellation.")
    allocation_exceptions = contributions.filter(
        Q(status=Contribution.Status.PAID_UNALLOCATED)
        | Q(
            status=Contribution.Status.PAID,
            scheme_account__savings_mode__in=["GOLD", "SILVER"],
            metal_allocation__isnull=True,
        )
    ).count()
    if allocation_exceptions:
        flags.append(f"Payments needing allocation review: {allocation_exceptions}.")
    # Include orphaned events that can be matched by order/reference, without
    # fetching raw provider payloads or credentials into the owner preview.
    webhooks = PaymentWebhookEvent.objects.filter(
        Q(contribution__in=contributions)
        | Q(
            gateway_order_id__in=contributions.exclude(
                gateway_order_id__isnull=True,
            ).exclude(gateway_order_id="").values("gateway_order_id"),
        )
        | Q(
            gateway_reference__in=contributions.exclude(
                gateway_reference__isnull=True,
            ).exclude(gateway_reference="").values("gateway_reference"),
        )
    )
    unresolved = unresolved_payment_events(webhooks).count()
    if unresolved:
        flags.append(f"Linked or identifier-matched webhook events need review: {unresolved}.")
    if enrolments.filter(
        status=SchemeEnrolmentRequest.Status.PENDING_OWNER_REVIEW,
    ).exists():
        flags.append("An enrolment request remains pending, including any expired request not yet closed by the owner.")
    if (
        user.is_active or user.is_staff or user.is_superuser
        or user.role != user.Role.CUSTOMER
    ):
        flags.append("Access containment or customer-role integrity needs review before further action.")
    if SocialAccount.objects.filter(user=user).exists():
        flags.append("A social credential remains; investigate containment integrity.")

    registrations = CustomerRegistration.objects.filter(
        Q(approved_user=user)
        | Q(email__iexact=customer.email)
        | Q(email__iexact=deletion_request.requested_email)
    )
    inventory = (
        ("Login/profile", 1, "Proposed removal: password, login email, names, phone and address not needed for a documented hold; keep protected internal keys."),
        ("Allauth email addresses", EmailAddress.objects.filter(user=user).count(), "Remove login bindings at completion; containment alone has not erased them."),
        ("Social accounts", SocialAccount.objects.filter(user=user).count(), "Remove credential/profile bindings; investigate any remaining after containment."),
        ("Stored social tokens", SocialToken.objects.filter(account__user=user).count(), "Must be zero; do not expose or copy token values."),
        ("Invitations", CustomerInvitation.objects.filter(user=user).count(), "Remove obsolete access tokens and duplicate email, subject to minimal decision evidence."),
        ("Linked or email-matched registrations", registrations.count(), "Review identity duplicates, consent and decisions individually; an email match is not authority to erase another application."),
        ("Enrolment requests", enrolments.count(), "Review customer messages, agreement/disclosure evidence and pending decisions."),
        ("Scheme agreements", len(balances), "Preserve contract and exact-grade entitlement history; document necessary identity separately."),
        ("Contributions", contributions.count(), "Preserve amount, channel/mode, status, rate lock and payment evidence. Includes historical test-mode records."),
        ("Metal allocations", MetalAllocation.objects.filter(contribution__in=contributions).count(), "Preserve six-decimal quantities and grade, including reversal history."),
        ("Cash receipts", InStoreCashReceipt.objects.filter(contribution__in=contributions).count(), "Review receipt and correction evidence; never cascade financial history."),
        ("Redemptions", Redemption.objects.filter(scheme_account__customer=customer).count(), "Preserve settlement and associated reversal evidence."),
        ("Webhook events", webhooks.count(), "Preserve payment/recovery evidence; local completion does not delete provider records."),
        ("Scheme reminders", SchemeReminder.objects.filter(scheme_account__customer=customer).count(), "Review recipient copies and delivery evidence held by email providers, including Amazon SES and historical Postmark copies."),
        ("Related financial audits", AuditEvent.objects.filter(Q(actor=user) | Q(scheme_account__customer=customer) | Q(contribution__in=contributions) | Q(redemption__scheme_account__customer=customer)).distinct().count(), "Review actor labels, free text and identifiers; immutable evidence is not automatically anonymous."),
        ("Privacy requests", customer.account_deletion_requests.count(), "Minimize request email/digests and customer actor labels; decisions/actions have their own bounded evidence purpose."),
    )
    from schemes import models as financial
    retained_history = (
        ("Closure requests", financial.SchemeClosureRequest, "scheme_account__customer"),
        ("Closure decisions", financial.SchemeClosureEvent, "request__scheme_account__customer"),
        ("Configured metal settlements", financial.ConfiguredSettlement, "redemption__scheme_account__customer"),
        ("Configured metal settlement reversals", financial.ConfiguredSettlementReversal, "settlement__redemption__scheme_account__customer"),
        ("INR principal receipts", financial.InrPrincipalReceipt, "scheme_account__customer"),
        ("INR principal corrections", financial.InrPrincipalCorrection, "receipt__scheme_account__customer"),
        ("INR settlement proposals", financial.InrSettlementProposal, "scheme_account__customer"),
        ("INR fulfilments", financial.InrSettlementFulfilment, "proposal__scheme_account__customer"),
        ("INR completions", financial.InrSettlementCompletion, "proposal__scheme_account__customer"),
        ("INR resolutions", financial.InrSettlementResolution, "proposal__scheme_account__customer"),
        ("INR physical returns", financial.InrFulfilmentReturn, "fulfilment__proposal__scheme_account__customer"),
        ("Retained benefit awards", financial.SchemeBenefitAward, "scheme_account__customer"),
        ("Benefit invoice applications", financial.BenefitInvoiceFulfilment, "award__scheme_account__customer"),
        ("Benefit invoice reversals", financial.BenefitInvoiceReversal, "fulfilment__award__scheme_account__customer"),
        ("Benefit reapplication reviews", financial.BenefitReapplicationDecision, "reversal__fulfilment__award__scheme_account__customer"),
    )
    inventory += tuple((label, model.objects.filter(**{path: customer}).count(),
        "Retain financial sources, invoice/return links and authority evidence, including embedded identity and free text; completion does not erase them.")
        for label, model, path in retained_history)
    return DeletionDispositionPreview(
        generated_at=timezone.now(),
        account_balances=tuple(balances),
        inventory=inventory,
        review_flags=tuple(flags),
        allocation_exceptions=allocation_exceptions,
        unresolved_webhooks=unresolved,
        has_financial_history=bool(balances) or enrolments.exists() or AuditEvent.objects.filter(actor=user).exists(),
        financial_exceptions=financial_exceptions,
        external_checks=(
            "Razorpay: verify unresolved captures, refunds, disputes and provider retention. Local zero counts do not establish their absence.",
            "Amazon SES, historical Postmark copies, Google and support mail: record deletion requests or justified retention and delivery evidence; do not claim provider copies were removed without confirmation.",
            "Showroom/exported records: review downloaded statements, CSVs and paper records; identify the responsible person and disposition evidence.",
            "Cloudflare/Caddy/application logs and Linode backups: record actual retention/expiry, restricted access and restoration suppression. A database restore must not resurrect erased accounts.",
            "For each retained category: record purpose/basis, minimum fields, start event, duration or hold-release condition, next review and responsible owner. Do not assume a blanket statutory period.",
        ),
    )


def customer_account_deletion_queue():
    return (
        CustomerAccountDeletionRequest.objects.filter(
            status__in=[
                CustomerAccountDeletionRequest.Status.CONTAINED,
                CustomerAccountDeletionRequest.Status.AWAITING_SETTLEMENT,
                CustomerAccountDeletionRequest.Status.COMPLETED_WITH_RETENTION,
            ]
        )
        .select_related("customer", "customer__user")
        .annotate(
            scheme_account_count=Count(
                "customer__scheme_accounts",
                distinct=True,
            ),
            contribution_count=Count(
                "customer__scheme_accounts__contributions",
                distinct=True,
            ),
            pending_provider_count=Count(
                "customer__scheme_accounts__contributions",
                filter=Q(
                    customer__scheme_accounts__contributions__status="PENDING",
                    customer__scheme_accounts__contributions__payment_gateway="razorpay",
                ),
                distinct=True,
            ),
        )
        .order_by("owner_review_due_at", "requested_at")
    )


def customer_account_deletion_detail(deletion_request_id):
    return (
        CustomerAccountDeletionRequest.objects.select_related(
            "customer",
            "customer__user",
        )
        .prefetch_related("actions", "decisions")
        .annotate(
            scheme_account_count=Count(
                "customer__scheme_accounts",
                distinct=True,
            ),
            contribution_count=Count(
                "customer__scheme_accounts__contributions",
                distinct=True,
            ),
            pending_provider_count=Count(
                "customer__scheme_accounts__contributions",
                filter=Q(
                    customer__scheme_accounts__contributions__status="PENDING",
                    customer__scheme_accounts__contributions__payment_gateway="razorpay",
                ),
                distinct=True,
            ),
        )
        .get(pk=deletion_request_id)
    )
