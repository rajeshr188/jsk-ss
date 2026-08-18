from decimal import Decimal

from django.db.models import DecimalField, Q, Sum, Value
from django.db.models.functions import Coalesce

from .models import Contribution, Customer, SchemeAccount


def get_customer_scheme_summary(user):
    return (
        SchemeAccount.objects.filter(customer__user=user)
        .select_related("plan", "customer")
        .annotate(
            cash_balance=Coalesce(
                Sum(
                    "contributions__amount",
                    filter=Q(contributions__status=Contribution.Status.PAID),
                ),
                Value(Decimal("0.00")),
                output_field=DecimalField(max_digits=14, decimal_places=2),
            )
        )
    )


def get_owner_customers():
    return Customer.objects.select_related("user").prefetch_related("scheme_accounts")


def get_owner_customer(customer_id):
    return Customer.objects.select_related("user").prefetch_related(
        "scheme_accounts__plan"
    ).get(pk=customer_id)


def get_customer_scheme_account(user, scheme_number):
    return get_customer_scheme_summary(user).filter(scheme_number=scheme_number).first()


def get_contribution_history(scheme_account):
    return scheme_account.contributions.all()


def get_owner_contributions():
    return Contribution.objects.select_related(
        "scheme_account", "scheme_account__customer", "scheme_account__plan"
    )


def get_cash_balance(scheme_account):
    if scheme_account.savings_mode != SchemeAccount.SavingsMode.CASH:
        return Decimal("0.00")
    return scheme_account.contributions.filter(status=Contribution.Status.PAID).aggregate(
        total=Coalesce(
            Sum("amount"),
            Value(Decimal("0.00")),
            output_field=DecimalField(max_digits=14, decimal_places=2),
        )
    )["total"]
