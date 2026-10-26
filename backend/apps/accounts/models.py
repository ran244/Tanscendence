import secrets

from django.conf import settings
from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinLengthValidator, RegexValidator
from django.db import models
from django.utils import timezone


class UserRole(models.TextChoices):
    USER = "USER", "User"
    ADMIN = "ADMIN", "Admin"


class CustomUserManager(BaseUserManager):
    def create_user(self, email, username, password=None, **extra_fields):
        if not email:
            raise ValueError("Users must provide an email address")
        if not username:
            raise ValueError("Users must provide a username")
        # Django's normalize_email only lowercases the domain. Email is our
        # login identifier, so normalize the complete value consistently.
        email = self.normalize_email(email).strip().lower()
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("role", UserRole.USER)
        extra_fields.setdefault("is_superuser", False)
        user = self.model(email=email, username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, username, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("role", UserRole.ADMIN)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True")
        return self.create_user(email=email, username=username, password=password, **extra_fields)


def avatar_upload_path(instance, filename):
    import os
    import uuid

    ext = os.path.splitext(filename)[1].lower()
    return f"avatars/{instance.pk or 'new'}/{uuid.uuid4().hex}{ext}"


class CustomUser(AbstractUser):
    email = models.EmailField(unique=True)
    username = models.CharField(max_length=150, unique=True)
    phone_number = models.CharField(
        max_length=20,
        blank=True,
        validators=[
            RegexValidator(
                regex=r"^\+?[0-9]+$",
                message="Enter digits only, optionally beginning with +.",
            )
        ],
    )
    role = models.CharField(max_length=10, choices=UserRole.choices, default=UserRole.USER)
    bio = models.TextField(blank=True, max_length=500)
    avatar = models.ImageField(upload_to=avatar_upload_path, blank=True, null=True)
    is_blocked = models.BooleanField(default=False)
    blocked_reason = models.CharField(max_length=255, blank=True)
    blocked_at = models.DateTimeField(null=True, blank=True)
    totp_secret = models.CharField(max_length=64, blank=True, validators=[MinLengthValidator(16)])
    totp_enabled = models.BooleanField(default=False)
    totp_confirmed_at = models.DateTimeField(null=True, blank=True)
    email_verified = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]
    objects = CustomUserManager()

    @property
    def is_admin(self):
        return self.role == UserRole.ADMIN

    def __str__(self):
        return self.username


class FriendshipStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    ACCEPTED = "ACCEPTED", "Accepted"
    DECLINED = "DECLINED", "Declined"


class Friendship(models.Model):
    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="friendships_requested",
    )
    addressee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="friendships_received",
    )
    status = models.CharField(
        max_length=10, choices=FriendshipStatus.choices, default=FriendshipStatus.PENDING
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["requester", "addressee"], name="unique_friendship_pair"),
            models.CheckConstraint(
                condition=~models.Q(requester=models.F("addressee")),
                name="friendship_not_self",
            ),
        ]

    def __str__(self):
        return f"{self.requester} -> {self.addressee} ({self.status})"


class UserBlock(models.Model):
    blocker = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="blocks_made",
    )
    blocked = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="blocks_received",
    )
    reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["blocker", "blocked"], name="unique_block_pair"),
            models.CheckConstraint(
                condition=~models.Q(blocker=models.F("blocked")),
                name="block_not_self",
            ),
        ]

    def __str__(self):
        return f"{self.blocker} blocked {self.blocked}"


class TwoFactorRecoveryCode(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="two_factor_recovery_codes",
    )
    code_hash = models.CharField(max_length=128, unique=True)
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Recovery code for {self.user} ({'used' if self.used_at else 'unused'})"

    @classmethod
    def issue_codes(cls, user, count=10):
        """Generate plaintext codes, store only their hashes."""
        import hashlib

        codes = []
        for _ in range(count):
            code = "".join(secrets.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(12))
            codes.append(code)
            cls.objects.create(
                user=user,
                code_hash=hashlib.sha256(code.encode()).hexdigest(),
            )
        return codes

    @classmethod
    def consume_code(cls, user, code):
        import hashlib

        digest = hashlib.sha256(code.strip().encode()).hexdigest()
        try:
            entry = cls.objects.get(user=user, code_hash=digest, used_at__isnull=True)
        except cls.DoesNotExist:
            return False
        entry.used_at = timezone.now()
        entry.save(update_fields=["used_at"])
        return True
