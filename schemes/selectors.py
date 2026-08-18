from .models import Customer, SchemeAccount


def get_customer_scheme_summary(user):
    return SchemeAccount.objects.filter(customer__user=user).select_related("plan", "customer")


def get_owner_customers():
    return Customer.objects.select_related("user").prefetch_related("scheme_accounts")


def get_owner_customer(customer_id):
    return Customer.objects.select_related("user").prefetch_related(
        "scheme_accounts__plan"
    ).get(pk=customer_id)

