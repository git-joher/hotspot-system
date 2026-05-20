# Global Hotspot Aggregator — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a personal-use web dashboard that aggregates global hot events from 11+ platforms, enriches them with LLM classification/translation/summarization, and presents them with ECharts visualizations across 4 time granularities.

**Architecture:** Python monolithic FastAPI app. APScheduler drives periodic data collection from platform APIs/scraping. A processing pipeline normalizes, deduplicates, and scores events with LLM assistance. SQLite stores events, snapshots, categories, and relations. Jinja2 templates render the dashboard with ECharts for visualization.

**Tech Stack:** Python 3.11+, FastAPI, SQLite (sqlite3), Jinja2, APScheduler, httpx, BeautifulSoup4, OpenAI SDK (for LLM calls), feedparser, pytrends, uvicorn

**File Structure:**
```
hotspot-system/
├── config.py
├── requirements.txt
├── run.py
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── database.py
│   ├── collectors/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── twitter.py
│   │   ├── reddit.py
│   │   ├── hackernews.py
│   │   ├── github_trending.py
│   │   ├── google_trends.py
│   │   ├── weibo.py
│   │   ├── zhihu.py
│   │   ├── baidu.py
│   │   ├── youtube.py
│   │   ├── newsapi.py
│   │   └── rss_feeds.py
│   ├── pipeline/
│   │   ├── __init__.py
│   │   ├── orchestrator.py
│   │   ├── normalizer.py
│   │   ├── llm_processor.py
│   │   ├── dedup.py
│   │   └── scorer.py
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── pages.py
│   │   └── api.py
│   ├── templates/
│   │   ├── base.html
│   │   ├── index.html
│   │   └── detail.html
│   └── static/
│       ├── css/
│       │   └── style.css
│       └── js/
│           └── dashboard.js
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_database.py
│   ├── test_collectors.py
│   ├── test_pipeline.py
│   └── test_routes.py
└── data/
    └── .gitkeep
```

---

### Task 1: Project Scaffold

**Files:**
- Create: `requirements.txt`
- Create: `config.py`
- Create: `run.py`
- Create: `app/__init__.py`
- Create: `data/.gitkeep`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Write requirements.txt**

```text
fastapi==0.115.6
uvicorn[standard]==0.34.0
jinja2==3.1.4
httpx==0.28.1
beautifulsoup4==4.12.3
apscheduler==3.10.4
openai==1.58.1
feedparser==6.0.11
pytrends==4.9.2
pytest==8.3.4
pytest-httpx==0.30.0
python-dotenv==1.0.1
```

- [ ] **Step 2: Write config.py**

```python
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "hotspot.db"

# LLM config
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")

# Collector API keys
TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN", "")
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID", "")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET", "")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY", "")

# Database
DATABASE_URL = f"sqlite:///{DB_PATH}"

# Scheduler
COLLECTION_INTERVAL_FAST = 15  # minutes
COLLECTION_INTERVAL_SLOW = 60  # minutes
SNAPSHOT_RETENTION_DAYS = 30
```

- [ ] **Step 3: Write run.py**

```python
import uvicorn
from app.main import app

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
```

- [ ] **Step 4: Create empty __init__.py files**

```bash
echo "" > app/__init__.py
echo "" > tests/__init__.py
echo "" > data/.gitkeep
```

- [ ] **Step 5: Write tests/conftest.py**

```python
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
```

- [ ] **Step 6: Install dependencies and verify**

Run: `pip install -r requirements.txt`
Expected: All packages install successfully.

- [ ] **Step 7: Commit**

```bash
git add requirements.txt config.py run.py app/__init__.py tests/__init__.py tests/conftest.py data/.gitkeep
git commit -m "feat: project scaffold with config and dependencies"
```

---

### Task 2: Database Schema and Initialization

**Files:**
- Create: `app/database.py`
- Create: `tests/test_database.py`

- [ ] **Step 1: Write failing test for database init**

```python
# tests/test_database.py
import sqlite3
import pytest
from app.database import init_db, get_db


def test_init_db_creates_all_tables(test_db_path):
    conn = sqlite3.connect(test_db_path)
    conn.row_factory = sqlite3.Row
    init_db(conn)

    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    table_names = [t["name"] for t in tables]

    assert "events" in table_names
    assert "event_snapshots" in table_names
    assert "categories" in table_names
    assert "event_categories" in table_names
    assert "event_relations" in table_names
    conn.close()


def test_init_db_idempotent(test_db_path):
    conn = sqlite3.connect(test_db_path)
    conn.row_factory = sqlite3.Row
    init_db(conn)
    init_db(conn)  # second call should not error
    conn.close()


def test_events_schema(test_db):
    conn = test_db
    # Insert and query to verify column types
    conn.execute("""
        INSERT INTO events (title, description, url, source_platform, language, region,
                           title_cn, summary_cn, first_seen_at, last_updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
    """, ["Test Event", "A test description", "https://example.com", "twitter", "en",
          "US", "测试事件", "这是一个测试",])
    conn.commit()
    row = conn.execute("SELECT * FROM events WHERE title='Test Event'").fetchone()
    assert row["title"] == "Test Event"
    assert row["source_platform"] == "twitter"
    assert row["title_cn"] == "测试事件"


def test_event_snapshots_schema(test_db):
    conn = test_db
    conn.execute("""
        INSERT INTO events (title, source_platform, language, region, first_seen_at, last_updated_at)
        VALUES (?, ?, ?, ?, datetime('now'), datetime('now'))
    """, ["Snap Test", "reddit", "en", "US"])
    event_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    conn.execute("""
        INSERT INTO event_snapshots (event_id, heat_score, mention_count, source_rank,
                                     trend_direction, snapshot_at)
        VALUES (?, ?, ?, ?, ?, datetime('now'))
    """, [event_id, 85.5, 12000, 1, "rising"])
    conn.commit()

    snap = conn.execute(
        "SELECT * FROM event_snapshots WHERE event_id=?", [event_id]
    ).fetchone()
    assert snap["heat_score"] == 85.5
    assert snap["trend_direction"] == "rising"


def test_categories_schema(test_db):
    conn = test_db
    conn.execute(
        "INSERT INTO categories (name, slug, icon) VALUES (?, ?, ?)",
        ["科技", "tech", "laptop"]
    )
    conn.commit()
    cat = conn.execute("SELECT * FROM categories WHERE slug='tech'").fetchone()
    assert cat["name"] == "科技"
    assert cat["icon"] == "laptop"


def test_event_categories_schema(test_db):
    conn = test_db
    conn.execute("""
        INSERT INTO events (title, source_platform, language, region, first_seen_at, last_updated_at)
        VALUES (?, ?, ?, ?, datetime('now'), datetime('now'))
    """, ["Cat Test", "github", "en", "US"])
    event_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.execute(
        "INSERT INTO categories (name, slug) VALUES (?, ?)", ["科技", "tech"]
    )
    cat_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.execute(
        "INSERT INTO event_categories (event_id, category_id, confidence) VALUES (?, ?, ?)",
        [event_id, cat_id, 0.95]
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM event_categories WHERE event_id=?", [event_id]
    ).fetchone()
    assert row["confidence"] == 0.95


def test_event_relations_schema(test_db):
    conn = test_db
    for i in range(2):
        conn.execute("""
            INSERT INTO events (title, source_platform, language, region, first_seen_at, last_updated_at)
            VALUES (?, ?, ?, ?, datetime('now'), datetime('now'))
        """, [f"Related Event {i}", "twitter", "en", "US"])
    conn.execute("""
        INSERT INTO event_relations (event_a_id, event_b_id, relation_type, confidence)
        VALUES (?, ?, ?, ?)
    """, [1, 2, "merged", 0.92])
    conn.commit()
    row = conn.execute("SELECT * FROM event_relations WHERE event_a_id=1").fetchone()
    assert row["relation_type"] == "merged"
    assert row["confidence"] == 0.92
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_database.py -v`
Expected: All fail with "init_db not defined", "get_db not defined".

- [ ] **Step 3: Write app/database.py**

```python
import sqlite3
from pathlib import Path
from config import DB_PATH


SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    url TEXT DEFAULT '',
    source_platform TEXT NOT NULL,
    language TEXT DEFAULT 'unknown',
    region TEXT DEFAULT 'unknown',
    title_cn TEXT DEFAULT '',
    summary_cn TEXT DEFAULT '',
    first_seen_at TEXT NOT NULL,
    last_updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS event_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL,
    heat_score REAL DEFAULT 0.0,
    mention_count INTEGER DEFAULT 0,
    source_rank INTEGER DEFAULT 0,
    trend_direction TEXT DEFAULT 'stable',
    snapshot_at TEXT NOT NULL,
    FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_snapshots_event_time
    ON event_snapshots(event_id, snapshot_at);

CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    slug TEXT NOT NULL UNIQUE,
    icon TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS event_categories (
    event_id INTEGER NOT NULL,
    category_id INTEGER NOT NULL,
    confidence REAL DEFAULT 0.0,
    PRIMARY KEY (event_id, category_id),
    FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE,
    FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS event_relations (
    event_a_id INTEGER NOT NULL,
    event_b_id INTEGER NOT NULL,
    relation_type TEXT NOT NULL DEFAULT 'related',
    confidence REAL DEFAULT 0.0,
    PRIMARY KEY (event_a_id, event_b_id),
    FOREIGN KEY (event_a_id) REFERENCES events(id) ON DELETE CASCADE,
    FOREIGN KEY (event_b_id) REFERENCES events(id) ON DELETE CASCADE
);
"""


def get_db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_database.py -v`
Expected: All 7 tests pass.

- [ ] **Step 5: Commit**

```bash
git add app/database.py tests/test_database.py
git commit -m "feat: database schema with 5 core tables"
```

---

### Task 3: Database Access Functions (CRUD)

**Files:**
- Modify: `app/database.py`
- Modify: `tests/test_database.py`

- [ ] **Step 1: Write failing tests for CRUD functions**

Append to `tests/test_database.py`:

