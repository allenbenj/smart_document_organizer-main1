from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from mem_db.memory.memory_interfaces import MemoryRecord, MemoryType
from mem_db.memory.unified_memory_manager import UnifiedMemoryManager


@pytest.mark.asyncio
async def test_memory_code_links_bidirectional_lookup(tmp_path: Path) -> None:
    db_path = tmp_path / "unified_memory_links.db"
    manager = UnifiedMemoryManager(db_path=db_path, vector_backend="faiss")
    assert await manager.initialize() is True

    record = MemoryRecord(
        record_id=str(uuid.uuid4()),
        namespace="tests",
        key="linkable-memory",
        content="This memory is linked to a file path",
        memory_type=MemoryType.ANALYSIS,
    )
    memory_record_id = await manager.store(record)
    file_path = "gui/tabs/data_explorer_tab.py"

    linked = await manager.link_memory_to_file(
        memory_record_id=memory_record_id,
        file_path=file_path,
        relation_type="supports",
        confidence=0.87,
        source="pytest",
    )
    assert linked is True

    memory_links = await manager.get_memories_for_file(file_path=file_path, limit=10)
    assert len(memory_links) == 1
    assert memory_links[0]["memory_record_id"] == memory_record_id
    assert memory_links[0]["relation_type"] == "supports"
    assert memory_links[0]["link_source"] == "pytest"

    file_links = await manager.get_files_for_memory(
        memory_record_id=memory_record_id, limit=10
    )
    assert len(file_links) == 1
    assert file_links[0]["file_path"] == file_path
    assert file_links[0]["relation_type"] == "supports"


@pytest.mark.asyncio
async def test_memory_code_links_upsert_and_unknown_record(tmp_path: Path) -> None:
    db_path = tmp_path / "unified_memory_links_upsert.db"
    manager = UnifiedMemoryManager(db_path=db_path, vector_backend="faiss")
    assert await manager.initialize() is True

    record = MemoryRecord(
        record_id=str(uuid.uuid4()),
        namespace="tests",
        key="upsert-memory",
        content="Edge table upsert check",
        memory_type=MemoryType.ANALYSIS,
    )
    memory_record_id = await manager.store(record)
    file_path = "routes/data_explorer.py"

    assert (
        await manager.link_memory_to_file(
            memory_record_id=memory_record_id,
            file_path=file_path,
            relation_type="references",
            confidence=0.40,
            source="seed",
        )
        is True
    )
    assert (
        await manager.link_memory_to_file(
            memory_record_id=memory_record_id,
            file_path=file_path,
            relation_type="references",
            confidence=0.95,
            source="updated",
        )
        is True
    )

    links = await manager.get_files_for_memory(memory_record_id=memory_record_id, limit=10)
    assert len(links) == 1
    assert links[0]["link_confidence"] == pytest.approx(0.95)
    assert links[0]["link_source"] == "updated"

    assert (
        await manager.link_memory_to_file(
            memory_record_id="missing-record-id",
            file_path=file_path,
        )
        is False
    )
