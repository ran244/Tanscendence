from django.contrib import admin

from .models import PublicApiKey


@admin.register(PublicApiKey)
class PublicApiKeyAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "key_prefix", "is_active", "last_used_at", "created_at")
    list_filter = ("is_active",)
    readonly_fields = ("key_hash", "key_prefix", "last_used_at", "created_at")