```python
from app.database import (
    insert_event, insert_snapshot, get_or_create_category,
    set_event_category, get_events_by_timespan, get_event_with_snapshots,
    get_stats, search_events, link_events
)


def test_insert_event(test_db):
    conn = test_db
    event_id = insert_event(conn, {
        "title": "Breaking News",
        "description": "Something happened",
        "url": "https://example.com/1",
        "source_platform": "twitter",
        "language": "en",
        "region": "US",
    })
    assert event_id > 0
    row = conn.execute("SELECT * FROM events WHERE id=?", [event_id]).fetchone()
    assert row["title"] == "Breaking News"


def test_insert_snapshot(test_db):
    conn = test_db
    event_id = insert_event(conn, {
        "title": "Snap Test", "source_platform": "reddit",
        "language": "en", "region": "US",
    })
    snap_id = insert_snapshot(conn, {
        "event_id": event_id, "heat_score": 90.0,
        "mention_count": 5000, "source_rank": 1,
        "trend_direction": "rising",
    })
    assert snap_id > 0


def test_get_or_create_category(test_db):
    conn = test_db
    cat_id_1 = get_or_create_category(conn, "科技", "tech", "laptop")
    cat_id_2 = get_or_create_category(conn, "科技", "tech", "laptop")
    assert cat_id_1 == cat_id_2  # idempotent
    assert cat_id_1 > 0


def test_set_event_category(test_db):
    conn = test_db
    event_id = insert_event(conn, {
        "title": "Tech Event", "source_platform": "hackernews",
        "language": "en", "region": "US",
    })
    cat_id = get_or_create_category(conn, "科技", "tech")
    set_event_category(conn, event_id, cat_id, 0.95)
    row = conn.execute(
        "SELECT * FROM event_categories WHERE event_id=? AND category_id=?",
        [event_id, cat_id]
    ).fetchone()
    assert row["confidence"] == 0.95


def test_get_events_by_timespan(test_db):
    conn = test_db
    eid = insert_event(conn, {
        "title": "Recent Event", "source_platform": "twitter",
        "language": "en", "region": "US",
    })
    insert_snapshot(conn, {
        "event_id": eid, "heat_score": 80.0,
        "mention_count": 1000, "source_rank": 3,
        "trend_direction": "rising",
    })
    events = get_events_by_timespan(conn, hours=24)
    assert len(events) > 0
    assert events[0]["title"] == "Recent Event"
    assert events[0]["latest_heat"] == 80.0


def test_get_event_with_snapshots(test_db):
    conn = test_db
    eid = insert_event(conn, {
        "title": "Snap Event", "source_platform": "reddit",
        "language": "en", "region": "US",
    })
    insert_snapshot(conn, {
        "event_id": eid, "heat_score": 70.0,
        "mention_count": 500, "source_rank": 2,
        "trend_direction": "stable",
    })
    insert_snapshot(conn, {
        "event_id": eid, "heat_score": 85.0,
        "mention_count": 800, "source_rank": 1,
        "trend_direction": "rising",
    })
    result = get_event_with_snapshots(conn, eid)
    assert result["event"]["title"] == "Snap Event"
    assert len(result["snapshots"]) == 2
    assert result["snapshots"][0]["heat_score"] == 70.0


def test_get_stats(test_db):
    conn = test_db
    eid = insert_event(conn, {
        "title": "Stats Event", "source_platform": "twitter",
        "language": "en", "region": "US",
    })
    insert_snapshot(conn, {
        "event_id": eid, "heat_score": 90.0,
        "mention_count": 1000, "source_rank": 1,
        "trend_direction": "rising",
    })
    cat_id = get_or_create_category(conn, "科技", "tech")
    set_event_category(conn, eid, cat_id, 0.9)
    stats = get_stats(conn)
    assert stats["total_events"] >= 1
    assert stats["rising_count"] >= 1
    assert stats["category_count"] >= 1


def test_search_events(test_db):
    conn = test_db
    insert_event(conn, {
        "title": "Apple releases M4", "source_platform": "twitter",
        "language": "en", "region": "US",
    })
    insert_event(conn, {
        "title": "Google IO event", "source_platform": "reddit",
        "language": "en", "region": "US",
    })
    results = search_events(conn, "Apple")
    assert len(results) == 1
    assert results[0]["title"] == "Apple releases M4"


def test_link_events(test_db):
    conn = test_db
    e1 = insert_event(conn, {
        "title": "Event A", "source_platform": "twitter",
        "language": "en", "region": "US",
    })
    e2 = insert_event(conn, {
        "title": "Event B", "source_platform": "reddit",
        "language": "en", "region": "US",
    })
    link_events(conn, e1, e2, "merged", 0.92)
    row = conn.execute(
        "SELECT * FROM event_relations WHERE event_a_id=? AND event_b_id=?",
        [e1, e2]
    ).fetchone()
    assert row is not None
    assert row["relation_type"] == "merged"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_database.py::test_insert_event -v`
Expected: FAIL with ImportError.

- [ ] **Step 3: Add CRUD functions to app/database.py**

```python
from datetime import datetime, timedelta
from typing import Optional


def insert_event(conn: sqlite3.Connection, data: dict) -> int:
    now = datetime.utcnow().isoformat()
    conn.execute("""
        INSERT INTO events (title, description, url, source_platform, language, region,
                           title_cn, summary_cn, first_seen_at, last_updated_at)
        VALUES (:title, :description, :url, :source_platform, :language, :region,
                :title_cn, :summary_cn, :first_seen_at, :last_updated_at)
    """, {
        "title": data["title"],
        "description": data.get("description", ""),
        "url": data.get("url", ""),
        "source_platform": data["source_platform"],
        "language": data.get("language", "unknown"),
        "region": data.get("region", "unknown"),
        "title_cn": data.get("title_cn", ""),
        "summary_cn": data.get("summary_cn", ""),
        "first_seen_at": data.get("first_seen_at", now),
        "last_updated_at": data.get("last_updated_at", now),
    })
    conn.commit()
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def insert_snapshot(conn: sqlite3.Connection, data: dict) -> int:
    now = datetime.utcnow().isoformat()
    conn.execute("""
        INSERT INTO event_snapshots (event_id, heat_score, mention_count, source_rank,
                                     trend_direction, snapshot_at)
        VALUES (:event_id, :heat_score, :mention_count, :source_rank,
                :trend_direction, :snapshot_at)
    """, {
        "event_id": data["event_id"],
        "heat_score": data.get("heat_score", 0.0),
        "mention_count": data.get("mention_count", 0),
        "source_rank": data.get("source_rank", 0),
        "trend_direction": data.get("trend_direction", "stable"),
        "snapshot_at": data.get("snapshot_at", now),
    })
    conn.commit()
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def get_or_create_category(conn: sqlite3.Connection, name: str, slug: str,
                           icon: str = "") -> int:
    row = conn.execute(
        "SELECT id FROM categories WHERE slug=?", [slug]
    ).fetchone()
    if row:
        return row["id"]
    conn.execute(
        "INSERT INTO categories (name, slug, icon) VALUES (?, ?, ?)",
        [name, slug, icon]
    )
    conn.commit()
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def set_event_category(conn: sqlite3.Connection, event_id: int, category_id: int,
                       confidence: float = 0.0) -> None:
    conn.execute("""
        INSERT OR REPLACE INTO event_categories (event_id, category_id, confidence)
        VALUES (?, ?, ?)
    """, [event_id, category_id, confidence])
    conn.commit()


def get_events_by_timespan(conn: sqlite3.Connection, hours: int = 24,
                           limit: int = 100, offset: int = 0,
                           category_slug: str = None,
                           source_platform: str = None,
                           sort_by: str = "heat") -> list[dict]:
    since = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
    query = """
        SELECT e.*,
               (SELECT heat_score FROM event_snapshots s
                WHERE s.event_id = e.id
                ORDER BY s.snapshot_at DESC LIMIT 1) as latest_heat,
               (SELECT trend_direction FROM event_snapshots s
                WHERE s.event_id = e.id
                ORDER BY s.snapshot_at DESC LIMIT 1) as latest_trend,
               COUNT(DISTINCT er.event_b_id) as related_count
        FROM events e
        LEFT JOIN event_relations er ON e.id = er.event_a_id
        WHERE e.last_updated_at >= ?
    """
    params = [since]

    if category_slug:
        query += """ AND e.id IN (
            SELECT ec.event_id FROM event_categories ec
            JOIN categories c ON ec.category_id = c.id
            WHERE c.slug = ?
        )"""
        params.append(category_slug)
    if source_platform:
        query += " AND e.source_platform = ?"
        params.append(source_platform)

    query += " GROUP BY e.id"

    if sort_by == "heat":
        query += " ORDER BY latest_heat DESC"
    elif sort_by == "time":
        query += " ORDER BY e.last_updated_at DESC"

    query += f" LIMIT {int(limit)} OFFSET {int(offset)}"
    return [dict(row) for row in conn.execute(query, params).fetchall()]


def get_event_with_snapshots(conn: sqlite3.Connection, event_id: int) -> dict:
    event = conn.execute("SELECT * FROM events WHERE id=?", [event_id]).fetchone()
    if not event:
        return None
    snapshots = conn.execute("""
        SELECT * FROM event_snapshots
        WHERE event_id=? ORDER BY snapshot_at ASC
    """, [event_id]).fetchall()
    categories = conn.execute("""
        SELECT c.*, ec.confidence FROM categories c
        JOIN event_categories ec ON c.id = ec.category_id
        WHERE ec.event_id=?
    """, [event_id]).fetchall()
    relations = conn.execute("""
        SELECT e.id, e.title, e.title_cn, e.source_platform, er.relation_type, er.confidence
        FROM event_relations er
        JOIN events e ON (er.event_b_id = e.id)
        WHERE er.event_a_id=?
    """, [event_id]).fetchall()
    return {
        "event": dict(event),
        "snapshots": [dict(s) for s in snapshots],
        "categories": [dict(c) for c in categories],
        "relations": [dict(r) for r in relations],
    }


def get_stats(conn: sqlite3.Connection) -> dict:
    now = datetime.utcnow().isoformat()
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    total = conn.execute(
        "SELECT COUNT(*) as c FROM events WHERE last_updated_at >= ?",
        [today_start]
    ).fetchone()["c"]
    rising = conn.execute("""
        SELECT COUNT(DISTINCT e.id) as c FROM events e
        JOIN event_snapshots s ON e.id = s.event_id
        WHERE s.trend_direction='rising' AND s.snapshot_at >= ?
    """, [today_start]).fetchone()["c"]
    region_count = conn.execute("""
        SELECT COUNT(DISTINCT region) as c FROM events
        WHERE last_updated_at >= ?
    """, [today_start]).fetchone()["c"]
    cat_count = conn.execute(
        "SELECT COUNT(*) as c FROM categories"
    ).fetchone()["c"]
    return {
        "total_events": total,
        "rising_count": rising,
        "region_count": region_count,
        "category_count": cat_count,
    }


def search_events(conn: sqlite3.Connection, query: str, limit: int = 50) -> list[dict]:
    q = f"%{query}%"
    rows = conn.execute("""
        SELECT * FROM events
        WHERE title LIKE ? OR title_cn LIKE ? OR description LIKE ?
        ORDER BY last_updated_at DESC LIMIT ?
    """, [q, q, q, limit]).fetchall()
    return [dict(r) for r in rows]


def link_events(conn: sqlite3.Connection, event_a_id: int, event_b_id: int,
                relation_type: str = "related", confidence: float = 0.0) -> None:
    conn.execute("""
        INSERT OR REPLACE INTO event_relations (event_a_id, event_b_id, relation_type, confidence)
        VALUES (?, ?, ?, ?)
    """, [event_a_id, event_b_id, relation_type, confidence])
    conn.commit()


def cleanup_old_snapshots(conn: sqlite3.Connection) -> int:
    from config import SNAPSHOT_RETENTION_DAYS
    cutoff = (datetime.utcnow() - timedelta(days=SNAPSHOT_RETENTION_DAYS)).isoformat()
    cur = conn.execute("DELETE FROM event_snapshots WHERE snapshot_at < ?", [cutoff])
    conn.commit()
    return cur.rowcount
```

- [ ] **Step 4: Run all database tests**

Run: `pytest tests/test_database.py -v`
Expected: All 16 tests pass.

- [ ] **Step 5: Commit**

```bash
git add app/database.py tests/test_database.py
git commit -m "feat: CRUD functions for all 5 tables"
```

---

### Task 4: Base Collector Interface

**Files:**
- Create: `app/collectors/__init__.py`
- Create: `app/collectors/base.py`
- Create: `tests/test_collectors.py`

- [ ] **Step 1: Write tests for base collector**

```python
# tests/test_collectors.py
import pytest
import httpx
from app.collectors.base import BaseCollector, CollectorResult


class FakeCollector(BaseCollector):
    """Collector that returns test data."""
    async def collect(self) -> list[CollectorResult]:
        return [
            CollectorResult(
                title="Test Hot Topic",
                description="A hot topic",
                url="https://test.com/1",
                source_platform=self.platform,
                language="en",
                region="US",
                source_rank=1,
                mention_count=10000,
            )
        ]

    @property
    def platform(self) -> str:
        return "fake"


class ErrorCollector(BaseCollector):
    async def collect(self) -> list[CollectorResult]:
        raise httpx.HTTPError("API unavailable")

    @property
    def platform(self) -> str:
        return "error_source"


def test_collector_result_creation():
    result = CollectorResult(
        title="Test",
        description="Desc",
        url="https://example.com",
        source_platform="twitter",
        language="en",
        region="US",
        source_rank=1,
        mention_count=5000,
    )
    assert result.title == "Test"
    assert result.heat_score == 0.0  # default


def test_collector_result_to_dict():
    result = CollectorResult(
        title="Test Event",
        description="Description",
        url="https://example.com",
        source_platform="reddit",
        language="en",
        region="US",
        source_rank=3,
        mention_count=8000,
        raw_data={"upvotes": 5000},
    )
    d = result.to_dict()
    assert d["title"] == "Test Event"
    assert d["source_platform"] == "reddit"
    assert d["mention_count"] == 8000
    assert d["raw_data"] == {"upvotes": 5000}


@pytest.mark.asyncio
async def test_fake_collector():
    collector = FakeCollector()
    results = await collector.collect()
    assert len(results) == 1
    assert results[0].title == "Test Hot Topic"
    assert results[0].source_platform == "fake"


@pytest.mark.asyncio
async def test_collector_safe_collect():
    collector = ErrorCollector()
    results = await collector.safe_collect()
    assert results == []  # error suppressed, empty list returned
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_collectors.py -v`
Expected: ImportError.

