"""Versioned extraction contracts for parser/plugin outputs (MVP)."""

from __future__ import annotations

from typing import Any, Dict

CURRENT_EXTRACTION_CONTRACT_VERSION = "1.0"


def build_extraction_contract(
    *,
    kind: str,
    parser_name: str,
    payload: Dict[str, Any],
    contract_version: str = CURRENT_EXTRACTION_CONTRACT_VERSION,
) -> Dict[str, Any]:
    return {
        "contract_version": str(contract_version),
        "kind": str(kind),
        "parser": str(parser_name),
        "payload": dict(payload or {}),
    }


def validate_extraction_contract(contract: Dict[str, Any]) -> bool:
    if not isinstance(contract, dict):
        return False
    for key in ("contract_version", "kind", "parser", "payload"):
        if key not in contract:
            return False
    return isinstance(contract.get("payload"), dict)


def migrate_contract_to_current(contract: Dict[str, Any]) -> Dict[str, Any]:
    """Best-effort migration to current schema version.

    MVP migration currently wraps legacy payload-only blobs.
    """
    if validate_extraction_contract(contract):
        if str(contract.get("contract_version")) == CURRENT_EXTRACTION_CONTRACT_VERSION:
            return contract
        migrated = dict(contract)
        migrated["contract_version"] = CURRENT_EXTRACTION_CONTRACT_VERSION
        return migrated

    return build_extraction_contract(
        kind="index_metadata",
        parser_name="legacy",
        payload=contract if isinstance(contract, dict) else {},
    )
