import sqlite3
from datetime import datetime, timedelta

import pytest
from app.database import (
    init_db, get_db, insert_event, insert_snapshot, get_or_create_category,
    set_event_category, get_events_by_timespan, get_event_with_snapshots,
    get_stats, search_events, link_events
)


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


def test_get_events_by_timespan_sort_by_source(test_db):
    conn = test_db
    e1 = insert_event(conn, {
        "title": "Alpha Event", "source_platform": "abc",
        "language": "en", "region": "US",
    })
    insert_snapshot(conn, {
        "event_id": e1, "heat_score": 50.0,
        "mention_count": 500, "source_rank": 2,
        "trend_direction": "stable",
    })
    e2 = insert_event(conn, {
        "title": "Zeta Event", "source_platform": "xyz",
        "language": "en", "region": "US",
    })
    insert_snapshot(conn, {
        "event_id": e2, "heat_score": 90.0,
        "mention_count": 1000, "source_rank": 1,
        "trend_direction": "rising",
    })
    events = get_events_by_timespan(conn, hours=24, sort_by="source")
    assert len(events) >= 2
    # First event should be from "abc" (alphabetically first source_platform)
    assert events[0]["source_platform"] == "abc"


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


def test_cleanup_old_snapshots(test_db):
    conn = test_db
    eid = insert_event(conn, {"title": "Old", "source_platform": "twitter",
                               "language": "en", "region": "US"})
    conn.execute("""
        INSERT INTO event_snapshots (event_id, heat_score, snapshot_at)
        VALUES (?, ?, ?)
    """, [eid, 10.0, (datetime.utcnow() - timedelta(days=365)).isoformat()])
    conn.commit()
    from app.database import cleanup_old_snapshots
    removed = cleanup_old_snapshots(conn)
    assert removed >= 1
