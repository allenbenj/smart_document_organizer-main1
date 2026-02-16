# Pipelines Module

## Purpose
This folder contains the **pipeline orchestration engine** for the Smart Document Organizer. It handles business logic processing workflows.

## ⚠️ Not to be confused with `routes/`
- **pipelines/** = Processing pipeline engine (business logic layer)
- **routes/** = API endpoints (web layer)
- **routes/pipeline.py** = API endpoint that *uses* this pipelines module

## Contents

### `runner.py` (322 lines)
The main pipeline orchestration engine with:
- Step execution and DAG (Directed Acyclic Graph) support
- Conditional logic for pipeline branching
- Error handling and recovery
- Pipeline state management

### `presets.py` (90+ lines)
Predefined pipeline configurations:
- Document processing pipelines
- Analysis workflows
- Extraction pipelines

### `__init__.py`
Package initialization file

## Usage
```python
from pipelines.runner import Pipeline, Step, run_pipeline
from pipelines.presets import get_presets

# Run a predefined pipeline
pipeline = get_presets("document_analysis")
result = await run_pipeline(pipeline)
```

## Dependencies
Used by:
- `routes/pipeline.py` - API endpoint for pipeline execution
- `gui.tabs.pipelines_tab` - GUI interface for pipeline management

---
**Last Updated**: 2026-02-16  
**Status**: Production-ready ✅
