from decimal import Decimal, InvalidOperation

from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def page_link(context, number, key="page"):
    query = context["request"].GET.copy()
    query[key or "page"] = number
    return "?" + query.urlencode()


@register.filter
def inr(value, places=2):
    """Indian digit grouping for display only; no financial arithmetic."""
    try:
        amount = Decimal(str(value))
        if not amount.is_finite():
            return "—"
        precision = int(places)
        if precision not in (2, 4, 6):
            precision = 2
        whole, fraction = f"{abs(amount):.{precision}f}".split(".")
        suffix = whole[-3:]
        prefix = whole[:-3]
        groups = []
        while prefix:
            groups.insert(0, prefix[-2:])
            prefix = prefix[:-2]
        return ("-" if amount < 0 else "") + ",".join([*groups, suffix]) + "." + fraction
    except (InvalidOperation, ValueError, TypeError):
        return "—"


@register.simple_tag(takes_context=True)
def query_link(context, **changes):
    query = context["request"].GET.copy()
    query.pop("page", None)
    for key, value in changes.items():
        if value is None or value == "":
            query.pop(key, None)
        else:
            query[key] = value
    return "?" + query.urlencode()
