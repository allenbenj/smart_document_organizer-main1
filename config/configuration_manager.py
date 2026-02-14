from __future__ import annotations

import os  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import Any, Dict, Optional  # noqa: E402

from .core.constants import Constants  # noqa: E402


class ConfigurationManager:
    """Layered configuration with env/.env support and dotted keys.

    Priority: initial overrides > environment > .env file > defaults
    """

    def __init__(
        self,
        initial: Optional[Dict[str, Any]] = None,
        env_prefix: Optional[str] = None,
        dotenv_path: Optional[str] = None,
    ) -> None:
        self._data: Dict[str, Any] = {}
        self.env_prefix = env_prefix
        # Load defaults
        self._apply_defaults()
        # Load from .env
        self.load_dotenv(dotenv_path)
        # Load from os.environ
        self.load_env()
        # Apply user-supplied overrides last
        if initial:
            self.merge(initial)

    # -------------------- Loaders --------------------
    def _apply_defaults(self) -> None:
        self._data.update(
            {
                "env": Constants.DEFAULT_ENV,
                "agents.cache_ttl_seconds": Constants.AGENTS_CACHE_TTL_SECONDS,
                "vector.dimension": Constants.VECTOR_DIMENSION,
            }
        )

    def load_dotenv(self, dotenv_path: Optional[str] = None) -> None:
        path = Path(dotenv_path) if dotenv_path else Path.cwd() / ".env"
        if not path.exists():
            return
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                self._ingest_env_var(key, val)
        except Exception:
            # Non-fatal: ignore malformed .env
            pass

    def load_env(self) -> None:
        for key, val in os.environ.items():
            if self.env_prefix and not key.startswith(self.env_prefix):
                continue
            self._ingest_env_var(key, val)

    def _ingest_env_var(self, key: str, val: str) -> None:  # noqa: C901
        # Store raw under env.KEY
        self._data[f"env.{key}"] = val
        # Map known keys to friendly dotted paths
        if key == Constants.ENV_KEY:
            self._data["env"] = val
        elif key == Constants.API_KEY_NAME:
            self._data["security.api_key"] = val
        elif key == Constants.AGENTS_ENABLE_LEGAL_REASONING:
            self._data["agents.enable_legal_reasoning"] = self._to_bool(val)
        elif key == Constants.AGENTS_ENABLE_ENTITY_EXTRACTOR:
            self._data["agents.enable_entity_extractor"] = self._to_bool(val)
        elif key == Constants.AGENTS_ENABLE_IRAC:
            self._data["agents.enable_irac"] = self._to_bool(val)
        elif key == Constants.AGENTS_ENABLE_TOULMIN:
            self._data["agents.enable_toulmin"] = self._to_bool(val)
        elif key == Constants.AGENTS_ENABLE_REGISTRY:
            self._data["agents.enable_registry"] = self._to_bool(val)
        elif key == Constants.AGENTS_CACHE_TTL_KEY:
            self._data["agents.cache_ttl_seconds"] = self._to_int(
                val, Constants.AGENTS_CACHE_TTL_SECONDS
            )
        elif key == Constants.VECTOR_DIMENSION_KEY:
            self._data["vector.dimension"] = self._to_int(
                val, Constants.VECTOR_DIMENSION
            )
        elif key == Constants.VECTOR_USE_ST_KEY:
            self._data["vector.use_sentence_transformers"] = self._to_bool(val)
        elif key == Constants.VECTOR_EMBEDDING_MODEL_KEY:
            self._data["vector.embedding_model"] = val
        elif key == Constants.MEMORY_APPROVAL_THRESHOLD_KEY:
            try:
                self._data["memory.approval_threshold"] = float(val)
            except Exception:
                self._data["memory.approval_threshold"] = (
                    Constants.MEMORY_APPROVAL_THRESHOLD_DEFAULT
                )

    # -------------------- Accessors --------------------
    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value

    def merge(self, values: Dict[str, Any]) -> None:
        for k, v in values.items():
            self._data[k] = v

    def get_bool(self, key: str, default: bool = False) -> bool:
        value = self.get(key, default)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return self._to_bool(value, default)
        return bool(value)

    def get_int(self, key: str, default: int = 0) -> int:
        value = self.get(key, default)
        return self._to_int(value, default)

    def get_float(self, key: str, default: float = 0.0) -> float:
        try:
            return float(self.get(key, default))
        except (TypeError, ValueError):
            return default

    def get_str(self, key: str, default: str = "") -> str:
        value = self.get(key, default)
        return str(value) if value is not None else default

    def get_section(self, section: str) -> Dict[str, Any]:
        prefix = section + "."
        out: Dict[str, Any] = {}
        for k, v in self._data.items():
            if k.startswith(prefix):
                out[k[len(prefix) :]] = v
        return out

    def as_dict(self) -> Dict[str, Any]:
        return dict(self._data)

    # -------------------- Helpers --------------------
    @staticmethod
    def _to_bool(value: Any, default: bool = False) -> bool:
        if isinstance(value, bool):
            return value
        s = str(value).strip().lower()
        if s in {"1", "true", "yes", "on", "y"}:
            return True
        if s in {"0", "false", "no", "off", "n"}:
            return False
        return default

    @staticmethod
    def _to_int(value: Any, default: int = 0) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default


def create_configuration_manager(
    initial: Optional[Dict[str, Any]] = None,
    env_prefix: Optional[str] = None,
    dotenv_path: Optional[str] = None,
) -> ConfigurationManager:
    return ConfigurationManager(
        initial=initial, env_prefix=env_prefix, dotenv_path=dotenv_path
    )
