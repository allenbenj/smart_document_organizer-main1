"""
Configuration providers for different sources (files, databases, etc.).
"""

import json
import sqlite3  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import Any, Dict, Optional  # noqa: E402

from ..interfaces.configuration import (  # noqa: E402
    ConfigurationFormat,
    ConfigurationProvider,
    ConfigurationSource,
    ConfigurationSourceError,
)


class FileConfigurationProvider(ConfigurationProvider):
    """Configuration provider for file-based configuration."""

    def __init__(self, file_path: Path, format_type: ConfigurationFormat):
        self.file_path = file_path
        self.format_type = format_type

    async def load(self) -> Dict[str, Any]:
        """Load configuration from file."""
        try:
            if not self.file_path.exists():
                return {}

            content = self.file_path.read_text(encoding="utf-8")

            if self.format_type == ConfigurationFormat.JSON:
                return json.loads(content)
            elif self.format_type == ConfigurationFormat.YAML:
                return self._load_yaml(content)
            elif self.format_type == ConfigurationFormat.TOML:
                return self._load_toml(content)
            elif self.format_type == ConfigurationFormat.INI:
                return self._load_ini(content)
            elif self.format_type == ConfigurationFormat.ENV:
                return self._load_env(content)
            else:
                raise ConfigurationSourceError(
                    f"Unsupported format: {self.format_type}"
                )

        except Exception as e:
            raise ConfigurationSourceError(
                f"Failed to load config from {self.file_path}: {e}"
            )

    async def save(self, config: Dict[str, Any]) -> None:
        """Save configuration to file."""
        try:
            if self.format_type == ConfigurationFormat.JSON:
                content = json.dumps(config, indent=2)
            elif self.format_type == ConfigurationFormat.YAML:
                content = self._save_yaml(config)
            elif self.format_type == ConfigurationFormat.TOML:
                content = self._save_toml(config)
            elif self.format_type == ConfigurationFormat.INI:
                content = self._save_ini(config)
            else:
                raise ConfigurationSourceError(
                    f"Saving not supported for format: {self.format_type}"
                )

            self.file_path.write_text(content, encoding="utf-8")

        except Exception as e:
            raise ConfigurationSourceError(
                f"Failed to save config to {self.file_path}: {e}"
            )

    def supports_write(self) -> bool:
        """Check if provider supports writing."""
        return self.format_type in (
            ConfigurationFormat.JSON,
            ConfigurationFormat.YAML,
            ConfigurationFormat.TOML,
            ConfigurationFormat.INI,
        )

    def get_source_type(self) -> ConfigurationSource:
        """Get source type."""
        return ConfigurationSource.FILE

    def _load_yaml(self, content: str) -> Dict[str, Any]:
        """Load YAML content."""
        try:
            import yaml  # noqa: E402

            return yaml.safe_load(content) or {}
        except ImportError:
            raise ConfigurationSourceError("PyYAML not installed for YAML support")

    def _save_yaml(self, config: Dict[str, Any]) -> str:
        """Save config as YAML."""
        try:
            import yaml  # noqa: E402

            return yaml.dump(config, default_flow_style=False, indent=2)
        except ImportError:
            raise ConfigurationSourceError("PyYAML not installed for YAML support")

    def _load_toml(self, content: str) -> Dict[str, Any]:
        """Load TOML content."""
        try:
            import tomllib as tomli  # noqa: E402

            return tomli.loads(content)
        except ImportError:
            try:
                import tomli  # noqa: E402

                return tomli.loads(content)
            except ImportError as e:
                raise ConfigurationSourceError(
                    "tomllib/tomli not installed for TOML support"
                ) from e

    def _save_toml(self, config: Dict[str, Any]) -> str:
        """Save config as TOML."""
        try:
            import tomli_w  # noqa: E402

            return tomli_w.dumps(config)
        except ImportError:
            raise ConfigurationSourceError("tomli-w not installed for TOML support")

    def _load_ini(self, content: str) -> Dict[str, Any]:
        """Load INI content."""
        import configparser  # noqa: E402

        parser = configparser.ConfigParser()
        parser.read_string(content)

        config = {}
        for section in parser.sections():
            config[section] = dict(parser[section])

        return config

    def _save_ini(self, config: Dict[str, Any]) -> str:
        """Save config as INI."""
        import configparser  # noqa: E402
        import io  # noqa: E402

        parser = configparser.ConfigParser()

        for section, values in config.items():
            if isinstance(values, dict):
                parser[section] = values

        output = io.StringIO()
        parser.write(output)
        return output.getvalue()

    def _load_env(self, content: str) -> Dict[str, Any]:
        """Load environment file content."""
        config = {}
        for line in content.splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                if "=" in line:
                    key, value = line.split("=", 1)
                    key = key.strip().lower().replace("_", ".")
                    value = value.strip().strip("\"'")

                    # Try to parse as JSON, fall back to string
                    try:
                        parsed_value = json.loads(value)
                        self._set_nested_value(config, key, parsed_value)
                    except json.JSONDecodeError:
                        self._set_nested_value(config, key, value)

        return config

    def _set_nested_value(self, data: Dict[str, Any], key: str, value: Any) -> None:
        """Set value in nested dictionary using dot notation."""
        keys = key.split(".")
        current = data

        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]

        current[keys[-1]] = value


