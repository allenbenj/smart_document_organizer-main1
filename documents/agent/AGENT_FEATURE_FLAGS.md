# Agent Feature Flags & Config

Configure agent behavior via environment variables. Defaults favor auto-detection with safe fallbacks.

## Mode Selection
- `AGENTS_MODE`: `auto` | `production` | `fallback`
  - default: `auto` (use production if available, else fallback)

## Timeouts & Caching
- `AGENTS_DEFAULT_TIMEOUT_SECONDS`: default RPC timeout for analyses (float, default: 6)
- `AGENTS_CACHE_TTL_SECONDS`: TTL for per-agent caches (int seconds, default: 300)

## Per-Agent Toggles (optional)
- `AGENTS_ENABLE_LEGAL_REASONING`: `1` to enable/`0` to disable (default enabled if available)
- `AGENTS_ENABLE_ENTITY_EXTRACTOR`: `1`/`0`
- `AGENTS_ENABLE_IRAC`: `1`/`0`
- `AGENTS_ENABLE_TOULMIN`: `1`/`0`
- `AGENTS_ENABLE_SEMANTIC`: `1`/`0`
- `AGENTS_ENABLE_KG`: `1`/`0`

## Models (optional)
- `AGENTS_EMBED_MODEL`: default embedding model (e.g., `sentence-transformers/all-MiniLM-L6-v2`)
- `AGENTS_ZS_CLASSIFIER_MODEL`: transformers zero-shot model id
- `AGENTS_SPACY_MODEL`: spaCy model for NER if used
- `AGENTS_GLINER_MODEL`: GLiNER model id
- `AGENTS_SUMMARIZER_MODEL`: transformers summarization model id (e.g., `sshleifer/distilbart-cnn-12-6`)

## Notes
- GUI and routes do not require changes; flags are read inside agent managers.
- Per-request options (e.g., `timeout`) override defaults from env.
