# Startup Baseline (Systemic Hardening)

## Goal

A startup is considered **clean** when:

- No `ERROR` log lines during startup
- No unexpected `WARNING` log lines during startup
- Every expected router loads successfully
- Required production agents initialize
- Required memory service initializes
- `/api/startup/report` returns a complete structured report

## Current policy

- `STRICT_PRODUCTION_STARTUP=1`
- Required agents:
  - document_processor
  - entity_extractor
  - legal_reasoning
  - irac_analyzer

## Startup report source of truth

Use:

- `GET /api/startup/report`

Fields tracked:

- router load status (ok/failed)
- strict startup mode
- required/available/missing agents
- memory readiness
- optional dependency availability

## Warning allowlist (temporary)

These are currently tolerated but tracked until fixed:

1. `Failed to import pipeline router: No module named 'agents.orchestration.message_bus'`
2. `ChromaDB not available, vector search will be disabled.`
3. `Optional service unavailable` for enhanced vector/persistence services in core integration
4. Deprecated string-key lookups (`memory_manager`, `config_manager`, etc.)

## Fix order

1. Pipeline router dependency chain (`agents.orchestration.message_bus`)
2. Enhanced service registrations for vector/persistence
3. Replace deprecated string-key lookups with type-key lookups
4. Optional dependency packaging profile for document processing stack
5. Chroma/vector capability profile cleanup

## Acceptance criteria per change

- Run full startup
- Confirm `/api/startup/report` is complete
- Verify warning count decreases or remains expected by allowlist
- No regression in critical endpoints (`/api/health`, `/api/taskmaster/*`, `/api/organization/*`)
