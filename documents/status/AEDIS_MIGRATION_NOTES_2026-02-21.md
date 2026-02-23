# AEDIS Migration Notes - 2026-02-21

## Added Migration
- Version: `0004`
- Module: `mem_db/migrations/versions/0004_learning_path_storage.py`
- Purpose: persistent learning-path storage for path headers and steps.

## Schema Changes
- New table: `aedis_learning_paths`
  - `path_id` (PK), `user_id`, `objective_id`, `status`, `ontology_version`, `heuristic_snapshot_json`, timestamps.
- New table: `aedis_learning_path_steps`
  - Composite PK (`path_id`, `step_id`), instruction payload, heuristic/evidence JSON, difficulty, completion flag, step order.
- New indexes:
  - `idx_learning_path_steps_path_order`
  - `idx_learning_path_steps_path_completed`

## Runtime Integration
- Added repository: `mem_db/repositories/learning_path_repository.py`
- Added DB manager wrappers:
  - `learning_path_upsert`
  - `learning_path_get`
  - `learning_path_update_step_completion`
  - `learning_path_list_recommended_steps`
- `services/learning_path_service.py` now uses DB-backed persistence.

## Rollback Guidance
- If rollback is required:
1. Stop application writes to learning-path routes.
2. Drop `aedis_learning_path_steps`.
3. Drop `aedis_learning_paths`.
4. Remove migration `0004` from runner list only if coordinating with a controlled schema reset process.

## Validation Evidence
- `tests/test_learning_path_persistence.py`
- `tests/test_learning_path_service.py`
- `tests/test_learning_path_runtime_routes.py`
