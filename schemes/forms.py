from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password

from .models import SchemeAccount, SchemePlan


class CustomerCreateForm(forms.Form):
    full_name = forms.CharField(max_length=200)
    email = forms.EmailField(max_length=150)
    mobile_number = forms.CharField(max_length=20)
    address = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), required=False)
    password1 = forms.CharField(label="Temporary password", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Confirm temporary password", widget=forms.PasswordInput)

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if get_user_model().objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("A user with this email already exists.")
        return email

    def clean(self):
        cleaned = super().clean()
        password = cleaned.get("password1")
        if password and password != cleaned.get("password2"):
            self.add_error("password2", "The passwords do not match.")
        if password:
            validate_password(password)
        return cleaned


class SchemePlanForm(forms.ModelForm):
    class Meta:
        model = SchemePlan
        fields = [
            "name",
            "code",
            "description",
            "minimum_months",
            "default_months",
            "amount_rule",
            "frequency_rule",
            "fixed_contribution_amount",
            "minimum_contribution",
            "maximum_contribution",
            "allow_contributions_after_eligibility",
            "active",
        ]


class EnrolmentForm(forms.Form):
    plan = forms.ModelChoiceField(queryset=SchemePlan.objects.none())
    savings_mode = forms.ChoiceField(choices=SchemeAccount.SavingsMode.choices)
    start_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    agreed_months = forms.IntegerField(min_value=12)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["plan"].queryset = SchemePlan.objects.filter(active=True)

    def clean(self):
        cleaned = super().clean()
        plan = cleaned.get("plan")
        agreed_months = cleaned.get("agreed_months")
        if plan and agreed_months and agreed_months < plan.minimum_months:
            self.add_error(
                "agreed_months",
                f"This plan requires at least {plan.minimum_months} months.",
            )
        return cleaned
