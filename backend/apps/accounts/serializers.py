from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from apps.common.validators import validate_image

User = get_user_model()


class RegistrationSerializer(serializers.ModelSerializer):
    first_name = serializers.CharField(required=False, allow_blank=True)
    last_name = serializers.CharField(required=False, allow_blank=True)
    password = serializers.CharField(write_only=True)
    password_confirm = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "username", "password", "password_confirm"]

    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError(
                {"password_confirm": "Passwords do not match."}
            )
        validate_password(attrs["password"])
        return attrs

    def create(self, validated_data):
        validated_data.pop("password_confirm")
        # Public registrations must prove ownership of the email address
        # before authentication is allowed.
        validated_data["is_active"] = False
        validated_data["email_verified"] = False
        return User.objects.create_user(**validated_data)


class ProfileSerializer(serializers.ModelSerializer):
    avatar = serializers.ImageField(required=False, allow_null=True)
    has_two_fa = serializers.BooleanField(source="totp_enabled", read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "first_name",
            "last_name",
            "email",
            "username",
            "phone_number",
            "bio",
            "avatar",
            "role",
            "date_joined",
            "is_blocked",
            "has_two_fa",
        ]
        read_only_fields = ["id", "email", "username", "role", "date_joined", "is_blocked", "has_two_fa"]

    def validate_avatar(self, value):
        return validate_image(value, max_size=2 * 1024 * 1024, field_name="avatar")


class PublicProfileSerializer(serializers.ModelSerializer):
    is_online = serializers.SerializerMethodField()
    friend_status = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "bio",
            "avatar",
            "date_joined",
            "is_online",
            "friend_status",
        ]

    def get_is_online(self, obj):
        from apps.accounts.services.presence import is_user_online

        return is_user_online(obj)

    def get_friend_status(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated or request.user == obj:
            return None
        from apps.accounts.services.friends import friendship_status_between

        return friendship_status_between(request.user, obj)


class AdminUserListSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "username",
            "role",
            "is_active",
            "is_staff",
            "is_blocked",
            "blocked_reason",
            "date_joined",
            "last_login",
        ]
        read_only_fields = ["id", "email", "date_joined", "last_login"]


class AdminUserUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["role", "is_active", "is_blocked", "blocked_reason"]
        extra_kwargs = {
            "role": {"required": False},
            "is_active": {"required": False},
            "is_blocked": {"required": False},
            "blocked_reason": {"required": False, "allow_blank": True},
        }


class PasswordChangeSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)
    new_password_confirm = serializers.CharField(write_only=True)

    def validate(self, attrs):
        if attrs["new_password"] != attrs["new_password_confirm"]:
            raise serializers.ValidationError(
                {"new_password_confirm": "Passwords do not match."}
            )
        validate_password(attrs["new_password"])
        return attrs


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class EmailVerificationResendSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True)
    new_password_confirm = serializers.CharField(write_only=True)

    def validate(self, attrs):
        if attrs["new_password"] != attrs["new_password_confirm"]:
            raise serializers.ValidationError(
                {"new_password_confirm": "Passwords do not match."}
            )
        validate_password(attrs["new_password"])
        return attrs


class TwoFAEnableSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=6, min_length=6)


class TwoFADisableSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=6, min_length=6, required=False, allow_blank=True)
    password = serializers.CharField(required=False, allow_blank=True, write_only=True)

    def validate(self, attrs):
        if not attrs.get("code") and not attrs.get("password"):
            raise serializers.ValidationError(
                {"code": "Provide a TOTP code or your password."}
            )
        return attrs


class TwoFAVerifySerializer(serializers.Serializer):
    code = serializers.CharField(max_length=64)
    recovery = serializers.BooleanField(default=False, required=False)


class DeleteAccountSerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True)
    code = serializers.CharField(max_length=64, required=False, allow_blank=True)


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
