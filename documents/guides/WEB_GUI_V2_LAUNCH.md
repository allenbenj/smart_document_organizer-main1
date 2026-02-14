# Web GUI v2 Launch (Phase C)

## Legacy Note
The existing PySide GUI remains available as **legacy fallback** during migration.
Do not remove it in this phase.

## Backend (FastAPI)
From repo root:

```bash
python3 Start.py
```

## Frontend (React + Vite)
From repo root:

```bash
cd frontend
npm install
npm run dev
```

Vite default: `http://127.0.0.1:5173`

## Optional build check
```bash
cd frontend
npm run build
```

## New additive v2 API routes
- `POST /api/workflow/jobs`
- `GET /api/workflow/jobs/{job_id}/status`
- `POST /api/workflow/jobs/{job_id}/steps/{step_name}/execute`
- `GET /api/workflow/jobs/{job_id}/results`

These are additive v2 routes and do not replace existing taskmaster/organization routes.

## Phase C smoke checks
From repo root:

```bash
pytest -q \
  tests/test_workflow_routes_v2.py \
  tests/test_org_console_static_and_proxy.py \
  tests/test_pyside_import_safety.py
```

Expected: all pass with PySide remaining a legacy fallback path.
