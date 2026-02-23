# AEDIS Endpoint Contract Alignment - 2026-02-21

## Purpose
Reconcile documented endpoints with implemented backend routes and preserve compatibility for existing callers.

## Canonical + Alias Mapping

- Organization apply:
  - Canonical: `POST /api/organization/apply`
  - Alias (compat): `POST /api/organization/proposals/apply`
  - Reason: existing workflow/proxy callers refer to the proposals-scoped apply path.

## Caller Guidance
- New callers should use canonical paths.
- Existing callers on alias paths remain supported for backward compatibility.

## Verification
- Route contract test updated:
  - `tests/test_organization_route_contracts.py::test_organization_apply_alias_contract`
