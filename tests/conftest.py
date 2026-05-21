import pytest
import sqlite3
from pathlib import Path

@pytest.fixture
def test_db_path(tmp_path):
    db_path = tmp_path / "test_hotspot.db"
    yield str(db_path)

@pytest.fixture
def test_db(test_db_path):
    from app.database import init_db
    conn = sqlite3.connect(test_db_path)
    conn.row_factory = sqlite3.Row
    init_db(conn)
    yield conn
    conn.close()
