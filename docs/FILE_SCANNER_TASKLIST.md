# File Scanner & Analytics Foundation Task List

**Status symbols:**
- `[x]` complete
- `[ ]` not started / waiting
- `[~]` in progress

## Objectives
- Build a strong pre-process scanner that converts raw files into normalized, queryable assets.
- Ensure ontology-aligned entity extraction and enrichment for downstream analytics.
- Support legal/forensic workflows with reliability, auditability, and incremental performance.

---

## Phase 0 — Immediate Patch / Gaps (**MVP NOW**)

- [x] **Markdown support end-to-end**
  - [x] Include `.md` in default extension allowlist for indexing/watchers.
  - [x] Validate `.md` as text-readable in quick-validity checks.
  - [x] Ensure markdown parser preserves heading structure and code block boundaries.
  - [x] Add markdown-specific chunking strategy (heading-aware segmentation).

- [x] **Ontology-enforced entities (critical)**
  - [x] Route all entity extraction through existing app ontology service/tables (no ad-hoc labels).
  - [x] Add ontology term normalization map (synonyms -> canonical concept IDs).
  - [x] Reject/flag entities not in ontology unless explicitly allowed as candidate terms.
  - [x] Persist entity->ontology link confidence and provenance (rule/model/parser source).

---

## Phase 1 — Baseline Scanner (Core Value) (**MVP NOW**)

### 1) Discovery & Traversal
- [x] Recursive scanner over local + mounted paths (WSL `/mnt/*`, network shares).
- [ ] Include/exclude filters:
  - [x] paths/globs (substring-style include/exclude path filters)
  - [x] extensions/MIME classes (extension filter + detected MIME field)
  - [x] size ranges
  - [x] date windows (modified-after timestamp filter)
- [ ] Symlink policy (skip/follow configurable) + loop detection.
- [x] Permission error handling and continuation policy.
- [ ] Depth control and scan budget limits (max files, max runtime).

### 2) File Metadata Extraction
- [ ] Extract per-file metadata:
  - [x] normalized full path
  - [x] file name + extension
  - [x] size
  - [x] MIME (magic bytes first, extension fallback)
  - [x] timestamps (modified + scanner check + accessed/ctime/birthtime captured in metadata/API output)
  - [x] owner/permissions
  - [x] FS attributes
- [x] Compute SHA-256 hash (content integrity + dedup key).
- [x] Store scanner/runtime provenance (host, scanner version, parser version).

### 3) Content Extraction
- [ ] Robust parsers by type:
  - [x] PDF (validation + processing path in production manager)
  - [x] DOCX (validation + processing path in production manager)
  - [x] TXT
  - [x] Markdown (`.md`)
  - [x] XLSX/CSV (indexed/supported extensions; deep table extraction pending)
- [x] Preserve structure where possible (markdown headings + chunk titles).
- [ ] OCR fallback for image-based PDFs and images.
- [ ] Save extraction confidence/completeness metrics.

### 4) Type Detection & Basic Classification
- [x] Classify file classes via extension + MIME fields (document-focused baseline).
- [ ] Flag potential evidence-oriented classes (photos, reports, spreadsheets, instructions).

### 5) Deduplication
- [x] Exact duplicate detection via SHA-256 (hash available for grouping).
- [x] Near-duplicate placeholder (text similarity hash) for phase 2.
- [x] Store canonical record + duplicate relationships.
  - [x] Add `file_duplicate_relationships` table for canonical↔duplicate mappings.
  - [x] Rebuild exact duplicate relationships from SHA groups (canonical = lowest `files_index.id`).
  - [x] Add duplicate relationship query endpoint (`GET /api/files/{file_id}/duplicates`).

### 6) Incremental & Resumable Scanning
- [x] Maintain scan manifest/checkpoint state.
- [x] Reprocess only new/changed/deleted files (hash+mtime strategy).
- [x] Resume after interruption with deterministic continuation.

### 7) Error Handling / Logging / Audit
- [x] Structured scan events (started/progress/completed/failed/cancelled via TaskMaster).
- [x] Error taxonomy baseline (damaged/unreadable/missing + taskmaster error codes).
- [x] Progress stats + resumable checkpoints baseline (manifest + progress counters; ETA pending).

---

## Phase 2 — Advanced Enrichment (High Leverage) (**PHASE 2**)

### 8) Deep Metadata
- [x] EXIF extraction for images.
  - [x] Add parser-level EXIF/image-dimension extraction with graceful fallback when optional image libs are unavailable.
  - [x] Capture camera make/model, capture timestamp, orientation, GPS raw payload, and bounded raw tag map in scanner metadata.
