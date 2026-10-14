"""Migration correctness: reversible, and in sync with the ORM models."""

from __future__ import annotations

from geoalchemy2 import alembic_helpers  # noqa: F401  (registers geography reflection)
from sqlalchemy import Engine, inspect, text

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from app.db.migration_utils import include_object
from app.db.registry import Base

APP_TABLES = {"users", "incidents", "incident_reports", "resources", "assignments"}
APP_ENUMS = {
    "user_role",
    "incident_category",
    "incident_severity",
    "incident_status",
    "report_processing_state",
    "resource_type",
    "resource_status",
    "assignment_status",
}


def _enum_names(engine: Engine) -> set[str]:
    with engine.connect() as conn:
        return set(conn.scalars(text("SELECT typname FROM pg_type WHERE typtype = 'e'")))


def test_single_linear_head(alembic_config: Config):
    heads = ScriptDirectory.from_config(alembic_config).get_heads()
    assert len(heads) == 1, f"multiple migration heads: {heads}"


def test_database_is_at_head(engine: Engine, alembic_config: Config):
    head = ScriptDirectory.from_config(alembic_config).get_current_head()
    with engine.connect() as conn:
        assert MigrationContext.configure(conn).get_current_revision() == head


def test_downgrade_to_base_then_upgrade_again(engine: Engine, alembic_config: Config):
    command.downgrade(alembic_config, "base")
    assert APP_TABLES.isdisjoint(inspect(engine).get_table_names())
    assert APP_ENUMS.isdisjoint(_enum_names(engine))

    command.upgrade(alembic_config, "head")
    assert set(inspect(engine).get_table_names()) >= APP_TABLES
    assert _enum_names(engine) >= APP_ENUMS


def test_models_and_migrations_have_no_drift(engine: Engine):
    """Equivalent to `alembic check`: autogenerate must find nothing to change."""
    with engine.connect() as conn:
        context = MigrationContext.configure(
            conn,
            opts={
                "include_object": include_object,
                "compare_type": True,
                "target_metadata": Base.metadata,
            },
        )
        diff = compare_metadata(context, Base.metadata)
    assert diff == [], f"ORM models and migrations differ: {diff}"
