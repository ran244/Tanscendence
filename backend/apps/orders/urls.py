from django.urls import path

from apps.orders import views

urlpatterns = [
    path("", views.orders_list, name="orders_list"),
    path("sales/", views.orders_list, name="orders_sales"),
    path("<int:order_id>/", views.order_detail, name="order_detail"),
    path("<int:order_id>/confirm-cod/", views.order_confirm_cod, name="order_confirm_cod"),
    path("<int:order_id>/cancel/", views.order_cancel, name="order_cancel"),
    path("<int:order_id>/fulfill/", views.order_fulfillment, name="order_fulfillment"),
]
