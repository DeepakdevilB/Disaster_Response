"""Unit tests for Phase 3 Intelligent Engine (T-037 to T-047).

Tests:
1. Multilingual embeddings and cosine similarity (T-037)
2. Duplicate detection & spatio-temporal clustering (T-038, T-039)
3. Geocoding pipeline with local gazetteer and cache (T-040)
4. Priority scoring formula and explainability breakdown (T-041)
5. Hungarian resource allocation optimizer (T-043)
6. Allocations & assignments API workflow (T-044)
"""

from __future__ import annotations

import math
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.modules.ai.dedup import DuplicateDetector, haversine_distance_km
from app.modules.ai.embeddings import cosine_similarity, generate_embedding
from app.modules.incidents.models import (
    Incident,
    IncidentCategory,
    IncidentSeverity,
    IncidentStatus,
)
from app.modules.incidents.priority import priority_engine
from app.modules.resources.allocator import resource_allocator
from app.modules.resources.models import Resource, ResourceStatus, ResourceType
from app.modules.users.models import User, UserRole
from app.services.geocoder import GeocodingService

# ==============================================================================
# 1. Embedding & Cosine Similarity Tests (T-037)
# ==============================================================================


def test_embedding_generation_dimension_and_norm():
    """Verify generated embedding is exactly 384-dimensional and unit normalized."""
    text = "Severe flood water entering residential ground floor"
    emb = generate_embedding(text)

    assert len(emb) == 384
    norm = math.sqrt(sum(x * x for x in emb))
    assert abs(norm - 1.0) < 1e-4


def test_cosine_similarity_identity_and_semantics():
    """Verify cosine similarity is 1.0 for identical text and higher for related crisis topics."""
    text1 = "Heavy flood waters rising rapidly, need rescue boat"
    text2 = "Rising water submerged houses, evacuation boat required"
    text3 = "Routine streetlight replacement schedule for next month"

    emb1 = generate_embedding(text1)
    emb2 = generate_embedding(text2)
    emb3 = generate_embedding(text3)

    sim_self = cosine_similarity(emb1, emb1)
    assert abs(sim_self - 1.0) < 1e-4

    sim_related = cosine_similarity(emb1, emb2)
    sim_unrelated = cosine_similarity(emb1, emb3)

    assert sim_related > sim_unrelated
    assert sim_related >= 0.70
    assert sim_unrelated < 0.50


# ==============================================================================
# 2. Duplicate Detection Tests (T-038 & T-039)
# ==============================================================================


def test_haversine_distance():
    """Verify great-circle distance calculation."""
    # Delhi AIIMS (28.5672, 77.2100) to Dhaula Kuan (28.5921, 77.1563) ~ 5.9 km
    dist = haversine_distance_km(28.5672, 77.2100, 28.5921, 77.1563)
    assert 5.0 <= dist <= 7.0

    # Same location distance is 0.0
    assert haversine_distance_km(28.6139, 77.2090, 28.6139, 77.2090) == 0.0


def test_duplicate_detector_matches_within_radius_and_time():
    """Verify duplicate detection matches reports within 1.5 km and 2 hours."""
    detector = DuplicateDetector(similarity_threshold=0.70, max_distance_km=1.5, max_time_hours=2.0)
    now = datetime.now(UTC)

    cand_id = uuid.uuid4()
    candidate_incidents = [
        {
            "id": cand_id,
            "title": "Severe Yamuna River Flood",
            "description": "Yamuna River flood water rising fast, family trapped on rooftop",
            "lat": 28.6812,
            "lon": 77.2541,
            "created_at": now - timedelta(minutes=20),
            "embedding": generate_embedding(
                "Yamuna River flood water rising fast, family trapped on rooftop"
            ),
        }
    ]

    # Incoming report 300 meters away with matching crisis narrative
    new_report_text = "Flood water rising near Yamuna bank, people trapped on rooftop"
    result = detector.find_duplicate(
        report_text=new_report_text,
        report_lat=28.6830,
        report_lon=77.2550,
        report_time=now,
        candidate_incidents=candidate_incidents,
    )

    assert result.is_duplicate is True
    assert result.matched_incident_id == cand_id
    assert result.distance_km is not None and result.distance_km < 1.5
    assert result.similarity >= 0.70


