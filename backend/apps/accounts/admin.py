from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html

from apps.accounts.models import CustomUser, Friendship, TwoFactorRecoveryCode, UserBlock


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    ordering = ("email",)
    list_display = ("email", "username", "role", "is_active", "is_blocked", "totp_enabled", "date_joined")
    list_filter = ("role", "is_active", "is_blocked", "totp_enabled", "is_staff")
    search_fields = ("email", "username")
    fieldsets = UserAdmin.fieldsets + (
        ("Auction profile", {"fields": ("role", "phone_number", "bio", "avatar")}),
        ("Bidding status", {"fields": ("is_blocked", "blocked_reason", "blocked_at")}),
        ("Two-factor", {"fields": ("totp_secret", "totp_enabled", "totp_confirmed_at")}),
    )

    def avatar_tag(self, obj):
        if obj.avatar:
            return format_html('<img src="{}" width="48" height="48"/>', obj.avatar.url)
        return "-"

    avatar_tag.short_description = "Avatar"


@admin.register(Friendship)
class FriendshipAdmin(admin.ModelAdmin):
    list_display = ("requester", "addressee", "status", "created_at")
    list_filter = ("status",)


@admin.register(UserBlock)
class UserBlockAdmin(admin.ModelAdmin):
    list_display = ("blocker", "blocked", "reason", "created_at")


@admin.register(TwoFactorRecoveryCode)
class TwoFactorRecoveryCodeAdmin(admin.ModelAdmin):
    list_display = ("user", "used_at", "created_at")
    readonly_fields = ("code_hash",)