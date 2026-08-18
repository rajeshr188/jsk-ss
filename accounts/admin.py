from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .forms import CustomUserCreationForm, CustomUserChangeForm
from .models import CustomUser


class CustomUserAdmin(UserAdmin):
    add_form = CustomUserCreationForm
    form = CustomUserChangeForm
    model = CustomUser
    list_display = [
        "email",
        "username",
        "role",
        "is_staff",
        "is_active",
    ]
    fieldsets = UserAdmin.fieldsets + (("Application role", {"fields": ("role",)}),)
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Application role", {"fields": ("email", "role")}),
    )


admin.site.register(CustomUser, CustomUserAdmin)