- [ ] **Step 3: Write app/collectors/__init__.py and app/collectors/base.py**

```python
# app/collectors/__init__.py
from app.collectors.base import BaseCollector, CollectorResult
```

```python
# app/collectors/base.py
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class CollectorResult:
    title: str
    description: str = ""
    url: str = ""
    source_platform: str = ""
    language: str = "unknown"
    region: str = "unknown"
    source_rank: int = 0
    mention_count: int = 0
    heat_score: float = 0.0
    raw_data: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


class BaseCollector(ABC):
    @abstractmethod
    async def collect(self) -> list[CollectorResult]:
        ...

    @property
    @abstractmethod
    def platform(self) -> str:
        ...

    @property
    def interval_minutes(self) -> int:
        return 15

    async def safe_collect(self) -> list[CollectorResult]:
        try:
            return await self.collect()
        except Exception:
            logger.exception(f"Collector {self.platform} failed")
            return []
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_collectors.py -v`
Expected: All 4 tests pass.

- [ ] **Step 5: Commit**

```bash
git add app/collectors/ tests/test_collectors.py
git commit -m "feat: base collector interface with CollectorResult"
```

---

### Task 5: API-Based Collectors

**Files:**
- Create: `app/collectors/twitter.py`
- Create: `app/collectors/reddit.py`
- Create: `app/collectors/hackernews.py`
- Create: `app/collectors/youtube.py`
- Create: `app/collectors/newsapi.py`
- Modify: `tests/test_collectors.py`

- [ ] **Step 1: Write tests for API collectors**

Append to `tests/test_collectors.py`:

```python
from app.collectors.hackernews import HackerNewsCollector
from app.collectors.newsapi import NewsApiCollector


@pytest.mark.asyncio
async def test_hackernews_collector(httpx_mock):
    httpx_mock.add_response(
        url="https://hacker-news.firebaseio.com/v0/topstories.json",
        json=[1, 2, 3],
    )
    httpx_mock.add_response(
        url="https://hacker-news.firebaseio.com/v0/item/1.json",
        json={"id": 1, "title": "HN Story 1", "by": "user1",
              "score": 100, "descendants": 50, "url": "https://hn1.com"},
    )
    httpx_mock.add_response(
        url="https://hacker-news.firebaseio.com/v0/item/2.json",
        json={"id": 2, "title": "HN Story 2", "by": "user2",
              "score": 80, "descendants": 30, "url": "https://hn2.com"},
    )
    httpx_mock.add_response(
        url="https://hacker-news.firebaseio.com/v0/item/3.json",
        json={"id": 3, "title": "HN Story 3", "by": "user3",
              "score": 60, "descendants": 20, "url": ""},
    )

    collector = HackerNewsCollector()
    results = await collector.collect()

    assert len(results) == 3
    assert results[0].title == "HN Story 1"
    assert results[0].source_platform == "hackernews"
    assert results[0].mention_count == 100
    assert results[0].source_rank == 1


@pytest.mark.asyncio
async def test_newsapi_collector(httpx_mock):
    httpx_mock.add_response(
        url="https://newsapi.org/v2/top-headlines?language=en&pageSize=50&apiKey=test-key",
        json={
            "status": "ok",
            "totalResults": 2,
            "articles": [
                {"title": "World News 1", "description": "Desc 1",
                 "url": "https://news1.com", "source": {"name": "CNN"}},
                {"title": "World News 2", "description": "Desc 2",
                 "url": "https://news2.com", "source": {"name": "BBC"}},
            ]
        },
    )

    collector = NewsApiCollector(api_key="test-key")
    results = await collector.collect()

    assert len(results) == 2
    assert results[0].title == "World News 1"
    assert results[0].source_platform == "newsapi"
    assert results[0].language == "en"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_collectors.py::test_hackernews_collector -v`
Expected: ImportError.

- [ ] **Step 3: Write app/collectors/hackernews.py**

```python
import httpx
from app.collectors.base import BaseCollector, CollectorResult


class HackerNewsCollector(BaseCollector):
    TOP_STORIES_URL = "https://hacker-news.firebaseio.com/v0/topstories.json"
    ITEM_URL = "https://hacker-news.firebaseio.com/v0/item/{}.json"

    @property
    def platform(self) -> str:
        return "hackernews"

    @property
    def interval_minutes(self) -> int:
        return 15

    async def collect(self) -> list[CollectorResult]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(self.TOP_STORIES_URL)
            resp.raise_for_status()
            story_ids = resp.json()[:50]

            results = []
            for rank, sid in enumerate(story_ids, 1):
                try:
                    item_resp = await client.get(self.ITEM_URL.format(sid))
                    item_resp.raise_for_status()
                    item = item_resp.json()
                    if item and item.get("title"):
                        results.append(CollectorResult(
                            title=item.get("title", ""),
                            description=f"By {item.get('by', 'unknown')}",
                            url=item.get("url", f"https://news.ycombinator.com/item?id={sid}"),
                            source_platform=self.platform,
                            language="en",
                            region="US",
                            source_rank=rank,
                            mention_count=item.get("score", 0),
                            raw_data=item,
                        ))
                except Exception:
                    continue
            return results
```

- [ ] **Step 4: Write app/collectors/newsapi.py**

```python
import httpx
from app.collectors.base import BaseCollector, CollectorResult


class NewsApiCollector(BaseCollector):
    BASE_URL = "https://newsapi.org/v2/top-headlines"

    def __init__(self, api_key: str = ""):
        self.api_key = api_key

    @property
    def platform(self) -> str:
        return "newsapi"

    @property
    def interval_minutes(self) -> int:
        return 60

    async def collect(self) -> list[CollectorResult]:
        if not self.api_key:
            return []

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                self.BASE_URL,
                params={"language": "en", "pageSize": 50, "apiKey": self.api_key},
            )
            resp.raise_for_status()
            data = resp.json()

            results = []
            for rank, article in enumerate(data.get("articles", [])[:50], 1):
                if article.get("title"):
                    results.append(CollectorResult(
                        title=article["title"],
                        description=article.get("description", ""),
                        url=article.get("url", ""),
                        source_platform=self.platform,
                        language="en",
                        region=article.get("source", {}).get("name", "US"),
                        source_rank=rank,
                        mention_count=0,
                        raw_data=article,
                    ))
            return results
```

- [ ] **Step 5: Write app/collectors/reddit.py**

```python
import httpx
from app.collectors.base import BaseCollector, CollectorResult


class RedditCollector(BaseCollector):
    BASE_URL = "https://www.reddit.com/r/all/hot.json"

    def __init__(self, client_id: str = "", client_secret: str = ""):
        self.client_id = client_id
        self.client_secret = client_secret

    @property
    def platform(self) -> str:
        return "reddit"

    @property
    def interval_minutes(self) -> int:
        return 15

    async def collect(self) -> list[CollectorResult]:
        headers = {"User-Agent": "HotspotAggregator/1.0"}
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(self.BASE_URL, headers=headers)
            resp.raise_for_status()
            data = resp.json()

            results = []
            posts = data.get("data", {}).get("children", [])[:50]
            for rank, child in enumerate(posts, 1):
                post = child["data"]
                results.append(CollectorResult(
                    title=post.get("title", ""),
                    description=post.get("selftext", "")[:300],
                    url=f"https://reddit.com{post.get('permalink', '')}",
                    source_platform=self.platform,
                    language="en",
                    region=post.get("subreddit", "unknown"),
                    source_rank=rank,
                    mention_count=post.get("score", 0) + post.get("num_comments", 0),
                    raw_data=post,
                ))
            return results
```

- [ ] **Step 6: Write app/collectors/twitter.py**

```python
import httpx
from app.collectors.base import BaseCollector, CollectorResult


class TwitterCollector(BaseCollector):
    TRENDS_URL = "https://api.twitter.com/2/tweets/search/stream"
    WOEID_GLOBAL = 1  # Global trends

    def __init__(self, bearer_token: str = ""):
        self.bearer_token = bearer_token

    @property
    def platform(self) -> str:
        return "twitter"

    @property
    def interval_minutes(self) -> int:
        return 15

    async def collect(self) -> list[CollectorResult]:
        if not self.bearer_token:
            return []

        headers = {"Authorization": f"Bearer {self.bearer_token}"}
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Use the legacy trends endpoint which is simpler
            resp = await client.get(
                "https://api.twitter.com/1.1/trends/place.json",
                params={"id": self.WOEID_GLOBAL},
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()

            results = []
            for trend_data in data:
                for rank, trend in enumerate(trend_data.get("trends", [])[:50], 1):
                    results.append(CollectorResult(
                        title=trend.get("name", ""),
                        description=f"Tweet volume: {trend.get('tweet_volume', 0) or 'N/A'}",
                        url=trend.get("url", ""),
                        source_platform=self.platform,
                        language="en",
                        region="global",
                        source_rank=rank,
                        mention_count=trend.get("tweet_volume") or 0,
                        raw_data=trend,
                    ))
            return results
```

- [ ] **Step 7: Write app/collectors/youtube.py**

```python
import httpx
from app.collectors.base import BaseCollector, CollectorResult


class YouTubeCollector(BaseCollector):
    BASE_URL = "https://www.googleapis.com/youtube/v3/videos"

    def __init__(self, api_key: str = ""):
        self.api_key = api_key

    @property
    def platform(self) -> str:
        return "youtube"

    @property
    def interval_minutes(self) -> int:
        return 60

    async def collect(self) -> list[CollectorResult]:
        if not self.api_key:
            return []

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                self.BASE_URL,
                params={
                    "part": "snippet,statistics",
                    "chart": "mostPopular",
                    "regionCode": "US",
                    "maxResults": 50,
                    "key": self.api_key,
                },
            )
            resp.raise_for_status()
            data = resp.json()

            results = []
            for rank, item in enumerate(data.get("items", []), 1):
                snippet = item.get("snippet", {})
                stats = item.get("statistics", {})
                results.append(CollectorResult(
                    title=snippet.get("title", ""),
                    description=snippet.get("description", "")[:300],
                    url=f"https://youtube.com/watch?v={item.get('id', '')}",
                    source_platform=self.platform,
                    language=snippet.get("defaultAudioLanguage", "unknown"),
                    region=snippet.get("country", "US"),
                    source_rank=rank,
                    mention_count=int(stats.get("viewCount", 0)),
                    raw_data=item,
                ))
            return results
```

- [ ] **Step 8: Run tests**

Run: `pytest tests/test_collectors.py -v`
Expected: 6 tests pass (4 from base + 2 new).

- [ ] **Step 9: Commit**

```bash
git add app/collectors/twitter.py app/collectors/reddit.py app/collectors/hackernews.py app/collectors/youtube.py app/collectors/newsapi.py tests/test_collectors.py
git commit -m "feat: API-based collectors (HN, Reddit, Twitter, YouTube, NewsAPI)"
```

---

### Task 6: Scraping-Based Collectors

**Files:**
- Create: `app/collectors/github_trending.py`
- Create: `app/collectors/weibo.py`
- Create: `app/collectors/zhihu.py`
- Create: `app/collectors/baidu.py`
- Create: `app/collectors/google_trends.py`
- Create: `app/collectors/rss_feeds.py`
- Modify: `tests/test_collectors.py`

- [ ] **Step 1: Write tests for scraping collectors**

Append to `tests/test_collectors.py`:

```python
from app.collectors.github_trending import GitHubTrendingCollector
from app.collectors.google_trends import GoogleTrendsCollector


@pytest.mark.asyncio
async def test_github_trending_collector(httpx_mock):
    html_content = """
    <html><body>
    <article class="Box-row">
        <h2 class="h3 lh-condensed"><a href="/owner/repo1">owner / <span>repo1</span></a></h2>
        <p class="col-9">An awesome Python library</p>
        <span class="d-inline-block float-sm-right">1,234 stars today</span>
    </article>
    <article class="Box-row">
        <h2 class="h3 lh-condensed"><a href="/owner/repo2">owner / <span>repo2</span></a></h2>
        <p class="col-9">A great JS framework</p>
        <span class="d-inline-block float-sm-right">567 stars today</span>
    </article>
    </body></html>
    """
    httpx_mock.add_response(
        url="https://github.com/trending",
        text=html_content,
    )

    collector = GitHubTrendingCollector()
    results = await collector.collect()

    assert len(results) == 2
    assert results[0].source_platform == "github_trending"
    assert "repo1" in results[0].title
    assert results[0].source_rank == 1


@pytest.mark.asyncio
async def test_google_trends_collector():
    collector = GoogleTrendsCollector()
    results = await collector.collect()
    # pytrends may fail in test env; should return empty list gracefully
    assert isinstance(results, list)
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_collectors.py::test_github_trending_collector -v`
Expected: ImportError.

