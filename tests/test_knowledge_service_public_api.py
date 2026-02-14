from pathlib import Path
import re


def test_knowledge_service_avoids_manager_private_fields() -> None:
    text = Path("services/knowledge_service.py").read_text(encoding="utf-8")
    patterns = [
        r"\._entities\b",
        r"\._relationships\b",
        r"\._networkx_graph\b",
        r"\._stats\b",
        r'getattr\([^)]*,\s*"_entities"',
        r'getattr\([^)]*,\s*"_relationships"',
        r'getattr\([^)]*,\s*"_networkx_graph"',
        r'getattr\([^)]*,\s*"_stats"',
    ]
    offenders = [p for p in patterns if re.search(p, text)]
    assert not offenders, (
        "KnowledgeService should use public manager APIs only; found private access patterns: "
        + ", ".join(offenders)
    )
