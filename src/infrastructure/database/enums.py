"""SQLAlchemy enum types for the noise module."""

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM
from sqlalchemy.engine import Connection
import enum


class ValueOrigin(str, enum.Enum):
    """Origin of exposure data."""

    measured = "measured"
    calculated = "calculated"
    estimated = "estimated"
    imported = "imported"
    ai_suggested = "ai_suggested"
    validated = "validated"
    default_value = "default_value"


class ThresholdBand(str, enum.Enum):
    """Risk band classification."""

    negligible = "negligible"
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class ActionType(str, enum.Enum):
    """Type of mitigation action."""

    administrative = "administrative"
    technical = "technical"
    ppe = "ppe"
    medical = "medical"
    training = "training"
    engineering = "engineering"


class EntityStatus(str, enum.Enum):
    """Generic entity status."""

    active = "active"
    inactive = "inactive"
    archived = "archived"


def create_enum_types(connection: Connection) -> None:
    """Create PostgreSQL ENUM types if they don't exist."""
    enums = [
        ("value_origin", [e.value for e in ValueOrigin]),
        ("threshold_band", [e.value for e in ThresholdBand]),
        ("action_type", [e.value for e in ActionType]),
        ("entity_status", [e.value for e in EntityStatus]),
    ]

    for enum_name, values in enums:
        existing = connection.execute(
            f"SELECT 1 FROM pg_type WHERE typname = '{enum_name}'"
        ).fetchone()

        if not existing:
            values_str = ", ".join(f"'{v}'" for v in values)
            connection.execute(f"CREATE TYPE {enum_name} AS ENUM ({values_str})")
