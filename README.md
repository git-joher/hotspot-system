# Hotspot · 全球热点雷达

实时聚合全球 11+ 平台热点事件，通过 LLM 智能分析生成中文摘要、影响点、财富机会和实体投资信号，提供多维度排序与未来预测的个人投资情报看板。

## 功能

### 热点采集
自动采集 11 个平台的实时热点趋势：

| 平台 | 类型 | 说明 |
|---|---|---|
| Hacker News | 英文科技 | IT 技术社区头条 |
| GitHub Trending | 英文科技 | 开源项目热门趋势 |
| Reddit r/all | 英文综合 | 全站热门话题 |
| BBC / NYT / NHK | 英文/日文 | 国际新闻 RSS |
| 微博 | 中文社交 | 微博热搜（需代理） |
| 知乎 | 中文问答 | 知乎热榜（需代理） |
| 百度 | 中文综合 | 百度实时热搜 |
| Google Trends | 全球搜索 | 搜索趋势 |
| NewsAPI | 多语言 | 综合新闻 |
| Twitter/X | 全球社交 | 趋势话题（需 API Key） |
| YouTube | 视频 | 热门视频（需 API Key） |

每 15 分钟自动采集一轮，无障碍的海外平台可直接使用。

### LLM 智能分析
每条事件通过 DeepSeek v4-pro（兼容 OpenAI API）完成 8 项分析：

| 分析项 | 说明 |
|---|---|
| 中文翻译 | 标题翻译为中文 |
| 摘要 | 30 字以内中文摘要 |
| 影响点 ×3 | 3 个关键新闻价值点 |
| 财富机会 | 与个人投资相关的机会，按价值排序 |
| 实体影响 | 涉及的股票/公司/人物，含影响方向和操作建议 |
| 分类 | 匹配到 15 个预定义类别 |
| 去重 | 跨平台同一话题自动合并 |
| 热度评分 | 综合评估全球热度 0-100 |

### 多维度排行

- **热度排序** — 按全球热度从高到低，含趋势方向（上升/下降）
- **财富机会** — 按个人投资价值排序，直接列出可操作建议
- **实体影响** — 跨事件聚合实体影响度，生成投资/态势双轨信号
  - 投资轨（股票/公司/行业/加密货币）→ 买入/卖出/观望
  - 态势轨（人物/政党/机构/国家）→ 高涨/低落/平稳
- **按来源** — 按平台分组查看
- **按时间** — 最新优先

### 未来预测

基于 LLM 训练数据中的历史模式 + 当前热点态势 + 已知未来事件日程，生成概率化投资预测：

- 识别未来 1 天到 1 个月内的重大事件（赛事、财报、政策会议、产品发布等）
- 每条预测给出概率标签（极高/较高/可能）、推理依据、受影响实体及操作建议
- 每 6 小时自动刷新

### 可视化

- ECharts 分类热力饼图、24h 热度走势、地区热点柱状图
- 事件详情页含热度时间线、关联实体、来源分布、相关事件

## 架构

```
                    ┌──────────────────────────────┐
                    │        11+ 平台采集器          │
                    │  httpx async 并发请求          │
                    └──────────────┬───────────────┘
                                   │ raw items
                                   ▼
                    ┌──────────────────────────────┐
                    │      归一化 & 预处理           │
                    │  语言检测 / 地区推断 / 清洗    │
                    └──────────────┬───────────────┘
                                   │ normalized
                                   ▼
                    ┌──────────────────────────────┐
                    │        LLM 批处理             │
                    │  DeepSeek v4-pro (5条/批)     │
                    │  翻译/摘要/影响点/实体/分类    │
                    └──────────────┬───────────────┘
                                   │ enriched
                                   ▼
                    ┌──────────────────────────────┐
                    │       去重 & 评分             │
                    │  跨平台合并 / 热度归一化 /     │
                    │  趋势方向计算                  │
                    └──────────────┬───────────────┘
                                   │ final events
                                   ▼
                    ┌──────────────────────────────┐
                    │        SQLite 存储            │
                    │  WAL 模式 / 外键约束          │
                    │  事件 / 快照 / 分类 / 关联    │
                    │  实体聚合 / 未来预测           │
                    └──────────────┬───────────────┘
                                   │
                    ┌──────────────┴───────────────┐
                    │          Web 前端              │
                    │  FastAPI + Jinja2 + ECharts   │
                    │  Vanilla JS / 暗色主题         │
                    │  响应式布局 (桌面+移动)         │
                    └──────────────────────────────┘
```

**技术栈**：Python 3.11+ / FastAPI / SQLite (WAL) / httpx / APScheduler / DeepSeek v4-pro / ECharts / Vanilla JS

