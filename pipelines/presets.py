from __future__ import annotations

from typing import Any, Dict, List  # noqa: E402


def get_presets() -> List[Dict[str, Any]]:
    """Return available pipeline presets."""
    return [
        {
            "name": "Legal Research & Drafting",
            "description": "Process document, extract entities (hybrid), build Lex prompt, analyze, classify, index, and prepare proposals.",
            "steps": [
                {"name": "process_document"},
                {
                    "name": "extract_entities",
                    "options": {"extractor": "hybrid", "min_conf": 0.5},
                },
                {
                    "name": "expert_prompt",
                    "options": {
                        "agent_name": "Lex _Legal Researcher_",
                        "task_type": "research_memo",
                    },
                },
                {"name": "semantic"},
                {"name": "contradictions"},
                {"name": "violations"},
                {"name": "classify", "options": {"quality_gate": True}},
                {"name": "embed_index"},
                {"name": "kg_propose", "options": {"kind": "entity", "data": {}}},
            ],
            "context": {"path": "<fill path to document>"},
        },
        {
            "name": "Collaborative Analysis",
            "description": "Semantic topics inform entity extraction; then contradictions/violations and optional indexing.",
            "steps": [
                {"name": "process_document"},
                {"name": "semantic"},
                {"name": "entity_focus"},
                {"name": "contradictions"},
                {"name": "violations"},
                {"name": "embed_index"},
            ],
            "context": {"path": "<fill path to document>"},
        },
        {
            "name": "Citations & Precedents (DAG)",
            "description": "Demonstrates ids/depends_on/when/retries/timeout with citations → precedents flow.",
            "steps": [
                {"name": "process_document", "options": {"id": "s_process"}},
                {
                    "name": "semantic",
                    "options": {
                        "id": "s_sem",
                        "depends_on": ["s_process"],
                        "timeout": 8,
                    },
                },
                {
                    "name": "extract_entities",
                    "options": {
                        "id": "s_ents",
                        "depends_on": ["s_process"],
                        "when": "semantic",
                    },
                },
                {
                    "name": "citations",
                    "options": {
                        "id": "s_cits",
                        "depends_on": ["s_process"],
                        "retries": 1,
                        "retry_delay": 0.25,
                    },
                },
                {
                    "name": "precedents",
                    "options": {
                        "id": "s_prec",
                        "depends_on": ["s_cits"],
                        "timeout": 10,
                    },
                },
                {
                    "name": "embed_index",
                    "options": {
                        "id": "s_index",
                        "depends_on": ["s_sem"],
                        "when": "semantic.key_phrases",
                    },
                },
            ],
            "context": {"path": "<fill path to document>"},
        },
    ]
