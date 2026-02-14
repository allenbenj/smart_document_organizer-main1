"""Configuration interfaces and common domain types."""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar

T = TypeVar("T")


class ConfigurationError(Exception):
    """Base configuration error."""


class ConfigurationNotFoundError(ConfigurationError):
    """Configuration key is missing."""


class ConfigurationValidationError(ConfigurationError):
    """Configuration value is invalid for requested type/schema."""


class ConfigurationSourceError(ConfigurationError):
    """A provider/source failed to load or save configuration."""


class ConfigurationSource(str, Enum):
    """Origin of a configuration value."""

    DEFAULT = "default"
    FILE = "file"
    ENVIRONMENT = "environment"
    DATABASE = "database"


class ConfigurationFormat(str, Enum):
    """Supported configuration file formats."""

    JSON = "json"
    YAML = "yaml"
    TOML = "toml"
    INI = "ini"
    ENV = "env"


class ConfigurationProvider(ABC):
    """Provider contract for loading and optionally saving configuration."""

    @abstractmethod
    async def load(self) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def save(self, config: Dict[str, Any]) -> None:
        raise NotImplementedError

    @abstractmethod
    def supports_write(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def get_source_type(self) -> ConfigurationSource:
        raise NotImplementedError


class ConfigurationManager(ABC):
    """High-level configuration access and lifecycle contract."""

    @abstractmethod
    async def initialize(self, config_paths: List[Path]) -> None:
        raise NotImplementedError

    @abstractmethod
    def get(self, key: str, default: Optional[T] = None) -> T:
        raise NotImplementedError

    @abstractmethod
    def get_typed(self, key: str, value_type: Type[T], default: Optional[T] = None) -> T:
        raise NotImplementedError

    @abstractmethod
    def get_section(self, section: str) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def set(
        self,
        key: str,
        value: Any,
        source: ConfigurationSource = ConfigurationSource.DEFAULT,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def has(self, key: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def get_all_keys(self) -> List[str]:
        raise NotImplementedError

    @abstractmethod
    async def get_sources(self, key: str) -> List[ConfigurationSource]:
        raise NotImplementedError

    @abstractmethod
    async def reload(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def add_change_listener(self, key: str, callback: Callable) -> None:
        raise NotImplementedError

    @abstractmethod
    def remove_change_listener(self, key: str, callback: Callable) -> None:
        raise NotImplementedError

    @abstractmethod
    def validate_schema(self, schema: Dict[str, Any]) -> bool:
        raise NotImplementedError
