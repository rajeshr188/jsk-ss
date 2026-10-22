from django.utils import timezone
from django.urls import reverse

from .applications import application_terms_current
from .models import CustomerRegistration, PlanApplication


def get_activated_plan(user):
    """Only an explicit approved identity/agreement link supplies continuation."""
    return PlanApplication.objects.filter(
        registration__approved_user=user,
        registration__status=CustomerRegistration.Status.APPROVED,
        scheme_account__customer__user=user,
    ).select_related("scheme_account__plan", "scheme_account__metal_grade").order_by(
        "-registration__reviewed_at", "-pk",
    ).first()


def activated_plan_url(user):
    application = get_activated_plan(user)
    if application is not None:
        return reverse("schemes:my_scheme_detail", args=[application.scheme_account.scheme_number])
    return None


def get_customer_plan_applications(user):
    return PlanApplication.objects.filter(
        registration__approved_user=user,
        scheme_account__customer__user=user,
    ).select_related("registration", "plan", "metal_grade", "scheme_account").order_by(
        "-registration__reviewed_at", "-pk",
    )


def first_payment_preference(account, user):
    from schemes.models import Contribution
    if account.amount_rule_snapshot != "VARIABLE" or account.contributions.filter(
        status__in=[Contribution.Status.PAID, Contribution.Status.PAID_UNALLOCATED],
    ).exists():
        return None
    return PlanApplication.objects.filter(
        scheme_account=account, registration__approved_user=user,
        scheme_account__customer__user=user,
    ).values_list("requested_amount", flat=True).first()


def get_plan_application(registration_id):
    return PlanApplication.objects.select_related(
        "registration__approved_user", "plan", "metal_grade", "scheme_account__customer__user",
    ).filter(registration_id=registration_id).first()


def application_progress(application):
    registration = application.registration
    if application.scheme_account_id:
        user = application.scheme_account.customer.user
        if user.has_usable_password():
            return "Approved", "Sign in to view your approved plan."
        return "Approved — set up your login", "Use the password-setup email to activate your login. Contact the showroom if it did not arrive."
    if registration.status == CustomerRegistration.Status.REJECTED:
        return "Not approved", "Contact the showroom to discuss your application."
    if application.expires_at <= timezone.now() or registration.status == CustomerRegistration.Status.EXPIRED:
        return "Application expired", "Contact the showroom before applying again."
    if not registration.email_verified_at:
        return "Verify your email", "Use the verification email to continue."
    if not application.completed_at:
        return "Complete your details", "Add your address and confirm your plan preferences below."
    if not application_terms_current(application):
        return "Confirm current terms", "The offer or requested start date needs a fresh confirmation. Review the current terms below."
    return "Showroom review", "The showroom must verify your contact details and review your application. You can contact the showroom for help."
