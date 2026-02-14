# Import Map (Tools)

- `import_map_detailed.json`: canonical detailed map with module edges and metadata.

Usage
- Use this file to tighten imports, detect cycles, and block imports from `_backup/`.
- Pair with CI to prevent accidental imports from backup or missing optional deps.
