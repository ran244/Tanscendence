from django.urls import path

from apps.common import public_api_views

urlpatterns = [
    path("categories/", public_api_views.public_categories, name="public_categories"),
    path("products/", public_api_views.public_products, name="public_products"),
    path("lots/", public_api_views.public_lots, name="public_lots"),
    path("lots/<int:lot_id>/", public_api_views.public_lot_detail, name="public_lot_detail"),
    path("bids/", public_api_views.public_bids, name="public_bids"),
    path("saved-lots/", public_api_views.public_saved_lots, name="public_saved_lots"),
    path("saved-lots/<int:saved_id>/", public_api_views.public_saved_lot_delete, name="public_saved_lot_delete"),
]