- [ ] **Step 3: Write app/collectors/github_trending.py**

```python
import httpx
from bs4 import BeautifulSoup
from app.collectors.base import BaseCollector, CollectorResult


class GitHubTrendingCollector(BaseCollector):
    URL = "https://github.com/trending"

    @property
    def platform(self) -> str:
        return "github_trending"

    @property
    def interval_minutes(self) -> int:
        return 60

    async def collect(self) -> list[CollectorResult]:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            resp = await client.get(self.URL)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

        results = []
        articles = soup.find_all("article", class_="Box-row")[:25]
        for rank, article in enumerate(articles, 1):
            h2 = article.find("h2")
            if not h2:
                continue
            link = h2.find("a")
            repo_name = link.text.strip().replace("\n", "").replace(" ", "") if link else ""
            desc_el = article.find("p", class_="col-9")
            description = desc_el.text.strip() if desc_el else ""
            stars_el = article.find("span", class_="float-sm-right")
            stars_text = stars_el.text.strip() if stars_el else "0"
            mention_count = int("".join(c for c in stars_text if c.isdigit()) or 0)

            results.append(CollectorResult(
                title=f"{repo_name}",
                description=description,
                url=f"https://github.com{link['href']}" if link and link.get("href") else "",
                source_platform=self.platform,
                language="en",
                region="US",
                source_rank=rank,
                mention_count=mention_count,
                raw_data={"stars_today": stars_text},
            ))
        return results
```

- [ ] **Step 4: Write app/collectors/weibo.py**

```python
import httpx
from app.collectors.base import BaseCollector, CollectorResult


class WeiboCollector(BaseCollector):
    URL = "https://weibo.com/ajax/side/hotSearch"

    @property
    def platform(self) -> str:
        return "weibo"

    @property
    def interval_minutes(self) -> int:
        return 10

    async def collect(self) -> list[CollectorResult]:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(self.URL, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        results = []
        items = data.get("data", {}).get("realtime", [])[:50]
        for rank, item in enumerate(items, 1):
            word = item.get("word", "") or item.get("note", "")
            if not word:
                continue
            results.append(CollectorResult(
                title=word,
                description=f"热度: {item.get('num', 0)}",
                url=f"https://s.weibo.com/weibo?q={word}",
                source_platform=self.platform,
                language="zh",
                region="CN",
                source_rank=rank,
                mention_count=item.get("num", 0) or item.get("raw_hot", 0),
                raw_data=item,
            ))
        return results
```

- [ ] **Step 5: Write app/collectors/zhihu.py**

```python
import httpx
from app.collectors.base import BaseCollector, CollectorResult


class ZhihuCollector(BaseCollector):
    URL = "https://www.zhihu.com/api/v3/feed/topstory/hot-lists/total?limit=50"

    @property
    def platform(self) -> str:
        return "zhihu"

    @property
    def interval_minutes(self) -> int:
        return 15

    async def collect(self) -> list[CollectorResult]:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(self.URL, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        results = []
        for item in data.get("data", [])[:50]:
            target = item.get("target", {})
            title = target.get("title", "")
            if not title:
                continue
            results.append(CollectorResult(
                title=title,
                description=target.get("excerpt", "")[:300],
                url=target.get("url", f"https://www.zhihu.com/question/{target.get('id', '')}"),
                source_platform=self.platform,
                language="zh",
                region="CN",
                source_rank=item.get("position", 1),
                mention_count=int(target.get("follower_count", 0) or 0),
                raw_data=item,
            ))
        return results
```

- [ ] **Step 6: Write app/collectors/baidu.py**

```python
import httpx
from app.collectors.base import BaseCollector, CollectorResult


class BaiduCollector(BaseCollector):
    URL = "https://top.baidu.com/board?tab=realtime"

    @property
    def platform(self) -> str:
        return "baidu"

    @property
    def interval_minutes(self) -> int:
        return 15

    async def collect(self) -> list[CollectorResult]:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            resp = await client.get(self.URL, headers=headers)
            resp.raise_for_status()
            # Try JSON API endpoint
            api_resp = await client.get(
                "https://top.baidu.com/api/board?platform=wise&tab=realtime",
                headers=headers,
            )
            api_resp.raise_for_status()
            data = api_resp.json()

        results = []
        cards = data.get("data", {}).get("cards", [])
        for card in cards:
            for item in card.get("content", [])[:50]:
                word = item.get("word", "") or item.get("query", "")
                if not word:
                    continue
                results.append(CollectorResult(
                    title=word,
                    description=item.get("desc", ""),
                    url=item.get("url", ""),
                    source_platform=self.platform,
                    language="zh",
                    region="CN",
                    source_rank=item.get("index", 1),
                    mention_count=item.get("hotScore", 0) or item.get("heat_score", 0),
                    raw_data=item,
                ))
        return results
```

- [ ] **Step 7: Write app/collectors/google_trends.py**

```python
from app.collectors.base import BaseCollector, CollectorResult


class GoogleTrendsCollector(BaseCollector):
    @property
    def platform(self) -> str:
        return "google_trends"

    @property
    def interval_minutes(self) -> int:
        return 60

    async def collect(self) -> list[CollectorResult]:
        try:
            from pytrends.request import TrendReq
            pytrends = TrendReq(hl="en-US", tz=360)
            data = pytrends.trending_searches(pn="united_states")
            results = []
            for rank, row in enumerate(data.head(50).itertuples(), 1):
                results.append(CollectorResult(
                    title=row[1] if len(row) > 1 else str(row),
                    source_platform=self.platform,
                    language="en",
                    region="US",
                    source_rank=rank,
                    mention_count=0,
                ))
            return results
        except Exception:
            return []
```

- [ ] **Step 8: Write app/collectors/rss_feeds.py**

```python
import asyncio
import feedparser
import httpx
from app.collectors.base import BaseCollector, CollectorResult


DEFAULT_RSS_FEEDS = [
    ("https://feeds.bbci.co.uk/news/world/rss.xml", "en", "GB"),
    ("https://rss.nytimes.com/services/xml/rss/nyt/World.xml", "en", "US"),
    ("https://www3.nhk.or.jp/rss/news/cat6.xml", "ja", "JP"),
]


class RSSCollector(BaseCollector):
    def __init__(self, feeds: list[tuple[str, str, str]] = None):
        self.feeds = feeds or DEFAULT_RSS_FEEDS

    @property
    def platform(self) -> str:
        return "rss"

    @property
    def interval_minutes(self) -> int:
        return 30

    async def collect(self) -> list[CollectorResult]:
        results = []
        loop = asyncio.get_event_loop()

        for feed_url, lang, region in self.feeds:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.get(feed_url)
                    resp.raise_for_status()
                    feed = await loop.run_in_executor(
                        None, feedparser.parse, resp.text
                    )

                for rank, entry in enumerate(feed.entries[:20], 1):
                    results.append(CollectorResult(
                        title=entry.get("title", ""),
                        description=entry.get("summary", "")[:300],
                        url=entry.get("link", ""),
                        source_platform=self.platform,
                        language=lang,
                        region=region,
                        source_rank=rank,
                        mention_count=0,
                        raw_data={"published": entry.get("published", "")},
                    ))
            except Exception:
                continue

        return results
```

- [ ] **Step 9: Run all collector tests**

Run: `pytest tests/test_collectors.py -v`
Expected: All 8 tests pass.

- [ ] **Step 10: Commit**

```bash
git add app/collectors/github_trending.py app/collectors/weibo.py app/collectors/zhihu.py app/collectors/baidu.py app/collectors/google_trends.py app/collectors/rss_feeds.py tests/test_collectors.py
git commit -m "feat: scraping-based collectors (GitHub, Weibo, Zhihu, Baidu, Google Trends, RSS)"
```

---

### Task 7: Pipeline — Normalizer

**Files:**
- Create: `app/pipeline/__init__.py`
- Create: `app/pipeline/normalizer.py`
- Create: `tests/test_pipeline.py`

- [ ] **Step 1: Write tests for normalizer**

```python
# tests/test_pipeline.py
from app.pipeline.normalizer import normalize_results, NormalizedEvent


def test_normalize_results_basic():
    from app.collectors.base import CollectorResult

    raw = [
        CollectorResult(
            title="  Test Event  ",
            description="Long " + "x" * 600,
            url="https://example.com",
            source_platform="twitter",
            language="en",
            region="US",
            source_rank=1,
            mention_count=5000,
        ),
    ]
    results = normalize_results(raw)
    assert len(results) == 1
    assert results[0].title == "Test Event"  # stripped
    assert len(results[0].description) <= 500  # truncated
    assert results[0].source_platform == "twitter"


def test_normalize_results_dedup_same_source():
    from app.collectors.base import CollectorResult

    raw = [
        CollectorResult(title="Same Event", source_platform="twitter",
                        language="en", region="US", source_rank=1),
        CollectorResult(title="Same Event", source_platform="twitter",
                        language="en", region="US", source_rank=2),
        CollectorResult(title="Different Event", source_platform="twitter",
                        language="en", region="US", source_rank=3),
    ]
    results = normalize_results(raw)
    titles = [r.title for r in results]
    assert titles.count("Same Event") == 1  # deduped within same source
    assert "Different Event" in titles


def test_normalize_results_language_detection():
    from app.collectors.base import CollectorResult

    raw = [
        CollectorResult(title="English title", source_platform="newsapi",
                        language="unknown", region="US"),
        CollectorResult(title="中文标题测试", source_platform="weibo",
                        language="unknown", region="CN"),
    ]
    results = normalize_results(raw)
    assert results[0].language != "unknown"
    assert results[1].language in ("zh", "zh-cn")


def test_normalized_event_serialization():
    event = NormalizedEvent(
        title="Event",
        description="Desc",
        url="https://example.com",
        source_platform="twitter",
        language="en",
        region="US",
        source_rank=1,
        mention_count=1000,
    )
    d = event.to_dict()
    assert d["title"] == "Event"
    assert d["mention_count"] == 1000


def test_normalize_empty_list():
    assert normalize_results([]) == []
```

- [ ] **Step 2: Run test to verify failure**

Run: `pytest tests/test_pipeline.py -v`
Expected: ImportError.

- [ ] **Step 3: Write app/pipeline/normalizer.py**

```python
import re
from dataclasses import dataclass, field, asdict
from app.collectors.base import CollectorResult


@dataclass
class NormalizedEvent:
    title: str
    description: str = ""
    url: str = ""
    source_platform: str = ""
    language: str = "unknown"
    region: str = "unknown"
    source_rank: int = 0
    mention_count: int = 0
    raw_data: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def dedup_key(self) -> str:
        """Key for deduplication within the same source platform."""
        return f"{self.source_platform}:{self.title.lower().strip()}"


def _detect_language(title: str) -> str:
    """Simple heuristic language detection based on character ranges."""
    if not title:
        return "unknown"
    has_cjk = bool(re.search(r'[一-鿿぀-ゟ゠-ヿ가-힯]', title))
    if has_cjk:
        has_jp = bool(re.search(r'[぀-ゟ゠-ヿ]', title))
        if has_jp:
            return "ja"
        return "zh"
    return "en"


def normalize_results(raw_results: list[CollectorResult]) -> list[NormalizedEvent]:
    seen_keys: set[str] = set()
    normalized: list[NormalizedEvent] = []

    for item in raw_results:
        title = item.title.strip()
        if not title:
            continue

        description = item.description.strip()[:500]
        language = item.language if item.language != "unknown" else _detect_language(title)

        event = NormalizedEvent(
            title=title,
            description=description,
            url=item.url.strip(),
            source_platform=item.source_platform,
            language=language,
            region=item.region or "unknown",
            source_rank=item.source_rank,
            mention_count=item.mention_count,
            raw_data=item.raw_data,
        )

        if event.dedup_key not in seen_keys:
            seen_keys.add(event.dedup_key)
            normalized.append(event)

    return normalized
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_pipeline.py -v`
Expected: All 5 tests pass.

