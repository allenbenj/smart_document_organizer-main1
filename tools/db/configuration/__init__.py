"""
Unified configuration management implementation.

Provides hierarchical configuration with multiple sources, type-safe access,
and change notification capabilities for the Legal AI Platform.
"""

from .manager import ConfigurationManagerImpl
from .providers import (
    FileConfigurationProvider,
    EnvironmentConfigurationProvider,
    DatabaseConfigurationProvider
)
from .schema import ConfigurationSchema, ValidationError

__all__ = [
    "ConfigurationManagerImpl",
    "FileConfigurationProvider", 
    "EnvironmentConfigurationProvider",
    "DatabaseConfigurationProvider",
    "ConfigurationSchema",
    "ValidationError",
]