def test_duplicate_detector_rejects_distant_location():
    """Verify report with similar text but 10 km away is not merged."""
    detector = DuplicateDetector(similarity_threshold=0.70, max_distance_km=1.5, max_time_hours=2.0)
    now = datetime.now(UTC)

    candidate_incidents = [
        {
            "id": uuid.uuid4(),
            "title": "Flood near Usmanpur",
            "description": "Water rising",
            "lat": 28.6812,
            "lon": 77.2541,
            "created_at": now,
        }
    ]

    result = detector.find_duplicate(
        report_text="Water rising near Mayapuri industrial area",
        report_lat=28.6289,  # ~15 km away
        report_lon=77.1126,
        report_time=now,
        candidate_incidents=candidate_incidents,
    )

    assert result.is_duplicate is False


# ==============================================================================
# 3. Geocoding Pipeline Tests (T-040)
# ==============================================================================


@pytest.mark.anyio
async def test_geocoding_service_local_gazetteer():
    """Verify local gazetteer resolves known landmarks without external network calls."""
    geocoder = GeocodingService(redis_client=None)

    res = await geocoder.geocode("Near Usmanpur 2nd Pusta")
    assert res is not None
    assert abs(res.latitude - 28.6812) < 0.01
    assert abs(res.longitude - 77.2541) < 0.01
    assert res.source == "gazetteer"

    res_aiims = await geocoder.geocode("AIIMS trauma center flyover")
    assert res_aiims is not None
    assert abs(res_aiims.latitude - 28.5672) < 0.01
    assert res_aiims.source == "gazetteer"


# ==============================================================================
# 4. Priority Scoring Engine Tests (T-041)
# ==============================================================================


def test_priority_engine_critical_calculation():
    """Verify critical life-threat incident produces a high priority score with explainable breakdown."""
    now = datetime.now(UTC)
    res = priority_engine.compute_priority(
        severity="CRITICAL",
        people_affected=6,
        created_at=now - timedelta(minutes=15),
        life_threat=1.0,
        resource_need=0.9,
        location_risk=0.8,
        incident_text="Family trapped in flooded house",
    )

    # Score should be in the ~80-90 range per live examples in Sheet: Priority Model
    assert res.priority_score >= 80.0
    assert "severity" in res.breakdown
    assert res.breakdown["severity"]["contribution"] == 35.0  # 35 * 1.0
    assert res.breakdown["people_affected"]["contribution"] == 12.0  # 20 * (6/10)

    # Sum of factor contributions equals total score
    sum_contrib = sum(f["contribution"] for f in res.breakdown.values())
    assert abs(sum_contrib - res.priority_score) < 0.05


def test_priority_engine_low_severity_calculation():
    """Verify low severity minor road damage produces a low priority score."""
    res = priority_engine.compute_priority(
        severity="LOW",
        people_affected=0,
        life_threat=0.0,
        resource_need=0.1,
        location_risk=0.2,
        incident_text="Minor pothole on secondary lane",
    )
    assert res.priority_score < 25.0


def test_priority_engine_waiting_time_escalation():
    """Verify waiting time escalates priority score over time."""
    now = datetime.now(UTC)
    res_immediate = priority_engine.compute_priority(
        severity="MEDIUM",
        people_affected=2,
        created_at=now,
    )
    res_waiting_60min = priority_engine.compute_priority(
        severity="MEDIUM",
        people_affected=2,
        created_at=now - timedelta(minutes=60),
    )

    assert res_waiting_60min.priority_score > res_immediate.priority_score
    # Max waiting contribution is weight 10.0
    diff = (
        res_waiting_60min.breakdown["waiting_time"]["contribution"]
        - res_immediate.breakdown["waiting_time"]["contribution"]
    )
    assert abs(diff - 10.0) < 0.2


# ==============================================================================
# 5. Hungarian Resource Allocator Tests (T-043)
# ==============================================================================


