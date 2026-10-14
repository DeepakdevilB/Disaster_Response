"""Message queue publisher for asynchronous event processing via RabbitMQ / Kombu.

Publishes emergency report submission events so Celery / NLP workers consume them
asynchronously. Never crashes report ingestion if RabbitMQ is temporarily unreachable.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from kombu import Connection, Exchange, Producer

from app.core.config import get_settings

logger = logging.getLogger(__name__)

INCIDENTS_EXCHANGE_NAME = "incident_events"
REPORT_SUBMITTED_ROUTING_KEY = "incident.reported"

incident_exchange = Exchange(INCIDENTS_EXCHANGE_NAME, type="topic", durable=True)


def publish_event(
    routing_key: str,
    payload: dict[str, Any],
    timeout_seconds: float = 0.5,
) -> bool:
    """Publish a JSON-serializable message to the incident_events exchange."""
    settings = get_settings()
    try:
        with Connection(
            settings.rabbitmq_url,
            connect_timeout=timeout_seconds,
        ) as conn:
            producer = Producer(conn)
            producer.publish(
                payload,
                exchange=incident_exchange,
                routing_key=routing_key,
                serializer="json",
                delivery_mode=2,  # Persistent
                declare=[incident_exchange],
            )
            logger.info("event published to queue", extra={"routing_key": routing_key})
            return True
    except Exception as exc:
        logger.warning(
            "failed to publish event to RabbitMQ (worker will pick up via fallback/polling)",
            extra={"routing_key": routing_key, "error": str(exc)},
        )
        return False


def publish_report_submitted_event(
    *,
    report_id: uuid.UUID,
    incident_id: uuid.UUID | None,
    user_id: uuid.UUID,
    raw_text: str,
    location_lat: float | None = None,
    location_lon: float | None = None,
    location_text: str | None = None,
) -> bool:
    """Publish an incident.reported event for NLP and deduplication workers."""
    payload = {
        "report_id": str(report_id),
        "incident_id": str(incident_id) if incident_id else None,
        "user_id": str(user_id),
        "raw_text": raw_text,
        "location": {
            "lat": location_lat,
            "lon": location_lon,
        }
        if (location_lat is not None and location_lon is not None)
        else None,
        "location_text": location_text,
    }
    return publish_event(REPORT_SUBMITTED_ROUTING_KEY, payload)
