"""Schema behaviour: extensions, geography columns, indexes, constraints and spatial queries."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from geoalchemy2 import WKTElement
from sqlalchemy import Engine, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.assignments.models import Assignment, AssignmentStatus
from app.modules.incidents.models import (
    Incident,
    IncidentReport,
    IncidentSeverity,
    IncidentStatus,
    ReportProcessingState,
)
from app.modules.resources.models import Resource, ResourceStatus, ResourceType
from app.modules.users.models import User, UserRole


def point(lon: float, lat: float) -> WKTElement:
    return WKTElement(f"POINT({lon} {lat})", srid=4326)


# Mumbai landmarks (lon, lat) used for spatial assertions.
CSMT = (72.8355, 18.9398)
GATEWAY = (72.8347, 18.9220)  # ~2 km from CSMT
POWAI = (72.9050, 19.1176)  # ~21 km from CSMT


def make_user(db: Session, **kw) -> User:
    user = User(
        name=kw.pop("name", "Test User"),
        email=kw.pop("email", f"user-{uuid.uuid4().hex[:8]}@example.com"),
        password_hash="argon2-hash-placeholder",
        **kw,
    )
    db.add(user)
    db.flush()
    return user


def make_incident(db: Session, **kw) -> Incident:
    incident = Incident(title=kw.pop("title", "Flooded street"), description="Water rising", **kw)
    db.add(incident)
    db.flush()
    return incident


def make_resource(db: Session, **kw) -> Resource:
    resource = Resource(
        type=kw.pop("type", ResourceType.BOAT),
        name=kw.pop("name", f"BOAT-{uuid.uuid4().hex[:6]}"),
        **kw,
    )
    db.add(resource)
    db.flush()
    return resource


def assert_violates(db: Session, constraint: str) -> None:
    with pytest.raises(IntegrityError) as exc:
        db.flush()
    assert constraint in str(exc.value)
    db.rollback()


# ------------------------------------------------------------------ extensions & columns


def test_postgis_and_pgvector_extensions_installed(engine: Engine):
    with engine.connect() as conn:
        installed = set(conn.scalars(text("SELECT extname FROM pg_extension")))
        assert {"postgis", "vector"} <= installed
        # pgvector really works (used for report embeddings in T-037).
        distance = conn.scalar(text("SELECT '[1,0,0]'::vector <=> '[0,1,0]'::vector"))
        assert distance == pytest.approx(1.0)


def test_location_columns_are_geography_points_wgs84(engine: Engine):
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT f_table_name, type, srid FROM geography_columns "
                "WHERE f_geography_column = 'location' ORDER BY f_table_name"
            )
        ).all()
    assert [tuple(r) for r in rows] == [
        ("incident_reports", "Point", 4326),
        ("incidents", "Point", 4326),
        ("resources", "Point", 4326),
    ]


def _indexes(engine: Engine) -> dict[str, str]:
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT indexname, indexdef FROM pg_indexes WHERE schemaname = 'public'")
        ).all()
    return dict(rows)


@pytest.mark.parametrize(
    "index", ["ix_incidents_location", "ix_incident_reports_location", "ix_resources_location"]
)
def test_location_columns_have_gist_indexes(engine: Engine, index: str):
    assert "USING gist (location)" in _indexes(engine)[index]


def test_priority_and_partial_indexes_exist(engine: Engine):
    idx = _indexes(engine)
    assert "(status, priority_score DESC)" in idx["ix_incidents_status_priority_score"]
    assert "WHERE (status = ANY" in idx["ix_incidents_active_priority_score"]
    assert "WHERE (processing_state <> 'done'" in idx["ix_incident_reports_pending_state"]
    assert idx["uq_assignments_resource_active"].startswith("CREATE UNIQUE INDEX")


def test_foreign_keys_are_indexed(engine: Engine):
    idx = _indexes(engine)
    for name in (
        "ix_incident_reports_incident_id",
        "ix_incident_reports_user_id",
        "ix_assignments_incident_id",
        "ix_assignments_resource_id",
    ):
        assert name in idx


# ------------------------------------------------------------------ ORM round trip


def test_orm_round_trip_with_defaults_and_enums(db: Session):
    user = make_user(db, role=UserRole.AUTHORITY)
    incident = make_incident(
        db,
        severity=IncidentSeverity.CRITICAL,
        priority_score=Decimal("82.50"),
        location=point(*CSMT),
    )
    report = IncidentReport(
        user_id=user.id,
        incident_id=incident.id,
        raw_text="Help, water entering homes",
        idempotency_key="k-1",
    )
    db.add(report)
    db.flush()
    db.expire_all()

    loaded = db.get(Incident, incident.id)
    assert loaded.status is IncidentStatus.NEW
    assert loaded.severity is IncidentSeverity.CRITICAL
    assert loaded.priority_score == Decimal("82.50")
    assert loaded.report_count == 1
    assert loaded.people_affected == 0
    assert loaded.created_at.tzinfo is not None
    assert [r.id for r in loaded.reports] == [report.id]
    assert db.get(IncidentReport, report.id).processing_state is ReportProcessingState.QUEUED
    assert db.get(User, user.id).is_active is True

    lon, lat = db.execute(
        select(text("ST_X(location::geometry)"), text("ST_Y(location::geometry)"))
        .select_from(Incident.__table__)
        .where(Incident.id == incident.id)
    ).one()
    assert (lon, lat) == pytest.approx(CSMT)


def test_raw_enum_values_stored_as_documented(db: Session):
    make_user(db, role=UserRole.RESCUE, email="rescue@example.com")
    assert (
        db.scalar(text("SELECT role::text FROM users WHERE email = 'rescue@example.com'"))
        == "rescue"
    )


# ------------------------------------------------------------------ constraints


def test_email_must_be_unique(db: Session):
    make_user(db, email="dup@example.com")
    db.add(User(name="B", email="dup@example.com", password_hash="x"))
    assert_violates(db, "uq_users_email")


def test_email_must_be_lowercase(db: Session):
    db.add(User(name="A", email="Mixed@Example.com", password_hash="x"))
    assert_violates(db, "ck_users_email_lowercase")


@pytest.mark.parametrize("score", [Decimal("-0.01"), Decimal("100.01")])
def test_priority_score_must_be_between_0_and_100(db: Session, score: Decimal):
    db.add(Incident(title="t", description="d", priority_score=score))
    assert_violates(db, "ck_incidents_priority_score_range")


def test_people_affected_cannot_be_negative(db: Session):
    db.add(Incident(title="t", description="d", people_affected=-1))
    assert_violates(db, "ck_incidents_people_affected_non_negative")


def test_idempotency_key_prevents_duplicate_reports(db: Session):
    user = make_user(db)
    db.add(IncidentReport(user_id=user.id, raw_text="first", idempotency_key="same-key"))
    db.flush()
    db.add(IncidentReport(user_id=user.id, raw_text="retry", idempotency_key="same-key"))
    assert_violates(db, "uq_incident_reports_idempotency_key")


def test_blank_report_text_rejected(db: Session):
    user = make_user(db)
    db.add(IncidentReport(user_id=user.id, raw_text="   ", idempotency_key="blank"))
    assert_violates(db, "ck_incident_reports_raw_text_not_blank")


def test_resource_capacity_must_be_positive(db: Session):
    db.add(Resource(type=ResourceType.AMBULANCE, name="AMB-0", capacity=0))
    assert_violates(db, "ck_resources_capacity_positive")


def test_resource_can_only_have_one_active_assignment(db: Session):
    resource = make_resource(db)
    first, second = make_incident(db), make_incident(db)
    # Many *recommendations* for the same resource are fine...
    db.add_all(
        [
            Assignment(incident_id=first.id, resource_id=resource.id),
            Assignment(incident_id=second.id, resource_id=resource.id),
            Assignment(
                incident_id=first.id, resource_id=resource.id, status=AssignmentStatus.APPROVED
            ),
        ]
    )
    db.flush()
    # ...but it cannot be committed to two incidents at once.
    db.add(
        Assignment(incident_id=second.id, resource_id=resource.id, status=AssignmentStatus.ACCEPTED)
    )
    assert_violates(db, "uq_assignments_resource_active")


def test_assignment_cannot_complete_before_it_was_assigned(db: Session):
    now = datetime.now(UTC)
    db.add(
        Assignment(
            incident_id=make_incident(db).id,
            resource_id=make_resource(db).id,
            assigned_at=now,
            completed_at=now - timedelta(minutes=1),
        )
    )
    assert_violates(db, "ck_assignments_completed_after_assigned")


# ------------------------------------------------------------------ referential behaviour


def test_deleting_incident_unlinks_reports_instead_of_deleting_them(db: Session):
    user = make_user(db)
    incident = make_incident(db)
    report = IncidentReport(
        user_id=user.id, incident_id=incident.id, raw_text="r", idempotency_key="k-del"
    )
    db.add(report)
    db.flush()

    db.execute(text("DELETE FROM incidents WHERE id = :id"), {"id": incident.id})
    db.expire_all()

    assert db.get(IncidentReport, report.id).incident_id is None  # raw reports are never lost


def test_cannot_delete_user_who_filed_reports(db: Session):
    user = make_user(db)
    db.add(IncidentReport(user_id=user.id, raw_text="r", idempotency_key="k-user"))
    db.flush()
    with pytest.raises(IntegrityError, match="fk_incident_reports_user_id_users"):
        db.execute(text("DELETE FROM users WHERE id = :id"), {"id": user.id})
    db.rollback()


# ------------------------------------------------------------------ spatial queries


def test_find_available_resources_within_radius(db: Session):
    near = make_resource(db, name="BOAT-NEAR", location=point(*GATEWAY))
    make_resource(db, name="BOAT-FAR", location=point(*POWAI))
    make_resource(db, name="BOAT-OFF", location=point(*GATEWAY), status=ResourceStatus.OFFLINE)
    incident = make_incident(db, location=point(*CSMT))

    found = db.scalars(
        select(Resource)
        .where(Resource.status == ResourceStatus.AVAILABLE)
        .where(Resource.location.ST_DWithin(incident.location, 5_000))  # metres
    ).all()

    assert [r.name for r in found] == [near.name]


def test_geography_distance_is_in_metres(db: Session):
    metres = db.scalar(select(point(*CSMT).ST_Distance(point(*POWAI)).label("d")))
    # CSMT -> Powai is roughly 21 km in a straight line.
    assert 19_000 < metres < 23_000
