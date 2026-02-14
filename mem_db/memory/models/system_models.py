"""
System configuration and monitoring database models
"""

from sqlalchemy import JSON, Boolean, Column, DateTime, Float, String, Text
from sqlalchemy.sql import func  # noqa: E402

from .base import Base, BaseModel  # noqa: E402


class SystemConfig(Base, BaseModel):
    """System configuration model"""

    __tablename__ = "system_configs"

    config_key = Column(
        String(255), unique=True, nullable=False, doc="Configuration key"
    )

    config_value = Column(JSON, nullable=False, doc="Configuration value")

    config_type = Column(
        String(50),
        default="application",
        doc="Configuration type (application, database, etc.)",
    )

    description = Column(Text, doc="Configuration description")

    is_encrypted = Column(Boolean, default=False, doc="Whether value is encrypted")

    is_readonly = Column(
        Boolean, default=False, doc="Whether configuration is readonly"
    )

    validation_schema = Column(JSON, doc="JSON schema for validation")


class SystemMetrics(Base, BaseModel):
    """System metrics model"""

    __tablename__ = "system_metrics"

    metric_name = Column(String(255), nullable=False, doc="Metric name")

    metric_value = Column(Float, nullable=False, doc="Metric value")

    metric_type = Column(
        String(50), nullable=False, doc="Metric type (counter, gauge, histogram)"
    )

    metric_unit = Column(String(50), doc="Metric unit")

    metric_labels = Column(JSON, default=dict, doc="Metric labels")

    component = Column(String(255), doc="System component")

    collected_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        doc="When metric was collected",
    )


class HealthCheck(Base, BaseModel):
    """Health check results model"""

    __tablename__ = "health_checks"

    check_name = Column(String(255), nullable=False, doc="Health check name")

    check_status = Column(
        String(50), nullable=False, doc="Check status (healthy, unhealthy, degraded)"
    )

    check_duration_ms = Column(Float, doc="Check duration in milliseconds")

    check_details = Column(JSON, default=dict, doc="Check details")

    error_message = Column(Text, doc="Error message if unhealthy")

    component = Column(String(255), doc="System component")

    checked_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        doc="When check was performed",
    )


class AuditLog(Base, BaseModel):
    """Audit log model"""

    __tablename__ = "audit_logs"

    user_id = Column(String(36), doc="User ID (if applicable)")

    action = Column(String(255), nullable=False, doc="Action performed")

    resource_type = Column(String(100), doc="Type of resource")

    resource_id = Column(String(36), doc="Resource ID")

    old_values = Column(JSON, doc="Old values (for updates)")

    new_values = Column(JSON, doc="New values (for updates)")

    ip_address = Column(String(45), doc="IP address")

    user_agent = Column(Text, doc="User agent")

    correlation_id = Column(String(36), doc="Correlation ID for tracing")

    additional_data = Column(JSON, default=dict, doc="Additional audit data")


class ErrorLog(Base, BaseModel):
    """Error log model"""

    __tablename__ = "error_logs"

    error_type = Column(String(255), nullable=False, doc="Error type/class")

    error_message = Column(Text, nullable=False, doc="Error message")

    error_traceback = Column(Text, doc="Error traceback")

    component = Column(String(255), doc="System component where error occurred")

    user_id = Column(String(36), doc="User ID (if applicable)")

    correlation_id = Column(String(36), doc="Correlation ID for tracing")

    request_data = Column(JSON, doc="Request data when error occurred")

    environment_data = Column(JSON, doc="Environment data")

    severity = Column(
        String(20),
        default="ERROR",
        doc="Error severity (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
    )

    resolved = Column(Boolean, default=False, doc="Whether error has been resolved")

    resolution_notes = Column(Text, doc="Resolution notes")
