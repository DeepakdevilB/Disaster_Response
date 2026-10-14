"""Priority scoring engine with transparent explainability breakdown (T-041).

Implements the 6-factor weighted crisis formula from Sheet: Priority Model.
Score (0-100) = sum(weight_i * normalized_factor_i).
Every calculation returns both the composite score and the per-factor contributions.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

from app.modules.incidents.models import IncidentSeverity

# Weights must total exactly 100
WEIGHT_SEVERITY = 35.0
WEIGHT_PEOPLE = 20.0
WEIGHT_LIFE_THREAT = 20.0
WEIGHT_WAITING = 10.0
WEIGHT_RESOURCE_NEED = 10.0
WEIGHT_LOCATION_RISK = 5.0

PEOPLE_CAP = 10.0
WAITING_MINUTES_CAP = 60.0

SEVERITY_VALUES: dict[str, float] = {
    IncidentSeverity.CRITICAL.value: 1.0,
    IncidentSeverity.HIGH.value: 0.75,
    IncidentSeverity.MEDIUM.value: 0.50,
    IncidentSeverity.LOW.value: 0.25,
}


@dataclass
class FactorContribution:
    """Breakdown of an individual factor's contribution to the priority score."""

    factor_name: str
    raw_value: Any
    normalized_value: float  # 0.0 to 1.0
    weight: float
    contribution: float  # weight * normalized_value


@dataclass
class PriorityResult:
    """Full priority evaluation result with explainability breakdown."""

    priority_score: float  # 0.0 to 100.0
    breakdown: dict[str, dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class PriorityEngine:
    """Configurable, transparent incident prioritization calculator."""

    def __init__(
        self,
        weight_severity: float = WEIGHT_SEVERITY,
        weight_people: float = WEIGHT_PEOPLE,
        weight_life_threat: float = WEIGHT_LIFE_THREAT,
        weight_waiting: float = WEIGHT_WAITING,
        weight_resource_need: float = WEIGHT_RESOURCE_NEED,
        weight_location_risk: float = WEIGHT_LOCATION_RISK,
        people_cap: float = PEOPLE_CAP,
        waiting_cap_min: float = WAITING_MINUTES_CAP,
    ) -> None:
        self.w_sev = weight_severity
        self.w_people = weight_people
        self.w_life = weight_life_threat
        self.w_wait = weight_waiting
        self.w_res = weight_resource_need
        self.w_loc = weight_location_risk
        self.people_cap = people_cap
        self.waiting_cap_min = waiting_cap_min

    def compute_priority(
        self,
        severity: str | None = None,
        people_affected: int = 0,
        created_at: datetime | None = None,
        life_threat: float | None = None,
        resource_need: float | None = None,
        location_risk: float | None = None,
        incident_text: str = "",
    ) -> PriorityResult:
        """Calculate the 0-100 priority score and individual factor contributions."""
        # 1. Severity Factor (0.25 - 1.0)
        sev_str = (severity or "LOW").upper()
        norm_sev = SEVERITY_VALUES.get(sev_str, 0.25)
        contrib_sev = self.w_sev * norm_sev

        # 2. People Affected Factor (0.0 - 1.0)
        norm_people = min(max(0, people_affected) / self.people_cap, 1.0)
        contrib_people = self.w_people * norm_people

        # 3. Waiting Time Factor (0.0 - 1.0)
        now = datetime.now(UTC)
        if created_at is not None:
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=UTC)
            waiting_minutes = max(0.0, (now - created_at).total_seconds() / 60.0)
        else:
            waiting_minutes = 0.0

        norm_wait = min(waiting_minutes / self.waiting_cap_min, 1.0)
        contrib_wait = self.w_wait * norm_wait

        # 4. Life Threat Factor (0.0 - 1.0)
        if life_threat is not None:
            norm_life = min(1.0, max(0.0, float(life_threat)))
        else:
            # Default derived from severity and keywords
            text_lower = incident_text.lower()
            if sev_str == "CRITICAL" or any(
                w in text_lower for w in ["trapped", "drowning", "unconscious", "phanse", "chhat"]
            ):
                norm_life = 1.0
            elif sev_str == "HIGH":
                norm_life = 0.6
            elif sev_str == "MEDIUM":
                norm_life = 0.2
            else:
                norm_life = 0.0
        contrib_life = self.w_life * norm_life

        # 5. Resource Need Factor (0.0 - 1.0)
        if resource_need is not None:
            norm_res = min(1.0, max(0.0, float(resource_need)))
        else:
            # Derived from emergency context
            text_lower = incident_text.lower()
            if any(w in text_lower for w in ["boat", "oxygen", "foam", "als", "ambulance"]):
                norm_res = 0.9
            elif sev_str in ("CRITICAL", "HIGH"):
                norm_res = 0.7
            elif sev_str == "MEDIUM":
                norm_res = 0.4
            else:
                norm_res = 0.2
        contrib_res = self.w_res * norm_res

        # 6. Location Risk Factor (0.0 - 1.0)
        if location_risk is not None:
            norm_loc = min(1.0, max(0.0, float(location_risk)))
        else:
            high_risk_landmarks = ["hospital", "school", "metro", "flyover", "substation"]
            if any(w in text_lower for w in high_risk_landmarks):
                norm_loc = 0.8
            elif any(w in text_lower for w in ["market", "colony", "residential", "road"]):
                norm_loc = 0.5
            else:
                norm_loc = 0.3
        contrib_loc = self.w_loc * norm_loc

        # Total Priority Score
        total_score = (
            contrib_sev + contrib_people + contrib_life + contrib_wait + contrib_res + contrib_loc
        )
        total_score = round(max(0.0, min(100.0, total_score)), 2)

        breakdown = {
            "severity": {
                "factor_name": "Severity",
                "raw_value": sev_str,
                "normalized": round(norm_sev, 3),
                "weight": self.w_sev,
                "contribution": round(contrib_sev, 2),
            },
            "people_affected": {
                "factor_name": "People Affected",
                "raw_value": people_affected,
                "normalized": round(norm_people, 3),
                "weight": self.w_people,
                "contribution": round(contrib_people, 2),
            },
            "life_threat": {
                "factor_name": "Life Threat",
                "raw_value": norm_life,
                "normalized": round(norm_life, 3),
                "weight": self.w_life,
                "contribution": round(contrib_life, 2),
            },
            "waiting_time": {
                "factor_name": "Waiting Time",
                "raw_value": f"{waiting_minutes:.1f} min",
                "normalized": round(norm_wait, 3),
                "weight": self.w_wait,
                "contribution": round(contrib_wait, 2),
            },
            "resource_need": {
                "factor_name": "Resource Need",
                "raw_value": norm_res,
                "normalized": round(norm_res, 3),
                "weight": self.w_res,
                "contribution": round(contrib_res, 2),
            },
            "location_risk": {
                "factor_name": "Location Risk",
                "raw_value": norm_loc,
                "normalized": round(norm_loc, 3),
                "weight": self.w_loc,
                "contribution": round(contrib_loc, 2),
            },
        }

        return PriorityResult(priority_score=total_score, breakdown=breakdown)


# Default singleton instance
priority_engine = PriorityEngine()
