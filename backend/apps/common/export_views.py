import csv
import io
import json

from django.http import HttpResponse
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.auctions.models import Bid, BidStatus
from apps.orders.models import Order, Payment, PaymentStatus
from apps.products.models import Product


def _export_rows(request, kind):
    if kind == "bids":
        queryset = (
            Bid.objects.filter(status=BidStatus.ACCEPTED)
            .select_related("bidder", "auction_lot")
            .order_by("-created_at")
        )
        if not request.user.is_admin:
            queryset = queryset.filter(auction_lot__auction_event__organizer=request.user)
        return list(
            queryset.values(
                "id", "auction_lot_id", "bidder__username", "amount", "created_at", "status"
            )
        )
    if kind == "orders":
        queryset = Order.objects.select_related("buyer", "seller", "auction_lot")
        if not request.user.is_admin:
            queryset = queryset.filter(seller=request.user)
        return list(
            queryset.values(
                "id", "auction_lot_id", "buyer__username", "seller__username",
                "final_price", "status", "created_at",
            )
        )
    if kind == "cash-on-delivery":
        queryset = Payment.objects.select_related("order")
        if not request.user.is_admin:
            queryset = queryset.filter(order__seller=request.user)
        return list(
            queryset.values(
                "id", "order_id", "status", "amount", "method", "created_at", "collected_at"
            )
        )
    return None


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def export_data(request, kind):
    if kind not in ("bids", "orders", "cash-on-delivery"):
        return Response({"code": "NOT_FOUND", "message": "Unknown export kind."}, status=404)
    rows = _export_rows(request, kind)
    fmt = request.query_params.get("format", "csv").lower()
    filename = f"{kind}_{timezone.now():%Y%m%d_%H%M}"
    if fmt == "json":
        return HttpResponse(
            json.dumps(rows, indent=2, default=str),
            content_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{filename}.json"'},
        )
    buffer = io.StringIO()
    if rows:
        writer = csv.DictWriter(buffer, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    else:
        buffer.write("no_data\n")
    return HttpResponse(
        buffer.getvalue(),
        content_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}.csv"'},
    )