**项目结构**：

```
├── app/
│   ├── collectors/     # 11 个平台采集器
│   │   ├── base.py         # 采集器基类
│   │   ├── hackernews.py   # Hacker News
│   │   ├── github_trending.py
│   │   ├── reddit.py
│   │   ├── rss_feeds.py    # BBC/NYT/NHK
│   │   ├── weibo.py
│   │   ├── zhihu.py
│   │   ├── baidu.py
│   │   ├── newsapi.py
│   │   ├── twitter.py
│   │   ├── youtube.py
│   │   └── google_trends.py
│   ├── pipeline/
│   │   ├── normalizer.py   # 归一化 & 语言/地区检测
│   │   ├── llm_processor.py # LLM 批处理 & 预测
│   │   ├── dedup.py        # 跨平台去重
│   │   ├── scorer.py       # 热度归一化 & 趋势方向
│   │   └── orchestrator.py # 流水线编排
│   ├── routes/
│   │   ├── pages.py        # 页面路由
│   │   └── api.py          # API 路由
│   ├── static/
│   │   ├── css/style.css
│   │   └── js/dashboard.js
│   ├── templates/
│   │   ├── base.html
│   │   ├── index.html      # 主看板
│   │   └── detail.html     # 事件详情页
│   ├── database.py         # 数据库 schema & 操作
│   └── main.py             # 应用入口 & 调度
├── tests/
├── config.py               # 配置
├── run.py                  # 启动脚本
└── requirements.txt
```

## 部署

### 环境要求

- Python 3.11+
- DeepSeek API Key（或其他 OpenAI 兼容 API）
- 无障碍访问海外网站（用于 Reddit、GitHub、RSS 等采集器）

### 安装

```bash
git clone <repo-url>
cd hotspot-system
pip install -r requirements.txt
```

### 配置

```bash
cp .env.example .env
```

编辑 `.env`：

```env
# 必填：LLM API 配置（支持所有 OpenAI 兼容接口）
LLM_API_KEY=sk-your-api-key-here
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=deepseek-v4-pro

# 可选：各平台 API Key（不填则对应采集器自动跳过）
TWITTER_BEARER_TOKEN=
REDDIT_CLIENT_ID=
REDDIT_CLIENT_SECRET=
YOUTUBE_API_KEY=
NEWSAPI_KEY=
```

### 运行

```bash
python run.py
```

打开 `http://127.0.0.1:8000`。

首次启动会自动：
1. 创建 SQLite 数据库及表结构
2. 在后台运行一轮采集（约 102 条原始事件 → 5条/批 LLM 处理 → 逐批写入）
3. 启动 APScheduler，每 30 分钟自动采集，每 6 小时刷新预测

数据出现在看板上需要等待 1-3 分钟（取决于 LLM API 响应速度）。

### 配置项说明

`config.py` 中可调整：

| 配置 | 默认值 | 说明 |
|---|---|---|
| `LLM_API_KEY` | 环境变量 | LLM API 密钥 |
| `LLM_BASE_URL` | 环境变量 | LLM API 地址 |
| `LLM_MODEL` | 环境变量 | 模型名称 |
| `COLLECTION_INTERVAL_FAST` | 15 分钟 | 采集间隔 |
| `SNAPSHOT_RETENTION_DAYS` | 30 天 | 快照保留天数 |

## API

| 端点 | 方法 | 说明 |
|---|---|---|
| `/` | GET | 主看板页面 |
| `/event/{id}` | GET | 事件详情页 |
| `/api/stats` | GET | 统计数据（总数/上升/地区/分类） |
| `/api/events?timespan=&sort_by=&limit=` | GET | 事件列表（timespan: realtime/hourly/daily） |
| `/api/events/{id}` | GET | 事件详情含快照和关联 |
| `/api/entities?timespan=` | GET | 实体影响聚合排行 |
| `/api/categories` | GET | 分类列表 |
| `/api/predictions` | GET | 未来预测列表 |
| `/api/predictions/refresh` | POST | 触发预测刷新 |
| `/api/refresh` | POST | 触发即时采集 |
| `/api/search?q=` | GET | 事件搜索 |

## 数据库

SQLite + WAL 模式，核心表：

| 表 | 说明 |
|---|---|
| `events` | 热点事件（含 LLM 分析结果） |
| `event_snapshots` | 热度快照（时间序列） |
| `categories` | 分类字典 |
| `event_categories` | 事件-分类关联 |
| `event_relations` | 事件关联（跨平台合并） |
| `predictions` | 未来预测 |

## License

MIT
