"""Unified LLM provider integration with xAI-first defaults.

This module exposes a single async LLM manager used by production agents.
It follows xAI's Responses API via OpenAI-compatible HTTP calls.
"""

from __future__ import annotations

import json
import os
from enum import Enum
from typing import Any, Dict, Optional

import httpx


class LLMProviderEnum(str, Enum):
    XAI = "xai"
    DEEPSEEK = "deepseek"

    @classmethod
    def _missing_(cls, value: object) -> "LLMProviderEnum | None":
        if isinstance(value, str):
            normalized = value.strip().lower()
            for member in cls:
                if member.value == normalized:
                    return member
        return None


class LLMCompletion(str):
    """String response that also supports `.content` access for compatibility."""

    def __new__(
        cls,
        content: str,
        model: Optional[str] = None,
        provider: Optional[str] = None,
        raw: Optional[Dict[str, Any]] = None,
    ) -> "LLMCompletion":
        obj = str.__new__(cls, content)
        obj._content = content
        obj.model = model
        obj.provider = provider
        obj.raw = raw or {}
        return obj

    @property
    def content(self) -> str:
        return self._content


class LLMManager:
    """Async manager for text generation/reasoning/structured output."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        provider: str = "xai",
        base_url: Optional[str] = None,
        default_model: Optional[str] = None,
        timeout_seconds: float = 60.0,
    ):
        self.provider = LLMProviderEnum(provider)
        self.api_key = api_key or os.getenv("XAI_API_KEY", "").strip()
        self.base_url = (
            base_url
            or os.getenv("XAI_BASE_URL", "https://api.x.ai/v1").strip()
            or "https://api.x.ai/v1"
        )
        self.default_model = (
            default_model
            or os.getenv("LLM_MODEL", "grok-4-fast-reasoning").strip()
            or "grok-4-fast-reasoning"
        )
        self.timeout_seconds = timeout_seconds

    async def complete(
        self,
        prompt: str,
        model: Optional[str] = None,
        provider: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        system_prompt: Optional[str] = None,
        json_schema: Optional[Dict[str, Any]] = None,
        reasoning_effort: Optional[str] = None,
        stream: bool = False,
        **_: Any,
    ) -> LLMCompletion:
        """Generate text using xAI Responses API.

        Compatibility:
        - Returns a string-like object (works with json.loads(response))
        - Also supports response.content (used in some existing modules)
        """
        active_provider = LLMProviderEnum(provider or self.provider.value)

        if active_provider is LLMProviderEnum.XAI:
            api_key = self.api_key or os.getenv("XAI_API_KEY", "").strip()
            base_url = self.base_url or os.getenv("XAI_BASE_URL", "https://api.x.ai/v1").strip()
            if not api_key:
                raise RuntimeError("Missing XAI_API_KEY")
            payload: Dict[str, Any] = {
                "model": model or self.default_model,
                "input": prompt,
            }
            if system_prompt:
                payload["instructions"] = system_prompt
            if temperature is not None:
                payload["temperature"] = temperature
            if max_tokens is not None:
                payload["max_output_tokens"] = max_tokens
            if reasoning_effort:
                payload["reasoning"] = {"effort": reasoning_effort}
            if json_schema:
                payload["response_format"] = {
                    "type": "json_schema",
                    "json_schema": json_schema,
                }
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            url = f"{base_url.rstrip('/')}/responses"
        elif active_provider is LLMProviderEnum.DEEPSEEK:
            api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
            base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1").strip()
            if not api_key:
                raise RuntimeError("Missing DEEPSEEK_API_KEY")
            payload = {
                "model": model or os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
                "messages": [{"role": "user", "content": prompt}],
            }
            if temperature is not None:
                payload["temperature"] = temperature
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            url = f"{base_url.rstrip('/')}/chat/completions"
        else:
            raise ValueError(f"Unsupported provider: {active_provider}")

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            if stream:
                if active_provider is not LLMProviderEnum.XAI:
                    raise ValueError("stream is currently supported for xai provider only")
                payload["stream"] = True
                text_out = []
                async with client.stream(
                    "POST", url, headers=headers, json=payload
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line or not line.startswith("data: "):
                            continue
                        data = line[6:].strip()
                        if data == "[DONE]":
                            break
                        try:
                            evt = json.loads(data)
                        except Exception:
                            continue
                        evt_type = evt.get("type", "")
                        if evt_type == "response.output_text.delta":
                            delta = evt.get("delta", "")
                            if delta:
                                text_out.append(delta)
                content = "".join(text_out).strip()
                return LLMCompletion(
                    content=content,
                    model=payload["model"],
                    provider=active_provider.value,
                    raw={"streamed": True},
                )

            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            if active_provider is LLMProviderEnum.DEEPSEEK:
                content = (((data or {}).get("choices") or [{}])[0].get("message") or {}).get("content") or ""
            else:
                content = self._extract_output_text(data)
            return LLMCompletion(
                content=content,
                model=payload["model"],
                provider=active_provider.value,
                raw=data,
            )

    def complete_sync(
        self,
        prompt: str,
        model: Optional[str] = None,
        provider: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        system_prompt: Optional[str] = None,
        json_schema: Optional[Dict[str, Any]] = None,
        reasoning_effort: Optional[str] = None,
        **_: Any,
    ) -> LLMCompletion:
        """Synchronous variant used by legacy sync service paths."""
        active_provider = LLMProviderEnum(provider or self.provider.value)

        if active_provider is LLMProviderEnum.XAI:
            api_key = self.api_key or os.getenv("XAI_API_KEY", "").strip()
            base_url = self.base_url or os.getenv("XAI_BASE_URL", "https://api.x.ai/v1").strip()
            if not api_key:
                raise RuntimeError("Missing XAI_API_KEY")
            payload: Dict[str, Any] = {
                "model": model or self.default_model,
                "input": prompt,
            }
            if system_prompt:
                payload["instructions"] = system_prompt
            if temperature is not None:
                payload["temperature"] = temperature
            if max_tokens is not None:
                payload["max_output_tokens"] = max_tokens
            if reasoning_effort:
                payload["reasoning"] = {"effort": reasoning_effort}
            if json_schema:
                payload["response_format"] = {
                    "type": "json_schema",
                    "json_schema": json_schema,
                }
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            url = f"{base_url.rstrip('/')}/responses"
        elif active_provider is LLMProviderEnum.DEEPSEEK:
            api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
            base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1").strip()
            if not api_key:
                raise RuntimeError("Missing DEEPSEEK_API_KEY")
            payload = {
                "model": model or os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
                "messages": [{"role": "user", "content": prompt}],
            }
            if temperature is not None:
                payload["temperature"] = temperature
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            url = f"{base_url.rstrip('/')}/chat/completions"
        else:
            raise ValueError(f"Unsupported provider: {active_provider}")

        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            if active_provider is LLMProviderEnum.DEEPSEEK:
                content = (((data or {}).get("choices") or [{}])[0].get("message") or {}).get("content") or ""
            else:
                content = self._extract_output_text(data)
            return LLMCompletion(
                content=content,
                model=payload["model"],
                provider=active_provider.value,
                raw=data,
            )

    async def compare(
        self,
        text_a: str,
        text_b: str,
        criteria: str = "factual consistency, legal accuracy, and completeness",
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Comparison helper built on structured outputs."""
        schema = {
            "name": "comparison_result",
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "winner": {"type": "string", "enum": ["A", "B", "tie"]},
                    "scores": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "A": {"type": "number"},
                            "B": {"type": "number"},
                        },
                        "required": ["A", "B"],
                    },
                    "justification": {"type": "string"},
                },
                "required": ["winner", "scores", "justification"],
            },
        }
        prompt = (
            "Compare response A and B.\n"
            f"Criteria: {criteria}\n\n"
            f"Response A:\n{text_a}\n\n"
            f"Response B:\n{text_b}\n"
        )
        out = await self.complete(
            prompt=prompt,
            model=model,
            temperature=0.0,
            json_schema=schema,
        )
        try:
            return json.loads(out)
        except Exception:
            return {"winner": "tie", "scores": {"A": 0.0, "B": 0.0}, "justification": out}

    @staticmethod
    def _extract_output_text(data: Dict[str, Any]) -> str:
        txt = data.get("output_text")
        if isinstance(txt, str) and txt.strip():
            return txt.strip()

        chunks = []
        for item in data.get("output", []) or []:
            for c in item.get("content", []) or []:
                if c.get("type") == "output_text" and c.get("text"):
                    chunks.append(c["text"])
        return "\n".join(chunks).strip()
