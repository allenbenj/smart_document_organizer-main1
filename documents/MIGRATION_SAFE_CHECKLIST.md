# Migration-Safe Checklist

Use this checklist for every schema change.

## Before writing migration

- [ ] Define exact backward/forward compatibility expectation.
- [ ] Confirm target SQLite version assumptions.
- [ ] Write idempotent DDL where possible (`IF NOT EXISTS`, guarded operations).
- [ ] Identify data backfill needs and rollback expectations.
- [ ] Estimate lock duration and runtime impact.

## Implementing migration

- [ ] Assign incremental `VERSION` and stable `NAME`.
- [ ] Keep migration deterministic and side-effect free outside DB.
- [ ] Avoid long transactions; batch updates when safe.
- [ ] Fail loudly in strict mode; capture error details in `schema_migrations`.
- [ ] Ensure migration can run on fresh DB and legacy DB.

## Validation

- [ ] Run `python -m mem_db.migrations.runner status` before/after.
- [ ] Run `python -m mem_db.migrations.runner migrate --strict` in CI-like env.
- [ ] Verify startup migration report endpoint reflects expected status.
- [ ] Verify app boot behavior in both strict/non-strict modes.

## Policy knobs

- `STRICT_DB_MIGRATIONS=1` (default): fail-fast on migration errors.
- `STRICT_DB_MIGRATIONS=0`: record failures and continue startup (degraded).
- CLI equivalents: `--strict` / `--no-strict`.
