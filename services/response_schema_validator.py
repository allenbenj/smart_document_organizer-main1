import copy
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)

try:
    from jsonschema import Draft202012Validator
except Exception:  # pragma: no cover
    Draft202012Validator = None


_SCHEMA_CACHE: Dict[str, Any] = {}


def _schema_path() -> Path:
    base = Path(__file__).resolve().parent.parent / "documents"
    preferred = base / "schemas" / "agent_result_schema_v2.json"
    if preferred.exists():
        return preferred
    return base / "agent_result_schema_v2.json"


def _load_validator():
    global _SCHEMA_CACHE
    if "validator" in _SCHEMA_CACHE:
        return _SCHEMA_CACHE["validator"]
    if Draft202012Validator is None:
        _SCHEMA_CACHE["validator"] = None
        return None
    p = _schema_path()
    if not p.exists():
        logger.warning("Schema file not found at %s", p)
        _SCHEMA_CACHE["validator"] = None
        return None
    schema = json.loads(p.read_text(encoding="utf-8"))
    _SCHEMA_CACHE["validator"] = Draft202012Validator(schema)
    return _SCHEMA_CACHE["validator"]


def _map_agent_type(agent_type: str) -> str:
    m = {
        "legal_reasoning": "legal",
        "irac_analyzer": "irac",
        "toulmin_analyzer": "toulmin",
        "entity_extractor": "entities",
    }
    return m.get(agent_type, agent_type)


def _normalize(agent_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(payload or {})
    out.setdefault("schema_version", "v2")
    out.setdefault("success", False)
    out.setdefault("data", {})
    if not isinstance(out.get("data"), dict):
        out["data"] = {"value": out.get("data")}
    out.setdefault("error", None)
    out.setdefault("processing_time", 0.0)
    out.setdefault("agent_type", agent_type)
    out.setdefault("metadata", {})
    out.setdefault("warnings", [])
    out.setdefault("fallback_used", False)
    return out


def enforce_agent_response(agent_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Validate/normalize API responses against v2 schema.

    Strict mode (default): AGENT_SCHEMA_ENFORCE=1 returns structured failure when invalid.
    Non-strict mode: attaches validation warning and returns normalized payload.
    """
    strict = os.getenv("AGENT_SCHEMA_ENFORCE", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }

    normalized = _normalize(agent_type, payload)
    validator = _load_validator()
    if validator is None:
        normalized.setdefault("metadata", {})["schema_validation"] = "skipped"
        return normalized

    candidate = copy.deepcopy(normalized)
    candidate["agent_type"] = _map_agent_type(candidate.get("agent_type", agent_type))

    errors = sorted(validator.iter_errors(candidate), key=lambda e: list(e.path))
    if not errors:
        normalized.setdefault("metadata", {})["schema_validation"] = "passed"
        return normalized

    first = errors[0]
    err_msg = f"{first.message} @ {'/'.join(str(p) for p in first.path) or '<root>'}"
    logger.warning("Schema validation failed for %s: %s", agent_type, err_msg)

    if strict:
        return {
            "schema_version": "v2",
            "success": False,
            "data": {},
            "error": f"Schema validation failed: {err_msg}",
            "processing_time": normalized.get("processing_time", 0.0),
            "agent_type": agent_type,
            "metadata": {
                "recoverable": True,
                "schema_validation": "failed",
                "schema_error": err_msg,
            },
            "warnings": [{"type": "schema_validation", "message": err_msg}],
            "fallback_used": True,
        }

    normalized.setdefault("metadata", {})["schema_validation"] = "failed"
    normalized.setdefault("warnings", []).append(
        {"type": "schema_validation", "message": err_msg}
    )
    return normalized