- [x] PDF properties (producer, author, title, page count).
  - [x] Add parser-level PDF property extraction (`fitz`) with `metadata_available`/`metadata_error` status fields.
- [x] Office metadata (author, revision, template).
  - [x] Add OpenXML `docProps/core.xml` + `docProps/app.xml` extraction for DOCX/XLSX/PPTX (author/title/subject/revision/template/application/pages/words).
- [ ] Media tags for audio/video.

### 9) Rule-Based Tagging
- [x] Configurable keyword/regex rules.
  - [x] Add `services/file_tagging_rules.py` rule engine with configurable rules path (`FILE_TAG_RULES_PATH`) and default JSON rules file.
  - [x] Add checked-in default rule file (`config/file_tagging_rules.json`) for easy user overrides.
- [x] Domain seed rules:
  - [x] Delta-9 / HHC / CBD / THC
  - [x] "lab report"
  - [x] case numbers
  - [x] dates and names
- [x] Track rule hit source span (offsets/snippets).
  - [x] Persist per-hit provenance (`source`, `start`, `end`, `match_text`, `snippet`) in indexed file metadata.

### 10) Advanced Content Processing
- [x] Semantic chunking for RAG.
  - [x] Persist per-file semantic chunks in `file_content_chunks` with chunk metadata.
  - [x] Add chunk retrieval endpoint (`GET /api/files/{file_id}/chunks`).
- [x] Table extraction and normalized table storage.
  - [x] Add baseline table persistence model `file_extracted_tables`.
  - [x] Add CSV/TSV placeholder extraction plumbing + retrieval endpoint (`GET /api/files/{file_id}/tables`).
- [ ] OCR quality scoring + retry pipeline for low-confidence scans.

### 11) AI Semantic Layer
- [x] Embeddings per chunk (configurable model provider).
  - [x] Add embedding persistence model `file_chunk_embeddings` (JSON vector baseline).
  - [x] Add deterministic local embedding baseline (`local-hash-v1`) for offline stack compatibility.
- [ ] Vector index integration (existing app vector stack).
- [~] Similarity search + clustering support.
  - [x] Add cosine similarity endpoint over persisted embeddings (`POST /api/files/semantic/search`).
  - [ ] Clustering support (deferred).

### 12) Entity Extraction + Ontology Linking
- [ ] Entity extraction pipeline for names/dates/locations/orgs/domain terms.
- [ ] Enforce mapping to ontology IDs.
- [ ] Store unresolved entities as proposals for ontology curation queue.
- [ ] Cross-file entity linking graph.

### 13) Sensitive Content Detection (**DEFERRED**)
- [ ] Domain legal thresholds and warning patterns (e.g., 0.3% THC references).
- [ ] Compliance flags and redaction candidates.

### 14) Relationships & Timelines
- [~] Parent-child and reference links.
- [x] Duplicate and near-duplicate linkage.
  - [x] Exact duplicate linkage persisted and queryable.
  - [x] Near-duplicate linkage reserved via relationship type placeholder (`near`).
- [~] Timeline reconstruction from file timestamps + embedded dates.
- [~] Basic anomaly flags (unexpected mtime bursts, oversized outliers).

### 15) Multi-Modal Support
- [ ] Thumbnails for images.
- [ ] Metadata-first handling for large binaries/video/audio.
- [ ] Preview extract snippets for UI.

### 16) Data Quality & Normalization
- [x] Encoding normalization.
- [x] Text cleanup/deartifacting.
- [x] Quality score per extraction (completeness/confidence/OCR quality).

---

## Phase 3 — Schema Evolution & Query Performance (**PHASE 2 / 3**)

### 17) Database Model (target)
- [~] `files` core metadata (path/hash/timestamps/mime/owner/status/tags)
- [~] `content` extracted text + chunks + OCR outputs
  - [x] Added `file_content_chunks` baseline (OCR output pending).
- [~] `embeddings` vector rows per chunk
  - [x] Added `file_chunk_embeddings` baseline persistence.
- [ ] `entities` normalized entities + ontology IDs + confidence
- [~] `relationships` duplicates/references/parent-child links
- [x] `scan_history` runs, checkpoints, errors, metrics

### 18) Indexes/Views
- [ ] Indexes on path hash, mtime, status, mime, ext.
- [ ] Full-text indexes on extracted content/chunks.
- [ ] Vector index on embeddings (existing stack).
- [ ] Materialized summary views:
  - [ ] timeline view
  - [ ] keyword/entity summary
  - [ ] damaged/missing/stale dashboard

