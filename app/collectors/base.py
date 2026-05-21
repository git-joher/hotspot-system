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