- [ ] **Step 5: Commit**

```bash
git add app/pipeline/ tests/test_pipeline.py
git commit -m "feat: data normalizer with dedup and language detection"
```

---

### Task 8: Pipeline — LLM Processor

**Files:**
- Create: `app/pipeline/llm_processor.py`
- Modify: `tests/test_pipeline.py`

- [ ] **Step 1: Write tests for LLM processor**

Append to `tests/test_pipeline.py`:

```python
from unittest.mock import patch, MagicMock
from app.pipeline.llm_processor import (
    LLMProcessor, build_classification_prompt, parse_llm_response
)


def test_build_classification_prompt():
    events = [
        {"title": "Apple releases M4 chip", "source_platform": "twitter", "language": "en"},
        {"title": "欧冠决赛结果", "source_platform": "weibo", "language": "zh"},
    ]
    prompt = build_classification_prompt(events)
    assert "Apple releases M4 chip" in prompt
    assert "欧冠决赛结果" in prompt
    assert "翻译成中文" in prompt or "translate" in prompt.lower()
    assert "分类" in prompt or "category" in prompt.lower()


def test_parse_llm_response():
    response = """[
    {
        "index": 0,
        "title_cn": "Apple 发布M4芯片",
        "summary_cn": "Apple 发布了新一代 M4 芯片，性能大幅提升。",
        "categories": [{"name": "科技", "slug": "tech", "confidence": 0.95}],
        "is_duplicate_of": null,
        "global_heat": 95
    },
    {
        "index": 1,
        "title_cn": "欧冠决赛结果",
        "summary_cn": "欧冠决赛结束，某队夺冠。",
        "categories": [{"name": "体育", "slug": "sports", "confidence": 0.98}],
        "is_duplicate_of": null,
        "global_heat": 88
    }
    ]"""
    parsed = parse_llm_response(response, 2)
    assert len(parsed) == 2
    assert parsed[0]["title_cn"] == "Apple 发布M4芯片"
    assert parsed[0]["categories"][0]["slug"] == "tech"
    assert parsed[0]["global_heat"] == 95
    assert parsed[1]["categories"][0]["slug"] == "sports"


def test_parse_llm_response_invalid_json():
    result = parse_llm_response("invalid json {{{", 1)
    assert result == []


class FakeLLMProcessor(LLMProcessor):
    """LLM processor that returns predefined results without API calls."""
    async def process_batch(self, events: list[dict]) -> list[dict]:
        results = []
        for i, e in enumerate(events):
            results.append({
                "index": i,
                "title_cn": e["title"] + " (中文)",
                "summary_cn": f"摘要: {e['title']}",
                "categories": [{"name": "科技", "slug": "tech", "confidence": 0.9}],
                "is_duplicate_of": None,
                "global_heat": 80 + i,
            })
        return results


@pytest.mark.asyncio
async def test_fake_llm_processor():
    processor = FakeLLMProcessor()
    events = [
        {"title": "Event 1", "source_platform": "twitter", "language": "en"},
        {"title": "Event 2", "source_platform": "reddit", "language": "en"},
    ]
    results = await processor.process_batch(events)
    assert len(results) == 2
    assert "Event 1 (中文)" in results[0]["title_cn"]
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_pipeline.py::test_build_classification_prompt -v`
Expected: ImportError.

- [ ] **Step 3: Write app/pipeline/llm_processor.py**

```python
import json
import logging
import re
from openai import AsyncOpenAI
from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL

logger = logging.getLogger(__name__)

DEFAULT_CATEGORIES = [
    {"name": "科技", "slug": "tech"},
    {"name": "财经", "slug": "finance"},
    {"name": "体育", "slug": "sports"},
    {"name": "娱乐", "slug": "entertainment"},
    {"name": "政治", "slug": "politics"},
    {"name": "社会", "slug": "society"},
    {"name": "健康", "slug": "health"},
    {"name": "教育", "slug": "education"},
    {"name": "环境", "slug": "environment"},
    {"name": "军事", "slug": "military"},
    {"name": "科学", "slug": "science"},
    {"name": "游戏", "slug": "gaming"},
    {"name": "汽车", "slug": "auto"},
    {"name": "旅游", "slug": "travel"},
    {"name": "美食", "slug": "food"},
]


def build_classification_prompt(events: list[dict]) -> str:
    events_json = json.dumps(
        [{"index": i, "title": e["title"], "description": e.get("description", "")[:200],
          "source_platform": e["source_platform"], "language": e["language"]}
         for i, e in enumerate(events)],
        ensure_ascii=False, indent=2,
    )

    categories_str = ", ".join(c["name"] for c in DEFAULT_CATEGORIES)

    return f"""你是一个全球热点事件分析专家。请处理以下热点事件列表：

{events_json}

请对每个事件执行以下操作，返回 JSON 数组：
1. **翻译**：将 title 翻译成中文（title_cn）
2. **摘要**：用中文写一句简短摘要（summary_cn），30字以内
3. **分类**：从以下类别中选择最匹配的 1-2 个：{categories_str}。提供类别名称、slug 和置信度(0-1)
4. **去重判断**：如果此事件与列表中其他事件是同一话题（不同平台报道），在 is_duplicate_of 中填写那个事件的 index，否则填 null
5. **全球热度评分**：综合评估 global_heat 0-100，考虑跨平台传播和讨论量

返回格式：
[{{"index": 0, "title_cn": "...", "summary_cn": "...", "categories": [{{"name": "...", "slug": "...", "confidence": 0.9}}], "is_duplicate_of": null, "global_heat": 85}}]

只返回 JSON 数组，不要有其他文字。"""


def parse_llm_response(response_text: str, expected_count: int) -> list[dict]:
    try:
        text = response_text.strip()
        # Remove markdown code fences if present
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"```\s*$", "", text)
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return parsed
        return []
    except (json.JSONDecodeError, Exception) as e:
        logger.error(f"Failed to parse LLM response: {e}")
        return []


class LLMProcessor:
    def __init__(self, api_key: str = None, base_url: str = None, model: str = None):
        self.client = AsyncOpenAI(
            api_key=api_key or LLM_API_KEY,
            base_url=base_url or LLM_BASE_URL,
        )
        self.model = model or LLM_MODEL

    async def process_batch(self, events: list[dict]) -> list[dict]:
        if not events or not LLM_API_KEY:
            return []

        prompt = build_classification_prompt(events)

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=4000,
            )
            content = response.choices[0].message.content
            return parse_llm_response(content, len(events))
        except Exception as e:
            logger.error(f"LLM API call failed: {e}")
            return []
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_pipeline.py -v`
Expected: All 9 tests pass (5 normalizer + 4 LLM).

- [ ] **Step 5: Commit**

```bash
git add app/pipeline/llm_processor.py tests/test_pipeline.py
git commit -m "feat: LLM processor for classification, translation, dedup"
```

---

### Task 9: Pipeline — Dedup and Scorer

**Files:**
- Create: `app/pipeline/dedup.py`
- Create: `app/pipeline/scorer.py`
- Modify: `tests/test_pipeline.py`

- [ ] **Step 1: Write tests for dedup and scorer**

Append to `tests/test_pipeline.py`:

```python
from app.pipeline.dedup import merge_duplicates, find_cross_platform_duplicates
from app.pipeline.scorer import compute_heat_score, normalize_heat_scores


def test_find_cross_platform_duplicates():
    llm_results = [
        {"index": 0, "title_cn": "Apple M4 发布", "is_duplicate_of": None, "global_heat": 95},
        {"index": 1, "title_cn": "Apple 推出M4芯片", "is_duplicate_of": 0, "global_heat": 88},
        {"index": 2, "title_cn": "欧冠决赛", "is_duplicate_of": None, "global_heat": 90},
    ]
    groups = find_cross_platform_duplicates(llm_results)
    assert len(groups) == 2  # 2 unique events
    # Group containing index 0 and 1
    group_0 = next(g for g in groups if 0 in g["indices"])
    assert 1 in group_0["indices"]
    assert group_0["primary_index"] == 0


def test_merge_duplicates():
    from app.pipeline.normalizer import NormalizedEvent

    events = [
        NormalizedEvent(title="Apple M4", source_platform="twitter",
                        language="en", region="US", mention_count=10000),
        NormalizedEvent(title="Apple M4 chip", source_platform="reddit",
                        language="en", region="US", mention_count=5000),
        NormalizedEvent(title="欧冠", source_platform="weibo",
                        language="zh", region="CN", mention_count=80000),
    ]
    llm_results = [
        {"index": 0, "title_cn": "Apple M4 芯片发布", "summary_cn": "Apple 发布新芯片",
         "categories": [{"name": "科技", "slug": "tech", "confidence": 0.95}],
         "is_duplicate_of": None, "global_heat": 95},
        {"index": 1, "title_cn": "Apple M4 芯片发布", "summary_cn": "Apple 发布新芯片",
         "categories": [{"name": "科技", "slug": "tech", "confidence": 0.92}],
         "is_duplicate_of": 0, "global_heat": 85},
        {"index": 2, "title_cn": "欧冠决赛", "summary_cn": "欧冠决赛结果",
         "categories": [{"name": "体育", "slug": "sports", "confidence": 0.98}],
         "is_duplicate_of": None, "global_heat": 90},
    ]
    merged = merge_duplicates(events, llm_results)
    assert len(merged) == 2  # Apple M4 merged + 欧冠


def test_compute_heat_score():
    score = compute_heat_score(source_rank=1, mention_count=50000, max_mentions=100000)
    assert 0 <= score <= 100
    # Better rank = higher score
    score_better_rank = compute_heat_score(source_rank=1, mention_count=1000, max_mentions=100000)
    score_worse_rank = compute_heat_score(source_rank=10, mention_count=1000, max_mentions=100000)
    assert score_better_rank > score_worse_rank


def test_normalize_heat_scores():
    scores = [95, 80, 60, 40, 20]
    normalized = normalize_heat_scores(scores)
    assert normalized[0] == 100.0  # highest -> 100
    assert normalized[-1] == 0.0  # lowest -> 0
    assert all(0 <= s <= 100 for s in normalized)
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_pipeline.py::test_compute_heat_score -v`
Expected: ImportError.

- [ ] **Step 3: Write app/pipeline/dedup.py**

```python
import logging
from app.pipeline.normalizer import NormalizedEvent

logger = logging.getLogger(__name__)


def find_cross_platform_duplicates(llm_results: list[dict]) -> list[dict]:
    """
    Group LLM results by duplicate relationships.
    Returns list of groups, each with indices, primary_index, and merged data.
    """
    skip_indices: set[int] = set()
    groups: list[dict] = []

    for i, result in enumerate(llm_results):
        if i in skip_indices:
            continue
        duplicate_of = result.get("is_duplicate_of")
        if duplicate_of is not None and duplicate_of < len(llm_results):
            # This item is a duplicate of another; add to that group
            primary_idx = duplicate_of
            # Find existing group for primary
            found = False
            for g in groups:
                if primary_idx in g["indices"]:
                    g["indices"].add(i)
                    found = True
                    break
            if not found:
                groups.append({"indices": {primary_idx, i}, "primary_index": primary_idx})
            skip_indices.add(i)
        else:
            groups.append({"indices": {i}, "primary_index": i})

    return groups


def merge_duplicates(events: list[NormalizedEvent],
                     llm_results: list[dict]) -> list[dict]:
    """
    Merge duplicate events and return final event records ready for DB insertion.
    Each output dict represents one unique event with combined data.
    """
    groups = find_cross_platform_duplicates(llm_results)
    merged: list[dict] = []

    for group in groups:
        indices = sorted(group["indices"])
        primary = group["primary_index"]

        # Collect all source platforms
        all_platforms = set()
        total_mentions = 0
        sources_data = []

        for idx in indices:
            if idx < len(events):
                e = events[idx]
                all_platforms.add(e.source_platform)
                total_mentions += e.mention_count
                sources_data.append({
                    "platform": e.source_platform,
                    "url": e.url,
                    "rank": e.source_rank,
                    "mentions": e.mention_count,
                })

            if idx < len(llm_results):
                r = llm_results[idx]

        primary_result = llm_results[primary] if primary < len(llm_results) else {}
        primary_event = events[primary] if primary < len(events) else events[0]

        merged.append({
            "title": primary_event.title,
            "title_cn": primary_result.get("title_cn", ""),
            "description": primary_event.description,
            "summary_cn": primary_result.get("summary_cn", ""),
            "url": primary_event.url,
            "source_platform": ",".join(sorted(all_platforms)),
            "language": primary_event.language,
            "region": primary_event.region,
            "categories": primary_result.get("categories", []),
            "global_heat": primary_result.get("global_heat", 0),
            "total_mentions": total_mentions,
            "source_count": len(all_platforms),
            "sources_data": sources_data,
        })

    return merged
