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
    def build_proposal_prompt(
        *,
        file_name: str,
        current_path: str,
        preview: str,
        known_folders: Optional[list[str]] = None,
        semantic_summary: Optional[Dict[str, Any]] = None,
    ) -> str:
        folder_hint = ""
        folders = [str(x).strip() for x in (known_folders or []) if str(x).strip()]
        if folders:
            sample = folders[:120]
            folder_hint = (
                "Known existing folders (prefer these; only create a new folder when necessary):\n"
                + "\n".join(f"- {f}" for f in sample)
                + "\n"
            )

        semantic_info = ""
        if semantic_summary:
            doc_type = semantic_summary.get("document_type")
            legal_domain = semantic_summary.get("legal_domain")
            key_topics = ", ".join(semantic_summary.get("key_topics", []))
            doc_summary = semantic_summary.get("document_summary")
            confidence = semantic_summary.get("confidence")

            semantic_info = (
                "\n--- Semantic Analysis ---\n"
                f"Document Type: {doc_type or 'N/A'}\n"
                f"Legal Domain: {legal_domain or 'N/A'}\n"
                f"Key Topics: {key_topics or 'N/A'}\n"
                f"Summary: {doc_summary or 'N/A'}\n"
                f"Confidence Score: {confidence:.2f}\n"
                "-------------------------\n"
            )

        return (
            "You are a file organization assistant. Return ONLY valid JSON with keys: "
            "proposed_folder, proposed_filename, confidence, rationale, alternatives, "
            "evidence_spans (list of objects with keys: start_char, end_char, quote). "
            "Use concise rationale. Evidence spans should point to the exact character "
            "offsets in the preview that justify the folder choice.\n"
            f"file_name: {file_name}\n"
            f"current_path: {current_path}\n"
            f"preview: {preview[:1200]}\n"
            f"{folder_hint}"
            f"{semantic_info}"
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

        if provider_name not in {"xai", "deepseek"}:
            provider_name = "xai"

        resolved_model = (
            model
            or runtime_model
            or os.getenv("ORGANIZER_LLM_MODEL")
            or (
                os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
                if provider_name == "deepseek"
                else os.getenv("LLM_MODEL", "grok-4-fast-reasoning")
            )
        )

        return OrganizationLLMConfig(provider=provider_name, model=str(resolved_model).strip())

    @staticmethod
    def configured_status() -> Dict[str, Any]:
        return {
            "xai": bool(os.getenv("XAI_API_KEY", "").strip()),
            "deepseek": bool(os.getenv("DEEPSEEK_API_KEY", "").strip()),
        }
