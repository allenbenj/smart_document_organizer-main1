"""Lightweight schema validation helpers for configuration payloads."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable


class ValidationError(Exception):
    """Raised when configuration does not meet schema requirements."""


@dataclass
class ConfigurationSchema:
    """Minimal schema object with required keys and optional field type hints."""

    required: Iterable[str] = field(default_factory=list)
    field_types: Dict[str, type] = field(default_factory=dict)

    def validate(self, config: Dict[str, Any]) -> None:
        for key in self.required:
            if key not in config:
                raise ValidationError(f"Missing required configuration key: {key}")

        for key, expected_type in self.field_types.items():
            if key in config and not isinstance(config[key], expected_type):
                raise ValidationError(
                    f"Invalid type for '{key}': expected {expected_type.__name__}, "
                    f"got {type(config[key]).__name__}"
                )
