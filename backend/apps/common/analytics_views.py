import csv
import io
import json
from datetime import datetime

from django.db.models import Count, DecimalField, F, Sum
from django.db.models.functions import TruncDate
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.models import CustomUser as User, UserRole
from apps.auctions.models import (
    AuctionEvent,
    AuctionEventStatus,
    AuctionLot,
    AuctionLotStatus,
    Bid,
    BidStatus,
    SavedLot,
)
from apps.common.permissions import IsAdmin
from apps.notifications.models import Notification
from apps.orders.models import Order, OrderStatus, Payment, PaymentStatus
from apps.products.models import Category, Product


def _date_range(request, user):
    """Parse from/to filters; defaults to the last 90 days. Returns (start, end)."""
    now = timezone.now()
    from datetime import timedelta

    end = now
    start = now - timedelta(days=90)
    try:
        start = datetime.fromisoformat(request.query_params.get("from", start.isoformat()))
    except ValueError:
        start = now - timedelta(days=90)
    try:
        end = datetime.fromisoformat(request.query_params.get("to", end.isoformat()))
    except ValueError:
        end = now
    return start, end


def _time_series(start, end):
    """Bids and collected cash-on-delivery orders per day in [start, end]."""
    bids = (
        Bid.objects.filter(status=BidStatus.ACCEPTED, created_at__gte=start, created_at__lte=end)
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(bids=Count("id"), total_value=Sum("amount", output_field=DecimalField(max_digits=12, decimal_places=2)))
        .order_by("day")
    )
    payments = (
        Payment.objects.filter(status=PaymentStatus.COLLECTED, collected_at__gte=start, collected_at__lte=end)
        .annotate(day=TruncDate("collected_at"))
        .values("day")
        .annotate(payments=Count("id"), revenue=Sum("amount", output_field=DecimalField(max_digits=12, decimal_places=2)))
        .order_by("day")
    )
    bid_map = {row["day"].isoformat(): row for row in bids}
    payment_map = {row["day"].isoformat(): row for row in payments}
    days = sorted(set(bid_map) | set(payment_map))
    return [
        {
            "date": day,
            "bids": int(bid_map.get(day, {}).get("bids", 0)),
            "bid_value": str(bid_map.get(day, {}).get("total_value", 0) or 0),
            "payments": int(payment_map.get(day, {}).get("payments", 0)),
            "revenue": str(payment_map.get(day, {}).get("revenue", 0) or 0),
        }
        for day in days
    ]


def _scoped_lots(user, is_admin, start, end):
    lots = AuctionLot.objects.select_related("auction_event", "auction_event__organizer")
    if not is_admin:
        lots = lots.filter(auction_event__organizer=user)
    return lots.filter(created_at__gte=start, created_at__lte=end)


