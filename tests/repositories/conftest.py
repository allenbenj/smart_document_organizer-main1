from __future__ import annotations

from pathlib import Path

import pytest

from mem_db.database import DatabaseManager


@pytest.fixture()
def temp_db_manager(tmp_path: Path) -> DatabaseManager:
    db_path = tmp_path / "repo-tests.db"
    return DatabaseManager(str(db_path))