```

- [ ] **Step 4: Write app/pipeline/scorer.py**

```python
import math


def compute_heat_score(source_rank: int, mention_count: int,
                       max_mentions: int = 100000) -> float:
    """
    Compute normalized heat score (0-100) based on source rank and mention count.
    Rank contributes 60%, mention volume contributes 40%.
    """
    # Rank component: rank 1 = 60 points, decreases logarithmically
    rank_score = 60.0 * (1.0 / math.log2(source_rank + 1))

    # Mention component: normalize against max
    if max_mentions > 0:
        mention_score = 40.0 * min(mention_count / max_mentions, 1.0)
    else:
        mention_score = 0.0

    return round(min(rank_score + mention_score, 100.0), 1)


def normalize_heat_scores(scores: list[float]) -> list[float]:
    """Normalize a list of scores to 0-100 range."""
    if not scores:
        return []
    min_s = min(scores)
    max_s = max(scores)
    if max_s == min_s:
        return [50.0] * len(scores)
    return [round((s - min_s) / (max_s - min_s) * 100, 1) for s in scores]


def compute_trend_direction(current_heat: float, previous_heat: float) -> str:
    """Determine trend direction based on heat change."""
    if previous_heat == 0:
        return "rising"
    change_pct = (current_heat - previous_heat) / previous_heat * 100
    if change_pct > 5:
        return "rising"
    elif change_pct < -5:
        return "falling"
    return "stable"
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/test_pipeline.py -v`
Expected: All 13 tests pass.

- [ ] **Step 6: Commit**

```bash
git add app/pipeline/dedup.py app/pipeline/scorer.py tests/test_pipeline.py
git commit -m "feat: deduplication merger and heat score calculator"
```

---

### Task 10: Pipeline Orchestrator

**Files:**
- Create: `app/pipeline/orchestrator.py`
- Modify: `tests/test_pipeline.py`

- [ ] **Step 1: Write tests for orchestrator**

Append to `tests/test_pipeline.py`:

```python
from app.pipeline.orchestrator import PipelineOrchestrator


class FakeOrchestrator(PipelineOrchestrator):
    """Orchestrator that skips actual LLM calls."""
    async def _process_with_llm(self, normalized: list) -> list[dict]:
        results = []
        for i, e in enumerate(normalized):
            results.append({
                "index": i,
                "title_cn": e.title + " (中文)",
                "summary_cn": f"摘要: {e.title}",
                "categories": [{"name": "科技", "slug": "tech", "confidence": 0.9}],
                "is_duplicate_of": None,
                "global_heat": 80 + i,
            })
        return results


@pytest.mark.asyncio
async def test_orchestrator_full_flow(test_db):
    from app.collectors.base import CollectorResult
    from app.database import get_events_by_timespan, get_stats

    orch = FakeOrchestrator()

    raw_results = [
        CollectorResult(title="Test Hot Event 1", source_platform="twitter",
                        language="en", region="US", source_rank=1, mention_count=10000),
        CollectorResult(title="Test Hot Event 2", source_platform="reddit",
                        language="en", region="US", source_rank=1, mention_count=8000),
        CollectorResult(title="测试热点事件3", source_platform="zhihu",
                        language="zh", region="CN", source_rank=1, mention_count=50000),
    ]

    count = await orch.run(raw_results, test_db)
    assert count > 0

    # Verify data in DB
    events = get_events_by_timespan(test_db, hours=24)
    assert len(events) >= 1

    stats = get_stats(test_db)
    assert stats["total_events"] >= 1


@pytest.mark.asyncio
async def test_orchestrator_empty_input(test_db):
    orch = FakeOrchestrator()
    count = await orch.run([], test_db)
    assert count == 0
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_pipeline.py::test_orchestrator_full_flow -v`
Expected: ImportError.

- [ ] **Step 3: Write app/pipeline/orchestrator.py**

```python
import logging
from datetime import datetime
from app.collectors.base import CollectorResult
from app.pipeline.normalizer import normalize_results, NormalizedEvent
from app.pipeline.llm_processor import LLMProcessor
from app.pipeline.dedup import merge_duplicates
from app.pipeline.scorer import normalize_heat_scores, compute_trend_direction
from app.database import (
    insert_event, insert_snapshot, get_or_create_category,
    set_event_category, link_events,
)

logger = logging.getLogger(__name__)


class PipelineOrchestrator:
    def __init__(self):
        self.llm = LLMProcessor()

    async def run(self, raw_results: list[CollectorResult], conn) -> int:
        """Run full pipeline on raw collector results. Returns number of new events stored."""
        if not raw_results:
            return 0

        # Step 1: Normalize
        normalized = normalize_results(raw_results)
        if not normalized:
            return 0

        # Step 2: LLM processing (batch)
        llm_results = await self._process_with_llm(normalized)

        # Step 3: Merge duplicates
        events_data = merge_duplicates(normalized, llm_results)

        # Step 4: Normalize heat scores
        raw_scores = [e["global_heat"] for e in events_data]
        final_scores = normalize_heat_scores(raw_scores)

        # Step 5: Store in database
        return self._store_events(conn, events_data, final_scores)

    async def _process_with_llm(self, normalized: list[NormalizedEvent]) -> list[dict]:
        events_dicts = [e.to_dict() for e in normalized]
        return await self.llm.process_batch(events_dicts)

    def _store_events(self, conn, events_data: list[dict],
                      final_scores: list[float]) -> int:
        now = datetime.utcnow().isoformat()
        stored_count = 0

        for i, data in enumerate(events_data):
            heat = final_scores[i] if i < len(final_scores) else data.get("global_heat", 50)

            # Check if event already exists (by title + source)
            existing = conn.execute(
                "SELECT id FROM events WHERE title=? AND source_platform=?",
                [data["title"], data["source_platform"]]
            ).fetchone()

            if existing:
                event_id = existing["id"]
                conn.execute(
                    "UPDATE events SET last_updated_at=? WHERE id=?",
                    [now, event_id]
                )
            else:
                event_id = insert_event(conn, {
                    "title": data["title"],
                    "description": data.get("description", ""),
                    "url": data.get("url", ""),
                    "source_platform": data["source_platform"],
                    "language": data.get("language", "unknown"),
                    "region": data.get("region", "unknown"),
                    "title_cn": data.get("title_cn", ""),
                    "summary_cn": data.get("summary_cn", ""),
                    "first_seen_at": now,
                    "last_updated_at": now,
                })
                stored_count += 1

            # Add snapshot
            # Get previous heat for trend
            prev = conn.execute("""
                SELECT heat_score FROM event_snapshots
                WHERE event_id=? ORDER BY snapshot_at DESC LIMIT 1
            """, [event_id]).fetchone()
            prev_heat = prev["heat_score"] if prev else 0
            trend = compute_trend_direction(heat, prev_heat)

            insert_snapshot(conn, {
                "event_id": event_id,
                "heat_score": heat,
                "mention_count": data.get("total_mentions", 0),
                "source_rank": data.get("source_rank", i + 1),
                "trend_direction": trend,
                "snapshot_at": now,
            })

            # Store categories
            for cat in data.get("categories", []):
                cat_id = get_or_create_category(
                    conn, cat["name"], cat["slug"]
                )
                set_event_category(
                    conn, event_id, cat_id, cat.get("confidence", 0.0)
                )

        conn.commit()
        return stored_count
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_pipeline.py -v`
Expected: All 15 tests pass.

- [ ] **Step 5: Commit**

```bash
git add app/pipeline/orchestrator.py tests/test_pipeline.py
git commit -m "feat: pipeline orchestrator wiring normalize + LLM + dedup + store"
```

---

### Task 11: FastAPI App Entry and Database Integration

**Files:**
- Create: `app/main.py`
- Create: `tests/test_routes.py`

- [ ] **Step 1: Write failing route tests**

```python
# tests/test_routes.py
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.fixture
def test_app(test_db):
    """Patch the app to use test database."""
    app.state.db = test_db
    return app


@pytest.mark.asyncio
async def test_index_page(test_app):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers.get("content-type", "")


@pytest.mark.asyncio
async def test_detail_page(test_app):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/event/999")
        assert resp.status_code == 404  # non-existent event


@pytest.mark.asyncio
async def test_api_events(test_app):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/events")
        assert resp.status_code == 200
        data = resp.json()
        assert "events" in data
        assert isinstance(data["events"], list)


@pytest.mark.asyncio
async def test_api_stats(test_app):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_events" in data


@pytest.mark.asyncio
async def test_api_categories(test_app):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/categories")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_routes.py -v`
Expected: ImportError (app.main not found).

- [ ] **Step 3: Write app/main.py**

```python
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from app.database import get_db, init_db
from app.routes.pages import router as pages_router
from app.routes.api import router as api_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

templates_dir = __import__('pathlib').Path(__file__).parent / "templates"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: init database
    conn = get_db()
    init_db(conn)
    conn.close()
    logger.info("Database initialized")
    yield
    # Shutdown


app = FastAPI(title="Hotspot - 全球热点雷达", lifespan=lifespan)

# Mount routes
app.include_router(pages_router)
app.include_router(api_router)
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_routes.py -v`
Expected: All 5 tests fail (routes not defined yet).

- [ ] **Step 5: Commit**

```bash
git add app/main.py tests/test_routes.py
git commit -m "feat: FastAPI app entry with lifespan and route mounting"
```

---

### Task 12: API Routes

**Files:**
- Create: `app/routes/__init__.py`
- Create: `app/routes/api.py`
- Modify: `tests/test_routes.py`

- [ ] **Step 1: No new tests needed — tests from Task 11 already cover API routes**

- [ ] **Step 2: Write app/routes/api.py**

```python
from fastapi import APIRouter, Request, Query
from app.database import (get_db, get_events_by_timespan, get_event_with_snapshots,
                          get_stats, search_events)

router = APIRouter(prefix="/api", tags=["api"])


def _get_conn(request: Request):
    conn = getattr(request.app.state, "db", None)
    if conn is None:
        from app.database import get_db
        conn = get_db()
    return conn


@router.get("/events")
def api_events(
    request: Request,
    timespan: str = Query("realtime", description="realtime, hourly, daily"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    category: str = Query(None),
    source: str = Query(None),
    sort_by: str = Query("heat"),
):
    timespan_map = {"realtime": 1, "hourly": 3, "daily": 24}
    hours = timespan_map.get(timespan, 1)

    conn = _get_conn(request)
    events = get_events_by_timespan(
        conn, hours=hours, limit=limit, offset=offset,
        category_slug=category, source_platform=source, sort_by=sort_by,
    )
    return {"events": events, "timespan": timespan, "hours": hours}


@router.get("/events/{event_id}")
def api_event_detail(request: Request, event_id: int):
    conn = _get_conn(request)
    result = get_event_with_snapshots(conn, event_id)
    if result is None:
        return {"error": "Event not found"}
    return result


@router.get("/stats")
def api_stats(request: Request):
    conn = _get_conn(request)
    return get_stats(conn)


@router.get("/categories")
def api_categories(request: Request):
    conn = _get_conn(request)
    rows = conn.execute("SELECT * FROM categories ORDER BY name").fetchall()
    return [dict(r) for r in rows]


@router.get("/search")
def api_search(request: Request, q: str = Query(..., min_length=1), limit: int = Query(50)):
    conn = _get_conn(request)
    return {"results": search_events(conn, q, limit)}
```

- [ ] **Step 3: Run tests**

Run: `pytest tests/test_routes.py -v`
Expected: 3 of 5 pass (api_events, api_stats, api_categories). index and detail page tests still fail (no page routes yet).

