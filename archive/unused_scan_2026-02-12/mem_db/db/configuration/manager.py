"""
Configuration manager implementation with hierarchical sources and type safety.
"""

import json
import os  # noqa: E402
import threading  # noqa: E402
from collections import defaultdict  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar  # noqa: E402

from ..interfaces.configuration import (  # noqa: E402
    ConfigurationError,
    ConfigurationManager,
    ConfigurationNotFoundError,
    ConfigurationProvider,
    ConfigurationSource,
    ConfigurationValidationError,
)

T = TypeVar("T")


class ConfigurationManagerImpl(ConfigurationManager):
    """
    Concrete implementation of configuration manager.

    Features:
    - Multiple configuration sources with priority ordering
    - Type-safe configuration access
    - Change notifications
    - Environment variable interpolation
    - Schema validation
    """

    def __init__(self):
        self._providers: List[ConfigurationProvider] = []
        self._config_data: Dict[str, Any] = {}
        self._change_listeners: Dict[str, List[Callable]] = defaultdict(list)
        self._lock = threading.RLock()
        self._initialized = False

    async def initialize(self, config_paths: List[Path]) -> None:
        """Initialize configuration manager with config file paths."""
        with self._lock:
            # Clear existing configuration
            self._providers.clear()
            self._config_data.clear()

            # Add file providers
            for path in config_paths:
                if path.exists():
                    provider = self._create_file_provider(path)
                    self._providers.append(provider)

            # Add environment provider (highest priority)
            env_provider = EnvironmentConfigurationProvider("LEGAL_AI")
            self._providers.append(env_provider)

            # Load configuration from all providers
            await self._load_configuration()
            self._initialized = True

    def get(self, key: str, default: Optional[T] = None) -> T:
        """Get configuration value by key."""
        if not self._initialized:
            raise ConfigurationError("Configuration manager not initialized")

        with self._lock:
            value = self._get_nested_value(self._config_data, key)
            if value is None:
                if default is not None:
                    return default
                raise ConfigurationNotFoundError(f"Configuration key '{key}' not found")

            # Perform environment variable interpolation
            if isinstance(value, str):
                value = self._interpolate_env_vars(value)

            return value

    def get_typed(
        self, key: str, value_type: Type[T], default: Optional[T] = None
    ) -> T:
        """Get configuration value with type validation."""
        value = self.get(key, default)

        if value is None:
            if default is not None:
                return default
            raise ConfigurationNotFoundError(f"Configuration key '{key}' not found")

        # Type conversion
        try:
            if value_type == bool and isinstance(value, str):
                return value.lower() in ("true", "1", "yes", "on")
            elif value_type in (int, float, str):
                return value_type(value)
            elif value_type == list and isinstance(value, str):
                # Support comma-separated lists
                return [item.strip() for item in value.split(",")]
            else:
                return value_type(value)
        except (ValueError, TypeError) as e:
            raise ConfigurationValidationError(
                f"Cannot convert '{value}' to type {value_type.__name__} for key '{key}': {e}"
            )

    def get_section(self, section: str) -> Dict[str, Any]:
        """Get entire configuration section."""
        if not self._initialized:
            raise ConfigurationError("Configuration manager not initialized")

        with self._lock:
            section_data = self._get_nested_value(self._config_data, section)
            if section_data is None:
                return {}

            if not isinstance(section_data, dict):
                raise ConfigurationError(f"Section '{section}' is not a dictionary")

            # Perform environment variable interpolation on all string values
            return self._interpolate_section(section_data)

    def set(
        self,
        key: str,
        value: Any,
        source: ConfigurationSource = ConfigurationSource.DEFAULT,
    ) -> None:
        """Set configuration value."""
        with self._lock:
            old_value = self._get_nested_value(self._config_data, key)
            self._set_nested_value(self._config_data, key, value)

            # Notify listeners if value changed
            if old_value != value:
                self._notify_listeners(key, old_value, value)

    def has(self, key: str) -> bool:
        """Check if configuration key exists."""
        if not self._initialized:
            return False

        with self._lock:
            return self._get_nested_value(self._config_data, key) is not None

    def get_all_keys(self) -> List[str]:
        """Get list of all configuration keys."""
        with self._lock:
            return self._get_all_keys_recursive(self._config_data)

    async def get_sources(self, key: str) -> List[ConfigurationSource]:
        """Get list of sources that provide a configuration key."""
        sources = []
        for provider in self._providers:
            provider_data = await provider.load()
            if self._get_nested_value(provider_data, key) is not None:
                sources.append(provider.get_source_type())
        return sources

    async def reload(self) -> None:
        """Reload configuration from all sources."""
        with self._lock:
            old_config = self._config_data.copy()
            await self._load_configuration()

            # Notify listeners of changes
            self._notify_all_changes(old_config, self._config_data)

    def add_change_listener(self, key: str, callback: Callable) -> None:
        """Add listener for configuration changes."""
        with self._lock:
            self._change_listeners[key].append(callback)

    def remove_change_listener(self, key: str, callback: Callable) -> None:
        """Remove configuration change listener."""
        with self._lock:
            if key in self._change_listeners:
                self._change_listeners[key] = [
                    cb for cb in self._change_listeners[key] if cb != callback
                ]

    def validate_schema(self, schema: Dict[str, Any]) -> bool:
        """Validate configuration against schema."""
        try:
            import jsonschema  # noqa: E402

            jsonschema.validate(self._config_data, schema)
            return True
        except ImportError:
            # Fallback to basic validation if jsonschema not available
            return self._basic_schema_validation(schema)
        except Exception:
            return False

    def _create_file_provider(self, path: Path) -> ConfigurationProvider:
        """Create appropriate file provider based on file extension."""
        from ..interfaces.configuration import ConfigurationFormat  # noqa: E402
        from .providers import FileConfigurationProvider  # noqa: E402

        suffix = path.suffix.lower()
        if suffix == ".json":
            format_type = ConfigurationFormat.JSON
        elif suffix in (".yml", ".yaml"):
            format_type = ConfigurationFormat.YAML
        elif suffix == ".toml":
            format_type = ConfigurationFormat.TOML
        elif suffix in (".ini", ".cfg"):
            format_type = ConfigurationFormat.INI
        else:
            format_type = ConfigurationFormat.JSON  # Default

        return FileConfigurationProvider(path, format_type)

    async def _load_configuration(self) -> None:
        """Load configuration from all providers."""
        self._config_data.clear()

        # Load from providers in order (later providers override earlier ones)
        for provider in self._providers:
            try:
                provider_data = await provider.load()
                self._merge_configuration(self._config_data, provider_data)
            except Exception as e:
                # Log error but continue with other providers
                print(f"Warning: Failed to load configuration from {provider}: {e}")

    def _merge_configuration(
        self, target: Dict[str, Any], source: Dict[str, Any]
    ) -> None:
        """Recursively merge configuration dictionaries."""
        for key, value in source.items():
            if (
                key in target
                and isinstance(target[key], dict)
                and isinstance(value, dict)
            ):
                self._merge_configuration(target[key], value)
            else:
                target[key] = value

    def _get_nested_value(self, data: Dict[str, Any], key: str) -> Any:
        """Get value from nested dictionary using dot notation."""
        keys = key.split(".")
        current = data

        for k in keys:
            if isinstance(current, dict) and k in current:
                current = current[k]
            else:
                return None

        return current

    def _set_nested_value(self, data: Dict[str, Any], key: str, value: Any) -> None:
        """Set value in nested dictionary using dot notation."""
        keys = key.split(".")
        current = data

        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]

        current[keys[-1]] = value

    def _get_all_keys_recursive(
        self, data: Dict[str, Any], prefix: str = ""
    ) -> List[str]:
        """Get all keys recursively from nested dictionary."""
        keys = []
        for key, value in data.items():
            full_key = f"{prefix}.{key}" if prefix else key
            keys.append(full_key)

            if isinstance(value, dict):
                keys.extend(self._get_all_keys_recursive(value, full_key))

        return keys

    def _interpolate_env_vars(self, value: str) -> str:
        """Interpolate environment variables in string values."""
        if not isinstance(value, str):
            return value

        # Simple ${VAR} interpolation
        import re  # noqa: E402

        pattern = r"\$\{([^}]+)\}"

        def replace_var(match):
            var_name = match.group(1)
            return os.environ.get(var_name, match.group(0))

        return re.sub(pattern, replace_var, value)

    def _interpolate_section(self, section: Dict[str, Any]) -> Dict[str, Any]:
        """Interpolate environment variables in all string values in a section."""
        result = {}
        for key, value in section.items():
            if isinstance(value, str):
                result[key] = self._interpolate_env_vars(value)
            elif isinstance(value, dict):
                result[key] = self._interpolate_section(value)
            else:
                result[key] = value
        return result

    def _notify_listeners(self, key: str, old_value: Any, new_value: Any) -> None:
        """Notify change listeners for a specific key."""
        if key in self._change_listeners:
            for callback in self._change_listeners[key]:
                try:
                    callback(key, old_value, new_value)
                except Exception as e:
                    print(f"Error in configuration change listener: {e}")

    def _notify_all_changes(
        self, old_config: Dict[str, Any], new_config: Dict[str, Any]
    ) -> None:
        """Notify listeners of all configuration changes."""
        all_keys = set(self._get_all_keys_recursive(old_config))
        all_keys.update(self._get_all_keys_recursive(new_config))

        for key in all_keys:
            old_value = self._get_nested_value(old_config, key)
            new_value = self._get_nested_value(new_config, key)

            if old_value != new_value:
                self._notify_listeners(key, old_value, new_value)

    def _basic_schema_validation(self, schema: Dict[str, Any]) -> bool:
        """Basic schema validation fallback."""
        # Implement basic validation for required fields
        required_fields = schema.get("required", [])
        for field in required_fields:
            if not self.has(field):
                return False
        return True


