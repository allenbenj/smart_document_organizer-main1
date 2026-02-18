## Agent Setup and Installation Guide

This file defines a practical, install-ready baseline for an autonomous coding
agent in this repository.

### 1. Purpose

The agent should:
- produce correct, testable, reviewable changes;
- keep diffs small and scoped;
- avoid fabricated facts, APIs, routes, or test results;
- explicitly label uncertainty and assumptions.

### 2. Prerequisites

- Python `3.11+`
- `pip`
- access to repository root

Optional:
- virtual environment (`venv`)
- `ruff`, `mypy`, `pytest`

### 3. Install

From repository root:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

If packaging/editable mode is supported:

```bash
pip install -e .
```

### 4. Run

Start app:

```bash
python Start.py
```

Alternative:

```bash
uvicorn Start:app --reload --host 0.0.0.0 --port 8000
```

### 5. Verify Installation

Health:

```bash
curl -sS http://127.0.0.1:8000/api/health
```

Optional deeper checks:

```bash
curl -sS http://127.0.0.1:8000/api/health/details
curl -sS http://127.0.0.1:8000/api/metrics
```

Test baseline:

```bash
pytest -q
```

### 6. Key Environment Variables

- `ENV` (default: `development`)
- `API_KEY` (requires `X-API-Key` header if set)
- `AGENTS_ENABLE_REGISTRY`
- `AGENTS_ENABLE_LEGAL_REASONING`
- `AGENTS_ENABLE_ENTITY_EXTRACTOR`
- `AGENTS_ENABLE_IRAC`
- `AGENTS_ENABLE_TOULMIN`
- `AGENTS_CACHE_TTL_SECONDS` (default: `300`)
- `VECTOR_DIMENSION` (default: `384`)
- `MEMORY_APPROVAL_THRESHOLD` (default: `0.7`)

### 7. Operating Rules

- Facts must be grounded in files, routes, tests, or logs.
- Inferences must be labeled.
- Keep implementation minimal; no unrelated refactors.
- For non-trivial work, define a short plan first.
- For debugging, use: reproduce, isolate, fix, regression-test.
- On every task, check relevant available skills first and use them when they
  match the request.
- If a required skill is missing, add/install it before proceeding when
  feasible, then continue with the task.

### 8. Quality Gates

Run before handoff when relevant:

```bash
ruff check .
ruff format .
mypy .
pytest -q
```

### 9. Quick Troubleshooting

- Server fails to start:
  - verify venv activation and dependency install.
- Health endpoint unavailable:
  - confirm server is running on `127.0.0.1:8000`.
- Tests fail after dependency install:
  - rerun with `pytest -q -x` and inspect first failure.

### 10. Definition of Done

A change is ready when:
- behavior is correct for stated scope;
- tests relevant to touched code pass;
- no fabricated claims are present in output;
- assumptions and uncertainties are explicit.
- needed skills were checked and applied (or explicitly noted as missing).
