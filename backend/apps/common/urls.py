from django.urls import path

from apps.common import views

urlpatterns = [
    path("health/", views.health_root),
    path("health/ready/", views.health_ready),
    path("api-keys/", views.api_keys, name="api_keys"),
    path("api-keys/<int:key_id>/", views.api_key_delete, name="api_key_delete"),
]
