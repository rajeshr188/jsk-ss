from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.models import F, Q

from schemes.models import (
    MetalAllocation,
    MetalGrade,
    Redemption,
    SchemeAccount,
    SchemeRate,
)


EXPECTED_GRADES = {
    MetalGrade.GOLD_22K_916: {
        "metal": MetalGrade.Metal.GOLD,
        "display_name": "22K Gold",
        "fineness": Decimal("0.916000"),
    },
    MetalGrade.GOLD_24K_9999: {
        "metal": MetalGrade.Metal.GOLD,
        "display_name": "24K Gold",
        "fineness": Decimal("0.999900"),
    },
    MetalGrade.SILVER_999: {
        "metal": MetalGrade.Metal.SILVER,
        "display_name": "999 Silver",
        "fineness": Decimal("0.999000"),
    },
}


class Command(BaseCommand):
    help = "Validate exact metal-grade definitions and financial-record mappings."

    def handle(self, *args, **options):
        if MetalGrade._meta.db_table not in connection.introspection.table_names():
            self._check_legacy_schema()
            return

        definition_errors = 0
        for code, expected in EXPECTED_GRADES.items():
            grade = MetalGrade.objects.filter(code=code).first()
            if grade is None or any(
                getattr(grade, field) != value for field, value in expected.items()
            ):
                definition_errors += 1

        metal_accounts_missing_grade = SchemeAccount.objects.filter(
            savings_mode__in=[
                SchemeAccount.SavingsMode.GOLD,
                SchemeAccount.SavingsMode.SILVER,
            ],
            metal_grade__isnull=True,
        ).count()
        cash_accounts_with_grade = SchemeAccount.objects.filter(
            savings_mode=SchemeAccount.SavingsMode.CASH,
            metal_grade__isnull=False,
        ).count()
        account_grade_mismatches = (
            SchemeAccount.objects.filter(metal_grade__isnull=False)
            .exclude(savings_mode=F("metal_grade__metal"))
            .count()
        )
        rate_grade_mismatches = SchemeRate.objects.filter(
            ~Q(metal=F("metal_grade__metal"))
            | ~Q(purity=F("metal_grade__fineness"))
        ).count()
        allocation_grade_mismatches = MetalAllocation.objects.filter(
            ~Q(metal=F("metal_grade__metal"))
            | ~Q(metal_grade=F("scheme_rate__metal_grade"))
            | ~Q(metal_grade=F("contribution__scheme_account__metal_grade"))
        ).count()
        redemption_grade_mismatches = Redemption.objects.filter(
            Q(cash_amount__isnull=False, metal_grade__isnull=False)
            | Q(cash_amount__isnull=True, metal_grade__isnull=True)
            | (
                Q(metal_grade__isnull=False)
                & ~Q(metal_grade=F("scheme_account__metal_grade"))
            )
        ).count()

        counts = {
            "definition_errors": definition_errors,
            "metal_accounts_missing_grade": metal_accounts_missing_grade,
            "cash_accounts_with_grade": cash_accounts_with_grade,
            "account_grade_mismatches": account_grade_mismatches,
            "rate_grade_mismatches": rate_grade_mismatches,
            "allocation_grade_mismatches": allocation_grade_mismatches,
            "redemption_grade_mismatches": redemption_grade_mismatches,
        }
        status = "ok" if not any(counts.values()) else "blocked"
        self.stdout.write(
            " ".join(
                [
                    f"graded_metal_rate_check status={status}",
                    f"release={settings.APP_RELEASE}",
                    *[f"{name}={value}" for name, value in counts.items()],
                ]
            )
        )
        if status == "blocked":
            blockers = [name for name, value in counts.items() if value]
            raise CommandError(
                "Graded metal-rate integrity is blocked by: " + ", ".join(blockers)
            )

    def _check_legacy_schema(self):
        queries = {
            "paid_unallocated_metal": """
                SELECT COUNT(*)
                FROM schemes_contribution contribution
                JOIN schemes_schemeaccount account
                  ON account.id = contribution.scheme_account_id
                WHERE contribution.status = 'PAID_UNALLOCATED'
                  AND account.savings_mode IN ('GOLD', 'SILVER')
            """,
            "open_razorpay_orders": """
                SELECT COUNT(*)
                FROM schemes_contribution
                WHERE status = 'PENDING'
                  AND payment_gateway = 'razorpay'
                  AND gateway_order_id IS NOT NULL
                  AND gateway_order_id <> ''
            """,
            "allocation_contract_mismatches": """
                SELECT COUNT(*)
                FROM schemes_metalallocation allocation
                JOIN schemes_schemerate rate
                  ON rate.id = allocation.scheme_rate_id
                JOIN schemes_contribution contribution
                  ON contribution.id = allocation.contribution_id
                JOIN schemes_schemeaccount account
                  ON account.id = contribution.scheme_account_id
                WHERE allocation.metal <> rate.metal
                   OR allocation.metal <> account.savings_mode
            """,
            "redemption_contract_mismatches": """
                SELECT COUNT(*)
                FROM schemes_redemption redemption
                JOIN schemes_schemeaccount account
                  ON account.id = redemption.scheme_account_id
                WHERE (redemption.gold_quantity IS NOT NULL
                       AND account.savings_mode <> 'GOLD')
                   OR (redemption.silver_quantity IS NOT NULL
                       AND account.savings_mode <> 'SILVER')
                   OR (redemption.cash_amount IS NOT NULL
                       AND account.savings_mode <> 'CASH')
            """,
        }
        counts = {}
        with connection.cursor() as cursor:
            for name, query in queries.items():
                cursor.execute(query)
                counts[name] = cursor.fetchone()[0]
        status = "ready" if not any(counts.values()) else "blocked"
        self.stdout.write(
            " ".join(
                [
                    f"graded_metal_rate_preflight status={status}",
                    f"release={settings.APP_RELEASE}",
                    *[f"{name}={value}" for name, value in counts.items()],
                ]
            )
        )
        if status == "blocked":
            blockers = [name for name, value in counts.items() if value]
            raise CommandError(
                "Graded metal-rate migration is blocked by: " + ", ".join(blockers)
            )
