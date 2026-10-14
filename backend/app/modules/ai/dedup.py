"""Duplicate detection and spatio-temporal clustering engine (T-038, T-039).

Determines whether incoming citizen reports refer to an existing active emergency
using multilingual sentence embeddings (cosine similarity), spatial radius (Haversine),
and time-window thresholds. Merges duplicates into canonical incidents.
"""

from __future__ import annotations

import logging
import math
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from app.modules.ai.embeddings import cosine_similarity, generate_embedding

logger = logging.getLogger(__name__)

# Tuned thresholds per T-039
DEFAULT_SIMILARITY_THRESHOLD = 0.75
DEFAULT_MAX_DISTANCE_KM = 1.5
DEFAULT_MAX_TIME_HOURS = 2.0
HIGH_CONFIDENCE_TEXT_SIMILARITY = 0.88


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great-circle distance between two points on Earth in kilometers."""
    radius_km = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2.0) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return radius_km * c


@dataclass
class DuplicateMatchResult:
    """Result of duplicate evaluation against existing incidents."""

    is_duplicate: bool
    matched_incident_id: uuid.UUID | None
    similarity: float
    distance_km: float | None
    time_diff_hours: float | None
    confidence: float
    reason: str


class DuplicateDetector:
    """Evaluates whether a new report matches an active incident."""

    def __init__(
        self,
        similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
        max_distance_km: float = DEFAULT_MAX_DISTANCE_KM,
        max_time_hours: float = DEFAULT_MAX_TIME_HOURS,
    ) -> None:
        self.similarity_threshold = similarity_threshold
        self.max_distance_km = max_distance_km
        self.max_time_hours = max_time_hours

    def find_duplicate(
        self,
        report_text: str,
        report_lat: float | None = None,
        report_lon: float | None = None,
        report_time: datetime | None = None,
        candidate_incidents: Sequence[dict] = (),
    ) -> DuplicateMatchResult:
        """Find best matching incident among candidate active incidents.

        Each candidate in ``candidate_incidents`` is a dict with:
        - ``id``: UUID
        - ``title``: str
        - ``description``: str
        - ``lat``: float | None
        - ``lon``: float | None
        - ``created_at``: datetime
        - ``embedding``: list[float] | None
        """
        if not candidate_incidents:
            return DuplicateMatchResult(
                is_duplicate=False,
                matched_incident_id=None,
                similarity=0.0,
                distance_km=None,
                time_diff_hours=None,
                confidence=0.0,
                reason="No candidate incidents available",
            )

        report_embedding = generate_embedding(report_text)
        now = report_time or datetime.now(UTC)

        best_match: DuplicateMatchResult | None = None
        highest_combined_score = -1.0

        for candidate in candidate_incidents:
            cand_id = candidate["id"]
            cand_text = f"{candidate.get('title', '')} {candidate.get('description', '')}".strip()
            cand_emb = candidate.get("embedding") or generate_embedding(cand_text)

            sim = cosine_similarity(report_embedding, cand_emb)

            # Spatial distance
            dist_km: float | None = None
            cand_lat = candidate.get("lat")
            cand_lon = candidate.get("lon")
            if (
                report_lat is not None
                and report_lon is not None
                and cand_lat is not None
                and cand_lon is not None
            ):
                dist_km = haversine_distance_km(report_lat, report_lon, cand_lat, cand_lon)

            # Temporal difference
            cand_time = candidate.get("created_at") or now
            if cand_time.tzinfo is None:
                cand_time = cand_time.replace(tzinfo=UTC)
            if now.tzinfo is None:
                now = now.replace(tzinfo=UTC)

            time_diff = abs((now - cand_time).total_seconds()) / 3600.0

            # Evaluate matching conditions
            is_match = False
            match_reason = ""

            # Case A: Spatial coordinates available on both sides
            if dist_km is not None:
                if (
                    sim >= self.similarity_threshold
                    and dist_km <= self.max_distance_km
                    and time_diff <= self.max_time_hours
                ):
                    is_match = True
                    match_reason = (
                        f"Cosine similarity {sim:.3f} >= {self.similarity_threshold}, "
                        f"Distance {dist_km:.2f}km <= {self.max_distance_km}km, "
                        f"Time {time_diff:.1f}h <= {self.max_time_hours}h"
                    )
            else:
                # Case B: One or both lack GPS; require higher semantic similarity
                if sim >= HIGH_CONFIDENCE_TEXT_SIMILARITY and time_diff <= self.max_time_hours:
                    is_match = True
                    match_reason = (
                        f"High semantic similarity {sim:.3f} >= {HIGH_CONFIDENCE_TEXT_SIMILARITY} "
                        f"(without coordinate lock), Time {time_diff:.1f}h"
                    )

            # Compute composite ranking score
            geo_score = 1.0 - (dist_km / self.max_distance_km) if dist_km is not None else 0.5
            geo_score = max(0.0, min(1.0, geo_score))
            combined_score = (0.7 * sim) + (0.3 * geo_score)

            if is_match and combined_score > highest_combined_score:
                highest_combined_score = combined_score
                best_match = DuplicateMatchResult(
                    is_duplicate=True,
                    matched_incident_id=cand_id,
                    similarity=sim,
                    distance_km=dist_km,
                    time_diff_hours=time_diff,
                    confidence=float(combined_score),
                    reason=match_reason,
                )

        if best_match is not None:
            return best_match

        return DuplicateMatchResult(
            is_duplicate=False,
            matched_incident_id=None,
            similarity=0.0,
            distance_km=None,
            time_diff_hours=None,
            confidence=0.0,
            reason="No existing incident passed semantic, spatial, and temporal thresholds",
        )
