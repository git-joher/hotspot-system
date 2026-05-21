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
        return f"{self.source_platform}:{self.title.lower().strip()}"


def _detect_language(title: str) -> str:
    if not title:
        return "unknown"
    has_cjk = bool(re.search(r'[一-鿿぀-ゟ゠-ヿ가-힣]', title))
    if has_cjk:
        has_kr = bool(re.search(r'[가-힣]', title))
        if has_kr:
            return "ko"
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
