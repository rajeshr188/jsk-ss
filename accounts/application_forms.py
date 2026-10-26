from django import forms
from django.utils import timezone

from schemes.forms import SchemeEnrolmentRequestForm
from .forms import CustomerRegistrationForm, CustomerRegistrationApprovalForm


class PlanApplicationContactForm(SchemeEnrolmentRequestForm):
    full_name = CustomerRegistrationForm.base_fields["full_name"]
    email = CustomerRegistrationForm.base_fields["email"]
    mobile_number = CustomerRegistrationForm.base_fields["mobile_number"]
    accept_policies = CustomerRegistrationForm.base_fields["accept_policies"]
    website = CustomerRegistrationForm.base_fields["website"]
    offer_digest = forms.CharField(widget=forms.HiddenInput)
    clean_full_name = CustomerRegistrationForm.clean_full_name
    clean_email = CustomerRegistrationForm.clean_email
    clean_mobile_number = CustomerRegistrationForm.clean_mobile_number

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["requested_months"].max_value = 32767


class PlanApplicationCompletionForm(SchemeEnrolmentRequestForm):
    accept_policies = CustomerRegistrationForm.base_fields["accept_policies"]
    address = CustomerRegistrationForm.base_fields["address"]
    start_date = forms.DateField(
        label="Requested agreement start date", widget=forms.DateInput(attrs={"type": "date"}),
        help_text="This anchors the agreement and any monthly windows. Duration, qualifying payment count and benefit rules are separate. Choose today or later; approval is still required.",
    )
    offer_digest = forms.CharField(widget=forms.HiddenInput)
    clean_address = CustomerRegistrationForm.clean_address

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["requested_months"].max_value = 32767
        self.fields["disclosure_accepted"].label = (
            "I confirm this plan, accumulation, amount, eligibility and benefit rules, and requested start date. "
            "This is a non-binding application; the showroom must verify my contact details "
            "and approve it before an agreement and payment access are available."
        )

    def clean_start_date(self):
        value = self.cleaned_data["start_date"]
        if value < timezone.localdate():
            raise forms.ValidationError("Confirm a start date today or later.")
        return value


class PlanApplicationApprovalForm(CustomerRegistrationApprovalForm):
    terms_reviewed = forms.BooleanField(
        label="I reviewed the customer-confirmed plan, accumulation, amount, independent eligibility and benefit rules, and start date with the applicant.",
    )
