from __future__ import annotations

import os
from pathlib import Path

from config.configuration_manager import ConfigurationManager


def test_load_dotenv_populates_os_environ(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "XAI_API_KEY=test-xai-key\n"
        "LLM_PROVIDER=xai\n",
        encoding="utf-8",
    )

    cfg = ConfigurationManager(dotenv_path=str(env_file))

    assert cfg.get_str("env.XAI_API_KEY", "") == "test-xai-key"
    assert cfg.get_str("env.LLM_PROVIDER", "") == "xai"
    assert os.getenv("XAI_API_KEY", "") == "test-xai-key"
