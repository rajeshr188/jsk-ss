from django.core.management.base import BaseCommand, CommandError
from django.db.models import Sum

from schemes.models import Contribution, Redemption, SchemeAccount, SchemePlan
from schemes.services import cash_scheme_activity_is_enabled


class Command(BaseCommand):
    help = (
        "Verify that production CASH activity is disabled and no CASH payment or "
        "liability exists before promoting the metal-only boundary."
    )

    def handle(self, *args, **options):
        cash_accounts = SchemeAccount.objects.filter(
            savings_mode=SchemeAccount.SavingsMode.CASH
        )
        cash_contributions = Contribution.objects.filter(
            scheme_account__savings_mode=SchemeAccount.SavingsMode.CASH
        )
        verified_cash = cash_contributions.filter(
            status__in=[
                Contribution.Status.PAID,
                Contribution.Status.PAID_UNALLOCATED,
            ]
        )
        values = {
            "cash_activity_enabled": cash_scheme_activity_is_enabled(),
            "cash_accounts_total": cash_accounts.count(),
            "cash_accounts_open": cash_accounts.exclude(
                status=SchemeAccount.Status.REDEEMED
            ).count(),
            "cash_accounts_redeemed": cash_accounts.filter(
                status=SchemeAccount.Status.REDEEMED
            ).count(),
            "pending_cash_payments": cash_contributions.filter(
                status=Contribution.Status.PENDING
            ).count(),
            "verified_cash_payments": verified_cash.count(),
            "verified_cash_amount_inr": (
                verified_cash.aggregate(total=Sum("amount"))["total"] or 0
            ),
            "cash_redemptions": Redemption.objects.filter(
                scheme_account__savings_mode=SchemeAccount.SavingsMode.CASH
            ).count(),
            "plans_with_nonzero_cash_bonus": SchemePlan.objects.filter(
                cash_bonus_percentage__gt=0
            ).count(),
        }
        blockers = [
            name
            for name in (
                "cash_activity_enabled",
                "pending_cash_payments",
                "verified_cash_payments",
                "verified_cash_amount_inr",
                "cash_redemptions",
                "plans_with_nonzero_cash_bonus",
            )
            if values[name]
        ]
        status = "blocked" if blockers else "ok"
        summary = " ".join(
            [f"cash_boundary_check status={status}"]
            + [f"{name}={value}" for name, value in values.items()]
        )
        self.stdout.write(summary)
        if blockers:
            raise CommandError(
                "Metal-only promotion is blocked by: " + ", ".join(blockers)
            )
