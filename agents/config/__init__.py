"""Shim package to satisfy relative imports in agents.*

Re-exports the top-level `config` package so that modules under
`agents.*` importing `...config.*` resolve without errors.
"""

from config.configuration_manager import (
    ConfigurationManager,
    create_configuration_manager,
)

__all__ = [
    "ConfigurationManager",
    "create_configuration_manager",
]
