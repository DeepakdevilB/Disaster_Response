"""Imports every ORM model so ``Base.metadata`` is complete.

Alembic's env.py and the test suite import this module; application code should import models
from their own module (e.g. ``app.modules.incidents.models``).
"""

from app.db.base import Base
from app.modules.assignments.models import Assignment
from app.modules.audit.models import AuditLog
from app.modules.incidents.models import Incident, IncidentReport
from app.modules.resources.models import Resource
from app.modules.users.models import User

__all__ = [
    "Assignment",
    "AuditLog",
    "Base",
    "Incident",
    "IncidentReport",
    "Resource",
    "User",
]
