from __future__ import annotations

from core.llm_providers import LLMProviderEnum


def test_llm_provider_enum_is_case_insensitive() -> None:
    assert LLMProviderEnum("Deepseek") is LLMProviderEnum.DEEPSEEK
    assert LLMProviderEnum("XAI") is LLMProviderEnum.XAI
    assert LLMProviderEnum("  deepseek  ") is LLMProviderEnum.DEEPSEEK
