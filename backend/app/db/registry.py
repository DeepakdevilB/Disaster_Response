"""Imports every ORM model so ``Base.metadata`` is complete.

Alembic's env.py and the test suite import this module; application code should import models
from their own module (e.g. ``app.modules.incidents.models``).
"""

from app.db.base import Base
from app.modules.ai.models import AIPrediction, ReportEmbedding
from app.modules.assignments.models import Assignment
from app.modules.audit.models import AuditLog
from app.modules.incidents.models import Incident, IncidentReport
from app.modules.media.models import Media
from app.modules.resources.models import Resource
from app.modules.users.models import User

__all__ = [
    "AIPrediction",
    "Assignment",
    "AuditLog",
    "Base",
    "Incident",
    "IncidentReport",
    "Media",
    "ReportEmbedding",
    "Resource",
    "User",
]
