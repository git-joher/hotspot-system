# Global Hotspot Aggregator — Design Spec

**Date:** 2026-05-19
**Status:** Approved

## Overview

Personal-use web dashboard that aggregates global hot events and trending topics from multiple platforms, enriches them with LLM (classification, translation, summarization), and presents them with temporal and quantitative data across multiple time granularities.

## Requirements Summary

| Dimension | Scope |
|-----------|-------|
| Data Sources | News media, social media, search trends, video platforms, tech communities — all major platforms |
| Languages | Chinese, English, Japanese, Korean, European, Southeast Asian — unified to Chinese via LLM translation |
| Time Granularity | Real-time (10-15min), Hourly, Daily Summary, On-demand — 4 tabs |
| Categories | AI auto-classification by topic, by source platform, by region, by heat score |
| Presentation | Web dashboard with ECharts visualizations |
| Audience | Personal use, single user |

## Architecture

Python monolithic application, six layers:

```
Browser Dashboard  ←  ECharts + Jinja2 templates
       │
   FastAPI          ←  REST API + page routes + static serving
       │
┌──────┼────────┬──────────┐
│ Scheduler    │ Pipeline  │  LLM Service     │
│ APScheduler  │ Processor │  Classification  │
│              │           │  Translation     │
│              │           │  Summarization   │
└──────┼────────┴──────────┘
       │
   SQLite           ←  Events, snapshots, categories, relations
       │
   Data Collectors  ←  httpx + APIs + scraping
```

**Tech stack:** Python, FastAPI, SQLite, Jinja2, ECharts, APScheduler, LLM API (Claude Haiku / GPT-4o-mini)

**Data flow:** Platform APIs → Collect & Store → LLM Classify/Translate → Heat Score & Deduplicate → API/Render → Dashboard

## Data Model

5 core tables in SQLite:

- **events** — Hot event master table (id, title, description, url, source_platform, language, region, title_cn, summary_cn, first_seen_at, last_updated_at)
- **event_snapshots** — Heat snapshots for time-series (event_id, heat_score 0-100, mention_count, source_rank, trend_direction, snapshot_at)
- **categories** — Category tags (id, name, slug, icon)
- **event_categories** — Event-category association (event_id, category_id, confidence)
- **event_relations** — Cross-platform dedup links (event_a_id, event_b_id, relation_type, confidence)

Quantitative metrics: heat_score, mention_count, source_rank, trend_direction (rising/falling/stable), growth_rate %

## Data Collection

| Platform | Method | Frequency |
|----------|--------|-----------|
| Twitter/X | X API v2 | 15 min |
| Reddit | Reddit API | 15 min |
| Hacker News | Firebase API | 15 min |
| GitHub Trending | httpx scraping | 1 hour |
| Google Trends | pytrends / RSS | 1 hour |
| Weibo Hot Search | httpx scraping | 10 min |
| Zhihu Hot List | httpx scraping | 15 min |
| Baidu Hot Search | httpx scraping | 15 min |
| YouTube | YouTube Data API v3 | 1 hour |
| NewsAPI | REST API | 1 hour |
| RSS feeds | feedparser | 30 min |

## Processing Pipeline

Raw data → Normalize → Language detection → LLM translate to Chinese → LLM topic classification → Dedup & merge → Unified heat scoring → Store in SQLite

LLM processing in batches (~50 items per call) to reduce cost. Single prompt handles translation + classification + dedup judgment + summary. Estimated $0.5-2/day API cost.

Dedup: semantic judgment by LLM across platforms. Same event across platforms merged into one event record. Composite heat = weighted average of per-platform normalized scores.

## Dashboard Design

**Main page layout:**

- **Top bar:** Time granularity tabs (Real-time / Hourly / Daily / On-demand) + last update timestamp
- **Stats cards row:** Total hot events today, rising trends count, regions covered, category count
- **Left column (60%):** Ranked hot topics list — each item shows rank, title, category tag, heat score, cross-platform coverage count. Sortable by heat / source / category
- **Right column (40%):** 3 ECharts — category distribution (pie), 24h heat trends top 5 (line), regional breakdown (bar)

**Detail page (click any event):**

- AI-generated Chinese summary integrating multi-source info
- 24h / 7d heat trend chart (ECharts area chart)
- Per-platform coverage: rank, discussion volume, links
- Related events identified by LLM

## Scheduling Strategy

| Tab | Behavior |
|-----|----------|
| Real-time | Latest 15-min snapshot, sorted by current heat |
| Hourly | Aggregated hourly window, average heat + trend |
| Daily | Day summary, "hottest today" + historical comparison |
| On-demand | "Refresh now" triggers full collection run |

## Project Structure (Target)

```
hotspot-system/
├── app/
│   ├── main.py              # FastAPI app entry
│   ├── collectors/           # Per-platform data collectors
│   ├── pipeline/             # Processing pipeline
│   ├── models/               # SQLite models
│   ├── routes/               # API + page routes
│   ├── templates/            # Jinja2 templates
│   └── static/               # ECharts, CSS, JS
├── data/
│   └── hotspot.db            # SQLite database
├── config.py                 # Configuration
├── requirements.txt
└── run.py                    # Entry point
```
