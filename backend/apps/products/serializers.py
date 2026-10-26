from rest_framework import serializers

from apps.common.validators import validate_attachment, validate_image
from .models import Category, Product, ProductAttachment, ProductImage


class CategorySerializer(serializers.ModelSerializer):
    product_count = serializers.IntegerField(source="products.count", read_only=True)

    class Meta:
        model = Category
        fields = ["id", "name", "description", "product_count"]
        read_only_fields = ["id", "product_count"]


class ProductImageSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = ProductImage
        fields = ["id", "image", "url", "alt_text", "is_primary", "uploaded_at"]
        read_only_fields = ["id", "url", "uploaded_at"]

    def get_url(self, obj):
        request = self.context.get("request")
        if obj.image and request:
            return request.build_absolute_uri(obj.image.url)
        return obj.image.url if obj.image else None

    def validate_image(self, value):
        return validate_image(value, field_name="image")


class ProductSerializer(serializers.ModelSerializer):
    images = ProductImageSerializer(many=True, read_only=True)
    primary_image = serializers.SerializerMethodField()
    category_name = serializers.CharField(source="category.name", read_only=True)

    class Meta:
        model = Product
        fields = [
            "id",
            "owner",
            "name",
            "description",
            "category",
            "category_name",
            "available",
            "images",
            "primary_image",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "owner", "primary_image", "created_at", "updated_at"]

    def get_primary_image(self, obj):
        request = self.context.get("request")
        image = obj.images.filter(is_primary=True).first() or obj.images.first()
        if image and image.image:
            url = request.build_absolute_uri(image.image.url) if request else image.image.url
            return url
        return None


class ProductImageUploadSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ["id", "image", "alt_text", "is_primary"]
        read_only_fields = ["id"]

    def validate_image(self, value):
        return validate_image(value, field_name="image")


class ProductAttachmentSerializer(serializers.ModelSerializer):
    download_url = serializers.SerializerMethodField()

    class Meta:
        model = ProductAttachment
        fields = ["id", "file", "original_name", "content_type", "size", "uploaded_at", "download_url"]
        read_only_fields = ["id", "original_name", "content_type", "size", "uploaded_at", "download_url"]
        extra_kwargs = {"file": {"write_only": True}}

    def validate_file(self, value):
        return validate_attachment(value)

    def create(self, validated_data):
        upload = validated_data["file"]
        return ProductAttachment.objects.create(product=self.context["product"], file=upload, original_name=upload.name[:255], content_type=upload.content_type, size=upload.size)

    def get_download_url(self, obj):
        request = self.context.get("request")
        path = f"/api/products/{obj.product_id}/attachments/{obj.id}/download/"
        return request.build_absolute_uri(path) if request else path
