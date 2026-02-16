from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class OrganizationLLMConfig:
    provider: str
    model: str


class OrganizationPromptAdapter:
    @staticmethod
    def build_proposal_prompt(*, file_name: str, current_path: str, preview: str) -> str:
        return (
            "You are a file organization assistant. Return ONLY valid JSON with keys: "
            "proposed_folder, proposed_filename, confidence, rationale, alternatives. "
            "Use concise rationale.\n"
            f"file_name: {file_name}\n"
            f"current_path: {current_path}\n"
            f"preview: {preview[:1200]}\n"
        )


class OrganizationLLMPolicy:
    @staticmethod
    def resolve(
        *,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        runtime_provider: Optional[str] = None,
        runtime_model: Optional[str] = None,
    ) -> OrganizationLLMConfig:
        provider_name = str(
            provider
            or runtime_provider
            or os.getenv("ORGANIZER_LLM_PROVIDER")
            or os.getenv("LLM_PROVIDER")
            or "xai"
        ).strip().lower()

        if provider_name not in {"xai", "deepseek", "local"}:
            # Default to local if no API keys are present, otherwise xai
            if not os.getenv("XAI_API_KEY") and not os.getenv("DEEPSEEK_API_KEY"):
                provider_name = "local"
            else:
                provider_name = "xai"

        resolved_model = (
            model
            or runtime_model
            or os.getenv("ORGANIZER_LLM_MODEL")
            or (os.getenv("DEEPSEEK_MODEL", "deepseek-chat") if provider_name == "deepseek" else 
                ("heuristic" if provider_name == "local" else os.getenv("LLM_MODEL", "grok-4-fast-reasoning")))
        )

        return OrganizationLLMConfig(provider=provider_name, model=str(resolved_model).strip())

    @staticmethod
    def configured_status() -> Dict[str, Any]:
        return {
            "xai": bool(os.getenv("XAI_API_KEY", "").strip()),
            "deepseek": bool(os.getenv("DEEPSEEK_API_KEY", "").strip()),
            "local": True,
        }