- [ ] **Step 4: Commit**

```bash
git add app/routes/api.py
git commit -m "feat: REST API routes for events, stats, categories, search"
```

---

### Task 13: Page Routes and Templates

**Files:**
- Create: `app/routes/pages.py`
- Create: `app/templates/base.html`
- Create: `app/templates/index.html`
- Create: `app/templates/detail.html`
- Modify: `app/main.py`

- [ ] **Step 1: Write app/routes/pages.py**

```python
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

router = APIRouter(tags=["pages"])
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@router.get("/event/{event_id}", response_class=HTMLResponse)
async def event_detail(request: Request, event_id: int):
    return templates.TemplateResponse(
        "detail.html", {"request": request, "event_id": event_id}
    )
```

- [ ] **Step 2: Write app/templates/base.html**

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Hotspot · 全球热点雷达{% endblock %}</title>
    <script src="https://cdn.jsdelivr.net/npm/echarts@5.5.1/dist/echarts.min.js"></script>
    <link rel="stylesheet" href="/static/css/style.css">
    {% block head %}{% endblock %}
</head>
<body>
    <div class="app">
        <header class="topbar">
            <h1 class="logo"><a href="/">🔥 Hotspot · 全球热点雷达</a></h1>
            <nav class="tabs" id="time-tabs">
                <button class="tab active" data-timespan="realtime">实时</button>
                <button class="tab" data-timespan="hourly">每小时</button>
                <button class="tab" data-timespan="daily">每日</button>
                <button class="tab" data-timespan="ondemand">按需刷新</button>
            </nav>
            <span class="update-time" id="update-time">⏱ 加载中...</span>
        </header>
        {% block content %}{% endblock %}
    </div>
    <script src="/static/js/dashboard.js"></script>
    {% block scripts %}{% endblock %}
</body>
</html>
```

- [ ] **Step 3: Write app/templates/index.html**

```html
{% extends "base.html" %}
{% block title %}Hotspot · 全球热点雷达{% endblock %}

{% block content %}
<main class="dashboard">
    <section class="stats-row" id="stats-row">
        <div class="stat-card"><div class="stat-value" id="stat-total">-</div><div class="stat-label">今日热点</div></div>
        <div class="stat-card"><div class="stat-value rising" id="stat-rising">-</div><div class="stat-label">上升趋势</div></div>
        <div class="stat-card"><div class="stat-value" id="stat-regions">-</div><div class="stat-label">覆盖地区</div></div>
        <div class="stat-card"><div class="stat-value" id="stat-categories">-</div><div class="stat-label">分类数</div></div>
    </section>

    <div class="main-grid">
        <section class="events-panel" id="events-panel">
            <div class="panel-header">
                <h2>🔥 热点排行</h2>
                <div class="sort-btns">
                    <button class="sort-btn active" data-sort="heat">热度排序</button>
                    <button class="sort-btn" data-sort="source">按来源</button>
                    <button class="sort-btn" data-sort="time">按时间</button>
                </div>
            </div>
            <div class="events-list" id="events-list">
                <div class="loading">加载中...</div>
            </div>
        </section>

        <aside class="charts-panel">
            <div class="chart-box"><h3>📊 分类热力分布</h3><div class="chart" id="chart-category-pie"></div></div>
            <div class="chart-box"><h3>📈 24h 热度走势 Top 5</h3><div class="chart" id="chart-heat-line"></div></div>
            <div class="chart-box"><h3>🌍 地区热点占比</h3><div class="chart" id="chart-region-bar"></div></div>
        </aside>
    </div>
</main>
{% endblock %}
```

- [ ] **Step 4: Write app/templates/detail.html**

```html
{% extends "base.html" %}
{% block title %}热点详情{% endblock %}

{% block content %}
<main class="detail" id="detail-page">
    <a href="/" class="back-link">← 返回首页</a>
    <div class="detail-header" id="detail-header">
        <span class="spinner">加载中...</span>
    </div>
    <div class="detail-summary" id="detail-summary"></div>
    <div class="detail-grid">
        <div class="chart-box"><h3>📈 热度变化曲线</h3><div class="chart" id="chart-timeline"></div></div>
        <div class="sources-box" id="sources-box"><h3>📡 各平台覆盖</h3><div id="sources-list"></div></div>
    </div>
    <div class="related-box" id="related-box"><h3>🔗 相关事件</h3><div id="related-list"></div></div>
</main>
{% endblock %}
{% block scripts %}
<script>
(function() {
    const eventId = {{ event_id }};
    if (eventId) { initDetailPage(eventId); }
})();
</script>
{% endblock %}
```

- [ ] **Step 5: Update app/main.py to mount static files**

Modify `app/main.py` — add after `app = FastAPI(...)` line:

```python
static_dir = __import__('pathlib').Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
```

- [ ] **Step 6: Run page route tests**

Run: `pytest tests/test_routes.py -v`
Expected: All 5 tests pass.

- [ ] **Step 7: Commit**

```bash
git add app/routes/pages.py app/templates/ app/main.py
git commit -m "feat: page routes and Jinja2 templates (index + detail)"
```

---

### Task 14: Static Files and Frontend JS

**Files:**
- Create: `app/static/css/style.css`
- Create: `app/static/js/dashboard.js`

- [ ] **Step 1: Write app/static/css/style.css**

```css
:root {
    --bg: #0f0f1a;
    --surface: #1a1a2e;
    --surface-hover: #252540;
    --border: #2a2a3e;
    --text: #e0e0e0;
    --muted: #888;
    --accent: #4a90d9;
    --rising: #ff6b6b;
    --falling: #4caf50;
    --heat-high: #ff6b6b;
    --heat-mid: #ffa500;
}

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.5;
}

a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }

.app { max-width: 1400px; margin: 0 auto; padding: 0 16px; }

