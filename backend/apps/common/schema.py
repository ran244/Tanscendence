from drf_spectacular.extensions import OpenApiAuthenticationExtension


class CookieJwtAuthenticationScheme(OpenApiAuthenticationExtension):
    target_class = "apps.common.authentication.CookieJWTAuthentication"
    name = "cookieJwt"

    def get_security_definition(self, auto_schema):
        return {
            "type": "apiKey",
            "in": "cookie",
            "name": "access_token",
            "description": "Secure HttpOnly JWT cookie issued by the login endpoint.",
        }


class PublicApiKeyAuthenticationScheme(OpenApiAuthenticationExtension):
    target_class = "apps.common.authentication.ApiKeyAuthentication"
    name = "publicApiKey"

    def get_security_definition(self, auto_schema):
        return {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key",
            "description": "Hashed, revocable key issued from /api/common/api-keys/.",
        }
