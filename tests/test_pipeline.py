import pytest
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
    assert results[0].title == "Test Event"
    assert len(results[0].description) <= 500
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
    assert titles.count("Same Event") == 1
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


def test_normalize_results_korean_detection():
    from app.collectors.base import CollectorResult

    raw = [
        CollectorResult(title="한국어 뉴스 제목", source_platform="naver",
                        language="unknown", region="KR"),
    ]
    results = normalize_results(raw)
    assert results[0].language == "ko"


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


@pytest.mark.asyncio
async def test_llm_processor_empty_api_key():
    """LLMProcessor with empty API key should return empty list."""
    from unittest.mock import patch, MagicMock
    import app.pipeline.llm_processor as lp
    # Temporarily clear the module-level LLM_API_KEY
    with patch.object(lp, 'LLM_API_KEY', ''):
        processor = lp.LLMProcessor(api_key='')
        events = [{"title": "Test", "source_platform": "twitter", "language": "en"}]
        results = await processor.process_batch(events)
        assert results == []


@pytest.mark.asyncio
async def test_llm_processor_empty_events():
    """Empty events list should return empty list."""
    processor = FakeLLMProcessor()
    results = await processor.process_batch([])
    assert results == []


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
    group_0 = next(g for g in groups if 0 in g["indices"])
    assert 1 in group_0["indices"]
    assert group_0["primary_index"] == 0


def test_find_cross_platform_duplicates_chain():
    """Resolve chained duplicates (A->B->C) to the ultimate root."""
    llm_results = [
        {"index": 0, "is_duplicate_of": None},
        {"index": 1, "is_duplicate_of": 0},
        {"index": 2, "is_duplicate_of": 1},
        {"index": 3, "is_duplicate_of": None},
    ]
    groups = find_cross_platform_duplicates(llm_results)
    assert len(groups) == 2
    group_primary = next(g for g in groups if g["primary_index"] == 0)
    assert group_primary["indices"] == {0, 1, 2}
    other = next(g for g in groups if g["primary_index"] == 3)
    assert other["indices"] == {3}


def test_find_cross_platform_duplicates_self_reference():
    """Self-referencing duplicate (points to itself) should form own group."""
    llm_results = [
        {"index": 0, "is_duplicate_of": 0},
        {"index": 1, "is_duplicate_of": None},
    ]
    groups = find_cross_platform_duplicates(llm_results)
    assert len(groups) == 2


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
    score_better_rank = compute_heat_score(source_rank=1, mention_count=1000, max_mentions=100000)
    score_worse_rank = compute_heat_score(source_rank=10, mention_count=1000, max_mentions=100000)
    assert score_better_rank > score_worse_rank


def test_normalize_heat_scores():
    scores = [95, 80, 60, 40, 20]
    normalized = normalize_heat_scores(scores)
    assert normalized[0] == 100.0
    assert normalized[-1] == 0.0
    assert all(0 <= s <= 100 for s in normalized)


from app.pipeline.orchestrator import PipelineOrchestrator
from app.database import get_events_by_timespan, get_stats


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
async def test_orchestrator_with_merged_events(test_db):
    """Merged duplicates should create event_relation links in the database."""
    from app.collectors.base import CollectorResult
    from app.database import insert_event

    # Pre-insert an individual platform event for reddit (simulates prior collection)
    pre_id = insert_event(test_db, {
        "title": "Merged Event",
        "source_platform": "reddit",
        "language": "en",
        "region": "US",
    })

    class MergingOrchestrator(PipelineOrchestrator):
        async def _process_with_llm(self, normalized: list) -> list[dict]:
            results = []
            for i, e in enumerate(normalized):
                dup_of = 0 if i == 1 else None
                results.append({
                    "index": i,
                    "title_cn": e.title + " (中文)",
                    "summary_cn": f"摘要: {e.title}",
                    "categories": [{"name": "科技", "slug": "tech", "confidence": 0.9}],
                    "is_duplicate_of": dup_of,
                    "global_heat": 80 + i,
                })
            return results

    orch = MergingOrchestrator()

    raw_results = [
        CollectorResult(title="Merged Event", source_platform="twitter",
                        language="en", region="US", source_rank=1, mention_count=10000),
        CollectorResult(title="Merged Event", source_platform="reddit",
                        language="en", region="US", source_rank=2, mention_count=8000),
    ]

    count = await orch.run(raw_results, test_db)
    assert count > 0

    # Verify event_relations were created linking the merged event to the pre-existing reddit event
    relations = test_db.execute(
        "SELECT * FROM event_relations WHERE relation_type='merged'"
    ).fetchall()
    assert len(relations) >= 1

    # Verify the link points to the pre-inserted reddit event
    assert any(r["event_b_id"] == pre_id for r in relations), \
        "Expected link to pre-existing reddit event"


@pytest.mark.asyncio
async def test_orchestrator_full_flow(test_db):
    from app.collectors.base import CollectorResult

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

    events = get_events_by_timespan(test_db, hours=24)
    assert len(events) >= 1

    stats = get_stats(test_db)
    assert stats["total_events"] >= 1


@pytest.mark.asyncio
async def test_orchestrator_empty_input(test_db):
    orch = FakeOrchestrator()
    count = await orch.run([], test_db)
    assert count == 0
