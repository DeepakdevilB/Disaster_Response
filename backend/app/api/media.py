"""Media API endpoints for uploading and querying attachments."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.modules.media.models import Media
from app.modules.media.schemas import MediaResponse, UploadUrlRequest, UploadUrlResponse
from app.modules.users.models import User
from app.services.storage import (
    StorageValidationError,
    generate_object_key,
    generate_presigned_download_url,
    generate_presigned_upload_url,
    validate_media_upload,
)

router = APIRouter(prefix="/media", tags=["media"])


@router.post(
    "/upload-url",
    response_model=UploadUrlResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Get presigned upload URL for direct attachment upload",
)
def create_upload_url(
    payload: UploadUrlRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> UploadUrlResponse:
    try:
        validate_media_upload(payload.mime_type, payload.file_size)
    except StorageValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    object_key = generate_object_key(payload.filename)
    presigned = generate_presigned_upload_url(
        object_key=object_key,
        mime_type=payload.mime_type,
    )

    # Persist media record
    media = Media(
        report_id=payload.report_id,
        object_key=object_key,
        mime_type=payload.mime_type,
        file_size=payload.file_size,
    )
    db.add(media)
    db.commit()

    return UploadUrlResponse(**presigned)


@router.get(
    "/{media_id}",
    response_model=MediaResponse,
    summary="Retrieve media attachment metadata and download URL",
)
def get_media(
    media_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> MediaResponse:
    media = db.scalar(select(Media).where(Media.id == media_id))
    if not media:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media not found")

    download_url = generate_presigned_download_url(media.object_key)
    return MediaResponse(
        id=media.id,
        report_id=media.report_id,
        object_key=media.object_key,
        mime_type=media.mime_type,
        file_size=media.file_size,
        download_url=download_url,
        cv_label=media.cv_label,
        cv_score=media.cv_score,
        created_at=media.created_at,
    )
