from django.contrib import admin, messages
from .models import Order, OrderItem
from .services import set_production_timeframe, mark_ready_for_balance


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("was_out_of_stock_at_purchase",)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "id", "phone", "status", "has_out_of_stock",
        "deposit_amount", "balance_amount",
        "target_completion_date", "created_at",
    )
    list_filter = ("status", "has_out_of_stock", "created_at")
    search_fields = ("phone", "email", "name")
    readonly_fields = (
        "created_at", "updated_at", "deposit_paid_at", "balance_paid_at",
    )
    inlines = [OrderItemInline]

    fieldsets = (
        (None, {"fields": ("name", "phone", "email", "area", "total", "status")}),
        ("Made-to-order", {"fields": (
            "has_out_of_stock", "estimated_days",
            "production_start_date", "target_completion_date",
            "owner_note_to_customer",
        )}),
        ("Deposit", {"fields": (
            "deposit_percentage", "deposit_amount", "deposit_paid_at",
            "balance_amount", "balance_paid_at",
        )}),
        ("Meta", {"fields": ("created_at", "updated_at")}),
    )

    actions = ["action_mark_ready_for_balance"]

    def save_model(self, request, obj, form, change):
        was_awaiting = change and Order.objects.filter(
            id=obj.id, status=Order.Status.AWAITING_TIMEFRAME
        ).exists()

        super().save_model(request, obj, form, change)

        if was_awaiting and obj.estimated_days and obj.status == Order.Status.AWAITING_TIMEFRAME:
            try:
                set_production_timeframe(
                    obj, obj.estimated_days, obj.owner_note_to_customer,
                )
                self.message_user(
                    request,
                    "Customer emailed with timeframe + deposit request.",
                    messages.SUCCESS,
                )
            except ValueError as e:
                self.message_user(request, str(e), messages.ERROR)

    @admin.action(description="Mark ready for balance (piece finished)")
    def action_mark_ready_for_balance(self, request, queryset):
        for order in queryset:
            try:
                mark_ready_for_balance(order)
            except ValueError as e:
                self.message_user(request, f"#{order.id}: {e}", messages.WARNING)
        self.message_user(request, "Balance requests sent.", messages.SUCCESS)