class EnvironmentConfigurationProvider(ConfigurationProvider):
    """Configuration provider for environment variables."""

    def __init__(self, prefix: Optional[str] = None):
        self.prefix = prefix

    async def load(self) -> Dict[str, Any]:
        """Load configuration from environment variables."""
        import os  # noqa: E402

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
                parsed_value = json.loads(value)
                self._set_nested_value(config, config_key, parsed_value)
            except json.JSONDecodeError:
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


class DatabaseConfigurationProvider(ConfigurationProvider):
    """Configuration provider for database-stored configuration."""

    def __init__(self, connection_string: str, table_name: str = "configuration"):
        self.connection_string = connection_string
        self.table_name = table_name

    async def load(self) -> Dict[str, Any]:
        """Load configuration from database."""
        try:
            # For SQLite (adjust for other databases as needed)
            if self.connection_string.startswith("sqlite:"):
                db_path = self.connection_string[7:]  # Remove 'sqlite:' prefix
                return await self._load_from_sqlite(db_path)
            else:
                raise ConfigurationSourceError(
                    f"Unsupported database type: {self.connection_string}"
                )

        except Exception as e:
            raise ConfigurationSourceError(f"Failed to load config from database: {e}")

    async def save(self, config: Dict[str, Any]) -> None:
        """Save configuration to database."""
        try:
            if self.connection_string.startswith("sqlite:"):
                db_path = self.connection_string[7:]
                await self._save_to_sqlite(db_path, config)
            else:
                raise ConfigurationSourceError(
                    f"Unsupported database type: {self.connection_string}"
                )

        except Exception as e:
            raise ConfigurationSourceError(f"Failed to save config to database: {e}")

    def supports_write(self) -> bool:
        """Database provider supports writing."""
        return True

    def get_source_type(self) -> ConfigurationSource:
        """Get source type."""
        return ConfigurationSource.DATABASE

    async def _load_from_sqlite(self, db_path: str) -> Dict[str, Any]:
        """Load configuration from SQLite database."""
        config = {}

        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()

            # Create table if it doesn't exist
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {self.table_name} (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    value_type TEXT
                )
            """
            )

            # Load all configuration entries
            cursor.execute(f"SELECT key, value, value_type FROM {self.table_name}")

            for key, value_str, value_type in cursor.fetchall():
                # Parse value based on type
                if value_type == "json":
                    value = json.loads(value_str)
                elif value_type == "int":
                    value = int(value_str)
                elif value_type == "float":
                    value = float(value_str)
                elif value_type == "bool":
                    value = value_str.lower() in ("true", "1", "yes")
                else:
                    value = value_str

                self._set_nested_value(config, key, value)

        return config

    async def _save_to_sqlite(self, db_path: str, config: Dict[str, Any]) -> None:
        """Save configuration to SQLite database."""
        flat_config = self._flatten_dict(config)

        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()

            # Create table if it doesn't exist
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {self.table_name} (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    value_type TEXT
                )
            """
            )

            # Clear existing configuration
            cursor.execute(f"DELETE FROM {self.table_name}")

            # Insert new configuration
            for key, value in flat_config.items():
                if isinstance(value, (dict, list)):
                    value_str = json.dumps(value)
                    value_type = "json"
                elif isinstance(value, bool):
                    value_str = str(value)
                    value_type = "bool"
                elif isinstance(value, int):
                    value_str = str(value)
                    value_type = "int"
                elif isinstance(value, float):
                    value_str = str(value)
                    value_type = "float"
                else:
                    value_str = str(value)
                    value_type = "str"

                cursor.execute(
                    f"INSERT INTO {self.table_name} (key, value, value_type) VALUES (?, ?, ?)",
                    (key, value_str, value_type),
                )

            conn.commit()

    def _flatten_dict(self, data: Dict[str, Any], prefix: str = "") -> Dict[str, Any]:
        """Flatten nested dictionary with dot notation keys."""
        flat = {}
        for key, value in data.items():
            full_key = f"{prefix}.{key}" if prefix else key

            if isinstance(value, dict):
                flat.update(self._flatten_dict(value, full_key))
            else:
                flat[full_key] = value

        return flat

    def _set_nested_value(self, data: Dict[str, Any], key: str, value: Any) -> None:
        """Set value in nested dictionary using dot notation."""
        keys = key.split(".")
        current = data

        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]

        current[keys[-1]] = value
