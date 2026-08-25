from django.conf import settings
from django.contrib import admin

from .models import (
    AuditEvent,
    Contribution,
    Customer,
    MetalAllocation,
    PaymentWebhookEvent,
    SchemeRate,
    Redemption,
    RedemptionReversal,
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
    list_display = (
        "code",
        "name",
        "amount_rule",
        "frequency_rule",
        "cash_bonus_percentage",
        "active",
        "publicly_listed",
    )
    list_filter = ("amount_rule", "frequency_rule", "active", "publicly_listed")
    search_fields = ("code", "name")
    readonly_fields = ("publicly_listed", "created_at", "updated_at")

    def get_readonly_fields(self, request, obj=None):
        fields = list(super().get_readonly_fields(request, obj))
        if not settings.DEBUG:
            fields.extend(["cash_bonus_percentage", "cash_bonus_minimum_months"])
        return fields


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
        "cash_bonus_policy_version_snapshot",
        "cash_bonus_percentage_snapshot",
        "cash_bonus_minimum_months_snapshot",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        return tuple(field.name for field in self.model._meta.fields)


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
        "scheme_rate",
        "rate_locked_at",
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
        "gateway_order_id",
        "gateway_reference",
        "gateway_signature",
        "allocation_error",
        "allocation_attempted_at",
        "created_at",
        "paid_at",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(PaymentWebhookEvent)
class PaymentWebhookEventAdmin(admin.ModelAdmin):
    list_display = (
        "event_id",
        "event_type",
        "status",
        "contribution",
        "received_at",
        "processed_at",
    )
    list_filter = ("gateway", "event_type", "status")
    search_fields = (
        "event_id",
        "gateway_order_id",
        "gateway_reference",
        "contribution__scheme_account__scheme_number",
    )
    readonly_fields = (
        "gateway",
        "event_id",
        "event_type",
        "payload_sha256",
        "status",
        "contribution",
        "gateway_order_id",
        "gateway_reference",
        "error",
        "received_at",
        "processed_at",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SchemeRate)
class SchemeRateAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "metal",
        "rate_per_gram",
        "purity",
        "effective_from",
        "published_by",
        "published_at",
    )
    list_filter = ("metal",)
    readonly_fields = (
        "metal",
        "rate_per_gram",
        "purity",
        "effective_from",
        "published_by",
        "published_at",
        "notes",
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
        "scheme_rate",
        "metal",
        "quantity",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Redemption)
class RedemptionAdmin(admin.ModelAdmin):
    list_display = (
        "redemption_number",
        "scheme_account",
        "settlement_type",
        "status",
        "completed_at",
        "processed_by",
    )
    list_filter = ("settlement_type", "status", "completed_at")
    search_fields = (
        "redemption_number",
        "external_reference",
        "scheme_account__scheme_number",
        "scheme_account__customer__full_name",
    )
    readonly_fields = (
        "redemption_number",
        "idempotency_key",
        "scheme_account",
        "settlement_type",
        "cash_amount",
        "cash_principal_amount",
        "cash_bonus_amount",
        "gold_quantity",
        "silver_quantity",
        "external_reference",
        "notes",
        "processed_by",
        "completed_at",
        "status",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(RedemptionReversal)
class RedemptionReversalAdmin(admin.ModelAdmin):
    list_display = (
        "reversal_number",
        "redemption",
        "processed_by",
        "reversed_at",
    )
    search_fields = (
        "reversal_number",
        "redemption__redemption_number",
        "redemption__scheme_account__scheme_number",
    )
    readonly_fields = (
        "reversal_number",
        "redemption",
        "reason",
        "processed_by",
        "reversed_at",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ("action", "actor_label", "scheme_account", "occurred_at")
    list_filter = ("action", "occurred_at")
    search_fields = (
        "actor_label",
        "reason",
        "scheme_account__scheme_number",
        "redemption__redemption_number",
    )
    readonly_fields = (
        "action",
        "actor",
        "actor_label",
        "reason",
        "scheme_plan",
        "scheme_account",
        "contribution",
        "scheme_rate",
        "redemption",
        "details",
        "occurred_at",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
