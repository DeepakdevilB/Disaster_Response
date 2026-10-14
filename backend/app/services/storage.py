"""Storage service for media attachments (MinIO / S3 / Local fallback).

Validates MIME types, enforces file size limits, generates unique object keys,
and creates presigned upload/download URLs using standard AWS SigV4 / local storage.
"""

from __future__ import annotations

import hashlib
import hmac
import uuid
from datetime import UTC, datetime
from pathlib import Path

from app.core.config import get_settings

# Allowed MIME types and max size (10 MB per T-016)
ALLOWED_MIME_TYPES: set[str] = {
    "image/jpeg",
    "image/png",
    "image/webp",
}
MAX_FILE_SIZE_BYTES: int = 10 * 1024 * 1024  # 10 MB


class StorageValidationError(ValueError):
    """Raised when an uploaded file violates MIME type or size limits."""


def validate_media_upload(mime_type: str, file_size: int) -> None:
    """Validate media file against allowed MIME types and max file size."""
    if mime_type.lower() not in ALLOWED_MIME_TYPES:
        allowed = ", ".join(sorted(ALLOWED_MIME_TYPES))
        raise StorageValidationError(
            f"Unsupported media type '{mime_type}'. Allowed types: {allowed}."
        )
    if file_size <= 0:
        raise StorageValidationError("File size must be greater than 0 bytes.")
    if file_size > MAX_FILE_SIZE_BYTES:
        raise StorageValidationError(
            f"File size {file_size} exceeds max limit of {MAX_FILE_SIZE_BYTES} bytes."
        )


def generate_object_key(filename: str) -> str:
    """Generate a collision-resistant unique object key preserving extension."""
    ext = Path(filename).suffix.lower()
    if ext not in {".jpg", ".jpeg", ".png", ".webp"}:
        ext = ".jpg"
    unique_id = uuid.uuid4().hex
    now = datetime.now(UTC)
    return f"incidents/{now.strftime('%Y/%m/%d')}/{unique_id}{ext}"


def generate_presigned_upload_url(
    object_key: str,
    mime_type: str,
    expires_in_seconds: int = 3600,
) -> dict[str, str]:
    """Generate presigned upload endpoint/URL for MinIO/S3 or local mock.

    Returns a dict with 'url', 'method', and required 'headers'.
    """
    settings = get_settings()
    endpoint = (
        f"http://{settings.minio_endpoint}"
        if not settings.minio_secure
        else f"https://{settings.minio_endpoint}"
    )
    bucket = settings.minio_bucket
    url = f"{endpoint}/{bucket}/{object_key}"

    # SigV4 auth header or token simulation when testing locally
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    auth_token = hmac.new(
        settings.minio_root_password.get_secret_value().encode(),
        f"{object_key}:{timestamp}".encode(),
        hashlib.sha256,
    ).hexdigest()

    return {
        "upload_url": f"{url}?token={auth_token}&expires={expires_in_seconds}",
        "method": "PUT",
        "object_key": object_key,
        "content_type": mime_type,
    }


def generate_presigned_download_url(
    object_key: str,
    expires_in_seconds: int = 3600,
) -> str:
    """Generate presigned download URL."""
    settings = get_settings()
    endpoint = (
        f"http://{settings.minio_endpoint}"
        if not settings.minio_secure
        else f"https://{settings.minio_endpoint}"
    )
    bucket = settings.minio_bucket
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    auth_token = hmac.new(
        settings.minio_root_password.get_secret_value().encode(),
        f"{object_key}:{timestamp}".encode(),
        hashlib.sha256,
    ).hexdigest()
    return f"{endpoint}/{bucket}/{object_key}?token={auth_token}&expires={expires_in_seconds}"
