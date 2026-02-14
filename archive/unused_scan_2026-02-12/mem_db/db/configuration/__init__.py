"""
Unified configuration management implementation.

Provides hierarchical configuration with multiple sources, type-safe access,
and change notification capabilities for the Legal AI Platform.
"""

from .manager import ConfigurationManagerImpl
from .providers import (  # noqa: E402
    FileConfigurationProvider,
    EnvironmentConfigurationProvider,
    DatabaseConfigurationProvider,
)
from .schema import ConfigurationSchema, ValidationError  # noqa: E402

__all__ = [
    "ConfigurationManagerImpl",
    "FileConfigurationProvider",
    "EnvironmentConfigurationProvider",
    "DatabaseConfigurationProvider",
    "ConfigurationSchema",
    "ValidationError",
]
