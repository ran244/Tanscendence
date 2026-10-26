from rest_framework.throttling import UserRateThrottle


class RegisterThrottle(UserRateThrottle):
    scope = "register"


class LoginThrottle(UserRateThrottle):
    scope = "login"


class TwoFactorThrottle(UserRateThrottle):
    scope = "two_fa"


class PasswordResetThrottle(UserRateThrottle):
    scope = "password_reset"


class BidThrottle(UserRateThrottle):
    scope = "bids"


class ImportThrottle(UserRateThrottle):
    scope = "imports"


class PublicApiThrottle(UserRateThrottle):
    scope = "public_api"
