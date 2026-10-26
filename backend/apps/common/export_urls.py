from django.urls import path

from apps.common import export_views

urlpatterns = [
    path("<str:kind>/", export_views.export_data, name="export_data"),
]
