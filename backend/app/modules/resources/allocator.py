"""Hungarian algorithm resource allocation optimizer (T-043).

Calculates the globally optimal minimum-cost matching between available emergency assets
(ambulances, boats, rescue squads, trauma kits) and active incidents using SciPy's
linear_sum_assignment. Respects incident-type compatibility and physical distance (km).
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
from scipy.optimize import linear_sum_assignment

from app.modules.ai.dedup import haversine_distance_km

logger = logging.getLogger(__name__)

INCOMPATIBLE_PENALTY_KM = 10000.0
DEFAULT_FALLBACK_DISTANCE_KM = 8.0

# Type affinity penalties in km (0.0 = perfect match, >0 = secondary/tertiary, large = forbidden)
TYPE_AFFINITY: dict[str, dict[str, float]] = {
    "flood": {
        "boat": 0.0,
        "rescue_team": 2.0,
        "ambulance": 15.0,
        "medical_kit": 20.0,
        "food_kit": 5.0,
        "other": 10.0,
    },
    "fire": {
        "other": 0.0,  # Fire tender
        "rescue_team": 1.0,
        "ambulance": 3.0,
        "medical_kit": 5.0,
        "food_kit": 25.0,
        "boat": INCOMPATIBLE_PENALTY_KM,
    },
    "medical": {
        "ambulance": 0.0,
        "medical_kit": 1.0,
        "rescue_team": 4.0,
        "food_kit": 30.0,
        "boat": 25.0,
        "other": 20.0,
    },
    "rescue": {
        "rescue_team": 0.0,
        "boat": 2.0,
        "ambulance": 4.0,
        "medical_kit": 5.0,
        "other": 6.0,
        "food_kit": 15.0,
    },
    "infrastructure": {
        "rescue_team": 0.0,
        "other": 1.0,
        "ambulance": 10.0,
        "medical_kit": 12.0,
        "food_kit": 20.0,
        "boat": 30.0,
    },
    "other": {
        "rescue_team": 0.0,
        "ambulance": 2.0,
        "other": 2.0,
        "medical_kit": 4.0,
        "food_kit": 4.0,
        "boat": 10.0,
    },
}


@dataclass
class AllocationRecommendation:
    """A recommended assignment between an incident and a resource."""

    incident_id: uuid.UUID
    incident_title: str
    incident_category: str
    priority_score: float
    resource_id: uuid.UUID
    resource_name: str
    resource_type: str
    distance_km: float
    total_cost: float
    is_compatible: bool

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["incident_id"] = str(d["incident_id"])
        d["resource_id"] = str(d["resource_id"])
        return d


class ResourceAllocator:
    """Min-cost bipartite matching optimizer using Hungarian algorithm."""

    def __init__(self, max_allowed_distance_km: float = 50.0) -> None:
        self.max_allowed_distance_km = max_allowed_distance_km

    def compute_optimal_allocation(
        self,
        incidents: Sequence[dict[str, Any]],
        available_resources: Sequence[dict[str, Any]],
    ) -> list[AllocationRecommendation]:
        """Compute globally optimal matches using SciPy's linear_sum_assignment."""
        if not incidents or not available_resources:
            return []

        n_incidents = len(incidents)
        n_resources = len(available_resources)

        # Build cost matrix: dimensions (n_incidents, n_resources)
        cost_matrix = np.zeros((n_incidents, n_resources), dtype=np.float64)

        for i, inc in enumerate(incidents):
            inc_cat = (inc.get("category") or "other").lower()
            inc_lat = inc.get("lat")
            inc_lon = inc.get("lon")
            priority = float(inc.get("priority_score") or 50.0)

            # Priority factor: higher priority incidents have slightly lower effective cost
            # so they get preference for closest resources
            priority_mult = 1.0 - (priority / 300.0)

            for j, res in enumerate(available_resources):
                res_type = (res.get("type") or "other").lower()
                res_lat = res.get("lat")
                res_lon = res.get("lon")

                # Physical distance in km
                if (
                    inc_lat is not None
                    and inc_lon is not None
                    and res_lat is not None
                    and res_lon is not None
                ):
                    dist_km = haversine_distance_km(inc_lat, inc_lon, res_lat, res_lon)
                else:
                    dist_km = DEFAULT_FALLBACK_DISTANCE_KM

                # Type affinity penalty
                affinity_pen = TYPE_AFFINITY.get(inc_cat, {}).get(res_type, 10.0)

                total_cost = (dist_km * priority_mult) + affinity_pen
                cost_matrix[i, j] = total_cost

        # Execute Hungarian algorithm (O(N^3))
        row_ind, col_ind = linear_sum_assignment(cost_matrix)

        recommendations: list[AllocationRecommendation] = []

        for row, col in zip(row_ind, col_ind, strict=False):
            cost = cost_matrix[row, col]
            inc = incidents[row]
            res = available_resources[col]

            inc_lat = inc.get("lat")
            inc_lon = inc.get("lon")
            res_lat = res.get("lat")
            res_lon = res.get("lon")
            if (
                inc_lat is not None
                and inc_lon is not None
                and res_lat is not None
                and res_lon is not None
            ):
                real_dist = haversine_distance_km(inc_lat, inc_lon, res_lat, res_lon)
            else:
                real_dist = DEFAULT_FALLBACK_DISTANCE_KM

            # Check if assignment is viable
            is_compatible = cost < (INCOMPATIBLE_PENALTY_KM / 2.0)
            if is_compatible and real_dist <= self.max_allowed_distance_km:
                recommendations.append(
                    AllocationRecommendation(
                        incident_id=inc["id"],
                        incident_title=inc.get("title", "Emergency Incident"),
                        incident_category=inc.get("category", "other"),
                        priority_score=float(inc.get("priority_score") or 50.0),
                        resource_id=res["id"],
                        resource_name=res.get("name", "Field Resource"),
                        resource_type=res.get("type", "other"),
                        distance_km=round(real_dist, 2),
                        total_cost=round(float(cost), 2),
                        is_compatible=is_compatible,
                    )
                )

        # Sort recommendations by incident priority score descending
        recommendations.sort(key=lambda r: r.priority_score, reverse=True)
        return recommendations


# Default singleton instance
resource_allocator = ResourceAllocator()
