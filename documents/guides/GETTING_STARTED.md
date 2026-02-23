# Getting Started with Smart Document Organizer

This document replaces earlier installation and quick‑start guides. It describes the **current** workflow for cloning, configuring, and launching the system.  Legacy guides have been archived in `documents/archive/guides/`.

## Prerequisites

- Python 3.10+ (3.11 recommended)
- Git (to clone the repo)
- A command‑line shell (PowerShell/WSL/Terminal)

Optional but useful:
- Windows if you plan to run the GUI
- WSL2 or native Linux for backend development

## Clone and install

```bash
# clone repository
cd /some/path
git clone https://github.com/allenbenj/smart_document_organizer-main.git
cd smart_document_organizer-main

# create a virtual environment and activate it
python -m venv .venv
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# or WSL/Linux/macOS:
source .venv/bin/activate

# install Python dependencies
pip install -r requirements.txt
```

## Configure environment

Copy and edit the example file:

```bash
cp .env.example .env           # use `copy` on Windows
```

Open `.env` and adjust settings as needed.  At minimum you may want to set
`ENV=development` (default) and enable/disable agents via the
`AGENTS_ENABLE_*` flags.  `STRICT_PRODUCTION_STARTUP` and
`REQUIRED_PRODUCTION_AGENTS` control startup guardrails for production
deployments.

> **Note:** GUI‑specific options (`GUI_THEME`, `GUI_MAX_WORKERS`) can be
> ignored when running in backend/headless mode.

## Launching the system

### Backend only (headless / CI / WSL)

```bash
python Start.py              # mode auto‑detects headless and behaves like --backend
# or explicitly
python Start.py --backend
```

This starts the FastAPI server on `http://127.0.0.1:8000` by default.  The
`/api/startup/report` endpoint provides a structured health/startup report
(useful for automated checks).

### GUI (Windows)

In a separate PowerShell window:

```powershell
python gui\gui_dashboard.py  # requires a Windows desktop environment
```

The GUI will attempt to connect to the backend at
`http://127.0.0.1:8000`.  If running the backend and GUI on different machines
or ports, use `GUI_BACKEND_URL` in `.env`.

> If you run `python Start.py` inside WSL without X11 support, the program
automatically defaults to backend mode and skips the Qt GUI.

## Validating startup

A clean startup has:

- no `ERROR` logs and minimal `WARNING` messages
- every router loaded successfully
- required agents listed in `/api/startup/report`

You can run the existing test suite to exercise startup logic:

```bash
pytest tests/test_start_lifespan.py::test_backend_startup
```

## Troubleshooting

- **Qt errors in WSL/CI** – use `--backend` or run `Start.py` from a native
  linux shell; GUI launch is disabled automatically in headless contexts.
- **Missing dependencies** – inspect logs; many optional features log a
  message like "module X not installed" and degrade gracefully.
- **Network requests during startup** – ensure offline by setting
  `OFFLINE_STARTUP=1` in `.env` (added per startup hardening work).

## Additional resources

- Startup hardening and diagnostics: see
  `documents/status/startup-baseline.md` and
  `documents/agent/startup_fix_order.md`.
- For advanced configuration, see other guides in this folder (e.g. GUI
  demonstration, workflow webhooks).

---

> Legacy guides:
> - `documents/archive/guides/INSTALLATION_GUIDE_legacy.md`
> - `documents/archive/guides/QUICK_START_GUIDE_legacy.md`