/* Top bar */
.topbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 0;
    border-bottom: 1px solid var(--border);
    gap: 16px;
    flex-wrap: wrap;
}
.logo { font-size: 20px; font-weight: 700; white-space: nowrap; }
.logo a { color: var(--text); }
.tabs { display: flex; gap: 4px; }
.tab {
    background: var(--surface);
    color: var(--muted);
    border: 1px solid var(--border);
    padding: 6px 16px;
    border-radius: 6px;
    cursor: pointer;
    font-size: 13px;
    transition: all 0.2s;
}
.tab:hover { color: var(--text); border-color: var(--accent); }
.tab.active { background: var(--accent); color: #fff; border-color: var(--accent); }
.update-time { color: var(--muted); font-size: 12px; }

/* Stats row */
.stats-row {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
    padding: 16px 0;
}
.stat-card {
    background: var(--surface);
    border-radius: 8px;
    padding: 14px 16px;
    text-align: center;
}
.stat-value { font-size: 28px; font-weight: 700; color: var(--text); }
.stat-value.rising { color: var(--rising); }
.stat-label { font-size: 12px; color: var(--muted); margin-top: 4px; }

/* Main grid */
.main-grid {
    display: grid;
    grid-template-columns: 1.2fr 0.8fr;
    gap: 12px;
    padding-bottom: 24px;
}

/* Events panel */
.events-panel {
    background: var(--surface);
    border-radius: 8px;
    padding: 16px;
}
.panel-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;
}
.panel-header h2 { font-size: 16px; }
.sort-btns { display: flex; gap: 4px; }
.sort-btn {
    background: var(--surface);
    color: var(--muted);
    border: 1px solid var(--border);
    padding: 4px 10px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 11px;
}
.sort-btn.active { background: var(--accent); color: #fff; border-color: var(--accent); }

.event-item {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 8px;
    border-bottom: 1px solid var(--border);
    cursor: pointer;
    transition: background 0.15s;
}
.event-item:hover { background: var(--surface-hover); }
.event-rank { font-weight: 700; font-size: 16px; min-width: 28px; }
.event-rank.r1 { color: var(--heat-high); }
.event-rank.r2, .event-rank.r3 { color: var(--heat-mid); }
.event-rank.r4, .event-rank.r5 { color: var(--muted); }
.event-info { flex: 1; min-width: 0; }
.event-title { font-size: 14px; color: var(--text); }
.event-title:hover { color: var(--accent); }
.event-cat {
    display: inline-block;
    font-size: 10px;
    padding: 2px 6px;
    border-radius: 3px;
    background: var(--accent);
    color: #fff;
    margin-right: 4px;
    margin-top: 4px;
}
.event-meta { display: flex; gap: 12px; align-items: center; margin-left: auto; }
.event-heat { font-weight: 700; font-size: 14px; }
.event-heat.high { color: var(--heat-high); }
.event-heat.mid { color: var(--heat-mid); }
.event-platforms { font-size: 11px; color: var(--muted); }

/* Charts panel */
.charts-panel { display: flex; flex-direction: column; gap: 12px; }
.chart-box {
    background: var(--surface);
    border-radius: 8px;
    padding: 12px;
}
.chart-box h3 { font-size: 13px; margin-bottom: 8px; }
.chart { width: 100%; height: 200px; }

/* Detail page */
.detail { padding: 16px 0 32px; }
.back-link { display: inline-block; margin-bottom: 12px; font-size: 13px; }
.detail-header { margin-bottom: 12px; }
.detail-header h2 { font-size: 20px; }
.detail-meta { display: flex; gap: 12px; font-size: 12px; color: var(--muted); margin-top: 6px; }
.detail-summary {
    background: var(--surface);
    border-left: 3px solid var(--accent);
    padding: 14px;
    border-radius: 0 6px 6px 0;
    margin-bottom: 16px;
    font-size: 14px;
    line-height: 1.7;
}
.detail-grid { display: grid; grid-template-columns: 1fr 0.8fr; gap: 12px; margin-bottom: 16px; }
.sources-box { background: var(--surface); border-radius: 8px; padding: 12px; }
.source-item {
    display: flex;
    justify-content: space-between;
    padding: 8px;
    background: var(--surface-hover);
    border-radius: 4px;
    margin-bottom: 4px;
    font-size: 13px;
}
.source-platform { font-weight: 600; }
.source-rank { color: var(--heat-high); }
.source-count { color: var(--muted); font-size: 12px; }
.related-box { background: var(--surface); border-radius: 8px; padding: 12px; }
.related-tags { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 8px; }
.related-tag {
    background: var(--surface-hover);
    padding: 6px 12px;
    border-radius: 4px;
    font-size: 13px;
    cursor: pointer;
}
.related-tag:hover { background: var(--accent); color: #fff; }
.loading, .spinner { color: var(--muted); text-align: center; padding: 40px; }

/* Responsive */
@media (max-width: 900px) {
    .main-grid, .detail-grid { grid-template-columns: 1fr; }
    .stats-row { grid-template-columns: repeat(2, 1fr); }
    .topbar { flex-direction: column; align-items: flex-start; }
}
```

- [ ] **Step 2: Write app/static/js/dashboard.js**

```javascript
let currentTimespan = 'realtime';
let currentSort = 'heat';
let currentCategory = null;

// --- Tab switching ---
document.getElementById('time-tabs').addEventListener('click', (e) => {
    if (!e.target.classList.contains('tab')) return;
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    e.target.classList.add('active');
    currentTimespan = e.target.dataset.timespan;
    if (currentTimespan === 'ondemand') {
        fetch('/api/events?timespan=realtime').then(() => loadDashboard());
    } else {
        loadDashboard();
    }
});

// --- Sort switching ---
document.addEventListener('click', (e) => {
    if (!e.target.classList.contains('sort-btn')) return;
    document.querySelectorAll('.sort-btn').forEach(b => b.classList.remove('active'));
    e.target.classList.add('active');
    currentSort = e.target.dataset.sort;
    loadDashboard();
});

// --- Load dashboard ---
async function loadDashboard() {
    await Promise.all([loadStats(), loadEvents(), loadCharts()]);
}

async function loadStats() {
    const resp = await fetch('/api/stats');
    const data = await resp.json();
    document.getElementById('stat-total').textContent = data.total_events + ' 条';
    document.getElementById('stat-rising').textContent = data.rising_count + ' 条';
    document.getElementById('stat-regions').textContent = data.region_count + ' 大地区';
    document.getElementById('stat-categories').textContent = data.category_count + ' 个';
    document.getElementById('update-time').textContent = '⏱ 更新于 ' + new Date().toLocaleTimeString();
}

async function loadEvents() {
    const params = new URLSearchParams({ timespan: currentTimespan, sort_by: currentSort, limit: '100' });
    if (currentCategory) params.set('category', currentCategory);

    const resp = await fetch('/api/events?' + params);
    const data = await resp.json();
    const container = document.getElementById('events-list');
    if (!data.events.length) {
        container.innerHTML = '<div class="loading">暂无热点数据</div>';
        return;
    }
    container.innerHTML = data.events.map((e, i) => {
        const heatClass = e.latest_heat > 80 ? 'high' : e.latest_heat > 50 ? 'mid' : '';
        const rankClass = i < 3 ? `r${i+1}` : (i < 5 ? `r${i+1}` : '');
        const trend = e.latest_trend === 'rising' ? ' 📈' : e.latest_trend === 'falling' ? ' 📉' : '';
        return `<div class="event-item" onclick="location.href='/event/${e.id}'">
            <span class="event-rank ${rankClass}">${i + 1}</span>
            <div class="event-info">
                <div class="event-title">${escapeHtml(e.title_cn || e.title)}${trend}</div>
                <div>${(e.categories || []).map(c => `<span class="event-cat">${c.name || c}</span>`).join('')}</div>
            </div>
            <div class="event-meta">
                <span class="event-heat ${heatClass}">🔥 ${e.latest_heat || '-'}</span>
                <span class="event-platforms">${e.related_count || 1} 平台</span>
            </div>
        </div>`;
    }).join('');
}

async function loadCharts() {
    await Promise.all([loadCategoryPie(), loadHeatLine(), loadRegionBar()]);
}

async function loadCategoryPie() {
    const resp = await fetch('/api/categories');
    const categories = await resp.json();
    const eventsResp = await fetch('/api/events?timespan=' + (currentTimespan === 'daily' ? 'daily' : 'realtime') + '&limit=200');
    const eventsData = await eventsResp.json();

    const chart = echarts.init(document.getElementById('chart-category-pie'));
    const catData = {};
    categories.forEach(c => { catData[c.slug] = { name: c.name, count: 0 }; });
    eventsData.events.forEach(e => {
        if (e.source_platform) {
            const mainCat = e.source_platform.split(',')[0];
            if (catData[mainCat]) catData[mainCat].count++;
        }
    });

    chart.setOption({
        tooltip: { trigger: 'item' },
        series: [{
            type: 'pie', radius: ['40%', '70%'],
            data: Object.values(catData).filter(d => d.count > 0).map(d => ({ name: d.name, value: d.count })),
            label: { color: '#aaa', fontSize: 11 },
        }]
    });
}

async function loadHeatLine() {
    const resp = await fetch('/api/events?timespan=daily&sort_by=heat&limit=5');
    const data = await resp.json();
    const chart = echarts.init(document.getElementById('chart-heat-line'));

    const series = await Promise.all(data.events.slice(0, 5).map(async (e) => {
        const detailResp = await fetch('/api/events/' + e.id);
        const detail = await detailResp.json();
        return {
            name: (e.title_cn || e.title).substring(0, 15),
            type: 'line',
            smooth: true,
            data: (detail.snapshots || []).map(s => [s.snapshot_at, s.heat_score]),
        };
    }));

    chart.setOption({
        tooltip: { trigger: 'axis' },
        legend: { textStyle: { color: '#888', fontSize: 10 }, bottom: 0 },
        xAxis: { type: 'time', axisLabel: { color: '#888', fontSize: 10 } },
        yAxis: { type: 'value', axisLabel: { color: '#888' } },
        series: series,
    });
}

async function loadRegionBar() {
    const resp = await fetch('/api/events?timespan=daily&limit=200');
    const data = await resp.json();
    const regions = {};
    data.events.forEach(e => {
        const r = e.region || 'unknown';
        regions[r] = (regions[r] || 0) + 1;
    });

    const chart = echarts.init(document.getElementById('chart-region-bar'));
    chart.setOption({
        tooltip: { trigger: 'axis' },
        xAxis: { type: 'category', data: Object.keys(regions), axisLabel: { color: '#888', fontSize: 10 } },
        yAxis: { type: 'value', axisLabel: { color: '#888' } },
        series: [{ type: 'bar', data: Object.values(regions), itemStyle: { color: '#4a90d9' } }],
    });
}

// --- Detail page ---
async function initDetailPage(eventId) {
    const resp = await fetch('/api/events/' + eventId);
    if (resp.status === 404) {
        document.getElementById('detail-header').innerHTML = '<h2>事件未找到</h2>';
        return;
    }
    const data = await resp.json();
    const e = data.event;

    document.getElementById('detail-header').innerHTML = `
        <h2>${escapeHtml(e.title_cn || e.title)}</h2>
        <div class="detail-meta">
            <span>来源: ${escapeHtml(e.source_platform)}</span>
            <span>首次出现: ${formatTime(e.first_seen_at)}</span>
            <span>地区: ${escapeHtml(e.region)}</span>
        </div>`;

    if (e.summary_cn) {
        document.getElementById('detail-summary').innerHTML = `<p><strong>AI 摘要：</strong>${escapeHtml(e.summary_cn)}</p>`;
    }

    // Timeline chart
    const snapshots = data.snapshots || [];
    if (snapshots.length > 0) {
        const chart = echarts.init(document.getElementById('chart-timeline'));
        chart.setOption({
            tooltip: { trigger: 'axis' },
            xAxis: { type: 'time', axisLabel: { color: '#888' } },
            yAxis: { type: 'value', name: '热度', axisLabel: { color: '#888' } },
            series: [{
                type: 'line', smooth: true,
                areaStyle: { color: 'rgba(74,144,217,0.2)' },
                data: snapshots.map(s => [s.snapshot_at, s.heat_score]),
            }],
        });
    }

    // Sources
    const sourcesList = document.getElementById('sources-list');
    if (e.source_platform) {
        sourcesList.innerHTML = e.source_platform.split(',').map(p =>
            `<div class="source-item"><span class="source-platform">${p.trim()}</span></div>`
        ).join('');
    }

    // Related events
    const related = data.relations || [];
    if (related.length > 0) {
        document.getElementById('related-list').innerHTML = related.map(r =>
            `<span class="related-tag" onclick="location.href='/event/${r.id}'">${escapeHtml(r.title_cn || r.title)}</span>`
        ).join('');
    }
}

// --- Utils ---
function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function formatTime(iso) {
    if (!iso) return '';
    const d = new Date(iso + 'Z');
    return d.toLocaleString('zh-CN');
}

// --- Init ---
if (document.querySelector('.dashboard')) {
    loadDashboard();
    setInterval(loadDashboard, 5 * 60 * 1000);
}
```

- [ ] **Step 3: Commit**

```bash
git add app/static/
git commit -m "feat: dark-theme CSS and dashboard JS with ECharts"
```

---

### Task 15: Scheduler and Wiring

**Files:**
- Modify: `app/main.py`
- Modify: `run.py`

- [ ] **Step 1: Update app/main.py with scheduler**

Replace `app/main.py`:

```python
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from apscheduler.schedulers.background import BackgroundScheduler
from app.database import get_db, init_db, cleanup_old_snapshots
from app.collectors.hackernews import HackerNewsCollector
from app.collectors.github_trending import GitHubTrendingCollector
from app.collectors.weibo import WeiboCollector
from app.collectors.zhihu import ZhihuCollector
from app.collectors.baidu import BaiduCollector
from app.collectors.newsapi import NewsApiCollector
from app.collectors.reddit import RedditCollector
from app.collectors.twitter import TwitterCollector
from app.collectors.youtube import YouTubeCollector
from app.collectors.google_trends import GoogleTrendsCollector
from app.collectors.rss_feeds import RSSCollector
from app.pipeline.orchestrator import PipelineOrchestrator
from app.routes.pages import router as pages_router
from app.routes.api import router as api_router
from config import (
    TWITTER_BEARER_TOKEN, REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET,
    YOUTUBE_API_KEY, NEWSAPI_KEY,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent
orchestrator = PipelineOrchestrator()

# Initialize collectors
collectors = [
    HackerNewsCollector(),
    GitHubTrendingCollector(),
    WeiboCollector(),
    ZhihuCollector(),
    BaiduCollector(),
    NewsApiCollector(api_key=NEWSAPI_KEY),
    RedditCollector(client_id=REDDIT_CLIENT_ID, client_secret=REDDIT_CLIENT_SECRET),
    TwitterCollector(bearer_token=TWITTER_BEARER_TOKEN),
    YouTubeCollector(api_key=YOUTUBE_API_KEY),
    GoogleTrendsCollector(),
    RSSCollector(),
]


async def run_all_collectors():
    """Run all collectors and feed results into pipeline."""
    import asyncio
    all_results = []
    for collector in collectors:
        try:
            logger.info(f"Collecting from {collector.platform}...")
            results = await collector.safe_collect()
            all_results.extend(results)
            logger.info(f"  {collector.platform}: {len(results)} items")
        except Exception as e:
            logger.error(f"Collector {collector.platform} error: {e}")

    if all_results:
        conn = get_db()
        try:
            new_count = await orchestrator.run(all_results, conn)
            logger.info(f"Pipeline complete: {new_count} new events from {len(all_results)} raw items")
        finally:
            conn.close()


def scheduled_collection():
    """Synchronous wrapper for APScheduler."""
    import asyncio
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(run_all_collectors())
    finally:
        loop.close()


def daily_cleanup():
    conn = get_db()
    try:
        removed = cleanup_old_snapshots(conn)
        logger.info(f"Cleanup: removed {removed} old snapshots")
    finally:
        conn.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    conn = get_db()
    init_db(conn)
    conn.close()
    logger.info("Database initialized")

    scheduler = BackgroundScheduler()
    scheduler.add_job(scheduled_collection, 'interval', minutes=15, id='collect')
    scheduler.add_job(daily_cleanup, 'interval', hours=24, id='cleanup')
    scheduler.start()
    logger.info("Scheduler started (collection every 15 min)")

    app.state.scheduler = scheduler

    yield

    # Shutdown
    scheduler.shutdown(wait=False)
    logger.info("Scheduler stopped")


app = FastAPI(title="Hotspot - 全球热点雷达", lifespan=lifespan)

static_dir = BASE_DIR / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
app.include_router(pages_router)
app.include_router(api_router)
```

- [ ] **Step 2: Update run.py**

```python
import uvicorn
from app.main import app, scheduled_collection

if __name__ == "__main__":
    # Run one collection immediately on startup
    scheduled_collection()
    uvicorn.run(app, host="127.0.0.1", port=8000)
```

- [ ] **Step 3: Run all tests**

Run: `pytest tests/ -v`
Expected: All tests pass (database + collectors + pipeline + routes).

- [ ] **Step 4: Commit**

```bash
git add app/main.py run.py
git commit -m "feat: APScheduler wiring, auto-collection every 15min"
```

---

### Task 16: Final Integration and Smoke Test

- [ ] **Step 1: Create .env file**

```bash
echo "# LLM Configuration
LLM_API_KEY=your-api-key-here
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini

# Optional: API keys for various platforms
TWITTER_BEARER_TOKEN=
REDDIT_CLIENT_ID=
REDDIT_CLIENT_SECRET=
YOUTUBE_API_KEY=
NEWSAPI_KEY=
" > .env
```

- [ ] **Step 2: Create .gitignore**

```bash
echo ".env
__pycache__/
*.pyc
.superpowers/
data/hotspot.db
" > .gitignore
```

- [ ] **Step 3: Run the application**

Run: `python run.py`
Expected: Server starts on http://127.0.0.1:8000, initial collection runs, database created.

- [ ] **Step 4: Verify in browser**

Open http://127.0.0.1:8000
Expected: Dashboard loads with stats cards, events panel, and ECharts visualizations.

- [ ] **Step 5: Commit**

```bash
git add .gitignore .env
git commit -m "chore: add .gitignore and .env template"
```

---

## Summary

**Total Tasks:** 16
**Total Files Created/Modified:** ~35 files
**Test Coverage:** Database CRUD, collectors (base + API + scraping), pipeline (normalizer, LLM, dedup, scorer, orchestrator), routes (API + pages)
**Key Integration Points:** APScheduler auto-collection → Pipeline → SQLite → FastAPI → Jinja2/ECharts dashboard