---

## Phase 4 — Operations, Security, Scale

### 19) Orchestration
- [ ] Queue-based workers for parsing/OCR/embedding.
- [ ] Parallelism controls and backpressure.
- [ ] Retry policy and dead-letter tracking.


### 21) Extensibility
- [x] Pluggable parser registry.
  - [x] Add scanner parser contract (`supports`, `quick_validate`, `extract_index_metadata`).
  - [x] Add ordered parser registry + default parser bootstrap.
  - [x] Wire index/refresh flows to registry with legacy fallback behavior.
  - [x] Move markdown chunk metadata extraction to markdown parser contract.
  - [x] Move PDF/DOCX/text quick validity checks to parser contracts.
- [ ] Domain plug-ins (e.g., lab report parser templates).
- [ ] Versioned extraction contracts.

### 22) Testing & Validation
- [~] Golden dataset across legal/forensic-like samples.
- [~] Accuracy tests for extraction/OCR/entities.
- [x] Dedup correctness tests.
- [~] Performance tests on large hierarchies.
- [x] Unit scaffold: incremental manifest skip behavior (`tests/test_file_index_incremental.py`) validates unchanged-file skip and changed-file reindex.
- [x] Unit scaffold: TaskMaster due-schedule execution (`tests/test_taskmaster_schedule_due.py`) validates due run dispatch and `last_run_at/next_run_at` update.
- [x] Unit scaffold: ontology-enforced entity baseline (`tests/test_file_entities_ontology_baseline.py`) validates ontology-only entity output + unknown-candidate questioning.
- [x] Unit/integration scaffold: scanner acceptance pack (`tests/test_file_scanner_acceptance.py`) validates markdown chunk/search path, cancellation+resume incremental behavior, missing/damaged/stale API projection, exact dedup relationships, recursive traversal, and file-id based workflows.

---

## API Tasks (Concrete)

- [x] `POST /api/files/watch` add/update watched directories.
- [x] `GET /api/files/watch` list watch config.
- [x] `POST /api/files/index` ad-hoc index run.
- [x] `POST /api/files/refresh` stale/missing/damaged validation pass.
- [x] `GET /api/files` rich list with sorting/filtering/keyword ranking.
- [x] `GET /api/files/:id/entities` ontology-linked entities.
- [x] `GET /api/files/:id/timeline-events` extracted timeline facts.
- [x] `GET /api/files/:id/quality` extraction quality details.
- [x] `POST /api/files/:id/semantic/enrich` baseline semantic chunk+embedding+table enrichment.
- [x] `GET /api/files/:id/chunks` persisted semantic chunks.
- [x] `GET /api/files/:id/tables` persisted extracted table records (placeholder-capable).
- [x] `POST /api/files/semantic/search` similarity query over persisted chunk embeddings.
- [x] `GET /api/files/:id/relationships` inferred parent/sibling/reference links.
- [x] `GET /api/files/:id/anomalies` baseline anomaly flags (mtime burst, size outlier).
- [x] `GET /api/files/:id/normalization` text normalization and deartifacting metrics.

### TaskMaster API & Orchestration (**MVP NOW / PHASE 2**) 

- [x] `POST /api/taskmaster/runs/file-pipeline` orchestrate index/refresh/watch-refresh runs.
- [x] `GET /api/taskmaster/runs` list orchestrator runs.
- [x] `GET /api/taskmaster/runs/:run_id` run detail with child tasks.
- [x] `GET /api/taskmaster/runs/:run_id/events` event stream per run.
- [x] Persist orchestration state in DB (`taskmaster_runs`, `taskmaster_tasks`, `taskmaster_events`).
- [x] Add live in-task progress updates for large scans (periodic progress events).
- [x] Add run cancellation endpoint (`POST /api/taskmaster/runs/:run_id/cancel`).
- [x] Add retry endpoint for failed tasks/runs (`POST /api/taskmaster/runs/:run_id/retry`).
- [x] Add run filtering (status/type/date) and pagination.
- [x] Add event severity/category taxonomy and standardized error codes.
- [x] Add lightweight dashboard endpoint for current active runs + KPIs.
- [x] Wire `/api/files/index` and `/api/files/refresh` routes to internally execute through TaskMaster by default.
- [x] Add cron-backed scheduled TaskMaster runs for watched directories.
- [x] Add native TaskMaster schedule APIs (`/api/taskmaster/schedules`, `/api/taskmaster/schedules/run-due`) as cron integration foundation.
- [x] Add internal scheduler loop to automatically execute due schedules.
- [x] Add run date filtering (`started_after`, `started_before`) to runs list API.
- [x] Add event filtering (`level`, `event_type`) to run events API.
- [x] Add cooperative cancellation checks inside long-running index/refresh tasks.

