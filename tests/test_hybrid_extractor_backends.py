from __future__ import annotations

import pytest

from agents.core.models import EntityType, ExtractedEntity
from agents.extractors.hybrid_extractor import HybridLegalExtractor


@pytest.mark.asyncio
async def test_hybrid_ner_backend_extracts_basic_entities() -> None:
    extractor = HybridLegalExtractor(enable_llm_extraction=False)
    text = "Officer John Miller found $1,250 downstairs on Jan 5, 2026 in Superior Court."

    entities = await extractor._extract_with_ner(text)

    assert entities
    assert any(e.source == "hybrid_ner_patterns" for e in entities)
    assert any(e.entity_type.value == "money" for e in entities)


@pytest.mark.asyncio
async def test_hybrid_llm_backend_extracts_cue_entities() -> None:
    extractor = HybridLegalExtractor(enable_ner=False)
    text = "The contract states the party shall comply with KRS 218A in court."

    entities = await extractor._extract_with_llm(text)

    assert entities
    assert any(e.source == "hybrid_llm_cues" for e in entities)
    kinds = {e.entity_type.value for e in entities}
    assert "contract" in kinds
    assert "obligation" in kinds
    assert "statute" in kinds


def test_hybrid_merge_entities_deduplicates_and_prefers_higher_confidence() -> None:
    extractor = HybridLegalExtractor(enable_ner=True, enable_llm_extraction=True)
    items = [
        ExtractedEntity(
            text="downstairs",
            entity_type=EntityType.LOCATION,
            confidence=0.71,
            start_pos=5,
            end_pos=15,
            source="hybrid_ner_patterns",
        ),
        ExtractedEntity(
            text="downstairs",
            entity_type=EntityType.LOCATION,
            confidence=0.89,
            start_pos=5,
            end_pos=15,
            source="hybrid_llm_cues",
        ),
    ]

    merged = extractor._merge_entities(items)
    assert len(merged) == 1
    assert merged[0].confidence == pytest.approx(0.89)
    assert merged[0].source == "hybrid_llm_cues"
