import json
import logging
from app.pipeline.normalizer import NormalizedEvent

logger = logging.getLogger(__name__)


def find_cross_platform_duplicates(llm_results: list[dict]) -> list[dict]:
    # Build direct parent mapping
    parent = {}
    for i, r in enumerate(llm_results):
        dup = r.get("is_duplicate_of")
        if dup is not None and 0 <= dup < len(llm_results) and dup != i:
            parent[i] = dup

    # Resolve chains to ultimate root
    def resolve(idx):
        while idx in parent:
            idx = parent[idx]
        return idx

    groups = {}
    for i in range(len(llm_results)):
        root = resolve(i)
        if root not in groups:
            groups[root] = {"indices": set(), "primary_index": root}
        groups[root]["indices"].add(i)

    return list(groups.values())


def merge_duplicates(events: list[NormalizedEvent],
                     llm_results: list[dict]) -> list[dict]:
    groups = find_cross_platform_duplicates(llm_results)
    merged: list[dict] = []

    for group in groups:
        indices = sorted(group["indices"])
        primary = group["primary_index"]

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

        primary_result = llm_results[primary] if primary < len(llm_results) else {}
        primary_event = events[primary] if primary < len(events) else events[0]

        def _serialize_list(val):
            if isinstance(val, list):
                return json.dumps(val, ensure_ascii=False)
            return ""

        merged.append({
            "title": primary_event.title,
            "title_cn": primary_result.get("title_cn", ""),
            "title_en": primary_result.get("title_en", ""),
            "description": primary_event.description,
            "summary_cn": primary_result.get("summary_cn", ""),
            "summary_en": primary_result.get("summary_en", ""),
            "impact_points": _serialize_list(primary_result.get("impact_points", [])),
            "impact_points_en": _serialize_list(primary_result.get("impact_points_en", [])),
            "personal_impact": _serialize_list(primary_result.get("personal_impact", [])),
            "personal_impact_en": _serialize_list(primary_result.get("personal_impact_en", [])),
            "entities": _serialize_list(primary_result.get("entities", [])),
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
