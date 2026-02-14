# Organization Console (Standalone)

A lightweight review UI for organization proposals.

## Run

```bash
python tools/org_console/app.py
```

Open: <http://127.0.0.1:8010>

## What it does

- Refresh/list proposals by status
- Generate proposals (optionally scoped by root folder prefix)
- Approve / Reject / Edit+Approve
- Clear (reject) proposals in current status/root scope
- Dry-run apply / Real apply
- Bulk approve by confidence threshold
- Shows recent feedback/actions (when API endpoints are available)
- Shows startup diagnostics for administrators (real startup steps, service checks, env snapshot)
- Shows awareness monitor (uptime, alert level, failed/slow services, recent startup events)

## API dependency

This console proxies to:

- `http://127.0.0.1:8000/api/organization/*`
- `http://127.0.0.1:8000/api/startup/*`

If feedback/action/stats panels show "endpoint unavailable", restart the API so new routes are loaded:

- `GET /api/organization/stats`
- `GET /api/organization/feedback`
- `GET /api/organization/actions`

