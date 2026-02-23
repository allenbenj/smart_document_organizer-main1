# AEDIS Release Notes - 2026-02-21

## Closed Gaps
- Added fail-closed provenance enforcement across required write paths.
- Added knowledge curated-write provenance gates and tests.
- Added memory claim-grade provenance requirements and tests.
- Added analysis-version provenance gate tests.
- Added heuristic lifecycle semantic alignment (candidate mapping, explicit transitions, transition logs).
- Added DB-backed learning-path persistence with migration `0004_learning_path_storage`.
- Added jurisdiction resolver centralization and consistency tests.
- Added endpoint contract cleanup alias: `POST /api/organization/proposals/apply`.

## New Artifacts
- `documents/status/AEDIS_PROGRAM_BASELINE_2026-02-21.md`
- `documents/status/AEDIS_IMPLEMENTATION_DEPENDENCY_MAP_2026-02-21.md`
- `documents/status/AEDIS_TEST_HARNESS_PLAN_2026-02-21.md`
- `documents/status/AEDIS_EXTRACTION_BACKEND_ARCH_DECISION_2026-02-21.md`
- `documents/status/AEDIS_ENDPOINT_CONTRACT_ALIGNMENT_2026-02-21.md`
- `documents/status/AEDIS_MANUAL_E2E_RUN_2026-02-21.md`

## Known Remaining Risks
- Repository-wide lint baseline is not clean (`ruff check .` reports extensive pre-existing issues outside critical-gap changes).
- Interactive GUI manual verification still required for full `8.3` closure.