### Manager Knowledge Repository (**MVP NOW**) 

- [x] Add manager knowledge table for user-validated context (`manager_knowledge`).
- [x] Add manager questions table for unresolved terms (`manager_questions`).
- [x] Add API to upsert/list knowledge items (`/api/knowledge/manager/items`).
- [x] Add API to create/list/answer manager questions (`/api/knowledge/manager/questions`).
- [x] Generate candidate knowledge questions from scanned/indexed content during TaskMaster runs.
- [x] Add explicit approve/reject workflow for proposed knowledge terms.
- [x] Link manager knowledge terms directly to ontology entity IDs when available.
- [x] Add export endpoint (JSON/CSV) for model portability and user review.
- [x] Expand manager knowledge schema with aliases/attributes/relations/sources/verification fields.
- [x] Add framework-focused query endpoint (`/api/knowledge/manager/frameworks`).
- [x] Add system-issue-focused query endpoint (`/api/knowledge/manager/issues`).
- [x] Extend schema with framework lifecycle fields (`framework_type`, `components_json`, `is_canonical`, etc.).
- [x] Extend schema with system issue lifecycle fields (`issue_category`, `severity`, `fix_status`, `resolution_evidence`, etc.).

### Swappable Personas & Skills (**MVP NOW / PHASE 2**) 

- [x] Add `manager_personas` table (role, prompt, rules, settings, active flag).
- [x] Add `manager_skills` table and persona-skill mapping table.
- [x] Add APIs to create/list personas and skills (`/api/personas`, `/api/personas/skills`).
- [x] Add API to attach skills to personas (`/api/personas/attach-skill`).
- [x] Add persona resolve endpoint (`/api/personas/resolve`).
- [x] Activate persona automatically in TaskMaster runs by mode/content type.
- [x] Emit persona activation events in TaskMaster.
- [x] Add default seeded personas (Indexer/Enricher/Analyst/Verifier/Organizer/Questioner/Summarizer).
- [x] Enforce tool/skill allowlists per persona in execution layer.
- [x] Add user-facing persona switch command per run/batch.

---

## Implementation Subtasks Completed (Visibility Log)

- [x] Progress snapshot (2026-02-12 07:10 CST): 50.0% complete (95/190), excluding deferred security section.

