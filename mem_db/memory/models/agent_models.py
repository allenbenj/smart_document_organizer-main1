"""
Agent-related database models
"""

from sqlalchemy import JSON, Boolean, Column, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship  # noqa: E402

from .base import Base, BaseModel  # noqa: E402


class Agent(Base, BaseModel):
    """Agent registry model"""

    __tablename__ = "agents"

    name = Column(String(255), unique=True, nullable=False, doc="Agent name")

    agent_type = Column(
        String(100), nullable=False, doc="Type of agent (document, analysis, etc.)"
    )

    description = Column(Text, doc="Agent description")

    version = Column(String(50), default="1.0.0", doc="Agent version")

    capabilities = Column(JSON, default=list, doc="List of agent capabilities")

    configuration = Column(JSON, default=dict, doc="Agent configuration")

    is_enabled = Column(Boolean, default=True, doc="Whether agent is enabled")

    # Relationships
    configs = relationship(
        "AgentConfig", back_populates="agent", cascade="all, delete-orphan"
    )
    memories = relationship(
        "AgentMemory", back_populates="agent", cascade="all, delete-orphan"
    )
    metrics = relationship(
        "AgentMetrics", back_populates="agent", cascade="all, delete-orphan"
    )


class AgentConfig(Base, BaseModel):
    """Agent configuration model"""

    __tablename__ = "agent_configs"

    agent_id = Column(
        String(36),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        doc="Agent ID",
    )

    config_name = Column(String(255), nullable=False, doc="Configuration name")

    config_data = Column(JSON, nullable=False, doc="Configuration data")

    is_default = Column(
        Boolean, default=False, doc="Whether this is the default configuration"
    )

    # Relationships
    agent = relationship("Agent", back_populates="configs")


class AgentMemory(Base, BaseModel):
    """Agent memory storage model"""

    __tablename__ = "agent_memories"

    agent_id = Column(
        String(36),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        doc="Agent ID",
    )

    memory_type = Column(
        String(100),
        nullable=False,
        doc="Type of memory (episodic, semantic, procedural)",
    )

    memory_key = Column(String(255), nullable=False, doc="Memory key")

    memory_data = Column(JSON, nullable=False, doc="Memory data")

    importance_score = Column(Float, default=0.0, doc="Importance score (0.0 - 1.0)")

    access_count = Column(Integer, default=0, doc="Number of times accessed")

    # Relationships
    agent = relationship("Agent", back_populates="memories")


class AgentMetrics(Base, BaseModel):
    """Agent performance metrics model"""

    __tablename__ = "agent_metrics"

    agent_id = Column(
        String(36),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        doc="Agent ID",
    )

    metric_name = Column(String(255), nullable=False, doc="Metric name")

    metric_value = Column(Float, nullable=False, doc="Metric value")

    metric_unit = Column(String(50), doc="Metric unit")

    metriccontext = Column(JSON, default=dict, doc="Additional metric context")

    # Relationships
    agent = relationship("Agent", back_populates="metrics")
