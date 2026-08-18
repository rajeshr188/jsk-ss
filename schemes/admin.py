from django.contrib import admin

from .models import (
    Contribution,
    Customer,
    MetalAllocation,
    RateSnapshot,
    SchemeAccount,
    SchemePlan,
)


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("customer_number", "full_name", "mobile_number", "email")
    search_fields = ("customer_number", "full_name", "mobile_number", "email")
    readonly_fields = ("created_at", "updated_at")


@admin.register(SchemePlan)
class SchemePlanAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "amount_rule", "frequency_rule", "active")
    list_filter = ("amount_rule", "frequency_rule", "active")
    search_fields = ("code", "name")
    readonly_fields = ("created_at", "updated_at")


@admin.register(SchemeAccount)
class SchemeAccountAdmin(admin.ModelAdmin):
    list_display = (
        "scheme_number",
        "customer",
        "savings_mode",
        "start_date",
        "eligible_from",
        "status",
    )
    list_filter = ("savings_mode", "status")
    search_fields = ("scheme_number", "customer__full_name", "customer__customer_number")
    readonly_fields = (
        "scheme_number",
        "amount_rule_snapshot",
        "frequency_rule_snapshot",
        "fixed_amount_snapshot",
        "minimum_amount_snapshot",
        "maximum_amount_snapshot",
        "allow_post_eligibility_contributions_snapshot",
        "created_at",
        "updated_at",
    )


@admin.register(Contribution)
class ContributionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "scheme_account",
        "amount",
        "contribution_period",
        "frequency_rule_snapshot",
        "status",
        "payment_gateway",
        "created_at",
    )
    list_filter = ("status", "payment_gateway", "contribution_period")
    search_fields = (
        "gateway_reference",
        "scheme_account__scheme_number",
        "scheme_account__customer__full_name",
    )
    readonly_fields = (
        "scheme_account",
        "amount",
        "contribution_period",
        "frequency_rule_snapshot",
        "status",
        "payment_gateway",
        "gateway_reference",
        "created_at",
        "paid_at",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(RateSnapshot)
class RateSnapshotAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "metal",
        "provider",
        "provider_rate",
        "applied_rate",
        "purity",
        "fetched_at",
    )
    list_filter = ("metal", "provider")
    readonly_fields = (
        "metal",
        "provider",
        "provider_timestamp",
        "fetched_at",
        "provider_rate",
        "applied_rate",
        "purity",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(MetalAllocation)
class MetalAllocationAdmin(admin.ModelAdmin):
    list_display = ("id", "contribution", "metal", "quantity", "created_at")
    list_filter = ("metal",)
    search_fields = (
        "contribution__gateway_reference",
        "contribution__scheme_account__scheme_number",
        "contribution__scheme_account__customer__full_name",
    )
    readonly_fields = (
        "contribution",
        "rate_snapshot",
        "metal",
        "quantity",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