class EnvironmentConfigurationProvider:
    """Configuration provider for environment variables."""

    def __init__(self, prefix: Optional[str] = None):
        self.prefix = prefix

    async def load(self) -> Dict[str, Any]:
        """Load configuration from environment variables."""
        config = {}

        for key, value in os.environ.items():
            if self.prefix and not key.startswith(f"{self.prefix}_"):
                continue

            # Remove prefix and convert to lowercase with dots
            config_key = key
            if self.prefix:
                config_key = key[len(self.prefix) + 1 :]

            config_key = config_key.lower().replace("_", ".")

            # Try to parse as JSON, fall back to string
            try:
                parsed_value = json.loads(value)  # noqa: F821
                self._set_nested_value(config, config_key, parsed_value)
            except json.JSONDecodeError:  # noqa: F821
                self._set_nested_value(config, config_key, value)

        return config

    async def save(self, config: Dict[str, Any]) -> None:
        """Environment variables are read-only."""
        raise NotImplementedError("Environment variables cannot be written")

    def supports_write(self) -> bool:
        """Environment provider is read-only."""
        return False

    def get_source_type(self) -> ConfigurationSource:
        """Get source type."""
        return ConfigurationSource.ENVIRONMENT

    def _set_nested_value(self, data: Dict[str, Any], key: str, value: Any) -> None:
        """Set value in nested dictionary using dot notation."""
        keys = key.split(".")
        current = data

        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]

        current[keys[-1]] = value
