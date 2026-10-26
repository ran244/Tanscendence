from django.contrib import admin

from .models import Category, Product, ProductImage


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "description")
    search_fields = ("name",)


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 0


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "category", "available", "created_at")
    list_filter = ("available", "category")
    search_fields = ("name", "owner__username")
    inlines = [ProductImageInline]
    readonly_fields = ("created_at", "updated_at")