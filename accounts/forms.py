from django import forms
from django.contrib.auth.forms import AdminUserCreationForm, SetPasswordForm, UserChangeForm

from .models import CustomUser
from .services import normalize_indian_mobile


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
