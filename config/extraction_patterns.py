"""Extraction patterns used by extraction agents.

Supports both built-in regex patterns and optional YAML-loaded patterns.
"""

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

PATTERNS: Dict[str, str] = {
    "case_citation": r"\b\d+\s+[A-Z][A-Za-z\.]*\s+\d+\b",
    "date": r"\b\d{4}-\d{2}-\d{2}\b",
    "email": r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
    "statute_reference": r"\b\d+\s+U\.?S\.?C\.?\s*§\s*\d+\b",
    "phone": r"\b\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b",
    "money": r"\$\s?\d{1,3}(?:,\d{3})*(?:\.\d{2})?\b",
    "url": r"https?://[^\s<>\"']+",
    "section_reference": r"\b[Ss]ection\s+\d+(?:\.\d+)*\b",
}


class PatternLoader:
    """Pattern loader for regex-based extraction.

    Loads patterns from built-in defaults and optionally from a YAML file.
    """

    def __init__(self, pattern_path: Optional[str] = None):
        self.pattern_path = pattern_path
        self.patterns: Dict[str, str] = PATTERNS.copy()
        self._compiled: Dict[str, re.Pattern] = {}
        self._load_yaml_patterns()
        self._compile_patterns()

    def _load_yaml_patterns(self) -> None:
        """Load additional patterns from YAML file if available."""
        if not self.pattern_path:
            default_path = Path(__file__).parent / "patterns.yaml"
            if default_path.exists():
                self.pattern_path = str(default_path)
            else:
                return

        path = Path(self.pattern_path)
        if not path.exists():
            logger.debug("Pattern file not found: %s", self.pattern_path)
            return

        try:
            import yaml
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            if isinstance(data, dict):
                for key, value in data.items():
                    if isinstance(key, str) and isinstance(value, str):
                        self.patterns[key] = value
                logger.info("Loaded %d patterns from %s", len(data), path)
        except ImportError:
            logger.debug("pyyaml not installed; using built-in patterns only")
        except Exception as e:
            logger.warning("Failed to load patterns from %s: %s", path, e)

    def _compile_patterns(self) -> None:
        """Pre-compile all regex patterns."""
        for name, pattern in self.patterns.items():
            try:
                self._compiled[name] = re.compile(pattern)
            except re.error as e:
                logger.warning("Invalid regex for pattern '%s': %s", name, e)

    def extract_entities_from_text(
        self, text: str, entity_types: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Extract entities from text using regex patterns.

        Args:
            text: Input text to search.
            entity_types: If provided, only extract these entity types.

        Returns:
            List of entity dicts with keys: type, value, start, end.
        """
        if not text:
            return []

        entities: List[Dict[str, Any]] = []
        patterns_to_use = (
            {k: v for k, v in self._compiled.items() if k in entity_types}
            if entity_types
            else self._compiled
        )

        for entity_type, compiled in patterns_to_use.items():
            for match in compiled.finditer(text):
                entities.append({
                    "type": entity_type,
                    "value": match.group(),
                    "start": match.start(),
                    "end": match.end(),
                })

        return entities

    def extract_relationships_from_text(
        self, text: str, relationship_types: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Extract co-occurrence relationships between entities found in text.

        Entities appearing within the same sentence are linked as co-occurring.

        Args:
            text: Input text to search.
            relationship_types: If provided, only consider these entity types.

        Returns:
            List of relationship dicts with keys: source, target, type.
        """
        if not text:
            return []

        entities = self.extract_entities_from_text(text, relationship_types)
        if len(entities) < 2:
            return []

        # Split into sentences and find co-occurrences
        sentences = re.split(r'[.!?]+', text)
        relationships: List[Dict[str, Any]] = []
        seen_pairs: set = set()

        for sentence in sentences:
            if not sentence.strip():
                continue
            sent_start = text.find(sentence)
            sent_end = sent_start + len(sentence)

            # Find entities within this sentence
            sent_entities = [
                e for e in entities
                if e["start"] >= sent_start and e["end"] <= sent_end
            ]

            # Create pairwise co-occurrence relationships
            for i, src in enumerate(sent_entities):
                for tgt in sent_entities[i + 1:]:
                    pair_key = (src["value"], tgt["value"])
                    if pair_key not in seen_pairs:
                        seen_pairs.add(pair_key)
                        relationships.append({
                            "source": {"type": src["type"], "value": src["value"]},
                            "target": {"type": tgt["type"], "value": tgt["value"]},
                            "type": "co_occurrence",
                        })

        return relationships

    def reload_patterns(self) -> None:
        """Reload patterns from YAML file and recompile."""
        self.patterns = PATTERNS.copy()
        self._compiled.clear()
        self._load_yaml_patterns()
        self._compile_patterns()

    def get_entity_patterns(self) -> Dict[str, Any]:
        """Get all active entity patterns."""
        return dict(self.patterns)

    def get_relationship_patterns(self) -> Dict[str, Any]:
        """Get relationship extraction patterns (entity patterns used for co-occurrence)."""
        return dict(self.patterns)


def get_pattern_loader(pattern_path: Optional[str] = None) -> PatternLoader:
    """Get a pattern loader instance.

    Args:
        pattern_path: Optional path to pattern configuration file

    Returns:
        PatternLoader instance
    """
    return PatternLoader(pattern_path)
