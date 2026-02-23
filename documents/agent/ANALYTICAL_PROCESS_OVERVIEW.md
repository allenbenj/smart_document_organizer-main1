# Analytical Processes and Entity Extraction Pipeline

This document describes, in thorough detail, every analytical step carried
out by the application with a focus on the legal entity extractor.  It
identifies the code modules involved, the data passed between them, and
examples of how the pieces can be composed into end-to-end pipelines.

> Note: the hybrid extractor is the core component, but many other
> services transform its output or feed it additional context.

---

## 1. Ingestion & Document Preparation

* **Module:** `gui/tabs/document_processing_tab.py` and the corresponding
  backend route `routes/documents.py` (`/api/files/upload`).
* **Inputs:** raw file bytes or folder path.
* **Actions:**
  1. Save file to workspace storage (e.g. `data/uploads/`).
  2. Normalize text via `utils/ingestion.py` (PDF text, OCR fallback,
     Office documents, etc.).
  3. Create a `LegalDocument` object (defined in `core/models.py`) which
     contains `id`, `filename`, `content`, `metadata`, and optional
     `file_path`.
  4. Store the document record in `mem_db/documents.sqlite`.
* **Outputs:** `LegalDocument` instance available for downstream agents.

Example pipeline snippet:
```python
from agents.extractors.hybrid_extractor import HybridLegalExtractor
from core.models import LegalDocument

# after ingestion
doc = LegalDocument(id="123", filename="contract.pdf", content=text)
extractor = HybridLegalExtractor()
result = await extractor.extract_from_document(doc)
```


## 2. Hybrid Legal Entity Extraction

* **Module:** `agents/extractors/hybrid_extractor.py` (class
  `HybridLegalExtractor`).
* **Invocation:**
  - directly via Python (see example above),
  - via agent manager `agents/production_agent_manager.py` which is
    exposed at `/api/agents/extract/run`.
* **Primary methods:**
  - `extract_from_document(document)` – asynchronous; orchestrates the
    sub‑steps below and returns `HybridExtractionResult`.
  - `_extract_with_ner(text)` – currently unimplemented placeholder; in a
    real system it would call spaCy or similar.
  - `_extract_with_llm(text)` – placeholder for LLM‑based pattern
    extraction (e.g. prompting an LLM to list entities).
  - `_validate_entities(entities)` – filters by confidence threshold and
    other quality rules.
  - `_extract_relationships(validated_entities, text)` – simple rule‑based
    proximity relationships; extendable with more sophisticated logic.
  - `_calculate_confidence_scores(entities)` – aggregates confidences.

### Data structures

`HybridExtractionResult` contains:
```python
@dataclass
class HybridExtractionResult:
    document_id: str
    document_path: str
    entities: List[ExtractedEntity]
    relationships: List[ExtractedRelationship]
    validated_entities: List[ExtractedEntity]
    extraction_methods_used: List[str]
    processing_time: float
    confidence_scores: Dict[str,float]
    total_entities_found: int
    high_confidence_entities: int
    validation_results: Dict[str,Any]
    created_at: datetime
```
Entities and relationships are defined in `core/models.py`.

### Example flow

1. `extract_from_document` called by ingestion or by a pipeline step.
2. If `enable_ner`, run `_extract_with_ner` → returns entities.
3. If `enable_llm_extraction`, run `_extract_with_llm` → returns entities.
4. Merge lists, then call `_validate_entities` to apply confidence filter.
5. If any validated entities, call `_extract_relationships` to produce
   simple `works_for` edges.
6. Compute confidence summary and log metrics.
7. Return `HybridExtractionResult` to caller.

### Pipeline example

A sample theoretical pipeline combining extraction with reasoning and
memory storage:

```python
from agents.extractors.hybrid_extractor import HybridLegalExtractor
from agents.memory_manager import MemoryManager
from agents.reasoning_service import CognitiveReasoningService

extractor = HybridLegalExtractor()
memory = MemoryManager()
reasoner = CognitiveReasoningService()

result = await extractor.extract_from_document(doc)
# convert entities to memory proposals
for ent in result.validated_entities:
    memory.propose(
        namespace="legal_entities",
        key=ent.id,
        content=ent.to_json(),
        confidence_score=ent.confidence,
    )
# run reasoning on entire document
reasoning = await reasoner.analyze_text(doc.content)
# store reasoning claims
for claim in reasoning.claims:
    memory.propose(...)
```

The above could be wrapped in a single pipeline definition file or
triggered as part of a `gui/tabs/pipelines_tab.py` job.


## 3. Analysis & Validation steps

Beyond extraction itself, the application provides multiple analytic
processes that can be chained:

