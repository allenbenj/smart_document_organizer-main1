import sys
import types

import pytest

from routes.files import file_entities


class _FakeDB:
    def __init__(self):
        self.questions = []
        self.upserts = []

    def get_indexed_file(self, file_id):
        return {
            "id": file_id,
            "display_name": "Case summary for Alice",
            "normalized_path": "/tmp/Contract_notes.txt",
            "metadata_json": {"preview": "Judge reviewed contract terms."},
        }

    def knowledge_upsert(self, **kwargs):
        self.upserts.append(kwargs)
        return 1

    def knowledge_has_term(self, term, category=None):
        return False

    def knowledge_add_question(self, **kwargs):
        self.questions.append(kwargs)
        return len(self.questions)


@pytest.mark.asyncio
async def test_file_entities_only_returns_ontology_labels_and_flags_unknown_candidates(monkeypatch):
    # Inject a lightweight fake ontology module at the import path used by routes.files
    mod = types.ModuleType("agents.entities.ontology.ontology")

    class _Val:
        def __init__(self, label):
            self.label = label

    class _Entity:
        def __init__(self, label):
            self.value = _Val(label)

    mod.LegalEntityType = [_Entity("Judge"), _Entity("Contract")]

    monkeypatch.setitem(sys.modules, "agents", types.ModuleType("agents"))
    monkeypatch.setitem(sys.modules, "agents.entities", types.ModuleType("agents.entities"))
    monkeypatch.setitem(sys.modules, "agents.entities.ontology", types.ModuleType("agents.entities.ontology"))
    monkeypatch.setitem(sys.modules, "agents.entities.ontology.ontology", mod)

    db = _FakeDB()
    out = await file_entities(file_id=7, db=db)

    assert out["success"] is True
    assert {e["label"] for e in out["entities"]} == {"Judge", "Contract"}
    assert all(e.get("ontology_id") for e in out["entities"])
    # persistence evidence: ontology-linked upserts are written through manager knowledge API
    assert len(db.upserts) >= 2
    assert all(u.get("ontology_entity_id") for u in db.upserts)

    # Alice is title-cased and not in ontology labels -> should be proposed as unknown candidate
    assert "Alice" in out["unknown_candidates"]
    assert db.questions, "Expected unknown candidate question generation"
