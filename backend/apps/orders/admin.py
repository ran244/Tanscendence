from django.contrib import admin

from .models import Order, Payment


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0
    readonly_fields = ("amount", "status", "method", "collection_note", "created_at", "collected_at")
    can_delete = False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "auction_lot", "buyer", "seller", "final_price", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("buyer__username", "seller__username", "auction_lot__product__name")
    inlines = [PaymentInline]
    readonly_fields = ("final_price", "created_at", "updated_at")


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("id", "order", "status", "amount", "method", "created_at", "collected_at")
    list_filter = ("status", "method")
    readonly_fields = ("created_at", "collected_at")