- [x] Added `files_index` table and indexing/list/query methods.
- [x] Added `watched_directories` table and watch management endpoints.
- [x] Added quick validity checks (`pdf` signature, `docx` zip, text readability).
- [x] Added MIME detection via `python-magic` fallback to `mimetypes`.
- [x] Added SHA-256 hashing in indexing + refresh pipelines.
- [x] Added markdown heading/code-block aware chunk metadata extraction.
- [x] Added UI-friendly file fields (`file_size_human`, `mtime_iso`, `is_stale`, quick preview).
- [x] Added TaskMaster core tables (`taskmaster_runs`, `taskmaster_tasks`, `taskmaster_events`).
- [x] Added TaskMaster endpoints for run/create/list/detail/events/cancel/retry/dashboard.
- [x] Added TaskMaster progress events and cancellation checks.
- [x] Added TaskMaster schedule tables/methods/endpoints and due-run execution.
- [x] Added internal scheduler loop at app startup to run due TaskMaster schedules.
- [x] Added scan manifest table and incremental skip-on-unchanged logic.
- [x] Added manager knowledge tables for entities/questions with user verification flow.
- [x] Added manager knowledge export (JSON/CSV).
- [x] Added framework/system-issue schema extensions (severity, fix lifecycle, evidence, etc.).
- [x] Added framework query endpoint (`/api/knowledge/manager/frameworks`).
- [x] Added system issue query endpoint (`/api/knowledge/manager/issues`).
- [x] Added ontology-link endpoint for manager knowledge items.
- [x] Added persona/skills tables and APIs.
- [x] Added default persona/skill seeding endpoint.
- [x] Added persona auto-resolution and activation events in TaskMaster.
- [x] Added persona override support per TaskMaster run (`persona_name`).
- [x] Added persona skill allowlist/mismatch checks by run mode.
- [x] Added file-level quality/entities/timeline endpoints.
- [x] Added ontology-enforced entity output with unknown-candidate question generation.
- [x] Added richer filesystem metadata capture in indexing/refresh (UID/GID, mode/permissions, file attrs, accessed/changed/modified times, and created time when available).
- [x] Added filesystem metadata projection in `/api/files` output and quality coverage flags for owner/permissions/fs-attrs.
- [x] Added file timeline enrichment from scanner metadata (`created`/`mtime`/`atime`/`ctime` + scanner check timestamp).
- [x] Added permission-denied handling with continuation + `permission_errors` counter in index runs.
- [x] Added pluggable scanner parser registry scaffold (`services/file_parsers.py`) and routed file index/refresh validation + parser metadata extraction through parser contracts with safe legacy fallbacks.
- [x] Added `file_duplicate_relationships` table + indexes for canonical/duplicate mapping.
- [x] Added DB reconciliation method to materialize exact duplicate relationships from SHA-256 groups.
- [x] Added `/api/files/{file_id}/duplicates` endpoint with near-duplicate placeholder response.
- [x] Added deep metadata parser enrichment for PDF (`pdf.*`), Office OpenXML (`office.*`), and image EXIF (`exif.*`) in scanner metadata.
- [x] Added configurable rule-based scanner tagging (`services/file_tagging_rules.py`) with default seed config (`config/file_tagging_rules.json`) and provenance spans (`start/end/snippet/source`).
- [x] Added rule-tag retrieval endpoint (`GET /api/files/{file_id}/rule-tags`) and quality surfacing (`has_exif`, `has_pdf_props`, `has_office_props`, `rule_tag_hit_count`).
- [x] Added enrichment-focused tests (`tests/test_file_enrichment_phase2.py`) for Office metadata extraction, rule-hit spans, and scanner integration.
- [x] Added semantic persistence tables (`file_content_chunks`, `file_extracted_tables`, `file_chunk_embeddings`) with supporting indexes.
- [x] Added baseline semantic enrichment service (`services/semantic_file_service.py`) for chunking, table placeholder extraction, and deterministic local embeddings.
- [x] Added file semantic APIs for enrich/chunks/tables and embedding similarity search.
- [x] Added `/api/files/{file_id}/relationships` endpoint with inferred parent-child/sibling/reference links.
- [x] Enriched `/api/files/{file_id}/timeline-events` with embedded date extraction and confidence annotations.
- [x] Added `/api/files/{file_id}/anomalies` endpoint with baseline oversized-outlier + mtime-burst flags.
- [x] Added text normalization/deartifacting metadata capture during index/refresh (encoding, replacement chars, control-char ratio, normalized preview).
- [x] Added `/api/files/{file_id}/normalization` endpoint and extended `/api/files/{file_id}/quality` with normalization/completeness/overall scoring fields.

## Acceptance Criteria (MVP)

- [x] Markdown files are discoverable, parsed, chunked, and searchable.
- [x] Each indexed file has SHA-256, MIME, timestamps, and status.
- [x] Scanner supports incremental reruns and resume.
- [x] Damaged/missing/stale are detectable and surfaced in API/UI.
- [x] Entity extraction persists ontology-linked entities (canonical IDs).
- [x] Main app workflows consume `file_id` from indexed DB, not raw user paths.

---

## Validation Evidence (2026-02-12)

- Command: `python3 -m py_compile services/file_index_service.py`
  - Result: pass (fixed unterminated string literal in normalization control-char handling).
- Command: `python3 -m py_compile routes/files.py`
  - Result: pass (fixed unterminated string literal in timeline/reference text join paths).
- Command: `pytest -q tests/test_file_scanner_acceptance.py tests/test_file_index_incremental.py tests/test_file_entities_ontology_baseline.py tests/test_taskmaster_schedule_due.py`
  - Result: **9 passed**, 0 failed.
  - Notes: warning-only output from third-party deps (Swig/Torch deprecations), no scanner/taskmaster test failures.

## Notes
- Keep runtime app lightweight by shifting expensive extraction/embedding/OCR into pre-processing jobs.
- Treat ontology as source-of-truth for entities to avoid taxonomy drift.
- Prioritize observability (scan metrics + quality metrics) from day one.

---

## Change Discipline
- [x] Every newly implemented scanner/taskmaster/persona/knowledge task must be reflected in this file.
- [x] If implementation introduces new scope, add a new checklist item immediately (do not leave implicit).
- [x] Mark completed items with `[x]` in the same commit/session where code is shipped.
