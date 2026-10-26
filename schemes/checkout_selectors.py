"""Read-only checkout continuation; never calls the payment provider."""
from django.conf import settings

from .models import RazorpayOrderRequest


def checkout_can_resume(contribution):
    if (contribution.status != "PENDING" or not contribution.gateway_order_id
            or contribution.gateway_mode != settings.RAZORPAY_MODE or contribution.razorpay_checkout_expired):
        return False
    request = RazorpayOrderRequest.objects.filter(contribution=contribution).first()
    if request and (hasattr(request, "recovery") or request.amount_subunits != contribution.amount * 100
            or request.gateway_mode != contribution.gateway_mode
            or request.scheme_rate_id != contribution.scheme_rate_id
            or request.checkout_expires_at != contribution.checkout_expires_at):
        return False
    from .selectors import get_customer_payment_availability
    return get_customer_payment_availability(contribution.scheme_account).allowed
