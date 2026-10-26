import csv
import io
import json
from decimal import Decimal

from django.db import transaction
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from apps.common.throttling import ImportThrottle

from apps.common.exceptions import BusinessError, business_error_response
from apps.common.permissions import IsAuctionParticipant
from apps.products.models import Category, Product


class BulkProductSerializer(serializers.ModelSerializer):
    category = serializers.CharField()

    class Meta:
        model = Product
        fields = ["name", "description", "category", "available"]

    def validate_category(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Category is required.")
        return value


class BulkLotSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    lot_number = serializers.IntegerField(min_value=1)
    starting_price = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal("0.01")
    )
    minimum_increment = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal("0.01"),
        required=False,
    )
    start_time = serializers.DateTimeField()
    end_time = serializers.DateTimeField()


def _parse_payload(request):
    """Read CSV or JSON rows from the multipart `file` or JSON body."""
    uploaded = request.FILES.get("file")
    if uploaded:
        content = uploaded.read().decode("utf-8-sig")
        name = (uploaded.name or "").lower()
        if name.endswith(".csv"):
            return list(csv.DictReader(io.StringIO(content)))
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            raise BusinessError("INVALID_FILE", "JSON file is not valid.")
        return data if isinstance(data, list) else data.get("rows", [])
    body = request.data
    if isinstance(body, dict) and isinstance(body.get("rows"), list):
        return body["rows"]
    if isinstance(body, list):
        return body
    raise BusinessError("INVALID_FILE", "Provide a `file` upload or a JSON `rows` list.")


def _as_bool(value, default=True):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("1", "true", "yes", "on")


@api_view(["POST"])
@permission_classes([IsAuthenticated, IsAuctionParticipant])
@throttle_classes([ImportThrottle])
def import_products(request):
    dry_run = _as_bool(request.data.get("dry_run"))
    rows = _parse_payload(request)
    if len(rows) > 500:
        raise BusinessError("FILE_TOO_LARGE", "Maximum 500 rows per import.")
    validated = []
    errors = []
    for index, row in enumerate(rows, start=1):
        serializer = BulkProductSerializer(data=row)
        if serializer.is_valid():
            validated.append(serializer)
        else:
            errors.append({"row": index, "errors": serializer.errors})
    if dry_run:
        return Response(
            {
                "dry_run": True,
                "total": len(rows),
                "valid": len(validated),
                "invalid": len(errors),
                "errors": errors,
            }
        )
    if errors:
        return Response({"dry_run": False, "total": len(rows), "imported": 0,
                         "invalid": len(errors), "errors": errors}, status=400)
    with transaction.atomic():
        created = []
        for serializer in validated:
            data = serializer.validated_data.copy()
            category_name = data.pop("category")
            category, _ = Category.objects.get_or_create(name=category_name)
            created.append(Product.objects.create(owner=request.user, category=category, **data))
    return Response({"dry_run": False, "imported": len(created), "errors": []})


@api_view(["POST"])
@permission_classes([IsAuthenticated, IsAuctionParticipant])
@throttle_classes([ImportThrottle])
def import_lots(request, event_id):
    from apps.auctions.models import AuctionEvent
    from apps.auctions.services.lots import add_lot, validate_lot_data

    event = AuctionEvent.objects.filter(pk=event_id).first()
    if event is None:
        raise BusinessError("NOT_FOUND", "Event not found.", 404)
    if event.organizer_id != request.user.id:
        raise BusinessError("NOT_OWNER", "Not your event.", 403)
    if not event.organizer_can_edit:
        raise BusinessError("EVENT_NOT_EDITABLE", "This event can no longer be edited.")
    dry_run = _as_bool(request.data.get("dry_run"))
    rows = _parse_payload(request)
    if len(rows) > 500:
        raise BusinessError("FILE_TOO_LARGE", "Maximum 500 rows per import.")
    validated = []
    errors = []
    batch_lot_numbers = set()
    batch_product_ids = set()
    for index, row in enumerate(rows, start=1):
        serializer = BulkLotSerializer(data=row)
        if not serializer.is_valid():
            errors.append({"row": index, "errors": serializer.errors})
            continue
        try:
            from apps.products.models import Product

            product = Product.objects.get(pk=serializer.validated_data["product_id"])
            if product.owner_id != request.user.id:
                raise BusinessError("NOT_OWNER", "You can only list products you own.")
            data = serializer.validated_data
            if data["lot_number"] in batch_lot_numbers:
                raise BusinessError("LOT_NUMBER_TAKEN", "Duplicate lot number in import.")
            if product.pk in batch_product_ids:
                raise BusinessError("PRODUCT_ALREADY_LISTED", "Duplicate product in import.")
            validate_lot_data(
                event, product, data["lot_number"], data["starting_price"],
                data.get("minimum_increment", 1), data["start_time"], data["end_time"]
            )
            batch_lot_numbers.add(data["lot_number"])
            batch_product_ids.add(product.pk)
            validated.append((product, data))
        except BusinessError as error:
            errors.append({"row": index, "errors": {"code": error.code, "message": error.message}})
        except Product.DoesNotExist:
            errors.append({"row": index, "errors": {"product_id": "Unknown product."}})
    if errors:
        return Response(
            {"dry_run": dry_run, "total": len(rows), "imported": 0,
             "invalid": len(errors), "errors": errors},
            status=200 if dry_run else 400,
        )
    if not dry_run:
        with transaction.atomic():
            for product, data in validated:
                add_lot(
                    event, request.user, product, data["lot_number"], data["starting_price"],
                    data.get("minimum_increment", 1), data["start_time"], data["end_time"]
                )
    return Response(
        {
            "dry_run": dry_run,
            "total": len(rows),
            "imported": 0 if dry_run else len(validated),
            "invalid": len(errors),
            "errors": errors,
        }
    )
