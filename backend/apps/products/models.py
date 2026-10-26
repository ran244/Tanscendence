import os
import uuid

from django.conf import settings
from django.db import models
from django.core.files.storage import FileSystemStorage


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name


def product_image_path(instance, filename):
    ext = os.path.splitext(filename)[1].lower()
    return f"products/{instance.product_id}/{uuid.uuid4().hex}{ext}"


private_upload_storage = FileSystemStorage(location=settings.PRIVATE_UPLOAD_ROOT)


def product_attachment_path(instance, filename):
    ext = os.path.splitext(filename)[1].lower()
    return f"products/{instance.product_id}/{uuid.uuid4().hex}{ext}"


class Product(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="products",
    )
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="products")
    available = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class ProductImage(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="images",
    )
    image = models.ImageField(upload_to=product_image_path)
    alt_text = models.CharField(max_length=200, blank=True)
    is_primary = models.BooleanField(default=False)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-is_primary", "uploaded_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["product", "is_primary"],
                condition=models.Q(is_primary=True),
                name="unique_primary_image_per_product",
            ),
        ]

    def __str__(self):
        return f"Image for {self.product.name}"


class ProductAttachment(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="attachments")
    file = models.FileField(storage=private_upload_storage, upload_to=product_attachment_path)
    original_name = models.CharField(max_length=255)
    content_type = models.CharField(max_length=120)
    size = models.PositiveBigIntegerField()
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["uploaded_at"]

    def delete(self, *args, **kwargs):
        storage, name = self.file.storage, self.file.name
        super().delete(*args, **kwargs)
        if name:
            storage.delete(name)
