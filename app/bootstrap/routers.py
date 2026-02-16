from __future__ import annotations

import importlib
from typing import Any, Callable, Sequence


def include_default_routers(
    app: Any,
    protected_dependencies: Sequence[Any],
    logger: Any,
    record_router: Callable[[str, str, bool, str | None], None],
) -> None:
    router_specs = [
        ("agents", "routes.agents", "router", "/api", True),
        ("documents", "routes.documents", "router", "/api/documents", True),
        ("analysis", "routes.analysis", "router", "/api/analysis", True),
        ("extraction", "routes.extraction", "router", "/api/extraction", True),
        ("reasoning", "routes.reasoning", "router", "/api/reasoning", True),
        ("embedding", "routes.embedding", "router", "/api/embeddings", True),
        ("classification", "routes.classification", "router", "/api/classification", True),
        ("search", "routes.search", "router", "/api", True),
        ("tags", "routes.tags", "router", "/api", True),
        ("health", "routes.health", "router", "/api", False),
        ("knowledge", "routes.knowledge", "router", "/api", True),
        ("pipeline", "routes.pipeline", "router", "/api", True),  # This mounts at /api/pipeline/presets
        ("vector_store", "routes.vector_store", "router", "/api/vector_store", True),
        ("vector_store_alias", "routes.vector_store", "router", "/api", True),
        ("files", "routes.files", "router", "/api/files", True),
        ("taskmaster", "routes.taskmaster", "router", "/api/taskmaster", True),
        ("personas", "routes.personas", "router", "/api", True),
        ("ontology", "routes.ontology", "router", "/api/ontology", True),
        ("ontology_alias", "routes.ontology", "router", "/api", True),
        ("experts", "routes.experts", "router", "/api", True),
        ("organization", "routes.organization", "router", "/api", True),
        ("workflow", "routes.workflow", "router", "/api", True),
    ]

    for name, module_name, attr_name, prefix, needs_auth in router_specs:
        try:
            mod = importlib.import_module(module_name)
            router = getattr(mod, attr_name)
            kwargs: dict[str, Any] = {"prefix": prefix}
            if needs_auth:
                kwargs["dependencies"] = list(protected_dependencies)
            app.include_router(router, **kwargs)
            logger.info("Included %s router", name)
            record_router(name, prefix, True)
        except Exception as e:
            logger.warning("Failed to import/include %s router: %s", name, e)
            record_router(name, prefix, False, str(e))
