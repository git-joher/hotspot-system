from datetime import datetime, timezone


def truncate(text: str, max_len: int = 160) -> str:
    """Truncate text at word boundary for meta descriptions."""
    if not text or len(text) <= max_len:
        return text or ""
    cut = text.rfind(" ", 0, max_len - 3)
    if cut > max_len // 2:
        return text[:cut] + "..."
    return text[:max_len - 3] + "..."


def build_canonical_url(site_url: str, path: str) -> str:
    base = site_url.rstrip("/")
    path = path.lstrip("/")
    return f"{base}/{path}"


def build_website_schema(site_url: str, lang: str, name: str, description: str) -> dict:
    return {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": name,
        "description": description,
        "url": site_url.rstrip("/"),
        "inLanguage": lang,
    }


def build_newsarticle_schema(event: dict, site_url: str, lang: str) -> dict:
    title = event.get(f"title_{lang}") or event.get("title", "")
    description = event.get(f"summary_{lang}") or event.get("description", "")
    return {
        "@context": "https://schema.org",
        "@type": "NewsArticle",
        "headline": title,
        "description": truncate(description, 200),
        "url": build_canonical_url(site_url, f"/event/{event['id']}"),
        "datePublished": event.get("first_seen_at", ""),
        "dateModified": event.get("last_updated_at", ""),
        "inLanguage": lang,
    }


def iso_to_rfc2822(iso_str: str) -> str:
    """Convert ISO 8601 to RFC 2822 for RSS pubDate."""
    if not iso_str:
        return ""
    try:
        dt = datetime.fromisoformat(iso_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.strftime("%a, %d %b %Y %H:%M:%S %z")
    except (ValueError, TypeError):
        return iso_str
