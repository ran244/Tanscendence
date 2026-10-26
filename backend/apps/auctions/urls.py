from django.urls import path

from apps.auctions import views

urlpatterns = [
    # Public browse
    path("browse/events/", views.browse_events, name="browse_events"),
    path("lots/", views.browse_lots, name="browse_lots"),
    path("lots/<int:lot_id>/", views.lot_detail, name="lot_detail"),
    path("lots/<int:lot_id>/bids/", views.lot_bids, name="lot_bids"),
    # Bidding
    path("lots/<int:lot_id>/bids/place/", views.place_bid, name="place_bid"),
    path("lots/<int:lot_id>/saved/", views.saved_lot, name="saved_lot"),
    path("saved/", views.my_saved_lots, name="my_saved_lots"),
    path("bids/mine/", views.my_bids, name="my_bids"),
    # Organizer events
    path("events/", views.events, name="events"),
    path("events/<int:event_id>/", views.event_detail, name="event_detail"),
    path("events/<int:event_id>/revise/", views.event_revision, name="event_revision"),
    path("events/<int:event_id>/lots/", views.event_lots, name="event_lots"),
    path("events/<int:event_id>/lots/<int:lot_id>/", views.event_lot_detail, name="event_lot_detail"),
    path("events/<int:event_id>/submit/", views.event_submit, name="event_submit"),
    path("events/<int:event_id>/cancel/", views.event_cancel, name="event_cancel"),
    path(
        "events/<int:event_id>/cancellation-request/",
        views.event_cancellation_request,
        name="event_cancellation_request",
    ),
    # Admin review
    path("admin/events/", views.admin_events, name="admin_events"),
    path(
        "admin/events/history/",
        views.admin_event_history,
        name="admin_event_history",
    ),
    path("admin/bids/", views.admin_active_bids, name="admin_active_bids"),
    path("admin/events/<int:event_id>/approve/", views.admin_event_approve, name="admin_event_approve"),
    path("admin/events/<int:event_id>/reject/", views.admin_event_reject, name="admin_event_reject"),
    path(
        "admin/cancellation-requests/",
        views.admin_cancellation_requests,
        name="admin_cancellation_requests",
    ),
    path(
        "admin/cancellation-requests/<int:request_id>/approve/",
        views.admin_cancellation_approve,
        name="admin_cancellation_approve",
    ),
    path(
        "admin/cancellation-requests/<int:request_id>/reject/",
        views.admin_cancellation_reject,
        name="admin_cancellation_reject",
    ),
]