def test_resource_allocator_optimal_matching():
    """Verify Hungarian algorithm matches appropriate assets to crisis types."""
    inc_flood = {
        "id": uuid.uuid4(),
        "title": "Severe river flood",
        "category": "flood",
        "severity": "CRITICAL",
        "lat": 28.6800,
        "lon": 77.2500,
        "priority_score": 92.0,
    }
    inc_trauma = {
        "id": uuid.uuid4(),
        "title": "Road collision with victims bleeding",
        "category": "medical",
        "severity": "HIGH",
        "lat": 28.5600,
        "lon": 77.2100,
        "priority_score": 85.0,
    }

    res_boat = {
        "id": uuid.uuid4(),
        "name": "NDRF Motor Boat Alpha",
        "type": "boat",
        "lat": 28.6850,
        "lon": 77.2520,
    }
    res_ambulance = {
        "id": uuid.uuid4(),
        "name": "Critical Care Ambulance 09",
        "type": "ambulance",
        "lat": 28.5650,
        "lon": 77.2120,
    }

    recs = resource_allocator.compute_optimal_allocation(
        incidents=[inc_flood, inc_trauma],
        available_resources=[res_boat, res_ambulance],
    )

    assert len(recs) == 2

    # Flood should be matched to Boat
    match_flood = next(r for r in recs if r.incident_id == inc_flood["id"])
    assert match_flood.resource_type == "boat"
    assert match_flood.distance_km < 2.0

    # Medical should be matched to Ambulance
    match_trauma = next(r for r in recs if r.incident_id == inc_trauma["id"])
    assert match_trauma.resource_type == "ambulance"
    assert match_trauma.distance_km < 2.0


# ==============================================================================
# 6. Allocation API Workflow Tests (T-044)
# ==============================================================================


def _create_user(db, name: str, email: str, role: UserRole) -> tuple[User, str]:
    from app.core.security import create_access_token

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


def test_allocation_api_recommend_and_approve_workflow(make_client, db_session):
    """Test full allocation lifecycle: recommend -> approve -> verify resource/incident status."""
    client = make_client(db=db_session)
    _, authority_token = _create_user(
        db_session, "Commander", "cmd_alloc@example.com", UserRole.AUTHORITY
    )

    # 1. Create open incident in DB
    inc = Incident(
        title="Yamuna Bridge Flood Distress",
        description="Water level high, family stranded",
        category=IncidentCategory.FLOOD,
        severity=IncidentSeverity.CRITICAL,
        status=IncidentStatus.NEW,
        priority_score=88.0,
        people_affected=5,
    )
    db_session.add(inc)

    # 2. Create available resource in DB
    boat = Resource(
        name="SDRF Evacuation Boat B-1",
        type=ResourceType.BOAT,
        status=ResourceStatus.AVAILABLE,
        capacity=8,
    )
    db_session.add(boat)
    db_session.commit()

    # 3. Request recommendations as Authority
    rec_resp = client.post(
        "/api/v1/allocations/recommend",
        headers={"Authorization": f"Bearer {authority_token}"},
    )
    assert rec_resp.status_code == 200
    recs = rec_resp.json()
    assert len(recs) >= 1

    assignment_id = recs[0]["assignment_id"]
    assert assignment_id is not None

    # 4. Approve assignment as Authority
    app_resp = client.post(
        f"/api/v1/allocations/{assignment_id}/approve",
        headers={"Authorization": f"Bearer {authority_token}"},
    )
    assert app_resp.status_code == 200
    app_data = app_resp.json()
    assert app_data["status"] == "approved"

    # Verify resource and incident were transitioned
    db_session.refresh(boat)
    db_session.refresh(inc)
    assert boat.status == ResourceStatus.ASSIGNED
    assert inc.status == IncidentStatus.ASSIGNED


def test_ranked_incidents_feed_endpoint(make_client, db_session):
    """Verify /api/v1/incidents/ranked returns incidents sorted by priority score."""
    client = make_client(db=db_session)
    _, responder_token = _create_user(
        db_session, "Commander 2", "cmd2_ranked@example.com", UserRole.AUTHORITY
    )

    inc_low = Incident(
        title="Low Pothole",
        description="Minor repair",
        category=IncidentCategory.INFRASTRUCTURE,
        severity=IncidentSeverity.LOW,
        status=IncidentStatus.NEW,
        priority_score=15.0,
        people_affected=0,
    )
    inc_high = Incident(
        title="Critical Chemical Fire",
        description="Solvent tanks burning",
        category=IncidentCategory.FIRE,
        severity=IncidentSeverity.CRITICAL,
        status=IncidentStatus.NEW,
        priority_score=95.0,
        people_affected=15,
    )
    db_session.add_all([inc_low, inc_high])
    db_session.commit()

    resp = client.get(
        "/api/v1/incidents/ranked",
        headers={"Authorization": f"Bearer {responder_token}"},
    )
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) >= 2

    # Higher priority score appears first
    scores = [item["priority_score"] for item in items if item["priority_score"] is not None]
    assert scores == sorted(scores, reverse=True)
