from django.contrib import admin

from .models import Customer, SchemeAccount, SchemePlan


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

