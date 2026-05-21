import math


def compute_heat_score(source_rank: int, mention_count: int,
                       max_mentions: int = 100000) -> float:
    rank_score = 60.0 * (1.0 / math.log2(source_rank + 1))
    if max_mentions > 0:
        mention_score = 40.0 * min(mention_count / max_mentions, 1.0)
    else:
        mention_score = 0.0
    return round(min(rank_score + mention_score, 100.0), 1)


def normalize_heat_scores(scores: list[float]) -> list[float]:
    if not scores:
        return []
    min_s = min(scores)
    max_s = max(scores)
    if max_s == min_s:
        return [50.0] * len(scores)
    return [round((s - min_s) / (max_s - min_s) * 100, 1) for s in scores]


def compute_trend_direction(current_heat: float, previous_heat: float) -> str:
    if previous_heat == 0:
        return "rising"
    change_pct = (current_heat - previous_heat) / previous_heat * 100
    if change_pct > 5:
        return "rising"
    elif change_pct < -5:
        return "falling"
    return "stable"
