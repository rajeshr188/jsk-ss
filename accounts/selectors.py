from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount, SocialToken
from django.db.models import Count, Q
from django.utils import timezone

from .models import (
    CustomerAccountDeletionRequest,
    CustomerInvitation,
    CustomerRegistration,
)


@dataclass(frozen=True)
class DeletionAccountBalance:
    scheme_number: str
    status: str
    grade: str
    cash_principal: Decimal
    cash_earned_bonus: Decimal
    metal_quantity: Decimal


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


def customer_account_deletion_disposition(deletion_request):
    """Read-only inventory, never a decision or proof that erasure is safe.

    Per-account balances use the financial selectors, without summing different
    grades or netting separate agreements. External disputes cannot be inferred
    from local payment status. A future completion service must recheck under locks.
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
    for account in accounts:
        cash = get_cash_bonus_summary(account)
        quantity = get_metal_balance(account)
        balances.append(
            DeletionAccountBalance(
                scheme_number=account.scheme_number,
                status=account.get_status_display(),
                grade=(
                    account.metal_grade.code
                    if account.metal_grade_id else "CASH (legacy)"
                ),
                cash_principal=cash.principal_outstanding,
                cash_earned_bonus=cash.earned_bonus,
                metal_quantity=quantity,
            )
        )
    if balances:
        flags.append("Scheme history exists, even if current balances are zero; review contractual and financial retention.")
    if any(
        b.cash_principal != 0 or b.cash_earned_bonus != 0 or b.metal_quantity != 0
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
    unresolved = webhooks.exclude(status__in=[
        PaymentWebhookEvent.Status.PROCESSED,
        PaymentWebhookEvent.Status.IGNORED,
    ]).count()
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
        ("Scheme reminders", SchemeReminder.objects.filter(scheme_account__customer=customer).count(), "Review recipient copies and delivery evidence, including copies held by Postmark."),
        ("Related financial audits", AuditEvent.objects.filter(Q(actor=user) | Q(scheme_account__customer=customer) | Q(contribution__in=contributions) | Q(redemption__scheme_account__customer=customer)).distinct().count(), "Review actor labels, free text and identifiers; immutable evidence is not automatically anonymous."),
        ("Privacy requests", customer.account_deletion_requests.count(), "Minimize request email/digests and customer actor labels; decisions/actions have their own bounded evidence purpose."),
    )
    return DeletionDispositionPreview(
        generated_at=timezone.now(),
        account_balances=tuple(balances),
        inventory=inventory,
        review_flags=tuple(flags),
        allocation_exceptions=allocation_exceptions,
        unresolved_webhooks=unresolved,
        has_financial_history=bool(balances) or enrolments.exists() or AuditEvent.objects.filter(actor=user).exists(),
        external_checks=(
            "Razorpay: verify unresolved captures, refunds, disputes and provider retention. Local zero counts do not establish their absence.",
            "Postmark, Google and support mail: record deletion requests or justified retention and delivery evidence; do not claim provider copies were removed without confirmation.",
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
