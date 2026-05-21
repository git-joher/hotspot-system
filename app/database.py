import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

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
    impact_points TEXT DEFAULT '',
    personal_impact TEXT DEFAULT '',
    entities TEXT DEFAULT '',
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

CREATE TABLE IF NOT EXISTS predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_title TEXT NOT NULL,
    timeframe TEXT DEFAULT '',
    scenario TEXT NOT NULL,
    probability REAL DEFAULT 0.0,
    probability_label TEXT DEFAULT '',
    reasoning TEXT DEFAULT '',
    entities TEXT DEFAULT '',
    wealth_rank INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    expires_at TEXT DEFAULT ''
);

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


def insert_event(conn: sqlite3.Connection, data: dict) -> int:
    now = datetime.utcnow().isoformat()
    conn.execute("""
        INSERT INTO events (title, description, url, source_platform, language, region,
                           title_cn, summary_cn, impact_points, personal_impact, entities, first_seen_at, last_updated_at)
        VALUES (:title, :description, :url, :source_platform, :language, :region,
                :title_cn, :summary_cn, :impact_points, :personal_impact, :entities, :first_seen_at, :last_updated_at)
    """, {
        "title": data["title"],
        "description": data.get("description", ""),
        "url": data.get("url", ""),
        "source_platform": data["source_platform"],
        "language": data.get("language", "unknown"),
        "region": data.get("region", "unknown"),
        "title_cn": data.get("title_cn", ""),
        "summary_cn": data.get("summary_cn", ""),
        "impact_points": data.get("impact_points", ""),
        "personal_impact": data.get("personal_impact", ""),
        "entities": data.get("entities", ""),
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
    try:
        conn.execute(
            "INSERT OR IGNORE INTO categories (name, slug, icon) VALUES (?, ?, ?)",
            [name, slug, icon]
        )
        conn.commit()
    except Exception:
        pass
    row = conn.execute(
        "SELECT id FROM categories WHERE slug=?", [slug]
    ).fetchone()
    if row:
        return row["id"]
    # Fallback: try by name
    row = conn.execute(
        "SELECT id FROM categories WHERE name=?", [name]
    ).fetchone()
    return row["id"] if row else 0


def set_event_category(conn: sqlite3.Connection, event_id: int, category_id: int,
                       confidence: float = 0.0) -> None:
    conn.execute("""
        INSERT OR REPLACE INTO event_categories (event_id, category_id, confidence)
        VALUES (?, ?, ?)
    """, [event_id, category_id, confidence])
    conn.commit()


def get_events_by_timespan(conn: sqlite3.Connection, hours: int = 24,
                           limit: int = 100, offset: int = 0,
                           category_slug: Optional[str] = None,
                           source_platform: Optional[str] = None,
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
    elif sort_by == "personal":
        query += " ORDER BY (CASE WHEN e.personal_impact = '' OR e.personal_impact = '[]' THEN 0 ELSE 1 END) DESC, latest_heat DESC"
    elif sort_by == "time":
        query += " ORDER BY e.last_updated_at DESC"
    elif sort_by == "source":
        query += " ORDER BY e.source_platform ASC, latest_heat DESC"

    query += f" LIMIT {int(limit)} OFFSET {int(offset)}"
    return [dict(row) for row in conn.execute(query, params).fetchall()]


def get_event_with_snapshots(conn: sqlite3.Connection, event_id: int) -> Optional[dict]:
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


def get_entity_aggregates(conn: sqlite3.Connection, hours: int = 24) -> list[dict]:
    since = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
    rows = conn.execute("""
        SELECT id, title_cn, title, entities FROM events
        WHERE last_updated_at >= ? AND entities != '' AND entities != '[]'
    """, [since]).fetchall()

    import json
    entity_map = {}
    for row in rows:
        try:
            items = json.loads(row["entities"])
        except (json.JSONDecodeError, TypeError):
            continue
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            name = item.get("entity", "")
            if not name:
                continue
            ent_type = item.get("type", "")
            if name not in entity_map:
                entity_map[name] = {
                    "entity": name,
                    "type": ent_type,
                    "total_impact": 0.0,
                    "mention_count": 0,
                    "positive_count": 0,
                    "negative_count": 0,
                    "type_votes": {},
                    "actions": [],
                    "events": [],
                }
            entity_map[name]["type_votes"][ent_type] = entity_map[name]["type_votes"].get(ent_type, 0) + 1
            score = float(item.get("impact_score", 0))
            direction = item.get("direction", "neutral")
            action = item.get("action", "")
            entity_map[name]["total_impact"] += score
            entity_map[name]["mention_count"] += 1
            if direction == "positive":
                entity_map[name]["positive_count"] += 1
            elif direction == "negative":
                entity_map[name]["negative_count"] += 1
            if action:
                entity_map[name]["actions"].append(action)
            entity_map[name]["events"].append({
                "id": row["id"],
                "title": row["title_cn"] or row["title"],
                "impact_score": score,
                "direction": direction,
                "action": action,
            })

    investable_types = {"股票", "公司", "行业", "板块", "加密货币", "ETF", "基金", "商品", "外汇"}

    result = []
    for name, data in entity_map.items():
        # Use most common type if entity appeared with multiple types
        if data["type_votes"]:
            data["type"] = max(data["type_votes"], key=data["type_votes"].get)
        del data["type_votes"]

        is_investable = data.get("type", "") in investable_types

        avg = data["total_impact"] / data["mention_count"]
        if avg > 0.2:
            if is_investable:
                data["signal"] = "buy"
                data["signal_label"] = "买入"
            else:
                data["signal"] = "rising"
                data["signal_label"] = "高涨"
        elif avg < -0.2:
            if is_investable:
                data["signal"] = "sell"
                data["signal_label"] = "卖出"
            else:
                data["signal"] = "falling"
                data["signal_label"] = "低落"
        else:
            if is_investable:
                data["signal"] = "hold"
                data["signal_label"] = "观望"
            else:
                data["signal"] = "stable"
                data["signal_label"] = "平稳"
        data["avg_impact"] = round(avg, 2)
        data["total_impact"] = round(data["total_impact"], 2)
        if data["actions"]:
            data["top_action"] = max(set(data["actions"]), key=data["actions"].count)
        else:
            data["top_action"] = ""
        del data["actions"]
        result.append(data)

    result.sort(key=lambda x: abs(x["total_impact"]), reverse=True)
    return result


def replace_predictions(conn: sqlite3.Connection, predictions: list[dict]) -> int:
    import json
    conn.execute("DELETE FROM predictions")
    now = datetime.utcnow().isoformat()
    count = 0
    for p in predictions:
        entities_val = p.get("entities", [])
        if isinstance(entities_val, list):
            entities_val = json.dumps(entities_val, ensure_ascii=False)
        elif not isinstance(entities_val, str):
            entities_val = "[]"
        conn.execute("""
            INSERT INTO predictions (event_title, timeframe, scenario, probability,
                probability_label, reasoning, entities, wealth_rank, created_at, expires_at)
            VALUES (:event_title, :timeframe, :scenario, :probability,
                :probability_label, :reasoning, :entities, :wealth_rank, :created_at, :expires_at)
        """, {
            "event_title": p.get("event_title", ""),
            "timeframe": p.get("timeframe", ""),
            "scenario": p.get("scenario", ""),
            "probability": p.get("probability", 0.0),
            "probability_label": p.get("probability_label", ""),
            "reasoning": p.get("reasoning", ""),
            "entities": entities_val,
            "wealth_rank": p.get("wealth_rank", 0),
            "created_at": now,
            "expires_at": p.get("expires_at", ""),
        })
        count += 1
    conn.commit()
    return count


def get_predictions(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM predictions ORDER BY wealth_rank ASC"
    ).fetchall()
    return [dict(r) for r in rows]


def cleanup_old_predictions(conn: sqlite3.Connection) -> int:
    now = datetime.utcnow().isoformat()
    cur = conn.execute(
        "DELETE FROM predictions WHERE expires_at != '' AND expires_at < ?", [now]
    )
    conn.commit()
    return cur.rowcount


def cleanup_old_snapshots(conn: sqlite3.Connection) -> int:
    from config import SNAPSHOT_RETENTION_DAYS
    cutoff = (datetime.utcnow() - timedelta(days=SNAPSHOT_RETENTION_DAYS)).isoformat()
    cur = conn.execute("DELETE FROM event_snapshots WHERE snapshot_at < ?", [cutoff])
    conn.commit()
    return cur.rowcount
