"""SQLAlchemy enum types for the noise module."""

import enum

from sqlalchemy import text
from sqlalchemy.engine import Connection


class ValueOrigin(enum.StrEnum):
    """Origin of exposure data."""

    measured = "measured"
    calculated = "calculated"
    estimated = "estimated"
    imported = "imported"
    ai_suggested = "ai_suggested"
    validated = "validated"
    default_value = "default_value"


class ThresholdBand(enum.StrEnum):
    """Risk band classification."""

    negligible = "negligible"
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class ActionType(enum.StrEnum):
    """Type of mitigation action."""

    administrative = "administrative"
    technical = "technical"
    ppe = "ppe"
    medical = "medical"
    training = "training"
    engineering = "engineering"


class EntityStatus(enum.StrEnum):
    """Generic entity status."""

    active = "active"
    inactive = "inactive"
    archived = "archived"


def create_enum_types(connection: Connection) -> None:
    """Create PostgreSQL ENUM types if they don't exist."""
    VALID_ENUMS = {
        "value_origin": [e.value for e in ValueOrigin],
        "threshold_band": [e.value for e in ThresholdBand],
        "action_type": [e.value for e in ActionType],
        "entity_status": [e.value for e in EntityStatus],
    }

    for enum_name, values in VALID_ENUMS.items():
        if not enum_name.isidentifier() or not all(v.isidentifier() for v in values):
            continue

        existing = connection.execute(
            text("SELECT 1 FROM pg_type WHERE typname = :name"),
            {"name": enum_name},
        ).fetchone()

        if not existing:
            values_str = ", ".join(f"'{v}'" for v in values)
            connection.execute(text(f"CREATE TYPE {enum_name} AS ENUM ({values_str})"))
