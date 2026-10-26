from django.db import transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404
from django.http import FileResponse
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.response import Response

from apps.common.exceptions import BusinessError, ErrorCodes, business_error_response
from apps.common.permissions import IsAdmin, IsAuctionParticipantOrReadOnly
from apps.auctions.models import AuctionLotStatus
from .models import Category, Product, ProductAttachment, ProductImage
from .serializers import (
    CategorySerializer,
    ProductImageSerializer,
    ProductImageUploadSerializer,
    ProductAttachmentSerializer,
    ProductSerializer,
)


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.annotate(product_count=Count("products")).order_by("name")
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    http_method_names = ["get", "post", "put", "patch", "delete", "head", "options"]

    def get_permissions(self):
        if self.action in ("create", "update", "partial_update", "destroy"):
            return [IsAdmin()]
        return super().get_permissions()

    def perform_destroy(self, instance):
        if instance.products.exists():
            raise BusinessError(
                "CATEGORY_IN_USE",
                "can't delete this category its in use",
            )
        if Category.objects.count() <= 1:
            raise BusinessError(
                "LAST_CATEGORY",
                "At least one product category must remain available.",
            )
        instance.delete()


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated, IsAuctionParticipantOrReadOnly]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        return (
            Product.objects.filter(owner=self.request.user)
            .select_related("category", "owner")
            .prefetch_related("images")
            .order_by("-created_at")
        )

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    def perform_destroy(self, instance):
        if instance.auction_lots.exclude(
            status__in=[
                AuctionLotStatus.CANCELLED,
                AuctionLotStatus.SOLD,
                AuctionLotStatus.UNSOLD,
            ]
        ).exists():
            raise BusinessError(
                ErrorCodes.PRODUCT_ALREADY_LISTED,
                "A product in an upcoming or active lot cannot be removed.",
            )
        instance.available = False
        instance.save(update_fields=["available", "updated_at"])

    @action(detail=True, methods=["post"])
    def images(self, request, pk=None):
        product = self.get_object()
        serializer = ProductImageUploadSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        if serializer.validated_data.get("is_primary"):
            ProductImage.objects.filter(product=product, is_primary=True).update(is_primary=False)
        image = serializer.save(product=product)
        return Response(
            ProductImageSerializer(image, context={"request": request}).data, status=201
        )

    @action(detail=True, methods=["delete"], url_path=r"images/(?P<image_id>[0-9]+)")
    def delete_image(self, request, pk=None, image_id=None):
        product = self.get_object()
        image = get_object_or_404(ProductImage, pk=image_id, product=product)
        was_primary = image.is_primary
        image.delete()
        if was_primary:
            fallback = product.images.first()
            if fallback:
                fallback.is_primary = True
                fallback.save(update_fields=["is_primary"])
        return Response({"message": "Image deleted."})

    @action(detail=True, methods=["put"], url_path=r"images/(?P<image_id>[0-9]+)/primary")
    def set_primary_image(self, request, pk=None, image_id=None):
        product = self.get_object()
        image = get_object_or_404(ProductImage, pk=image_id, product=product)
        with transaction.atomic():
            ProductImage.objects.filter(product=product, is_primary=True).update(is_primary=False)
            image.is_primary = True
            image.save(update_fields=["is_primary"])
        return Response(
            ProductImageSerializer(image, context={"request": request}).data
        )

    @action(detail=True, methods=["get", "post"])
    def attachments(self, request, pk=None):
        product = self.get_object()
        if request.method == "GET":
            return Response({"results": ProductAttachmentSerializer(product.attachments.all(), many=True, context={"request": request}).data})
        serializer = ProductAttachmentSerializer(data=request.data, context={"request": request, "product": product})
        serializer.is_valid(raise_exception=True)
        attachment = serializer.save()
        return Response(ProductAttachmentSerializer(attachment, context={"request": request}).data, status=201)

    @action(detail=True, methods=["delete"], url_path=r"attachments/(?P<attachment_id>[0-9]+)")
    def delete_attachment(self, request, pk=None, attachment_id=None):
        product = self.get_object()
        attachment = get_object_or_404(ProductAttachment, pk=attachment_id, product=product)
        attachment.delete()
        return Response({"message": "Attachment deleted."})

    @action(detail=True, methods=["get"], url_path=r"attachments/(?P<attachment_id>[0-9]+)/download")
    def download_attachment(self, request, pk=None, attachment_id=None):
        product = self.get_object()
        attachment = get_object_or_404(ProductAttachment, pk=attachment_id, product=product)
        return FileResponse(attachment.file.open("rb"), as_attachment=True, filename=attachment.original_name, content_type=attachment.content_type)
