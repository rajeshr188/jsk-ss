from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .forms import CustomUserCreationForm, CustomUserChangeForm
from .models import (
    CustomUser,
    CustomerAccountDeletionAction,
    CustomerAccountDeletionAttempt,
    CustomerAccountDeletionDecision,
    CustomerAccountDeletionRequest,
    CustomerAccountDeletionNotice,
    CustomerRegistration,
    CustomerRegistrationAttempt,
)


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

    def has_change_permission(self, request, obj=None):
        if obj is not None and obj.privacy_erased_at:
            return False
        return super().has_change_permission(request, obj)


admin.site.register(CustomUser, CustomUserAdmin)


@admin.register(CustomerRegistration)
class CustomerRegistrationAdmin(admin.ModelAdmin):
    list_display = (
        "email",
        "mobile_number",
        "status",
        "submitted_at",
        "email_verified_at",
        "reviewed_at",
    )
    list_filter = ("status",)
    search_fields = ("full_name", "email", "mobile_number")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        return tuple(field.name for field in self.model._meta.fields)


@admin.register(CustomerRegistrationAttempt)
class CustomerRegistrationAttemptAdmin(admin.ModelAdmin):
    list_display = ("attempted_at", "outcome")
    list_filter = ("outcome",)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        return tuple(field.name for field in self.model._meta.fields)


class ReadOnlyAccountDeletionAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(CustomerAccountDeletionRequest)
class CustomerAccountDeletionRequestAdmin(ReadOnlyAccountDeletionAdmin):
    list_display = ("id", "customer", "source", "status", "requested_at")
    list_filter = ("source", "status")


@admin.register(CustomerAccountDeletionDecision)
class CustomerAccountDeletionDecisionAdmin(ReadOnlyAccountDeletionAdmin):
    list_display = ("request", "outcome", "decided_by_label", "decided_at")
    list_filter = ("outcome",)


@admin.register(CustomerAccountDeletionAction)
class CustomerAccountDeletionActionAdmin(ReadOnlyAccountDeletionAdmin):
    list_display = ("request", "action", "actor_label", "created_at")
    list_filter = ("action",)


@admin.register(CustomerAccountDeletionAttempt)
class CustomerAccountDeletionAttemptAdmin(ReadOnlyAccountDeletionAdmin):
    list_display = ("attempted_at", "outcome")
    list_filter = ("outcome",)


@admin.register(CustomerAccountDeletionNotice)
class CustomerAccountDeletionNoticeAdmin(ReadOnlyAccountDeletionAdmin):
    list_display = ("decision", "created_at", "accepted_at", "attempts")
