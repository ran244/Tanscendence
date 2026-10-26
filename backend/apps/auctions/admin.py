from django.contrib import admin
from django.utils.html import format_html

from .models import AuctionCancellationRequest, AuctionEvent, AuctionLot, Bid, SavedLot


class AuctionLotInline(admin.TabularInline):
    model = AuctionLot
    extra = 0
    readonly_fields = ("highest_bid", "status", "start_time", "end_time", "created_at")


@admin.register(AuctionEvent)
class AuctionEventAdmin(admin.ModelAdmin):
    list_display = ("title", "organizer", "status", "start_time", "end_time", "reviewed_by", "submitted_at")
    list_filter = ("status",)
    search_fields = ("title", "organizer__username")
    inlines = [AuctionLotInline]
    readonly_fields = ("created_at", "updated_at", "submitted_at", "reviewed_at")


class BidInline(admin.TabularInline):
    model = Bid
    extra = 0
    readonly_fields = ("bidder", "amount", "created_at", "status", "rejection_reason")
    can_delete = False


@admin.register(AuctionLot)
class AuctionLotAdmin(admin.ModelAdmin):
    list_display = ("id", "lot_number", "product", "auction_event", "status", "current_price", "end_time")
    list_filter = ("status",)
    search_fields = ("product__name", "auction_event__title")
    inlines = [BidInline]
    readonly_fields = ("highest_bid", "current_price", "created_at", "updated_at")


@admin.register(Bid)
class BidAdmin(admin.ModelAdmin):
    list_display = ("id", "auction_lot", "bidder", "amount", "status", "rejection_reason", "created_at")
    list_filter = ("status", "rejection_reason")
    readonly_fields = ("created_at",)


@admin.register(SavedLot)
class SavedLotAdmin(admin.ModelAdmin):
    list_display = ("user", "lot", "created_at")


@admin.register(AuctionCancellationRequest)
class AuctionCancellationRequestAdmin(admin.ModelAdmin):
    list_display = ("auction_event", "requester", "status", "created_at", "reviewed_by")
    list_filter = ("status",)
    readonly_fields = ("created_at", "updated_at", "reviewed_at")
