from django.contrib.auth.forms import AdminUserCreationForm, SetPasswordForm, UserChangeForm

from .models import CustomUser


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
