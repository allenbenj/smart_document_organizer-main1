"""
User and session-related database models
"""

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    String,
    Text,
)
from sqlalchemy.orm import relationship  # noqa: E402

from .base import Base, BaseModel  # noqa: E402


class User(Base, BaseModel):
    """User model"""

    __tablename__ = "users"

    username = Column(String(255), unique=True, nullable=False, doc="Username")

    email = Column(String(255), unique=True, nullable=False, doc="Email address")

    full_name = Column(String(255), doc="Full name")

    password_hash = Column(String(255), nullable=False, doc="Hashed password")

    is_active = Column(Boolean, default=True, doc="Whether user is active")

    is_admin = Column(Boolean, default=False, doc="Whether user has admin privileges")

    role = Column(
        String(50), default="user", doc="User role (user, admin, analyst, etc.)"
    )

    organization = Column(String(255), doc="User's organization")

    last_login = Column(DateTime(timezone=True), doc="Last login timestamp")

    profile_data = Column(JSON, default=dict, doc="Additional profile data")

    # Relationships
    sessions = relationship(
        "UserSession", back_populates="user", cascade="all, delete-orphan"
    )
    preferences = relationship(
        "UserPreference", back_populates="user", cascade="all, delete-orphan"
    )


class UserSession(Base, BaseModel):
    """User session model"""

    __tablename__ = "user_sessions"

    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        doc="User ID",
    )

    session_token = Column(
        String(255), unique=True, nullable=False, doc="Session token"
    )

    expires_at = Column(
        DateTime(timezone=True), nullable=False, doc="Session expiration time"
    )

    ip_address = Column(String(45), doc="IP address")

    user_agent = Column(Text, doc="User agent string")

    is_active = Column(Boolean, default=True, doc="Whether session is active")

    session_data = Column(JSON, default=dict, doc="Additional session data")

    # Relationships
    user = relationship("User", back_populates="sessions")


class UserPreference(Base, BaseModel):
    """User preferences model"""

    __tablename__ = "user_preferences"

    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        doc="User ID",
    )

    preference_key = Column(String(255), nullable=False, doc="Preference key")

    preference_value = Column(JSON, nullable=False, doc="Preference value")

    preference_type = Column(
        String(50), default="user", doc="Preference type (user, system, etc.)"
    )

    # Relationships
    user = relationship("User", back_populates="preferences")


class UserActivity(Base, BaseModel):
    """User activity log model"""

    __tablename__ = "user_activities"

    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        doc="User ID",
    )

    activity_type = Column(String(100), nullable=False, doc="Type of activity")

    activity_description = Column(Text, doc="Activity description")

    resource_type = Column(String(100), doc="Type of resource accessed")

    resource_id = Column(String(36), doc="ID of resource accessed")

    ip_address = Column(String(45), doc="IP address")

    user_agent = Column(Text, doc="User agent string")

    activity_data = Column(JSON, default=dict, doc="Additional activity data")
