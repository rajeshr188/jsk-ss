from django import forms
from django.contrib.auth.forms import AdminUserCreationForm, SetPasswordForm, UserChangeForm

from .models import CustomUser
from .services import normalize_indian_mobile
from .deletion import RETENTION_CATEGORIES


class CustomUserCreationForm(AdminUserCreationForm):
    class Meta:
        model = CustomUser
        fields = (
            "email",
            "username",
        )


class CustomUserChangeForm(UserChangeForm):
    class Meta:
        model = CustomUser
        fields = (
            "email",
            "username",
        )


class CustomerInvitationPasswordForm(SetPasswordForm):
    error_css_class = "is-invalid"


class CustomerRegistrationForm(forms.Form):
    full_name = forms.CharField(max_length=150)
    email = forms.EmailField(max_length=150)
    mobile_number = forms.CharField(
        max_length=20,
        help_text="Enter a 10-digit Indian mobile number.",
    )
    address = forms.CharField(
        max_length=1000,
        widget=forms.Textarea(attrs={"rows": 3}),
    )
    accept_policies = forms.BooleanField(
        label="I have read and agree to the Terms and Privacy Policy.",
    )
    website = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={
                "autocomplete": "off",
                "tabindex": "-1",
            }
        ),
    )

    def clean_full_name(self):
        value = " ".join(self.cleaned_data["full_name"].split())
        if len(value) < 2:
            raise forms.ValidationError("Enter the customer's full name.")
        return value

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()

    def clean_mobile_number(self):
        return normalize_indian_mobile(self.cleaned_data["mobile_number"])

    def clean_address(self):
        value = self.cleaned_data["address"].strip()
        if len(value) < 8:
            raise forms.ValidationError("Enter the customer's complete address.")
        return value


class CustomerRegistrationApprovalForm(forms.Form):
    mobile_verified = forms.BooleanField(
        label="I contacted the applicant and verified this mobile number.",
    )
    reason = forms.CharField(
        label="Approval reason",
        max_length=500,
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Record how identity and contact details were checked.",
    )


class CustomerRegistrationRejectionForm(forms.Form):
    reason = forms.CharField(
        label="Rejection reason",
        max_length=500,
        widget=forms.Textarea(attrs={"rows": 3}),
    )


class CustomerAccountDeletionPublicForm(forms.Form):
    email = forms.EmailField(max_length=254)
    website = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={"autocomplete": "off", "tabindex": "-1"}
        ),
    )

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()


class CustomerAccountDeletionAuthenticatedForm(forms.Form):
    confirm = forms.BooleanField(
        label=(
            "I understand that my login will be disabled immediately while the "
            "showroom reviews deletion and any records that must be retained."
        )
    )


class CustomerAccountDeletionHoldForm(forms.Form):
    reason = forms.CharField(
        label="Reason for continued review or retention",
        max_length=1000,
        widget=forms.Textarea(attrs={"rows": 3}),
    )
    retained_categories = forms.CharField(
        label="Record categories currently retained",
        max_length=1000,
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text=(
            "Use plain language, for example: scheme agreement, contribution "
            "receipts, metal entitlement, or open provider review."
        ),
    )
    review_due_at = forms.DateTimeField(
        label="Next review date and time",
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
    )


class CustomerDeletionCompletionForm(forms.Form):
    reason = forms.CharField(max_length=3000, widget=forms.Textarea(attrs={"rows": 2}))
    external_review = forms.CharField(
        max_length=3000, widget=forms.Textarea(attrs={"rows": 3}),
        label="External review evidence and outstanding follow-ups",
        help_text="Document provider, export, log and backup checks. Do not paste customer identifiers, credentials or private correspondence.",
    )
    retain_profile_fields = forms.MultipleChoiceField(
        required=False, choices=[(v, v.replace("_", " ").title()) for v in ("full_name", "email", "mobile_number", "address")],
        widget=forms.CheckboxSelectMultiple,
        label="Showroom profile fields that must be retained",
        help_text="Leave unneeded fields unchecked. Open agreements/entitlements require name and email for settlement; the login is removed regardless.",
    )
    confirmation = forms.CharField(label="Type the request UUID to confirm irreversible removal")
    reviewed = forms.BooleanField(label="I reviewed the disposition and external records, and approve the stated purposes, fields and review dates.")


class CustomerDeletionRetentionForm(forms.Form):
    category = forms.ChoiceField(choices=RETENTION_CATEGORIES, disabled=True)
    treatment = forms.ChoiceField(choices=[("RETAIN", "Retain for documented purpose"), ("NOT_APPLICABLE", "Not applicable — explain why")])
    purpose = forms.CharField(max_length=1500, widget=forms.Textarea(attrs={"rows": 2}))
    fields = forms.CharField(max_length=1500, label="Minimum fields/records retained, or none with explanation")
    period_start = forms.CharField(max_length=1500, label="Event/date that starts the retention period")
    period_or_condition = forms.CharField(max_length=1500, label="Duration or hold-release condition and next action")
    review_on = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}), label="Next review date (within 365 days)")


CustomerDeletionRetentionFormSet = forms.formset_factory(
    CustomerDeletionRetentionForm, extra=0, min_num=7, max_num=7,
    validate_min=True, validate_max=True,
)