def _scoped_orders(user, is_admin, start, end):
    orders = Order.objects.all()
    if not is_admin:
        orders = orders.filter(seller=user)
    return orders.filter(created_at__gte=start, created_at__lte=end)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def analytics_dashboard(request):
    is_admin = request.user.role == UserRole.ADMIN
    start, end = _date_range(request, request.user)
    lots = _scoped_lots(request.user, is_admin, start, end)
    if is_admin:
        lots = lots.exclude(auction_event__status=AuctionEventStatus.DRAFT).exclude(
            auction_event__status=AuctionEventStatus.CANCELLED,
            auction_event__submitted_at__isnull=True,
        )
    orders = _scoped_orders(request.user, is_admin, start, end)

    status_counts = (
        lots.values("status")
        .annotate(count=Count("id"))
        .order_by("status")
    )
    admin_events = AuctionEvent.objects.filter(created_at__gte=start, created_at__lte=end)
    if is_admin:
        admin_events = admin_events.exclude(status=AuctionEventStatus.DRAFT).exclude(
            status=AuctionEventStatus.CANCELLED, submitted_at__isnull=True
        )
    event_status_counts = (
        admin_events
        .values("status")
        .annotate(count=Count("id"))
        .order_by("status")
    )
    category_counts = (
        lots.exclude(status=AuctionLotStatus.CANCELLED)
        .values("product__category__name")
        .annotate(count=Count("id"))
        .order_by("-count")
    )
    revenue = orders.filter(status=OrderStatus.DELIVERED).aggregate(
        total=Sum("final_price", output_field=DecimalField(max_digits=12, decimal_places=2))
    )["total"] or 0
    scoped_payments = Payment.objects.all()
    if not is_admin:
        scoped_payments = scoped_payments.filter(order__seller=request.user)
    revenue_paid = scoped_payments.filter(
        status=PaymentStatus.COLLECTED, collected_at__gte=start, collected_at__lte=end
    ).aggregate(total=Sum("amount", output_field=DecimalField(max_digits=12, decimal_places=2)))["total"] or 0

    response = {
        "scope": "admin" if is_admin else "seller",
        "range": {"from": start.isoformat(), "to": end.isoformat()},
        "totals": {
            "events": admin_events.count() if is_admin else lots.values("auction_event").distinct().count(),
            "lots": lots.count(),
            "bids": Bid.objects.filter(
                status=BidStatus.ACCEPTED,
                auction_lot__in=lots.values("pk"),
                created_at__gte=start,
                created_at__lte=end,
            ).count(),
            "sold": lots.filter(status=AuctionLotStatus.SOLD).count(),
            "unsold": lots.filter(status=AuctionLotStatus.UNSOLD).count(),
            "revenue": str(revenue),
            "revenue_paid": str(revenue_paid),
            "orders": orders.count(),
            "users": User.objects.all().count() if is_admin else 1,
        },
        "time_series": _time_series(start, end) if is_admin else _time_series_for_seller(lots, start, end),
        "lot_status_distribution": list(status_counts),
        "event_status_distribution": list(event_status_counts) if is_admin else None,
        "category_distribution": list(category_counts),
        "cod_not_collected": scoped_payments.filter(
            status=PaymentStatus.NOT_COLLECTED, created_at__gte=start, created_at__lte=end
        ).count(),
    }
    return Response(response)


def _time_series_for_seller(lots, start, end):
    lot_ids = list(lots.values_list("pk", flat=True))
    bids = (
        Bid.objects.filter(status=BidStatus.ACCEPTED, auction_lot_id__in=lot_ids,
                           created_at__gte=start, created_at__lte=end)
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(
            bids=Count("id"),
            total_value=Sum("amount", output_field=DecimalField(max_digits=12, decimal_places=2)),
        )
        .order_by("day")
    )
    payments = (
        Payment.objects.filter(
            status=PaymentStatus.COLLECTED,
            order__auction_lot_id__in=lot_ids,
            collected_at__gte=start,
            collected_at__lte=end,
        )
        .annotate(day=TruncDate("collected_at"))
        .values("day")
        .annotate(
            payments=Count("id"),
            revenue=Sum("amount", output_field=DecimalField(max_digits=12, decimal_places=2)),
        )
        .order_by("day")
    )
    bid_map = {row["day"].isoformat(): row for row in bids}
    payment_map = {row["day"].isoformat(): row for row in payments}
    return [
        {
            "date": day,
            "bids": int(bid_map.get(day, {}).get("bids", 0)),
            "bid_value": str(bid_map.get(day, {}).get("total_value", 0) or 0),
            "payments": int(payment_map.get(day, {}).get("payments", 0)),
            "revenue": str(payment_map.get(day, {}).get("revenue", 0) or 0),
        }
        for day in sorted(set(bid_map) | set(payment_map))
    ]


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def analytics_export(request):
    """CSV or JSON export of the current analytics snapshot."""
    fmt = request.query_params.get("format", "csv").lower()
    is_admin = request.user.role == UserRole.ADMIN
    start, end = _date_range(request, request.user)
    lots = _scoped_lots(request.user, is_admin, start, end)
    rows = list(
        lots.values(
            "id",
            "lot_number",
            "product__name",
            "status",
            "starting_price",
            "highest_bid__amount",
            "start_time",
            "end_time",
            "auction_event__title",
        ).order_by("start_time")
    )
    filename = f"analytics_{timezone.now():%Y%m%d_%H%M}"
    if fmt == "json":
        payload = json.dumps(rows, indent=2, default=str)
        return HttpResponse(payload, content_type="application/json",
                            headers={"Content-Disposition": f'attachment; filename="{filename}.json"'})
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0].keys()) if rows else ["no_data"])
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return HttpResponse(buffer.getvalue(), content_type="text/csv",
                        headers={"Content-Disposition": f'attachment; filename="{filename}.csv"'})