* **Semantic clustering** – `agents/semantic_service.py` (not shown but
  used by `semantic_analysis_tab.py`) generates theme clusters that can
  augment extraction results by providing context (e.g. classify an
  extracted name as a 'court' if it appears in a 'jurisdiction' theme).
* **Conflict detection** – `agents/contradictions.py` receives the
  latest memory entries and runs pairwise text comparisons to flag
  contradictions; the GUI tab allows manual review.
* **Violation analysis** – similar to contradictions, using rules from
  `agents/violations.py`.
* **Reasoning & truth evaluation** – described previously, this step
  consumes validated entities and facts to generate structured arguments.
* **Heuristic governance** – `agents/heuristics.py` and the GUI heuristics
  tab evaluate extractor/rule performance and provide expert review.

Each of these services exposes `/api/agents/<name>` endpoints and may be
invoked in sequence or parallel as part of a larger pipeline.

## 4. Pipelines and composition strategies

The system defines pipelines either in code (`pipelines/presets.py`) or
via dynamic definitions stored in the database.  A typical pipeline that
uses the entity extractor might look like:

1. **Upload** document via `/api/files/upload`.
2. **Process** document (`/api/processing/start`).
3. **Extract** entities (`/api/agents/extract/run`).
4. **Validate** and store proposals (`/api/agents/memory/proposals`).
5. **Reason** about document (`/api/agents/legal_reasoning`).
6. **Audit** via `/api/agents/shadow/*` if in production shadow mode.
7. **Finalize** by updating knowledge graph or vector store.

Pipelines are orchestrated by the `pipelines` module, which can run
steps sequentially or in parallel according to dependencies.  Example
pseudo‑definition:

```python
pipeline = [
    Step(name="ingest", func=ingest_file),
    Step(name="extract", func=extractor.extract_from_document, depends_on=["ingest"]),
    Step(name="reason", func=reasoner.analyze_text, depends_on=["extract"]),
    Step(name="store", func=memory.commit, depends_on=["reason"]),
]
run_pipeline(pipeline)
```

The GUI `PipelinesTab` allows non‑technical users to configure similar
workflows without writing code.

## 5. Hybrid Legal Extractor Review and Extensions

Though the simple `HybridLegalExtractor` shown above provides placeholders
for NER and LLM methods, the architecture anticipates:

* **Plug‑in extractors** – method names stored in result.extraction_methods
  so new strategies (e.g. regex, deep‑learning models) can be added just
  by implementing `_extract_with_<name>`.
* **Shadow audit** – when running in production with shadow mode, the
  extractor logs to `logs/shadow/` and returns results to `/api/agents/shadow/extract`.
  A separate process (`agents/audit.py`) compares shadow results to
  approved outputs and raises flags if discrepancies exceed thresholds.
* **Confidence calibration** – extracted entities are adjusted by a
  calibration service (`agents/confidence_calibrator.py`) which learns from
  past corrections in memory.

## 6. Analytical process summary

1. **Input** – any document or text blob.
2. **Normalization** – text extracted and cleaned.
3. **Entity extraction** – hybrid method yields candidate entities.
4. **Validation** – low‑confidence entities filtered out.
5. **Relationship extraction** – primitive pairwise relationships added.
6. **Memory proposal creation** – every validated entity becomes a
   pending memory entry.
7. **Reasoning & Truthing** – cognitive service evaluates claims against
   issue trees; approved claims join memory.
8. **Further analysis** – semantic, contradiction, violation, heuristic
   checks may run on memory or directly on document content.
9. **Indexing** – approved memory entries are vectorized; graph nodes
   added to knowledge graph.
10. **User review** – experts inspect proposals via GUI tabs, approve or
    reject, and optionally re‑run pipelines with modified parameters.

Each of these steps can be considered a pipeline stage; the framework
supports combining them in arbitrary sequences based on the task.

---

This document should serve as the definitive reference for developers
and architects working on the legal entity extraction and analytic
workflow.  It articulates both existing code behavior and theoretical
extensions, and suggests how components can be tied together to form
rich, auditable pipelines.
## Implementation Update (2026-02-21)
- Planner/Judge runtime, fail-closed persistence gate, and provenance readback routes are implemented and test-covered.
- Hybrid extraction backends are implemented with deterministic merge/dedup/validation behavior.
- Cross-service provenance enforcement has been expanded to organization proposals, knowledge curated writes, memory claim-grade proposals, analysis-version writes, and heuristic promotion.
- Learning paths are now persisted in DB-backed storage (`aedis_learning_paths`, `aedis_learning_path_steps`) with migration `0004_learning_path_storage`.
- Jurisdiction handling has been centralized through `services/jurisdiction_service.py` and integrated into knowledge/memory write paths.
