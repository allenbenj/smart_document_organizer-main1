"""
Centralized configuration for File Organizer.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, Optional

@dataclass
class DeepSeekConfig:
    api_key: str
    base_url: str = "https://api.deepseek.com/v1"
    model: str = "deepseek-chat"
    timeout: int = 30

@dataclass
class ExtractionConfig:
    enable_ocr: bool = False
    cache_content: bool = True
    max_content_chars: int = 15000  # Increased for better context
    timeout: int = 15

@dataclass
class OrganizerConfig:
    source_folder: Path
    output_folder: Path
    db_path: Optional[Path] = None
    dry_run: bool = False
    use_llm: bool = True
    llm_confidence_threshold: float = 0.8  # Strict high confidence
    extraction_config: ExtractionConfig = field(default_factory=ExtractionConfig)
    enable_deduplication: bool = False
    enable_renaming: bool = False
    enable_indexing: bool = False

    # Resumption
    resume_from_last_run: bool = False

    # Performance tuning
    assignment_batch_size: int = 50  # Files per LLM batch
    max_concurrent_batches: int = 20   # Parallel LLM requests (increased for faster processing)
    content_excerpt_length: int = 100  # Characters per file in assignment

    # Path templates
    path_templates: Dict[str, str] = field(default_factory=lambda: {
        "legal": "01_Cases/{case_number}/01_Court_Filings/{doc_type}",
        "research": "02_Research/{category}/{year}",
        "data": "03_Data/{category}/{subcategory}",
        "reference": "04_Reference/{category}",
        "default": "99_Unsorted/{doc_type}"
    })

    def __post_init__(self):
        if self.db_path is None:
            self.db_path = self.source_folder / ".organizer" / "organizer.db"

def load_config_from_env() -> DeepSeekConfig:
    """Load DeepSeek config from environment variables."""
    return DeepSeekConfig(
        api_key=os.environ.get("DEEPSEEK_API_KEY", ""),
        base_url=os.environ.get("DEEPSEEK_BASE_URL", ""),
        model=os.environ.get("DEEPSEEK_MODEL", "")
    )

