"""
Model Capability Registry for local model assets.

Scans the local models directory and produces a capability-driven registry
that the GUI can use to explain what each model can do in this application.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ModelSpec:
    """Static model metadata used to build runtime registry entries."""

    folder: str
    display_name: str
    category: str
    capabilities: tuple[str, ...]
    app_uses: tuple[str, ...]
    strategic_plays: tuple[str, ...]
    required_markers: tuple[str, ...]
    optional_markers: tuple[str, ...] = ()


MODEL_SPECS: tuple[ModelSpec, ...] = (
    ModelSpec(
        folder="all-minilm-L6-v2",
        display_name="MiniLM-L6",
        category="Embedding",
        capabilities=(
            "Fast local sentence embeddings",
            "Semantic clustering for theme discovery",
            "Cross-document similarity search",
        ),
        app_uses=(
            "Semantic Analysis -> Strategic Clustering",
            "Embedding Operations -> Generate Embeddings / Similarity Search",
        ),
        strategic_plays=(
            "Auto-label cluster themes for knowledge graph prep",
            "Find recurring legal-pattern vectors across cases",
        ),
        required_markers=("config.json",),
        optional_markers=("model.safetensors", "pytorch_model.bin"),
    ),
    ModelSpec(
        folder="nomic-embed-text",
        display_name="Nomic v1.5",
        category="Embedding",
        capabilities=(
            "High-fidelity long-text embeddings",
            "Robust clustering center vectors",
            "High-quality retrieval signal",
        ),
        app_uses=(
            "Embedding Operations -> Nomic v1.5 (High-Fidelity)",
            "Semantic Analysis -> Pattern Finder strategy",
        ),
        strategic_plays=(
            "Use cluster centers as search probes across document sets",
            "Prioritize anomaly candidates via vector distance",
        ),
        required_markers=("config.json",),
        optional_markers=("model.safetensors", "pytorch_model.bin"),
    ),
    ModelSpec(
        folder="gliner_zero_shot",
        display_name="GLiNER Zero-Shot",
        category="Entity Extraction",
        capabilities=(
            "Open-vocabulary entity extraction",
            "Flexible label-driven discovery",
            "Exploratory ontology expansion",
        ),
        app_uses=(
            "Entity Extraction -> GLiNER",
            "Entity Extraction -> Auto fallback path",
        ),
        strategic_plays=(
            "Probe unknown label spaces before ontology promotion",
            "Feed accepted entities into memory curation workflows",
        ),
        required_markers=("config.json",),
        optional_markers=("model.safetensors", "pytorch_model.bin"),
    ),
    ModelSpec(
        folder="bart-large-NER",
        display_name="BART Large NER",
        category="Entity Extraction",
        capabilities=(
            "Transformer-based named entity extraction",
            "Cross-validation source for extraction quality",
        ),
        app_uses=("Entity Extraction -> HF NER backend path",),
        strategic_plays=(
            "Use as secondary extractor for disagreement checks",
        ),
        required_markers=("config.json",),
        optional_markers=("model.safetensors", "pytorch_model.bin"),
    ),
    ModelSpec(
        folder="led-base-16384",
        display_name="LED Long Summarizer",
        category="Summarization",
        capabilities=(
            "Long-context summarization",
            "Large transcript compression",
        ),
        app_uses=("Semantic Analysis -> Summarization for long documents",),
        strategic_plays=(
            "Produce executive brief before deep extraction and clustering",
        ),
        required_markers=("config.json",),
        optional_markers=("model.safetensors", "pytorch_model.bin"),
    ),
    ModelSpec(
        folder="nli-deberta-v3-base",
        display_name="NLI DeBERTa v3",
        category="Verification",
        capabilities=(
            "Claim-evidence support/contradiction checks",
            "Evidence quality filtering",
        ),
        app_uses=("Judge/verification pipelines (backend integration)",),
        strategic_plays=(
            "Promote only supported claims into high-confidence memory",
        ),
        required_markers=("config.json",),
        optional_markers=("model.safetensors", "pytorch_model.bin"),
    ),
    ModelSpec(
        folder="rebel-large",
        display_name="REBEL Large",
        category="Relation Extraction",
        capabilities=(
            "Subject-relation-object extraction",
            "Graph relationship suggestion",
        ),
        app_uses=("Knowledge graph relationship extraction workflows",),
        strategic_plays=(
            "Run post-entity extraction to attach predicate edges",
        ),
        required_markers=("config.json",),
        optional_markers=("model.safetensors", "pytorch_model.bin"),
    ),
)


class ModelCapabilityRegistry:
    """Capability registry generated from local model folders."""

    def __init__(self, models_dir: str | Path = "models") -> None:
        self.models_dir = Path(models_dir)

    def build(self) -> dict:
        """Build registry payload for GUI consumption."""
        registry_items: list[dict] = []
        for spec in MODEL_SPECS:
            model_path = self.models_dir / spec.folder
            exists = model_path.exists() and model_path.is_dir()
            required_ok = self._has_markers(model_path, spec.required_markers)
            weight_ok = self._has_markers(
                model_path,
                tuple(spec.optional_markers) if spec.optional_markers else (),
            )
            status = self._status(exists, required_ok, weight_ok)

            registry_items.append(
                {
                    "id": spec.folder,
                    "display_name": spec.display_name,
                    "category": spec.category,
                    "path": str(model_path),
                    "exists": exists,
                    "status": status,
                    "capabilities": list(spec.capabilities),
                    "app_uses": list(spec.app_uses),
                    "strategic_plays": list(spec.strategic_plays),
                    "required_markers": list(spec.required_markers),
                    "optional_markers": list(spec.optional_markers),
                }
            )

        present_count = sum(1 for item in registry_items if item["exists"])
        ready_count = sum(1 for item in registry_items if item["status"] == "ready")
        return {
            "models_dir": str(self.models_dir.resolve()),
            "summary": {
                "total_cataloged": len(registry_items),
                "present": present_count,
                "ready": ready_count,
                "degraded_or_missing": len(registry_items) - ready_count,
            },
            "items": registry_items,
        }

    @staticmethod
    def _has_markers(model_path: Path, markers: tuple[str, ...]) -> bool:
        if not markers:
            return True
        if not model_path.exists():
            return False
        return any((model_path / marker).exists() for marker in markers)

    @staticmethod
    def _status(exists: bool, required_ok: bool, weight_ok: bool) -> str:
        if not exists:
            return "missing"
        if required_ok and weight_ok:
            return "ready"
        if required_ok:
            return "degraded"
        return "invalid"
