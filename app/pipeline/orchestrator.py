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

BATCH_SIZE = 5  # Small batches so results appear quickly


class PipelineOrchestrator:
    def __init__(self):
        self.llm = LLMProcessor()

    async def run(self, raw_results: list[CollectorResult], conn) -> int:
        if not raw_results:
            return 0

        normalized = normalize_results(raw_results)
        if not normalized:
            return 0

        total_stored = 0

        for i in range(0, len(normalized), BATCH_SIZE):
            batch = normalized[i:i + BATCH_SIZE]
            batch_dicts = [e.to_dict() for e in batch]

            llm_results = await self.llm.process_batch(batch_dicts)

            if not llm_results:
                llm_results = [{}] * len(batch)

            events_data = merge_duplicates(batch, llm_results)

            raw_scores = [e.get("global_heat", 50) for e in events_data]
            final_scores = normalize_heat_scores(raw_scores)

            stored = self._store_events(conn, events_data, final_scores)
            total_stored += stored
            logger.info(f"Batch {i // BATCH_SIZE + 1}: {len(batch)} items → {stored} new events stored")

        return total_stored

    def _store_events(self, conn, events_data: list[dict],
                      final_scores: list[float]) -> int:
        now = datetime.utcnow().isoformat()
        stored_count = 0

        for i, data in enumerate(events_data):
            heat = final_scores[i] if i < len(final_scores) else data.get("global_heat", 50)

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
                    "impact_points": data.get("impact_points", ""),
                    "personal_impact": data.get("personal_impact", ""),
                    "entities": data.get("entities", ""),
                    "first_seen_at": now,
                    "last_updated_at": now,
                })
                stored_count += 1

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

            for cat in data.get("categories", []):
                cat_id = get_or_create_category(
                    conn, cat["name"], cat["slug"]
                )
                set_event_category(
                    conn, event_id, cat_id, cat.get("confidence", 0.0)
                )

            sources = data.get("sources_data", [])
            if len(sources) > 1:
                for src in sources[1:]:
                    existing_src = conn.execute(
                        "SELECT id FROM events WHERE title=? AND source_platform=?",
                        [data["title"], src["platform"]]
                    ).fetchone()
                    if existing_src and existing_src["id"] != event_id:
                        link_events(conn, event_id, existing_src["id"], "merged", 0.8)

        conn.commit()
        return stored_count
