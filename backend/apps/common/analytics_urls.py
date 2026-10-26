from django.urls import path

from apps.common import analytics_views

urlpatterns = [
    path("dashboard/", analytics_views.analytics_dashboard, name="analytics_dashboard"),
    path("export/", analytics_views.analytics_export, name="analytics_export"),
]
