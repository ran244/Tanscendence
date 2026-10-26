from django.urls import path

from apps.auctions.consumers import BrowseConsumer, LotConsumer
from apps.accounts.consumers import AuthConsumer

websocket_urlpatterns = [
    path("ws/auth/", AuthConsumer.as_asgi()),
    path("ws/browse/", BrowseConsumer.as_asgi()),
    path("ws/lot/<int:lot_id>/", LotConsumer.as_asgi()),
]