from io import BytesIO

from django.conf import settings
from rest_framework import serializers
from PIL import Image
import os


def validate_image(upload, max_size=None, max_dimension=None, field_name="image"):
    """Content-based image validation: MIME sniffing, size, and dimensions."""
    max_size = max_size or settings.IMAGE_MAX_SIZE
    max_dimension = max_dimension or 4096
    if upload.size > max_size:
        raise serializers.ValidationError(
            {field_name: f"File is too large. Maximum size is {max_size // (1024 * 1024)} MB."}
        )
    if upload.size == 0:
        raise serializers.ValidationError({field_name: "Empty file."})
    try:
        upload.seek(0)
        image = Image.open(upload)
        image.verify()
        upload.seek(0)
        image = Image.open(upload)
        fmt = (image.format or "").upper()
        if fmt not in ("JPEG", "PNG", "WEBP", "GIF"):
            raise serializers.ValidationError(
                {field_name: "Unsupported image format. Use JPEG, PNG, WEBP or GIF."}
            )
        width, height = image.size
        if width > max_dimension or height > max_dimension:
            raise serializers.ValidationError(
                {field_name: f"Image dimensions exceed {max_dimension}x{max_dimension}."}
            )
    except serializers.ValidationError:
        raise
    except Exception:
        raise serializers.ValidationError({field_name: "File is not a valid image."})
    finally:
        upload.seek(0)
    return upload


def validate_attachment(upload, field_name="file"):
    """Validate private lot attachments by size, extension, MIME, and signature."""
    max_size = settings.ATTACHMENT_MAX_SIZE
    if not upload.size or upload.size > max_size:
        raise serializers.ValidationError({field_name: f"File must be between 1 byte and {max_size // (1024 * 1024)} MB."})
    extension = os.path.splitext(upload.name)[1].lower()
    allowed = {
        ".jpg": {"image/jpeg"}, ".jpeg": {"image/jpeg"}, ".png": {"image/png"},
        ".webp": {"image/webp"}, ".gif": {"image/gif"}, ".pdf": {"application/pdf"},
        ".txt": {"text/plain"}, ".csv": {"text/csv", "application/vnd.ms-excel", "text/plain"},
        ".docx": {"application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/zip"},
    }
    content_type = (getattr(upload, "content_type", "") or "").lower()
    if extension not in allowed or content_type not in allowed[extension]:
        raise serializers.ValidationError({field_name: "Unsupported file. Use JPEG, PNG, WEBP, GIF, PDF, TXT, CSV, or DOCX."})
    upload.seek(0); header = upload.read(12); upload.seek(0)
    signatures = {
        ".jpg": (b"\xff\xd8\xff",), ".jpeg": (b"\xff\xd8\xff",), ".png": (b"\x89PNG\r\n\x1a\n",),
        ".gif": (b"GIF87a", b"GIF89a"), ".webp": (b"RIFF",), ".pdf": (b"%PDF-",), ".docx": (b"PK\x03\x04",),
    }
    if extension in signatures and not any(header.startswith(value) for value in signatures[extension]):
        raise serializers.ValidationError({field_name: "The file content does not match its extension."})
    return upload
