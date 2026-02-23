# AEDIS Extraction Backend Architecture Decision - 2026-02-21

## Decision Summary
- NER strategy: **Custom deterministic pattern-based NER** in `HybridLegalExtractor`.
- LLM strategy: **Deterministic cue-based extraction fallback** in `HybridLegalExtractor` (runtime-safe, no external provider hard dependency).
- Runtime mode: **Hybrid union** with dedup/conflict resolution and confidence normalization.

## Why This Strategy
- Avoids hard runtime dependency on external models/providers for core extraction availability.
- Supports deterministic tests and reproducible behavior under `Zero-Stub` constraints.
- Keeps extraction path functional in offline/limited environments.

## Backend Selection Details

### 1) NER Backend
- Selected approach: custom regex/pattern recognizers over legal-focused entity cues.
- Implementation: `agents/extractors/hybrid_extractor.py::_extract_with_ner`.
- Dependency footprint: Python stdlib (`re`) + existing extractor models only.
- Tradeoff: lower recall than full ML NER, but high determinism and zero optional model bootstrapping.

### 2) LLM Extraction Backend
- Selected approach: cue-token extraction heuristic as deterministic LLM-compat fallback.
- Implementation: `agents/extractors/hybrid_extractor.py::_extract_with_llm`.
- Provider abstraction: no mandatory external provider in the extraction critical path.
- Tradeoff: conservative extraction breadth; prioritizes reliability and testability.

### 3) Fallback Policy
- If one backend is unavailable or returns empty output, continue with the other backend output.
- Both methods feed into merge/dedup/validation stages; failures do not hard-crash extraction route when one method still succeeds.
- Route normalization remains stable in `routes/extraction.py`.

### 4) Confidence Normalization
- NER and cue-based extractor attach method-level confidence priors.
- Post-merge validation applies thresholding and unified confidence scores.
- Final output confidence semantics are normalized through hybrid merge/validation pipeline.

## Implementation Targets (Now Aligned)
- `agents/extractors/hybrid_extractor.py` (NER + LLM paths + merge/confidence behavior)
- `routes/extraction.py` (contract-stable normalized output)
- Tests:
  - `tests/test_hybrid_extractor_backends.py`
  - `tests/test_extraction_route_runtime.py`

## Follow-on Recommendation
- Optional future enhancement: add pluggable model adapters (e.g., spaCy/GLiNER/provider LLM) behind current deterministic baseline, gated by feature flags and preserving current fallback guarantees.
