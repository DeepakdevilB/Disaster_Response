"""Helpers shared by Alembic's env.py and the schema-drift test."""

from __future__ import annotations

from typing import Any

# Tables created by PostgreSQL extensions (PostGIS) that we do not manage.
EXTENSION_TABLES = frozenset({"spatial_ref_sys"})


def include_object(
    obj: Any, name: str | None, type_: str, reflected: bool, compare_to: Any
) -> bool:
    """Tell autogenerate to ignore objects owned by extensions rather than by our models."""
    if type_ == "table" and name in EXTENSION_TABLES:
        return False
    # A table that exists in the DB but not in our metadata and isn't ours to drop.
    return not (type_ == "table" and reflected and compare_to is None)
