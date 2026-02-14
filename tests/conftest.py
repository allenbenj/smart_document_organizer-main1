"""
Pytest configuration for Smart Document Organizer tests.
"""

import sys
from pathlib import Path  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

# Ensure the project root is in sys.path so we can import modules directly
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Import the FastAPI app directly from Start.py
from Start import app  # noqa: E402

# Optional: isolate DB to a temp path by swapping managers in routers
try:
    import routes.documents as documents  # noqa: E402
    import routes.search as search  # noqa: E402
    import routes.tags as tags  # noqa: E402
    from mem_db.database import DatabaseManager  # noqa: E402
except Exception as e:  # noqa: F841
    DatabaseManager = None  # type: ignore
    documents = search = tags = None  # type: ignore


@pytest.fixture(scope="session")
def client(tmp_path_factory):
    """FastAPI TestClient with isolated temporary DB when possible."""
    if DatabaseManager and documents and search and tags:
        tmpdir = tmp_path_factory.mktemp("db")
        db_path = tmpdir / "documents.db"
        test_db = DatabaseManager(str(db_path))
        documents.db_manager = test_db
        search.db_manager = test_db
        try:
            # tags router may expose a different getter; patch if available
            tags.db_manager = test_db  # type: ignore[attr-defined]
        except Exception:
            pass

    return TestClient(app)
