from django.urls import path

from apps.common import import_views

urlpatterns = [
    path("products/", import_views.import_products, name="import_products"),
    path("lots/<int:event_id>/", import_views.import_lots, name="import_lots"),
]
