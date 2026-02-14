# Web GUI v2 Launch (Kickoff)

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

These are scaffold endpoints and do not replace existing taskmaster/organization routes.
