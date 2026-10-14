"""Asynchronous AI triage worker (T-033).

Consumes report submission jobs from RabbitMQ, executes the AI NLP pipeline
(preprocessing -> entity extraction -> category classifier -> severity classifier),
persists predictions idempotently, updates report state, and supports DLQ on failures.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.registry import run_ai_pipeline
from app.modules.ai.models import AIPrediction
from app.modules.audit.service import record_audit_log
from app.modules.incidents.models import (
    Incident,
    IncidentCategory,
    IncidentReport,
    IncidentSeverity,
    ReportProcessingState,
)

logger = logging.getLogger(__name__)

MAX_RETRIES = 3


class WorkerProcessingError(Exception):
    """Raised when an unrecoverable worker failure occurs."""


def process_report_ai_job(
    db: Session,
    report_id: uuid.UUID,
    attempt: int = 1,
) -> AIPrediction:
    """Process a citizen report asynchronously through the AI triage pipeline.

    Idempotent: If an AIPrediction already exists for this report, it is returned
    without redundant inference.
    """
    # 1. Idempotency check
    existing = db.scalar(select(AIPrediction).where(AIPrediction.report_id == report_id))
    if existing:
        logger.info("Report %s already processed by AI worker (idempotent)", report_id)
        return existing

    # 2. Fetch report
    report = db.scalar(select(IncidentReport).where(IncidentReport.id == report_id))
    if not report:
        raise WorkerProcessingError(f"IncidentReport {report_id} not found in database")

    try:
        # 3. Update processing state to PROCESSING
        report.processing_state = ReportProcessingState.PROCESSING
        db.commit()

        # 4. Run AI NLP inference pipeline
        ai_result: dict[str, Any] = run_ai_pipeline(report.raw_text)

        pred_cat_str = ai_result["predicted_category"]
        pred_sev_str = ai_result["predicted_severity"]
        cat_conf = ai_result["category_confidence"]
        sev_conf = ai_result["severity_confidence"]
        entities = ai_result["extracted_entities"]
        raw_output = ai_result["raw_output"]

        # Validate against enums
        try:
            pred_cat = IncidentCategory(pred_cat_str.lower())
        except ValueError:
            pred_cat = IncidentCategory.OTHER

        try:
            pred_sev = IncidentSeverity(pred_sev_str.upper())
        except ValueError:
            pred_sev = IncidentSeverity.MEDIUM

        # 5. Persist prediction
        prediction = AIPrediction(
            report_id=report.id,
            model_name=ai_result["model_name"],
            model_version=ai_result["model_version"],
            predicted_category=pred_cat.value,
            category_confidence=cat_conf,
            predicted_severity=pred_sev.value,
            severity_confidence=sev_conf,
            extracted_entities=entities,
            raw_output=raw_output,
        )
        db.add(prediction)

        # 6. Update report with AI results & mark DONE
        report.predicted_category = pred_cat
        report.predicted_severity = pred_sev
        report.processing_state = ReportProcessingState.DONE

        # 7. Update parent incident if linked
        if report.incident_id:
            incident = db.scalar(select(Incident).where(Incident.id == report.incident_id))
            if incident:
                incident.category = pred_cat
                incident.severity = pred_sev
                people_count = entities.get("people_count", 0)
                if people_count > (incident.people_affected or 0):
                    incident.people_affected = people_count

        db.commit()
        db.refresh(prediction)

        # 8. Record audit trail
        record_audit_log(
            db=db,
            actor_id=None,  # system actor
            action="ai.prediction_created",
            entity="ai_prediction",
            entity_id=prediction.id,
            payload={
                "report_id": str(report.id),
                "category": pred_cat.value,
                "confidence_category": cat_conf,
                "severity": pred_sev.value,
                "confidence_severity": sev_conf,
                "people_count": entities.get("people_count", 0),
            },
        )

        logger.info(
            "AI worker successfully classified report %s as %s (%s)",
            report.id,
            pred_cat.value,
            pred_sev.value,
        )
        return prediction

    except Exception as exc:
        db.rollback()
        logger.error(
            "AI worker attempt %d failed for report %s: %s",
            attempt,
            report_id,
            exc,
            exc_info=True,
        )
        if attempt < MAX_RETRIES:
            return process_report_ai_job(db, report_id, attempt=attempt + 1)

        # Dead-letter queue / failure mark after max retries
        try:
            report = db.scalar(select(IncidentReport).where(IncidentReport.id == report_id))
            if report:
                report.processing_state = ReportProcessingState.FAILED
                db.commit()
        except Exception:
            db.rollback()

        raise WorkerProcessingError(
            f"Permanent worker failure for report {report_id} after {attempt} attempts: {exc}"
        ) from exc
