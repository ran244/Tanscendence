import logging
import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.common.authentication import hash_api_key

logger = logging.getLogger("apps.common")


class PublicApiKey(models.Model):
    """
    API keys for the versioned public API (/api/v1/). Only the SHA-256 hash
    of the key is stored; the plaintext is shown once at creation.
    """
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="public_api_keys",
    )
    name = models.CharField(max_length=100)
    key_hash = models.CharField(max_length=64, unique=True)
    key_prefix = models.CharField(max_length=12, unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"API key '{self.name}' ({self.key_prefix}...)"

    @classmethod
    def issue_key(cls, owner, name):
        from apps.common.authentication import generate_api_key

        raw = generate_api_key()
        prefix = raw[:8]
        while cls.objects.filter(key_prefix=prefix).exists():
            raw = generate_api_key()
            prefix = raw[:8]
        api_key = cls.objects.create(
            owner=owner, name=name, key_hash=hash_api_key(raw), key_prefix=prefix
        )
        return api_key, raw