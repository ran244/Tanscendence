import os

from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

django_asgi_app = get_asgi_application()

from apps.common.ws_middleware import (
    JwtAuthMiddleware,
    OriginValidatorMiddleware,
)
from config import ws_urls

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": OriginValidatorMiddleware(
            JwtAuthMiddleware(URLRouter(ws_urls.websocket_urlpatterns))
        ),
    }
)