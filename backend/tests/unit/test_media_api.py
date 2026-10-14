"""Unit tests for media upload and storage API (T-016)."""

from __future__ import annotations

import uuid

import pytest

from app.core.security import create_access_token
from app.modules.media.models import Media
from app.modules.users.models import User, UserRole
from app.services.storage import MAX_FILE_SIZE_BYTES, StorageValidationError, validate_media_upload


def _create_user(db, name: str, email: str, role: UserRole) -> tuple[User, str]:
    user = User(
        name=name,
        email=email.lower(),
        password_hash="fake-hash",
        role=role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token(subject=str(user.id), role=role.value, email=user.email)
    return user, token


def test_validate_media_upload_allowed():
    # Valid types and sizes
    validate_media_upload("image/jpeg", 1024)
    validate_media_upload("image/png", 5 * 1024 * 1024)
    validate_media_upload("image/webp", MAX_FILE_SIZE_BYTES)


def test_validate_media_upload_invalid_mime():
    with pytest.raises(StorageValidationError, match="Unsupported media type"):
        validate_media_upload("application/pdf", 1024)


def test_validate_media_upload_too_large():
    with pytest.raises(StorageValidationError, match="exceeds max limit"):
        validate_media_upload("image/jpeg", MAX_FILE_SIZE_BYTES + 1)


def test_create_upload_url_success(make_client, db_session):
    client = make_client(db=db_session)
    _, token = _create_user(
        db_session, "Citizen Uploader", "uploader@example.com", UserRole.CITIZEN
    )

    payload = {
        "filename": "water_damage.jpg",
        "mime_type": "image/jpeg",
        "file_size": 1024 * 1024,
    }
    response = client.post(
        "/api/v1/media/upload-url",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
    )
    assert response.status_code == 201
    data = response.json()
    assert "upload_url" in data
    assert data["method"] == "PUT"
    assert "water_damage" not in data["object_key"]  # unique randomized object key
    assert data["object_key"].endswith(".jpg")


def test_create_upload_url_invalid_mime(make_client, db_session):
    client = make_client(db=db_session)
    _, token = _create_user(db_session, "Citizen", "uploader2@example.com", UserRole.CITIZEN)

    payload = {
        "filename": "payload.exe",
        "mime_type": "application/x-msdownload",
        "file_size": 2048,
    }
    response = client.post(
        "/api/v1/media/upload-url",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
    )
    assert response.status_code == 422


def test_get_media_detail(make_client, db_session):
    client = make_client(db=db_session)
    _, token = _create_user(db_session, "Authority", "media_auth@example.com", UserRole.AUTHORITY)

    media = Media(
        object_key="incidents/2026/10/14/sample.png",
        mime_type="image/png",
        file_size=50000,
    )
    db_session.add(media)
    db_session.commit()
    db_session.refresh(media)

    response = client.get(
        f"/api/v1/media/{media.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["object_key"] == "incidents/2026/10/14/sample.png"
    assert "download_url" in data
    assert "token=" in data["download_url"]


def test_get_media_not_found(make_client, db_session):
    client = make_client(db=db_session)
    _, token = _create_user(db_session, "Citizen", "user3@example.com", UserRole.CITIZEN)

    response = client.get(
        f"/api/v1/media/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404
