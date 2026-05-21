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
3. **影响点**：分析该事件最重要的 3 个影响或新闻价值点（impact_points），每条20字以内
4. **个人影响**：分析该事件对个人的财富机会和投资影响（personal_impact）。重点关注：可购买的股票/基金、相关概念股、加密货币、行业机会等。每条20字以内，按价值从高到低排列，最多3条。若事件与个人财富无关则返回空数组[]
5. **实体影响**：提取事件中涉及的具名实体（entities）。type 从以下选择：股票、公司、行业、加密货币、ETF、基金、商品、人物、政党、机构、国际组织、国家、产品、品牌。

**重要** — action 必须按实体类型区分：
- 投资类（股票/公司/行业/加密货币/ETF/基金/商品）→ action 用：买入 / 卖出 / 观望
- 非投资类（人物/政党/机构/国际组织/国家/产品/品牌）→ action 用：高涨 / 低落 / 平稳

格式：[{{"entity": "微软", "type": "股票", "impact_score": -0.7, "direction": "negative", "action": "卖出"}}, {{"entity": "特朗普", "type": "人物", "impact_score": -0.5, "direction": "negative", "action": "低落"}}]
impact_score范围-1到1，负值=利空/负面，正值=利好/正面。最多3个实体，若无关则返回空数组[]
6. **分类**：从以下类别中选择最匹配的 1-2 个：{categories_str}。提供类别名称、slug 和置信度(0-1)
7. **去重判断**：如果此事件与列表中其他事件是同一话题（不同平台报道），在 is_duplicate_of 中填写那个事件的 index，否则填 null
8. **全球热度评分**：综合评估 global_heat 0-100，考虑跨平台传播和讨论量

返回格式：
[{{"index": 0, "title_cn": "...", "summary_cn": "...", "impact_points": ["影响1", "影响2", "影响3"], "personal_impact": ["买入SpaceX股票", "关注商业航天ETF", "布局卫星互联网概念股"], "entities": [{{"entity": "SpaceX", "type": "股票", "impact_score": 0.9, "direction": "positive", "action": "买入"}}], "categories": [{{"name": "...", "slug": "...", "confidence": 0.9}}], "is_duplicate_of": null, "global_heat": 85}}]

只返回 JSON 数组，不要有其他文字。"""


def build_prediction_prompt(events: list[dict], entities: list[dict]) -> str:
    events_json = json.dumps(
        [{"title_cn": e.get("title_cn", ""), "title": e.get("title", ""),
          "summary_cn": e.get("summary_cn", ""), "source_platform": e.get("source_platform", "")}
         for e in events[:20]],
        ensure_ascii=False, indent=2,
    )
    entities_json = json.dumps(
        [{"entity": e.get("entity", ""), "type": e.get("type", ""),
          "signal": e.get("signal_label", ""), "total_impact": e.get("total_impact", 0)}
         for e in entities[:15]],
        ensure_ascii=False, indent=2,
    )

    return f"""你是一位全球投资策略师。你需要基于当前热点事件和实体影响趋势，预测未来可能发生的重大事件及其财富机会。

当前热点事件（最近24小时）：
{events_json}

当前实体影响趋势（投资信号）：
{entities_json}

请从你的知识中找到 **未来1天到1个月内** 将要发生或极可能发生的全球重大事件（如体育赛事、选举、财报季、政策会议、产品发布、行业活动等）。可以结合当前热点中提到的"计划"、"将于"等线索，也可以从你的训练数据中检索已知日程。

对每个事件，给出：
1. **事件名称** (event_title)：简洁中文描述
2. **时间窗口** (timeframe)：如 "2026年6月"、"下周"
3. **预测情景** (scenario)：该事件最可能引发的财富机会，30字以内
4. **概率标签** (probability_label)：极高 / 较高 / 可能
5. **概率值** (probability)：0-1，辅助排序用
6. **推理依据** (reasoning)：结合历史模式说明，如"过去5届世界杯赛前1月，啤酒股平均涨12%"。50字以内
7. **受影响实体** (entities)：具体的公司/股票/行业/加密货币等，附带投资建议。格式：[{{"entity": "百威英博", "type": "股票", "action": "买入", "impact_score": 0.7}}]。impact_score -1到1
8. **财富排名** (wealth_rank)：按财富机会从高到低的序号，从1开始

只返回最值得关注的 5-8 条预测。返回 JSON 数组：

[{{"event_title": "2026世界杯开幕", "timeframe": "2026年6月", "scenario": "啤酒饮料消费股短期上涨", "probability": 0.80, "probability_label": "极高", "reasoning": "过去5届世界杯赛前1月啤酒股平均涨12%，夏季消费旺季叠加赛事效应", "entities": [{{"entity": "百威英博", "type": "股票", "action": "买入", "impact_score": 0.7}}], "wealth_rank": 1}}]

只返回 JSON 数组，不要有其他文字。"""


def parse_llm_response(response_text: str, expected_count: int = 0) -> list[dict]:
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
        if not events or not getattr(self.client, 'api_key', None):
            return []

        prompt = build_classification_prompt(events)

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=12000,
                timeout=60,
            )
            content = response.choices[0].message.content
            if not content:
                logger.warning("LLM returned empty content")
                return []
            return parse_llm_response(content, len(events))
        except Exception as e:
            logger.error(f"LLM API call failed: {e}")
            return []

    async def predict_opportunities(self, events: list[dict],
                                     entities: list[dict]) -> list[dict]:
        if not events or not getattr(self.client, 'api_key', None):
            return []

        prompt = build_prediction_prompt(events, entities)

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.4,
                max_tokens=8000,
                timeout=90,
            )
            content = response.choices[0].message.content
            if not content:
                logger.warning("LLM returned empty prediction content")
                return []
            return parse_llm_response(content)
        except Exception as e:
            logger.error(f"LLM prediction call failed: {e}")
            return []
