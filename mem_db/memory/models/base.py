"""
Base database models and mixins
"""

import uuid
from datetime import datetime  # noqa: E402
from typing import Any, Dict  # noqa: E402

from sqlalchemy import JSON, Boolean, Column, DateTime, String  # noqa: E402
from sqlalchemy.ext.declarative import declarative_base  # noqa: E402
from sqlalchemy.sql import func  # noqa: E402

Base = declarative_base()


class TimestampMixin:
    """Mixin for automatic timestamp management"""

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        doc="When the record was created",
    )

    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        doc="When the record was last updated",
    )


class BaseModel(TimestampMixin):
    """Base model with common fields"""

    id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        doc="Unique identifier",
    )

    active = Column(
        Boolean, default=True, nullable=False, doc="Whether the record is active"
    )

    metadata_json = Column(JSON, default=dict, doc="Additional metadata as JSON")

    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary"""
        result = {}
        for column in self.__table__.columns:
            value = getattr(self, column.name)
            if isinstance(value, datetime):
                value = value.isoformat()
            result[column.name] = value
        return result

    def update_from_dict(self, data: Dict[str, Any]) -> None:
        """Update model from dictionary"""
        for key, value in data.items():
            if hasattr(self, key) and key not in ["id", "created_at"]:
                setattr(self, key, value)

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(id={self.id})>"
