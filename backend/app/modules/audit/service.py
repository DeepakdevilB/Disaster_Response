"""Audit logging service."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.audit.models import AuditLog

logger = logging.getLogger("audit")


def record_audit_log(
    db: Session,
    *,
    actor_id: uuid.UUID | None,
    action: str,
    entity: str,
    entity_id: str | None = None,
    payload: dict[str, Any] | None = None,
) -> AuditLog:
    """Append a tamper-evident audit record and emit a structured audit log entry."""
    entry = AuditLog(
        actor_id=actor_id,
        action=action,
        entity=entity,
        entity_id=str(entity_id) if entity_id is not None else None,
        payload=payload or {},
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)

    logger.info(
        "audit event recorded",
        extra={
            "audit_id": entry.id,
            "actor_id": str(actor_id) if actor_id else "system",
            "action": action,
            "entity": entity,
            "entity_id": entry.entity_id,
        },
    )
    return entry


def list_audit_logs(
    db: Session,
    *,
    page: int = 1,
    size: int = 20,
    action: str | None = None,
    entity: str | None = None,
    actor_id: uuid.UUID | None = None,
) -> tuple[list[AuditLog], int]:
    """Retrieve paginated audit entries with optional filtering."""
    query = select(AuditLog)
    count_query = select(func.count(AuditLog.id))

    if action:
        query = query.where(AuditLog.action == action)
        count_query = count_query.where(AuditLog.action == action)
    if entity:
        query = query.where(AuditLog.entity == entity)
        count_query = count_query.where(AuditLog.entity == entity)
    if actor_id:
        query = query.where(AuditLog.actor_id == actor_id)
        count_query = count_query.where(AuditLog.actor_id == actor_id)

    total = db.scalar(count_query) or 0
    offset = (page - 1) * size
    items = db.scalars(query.order_by(AuditLog.created_at.desc()).offset(offset).limit(size)).all()
    return list(items), total
