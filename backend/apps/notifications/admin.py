from django.contrib import admin

from .models import Notification, SupportMessage, SupportTicket


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("recipient", "verb", "actor", "read_at", "created_at")
    list_filter = ("verb", "read_at")
    search_fields = ("recipient__username",)
    readonly_fields = ("created_at",)


class SupportMessageInline(admin.TabularInline):
    model = SupportMessage
    extra = 0
    readonly_fields = ("created_at",)


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = ("id", "subject", "reporter", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("subject", "reporter__username")
    inlines = [SupportMessageInline]


@admin.register(SupportMessage)
class SupportMessageAdmin(admin.ModelAdmin):
    list_display = ("ticket", "author", "created_at")