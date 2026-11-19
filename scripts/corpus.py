"""Store every dated insurance candidate before daily editorial selection."""
from datetime import datetime
import hashlib
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from update_news import atomic_json, canonical_url, clean, has_keyword, parse_date, news_text

START = "2026-10-01"
SEOUL = ZoneInfo("Asia/Seoul")


def normalize_candidate(article, config, now):
    stamp = parse_date(article.get("published_at", ""))
    title = clean(article.get("title", ""))
    if not stamp or stamp > now or stamp.astimezone(SEOUL).date().isoformat() < START:
        return None
    if not any(has_keyword(title, k) for k in config.get("context_keywords", ["보험"])):
        return None
    url = canonical_url(article["url"])
    excerpt = article.get("description") or article.get("_rss_text") or article.get("summary") or ""
    if article.get("summary_parts"):
        excerpt = " ".join(article["summary_parts"].values())
    return {"id": hashlib.sha256(url.encode()).hexdigest()[:12], "title": title,
            "url": url, "source": article["source"], "source_group": article.get("source_group", "specialist"),
            "published_at": stamp.astimezone(SEOUL).isoformat(),
            "description": news_text(excerpt)[:1000]}


def save_candidates(root: Path, candidates: list, config: dict, now: datetime):
    by_day = {}
    for article in candidates:
        row = normalize_candidate(article, config, now)
        if row:
            by_day.setdefault(row["published_at"][:10], []).append(row)
    for day, rows in by_day.items():
        path = root / "data/articles" / (day + ".json")
        prior = json.loads(path.read_text()) if path.exists() else []
        merged = {r["url"]: r for r in prior}
        for row in rows:
            old = merged.get(row["url"])
            if old and len(old.get("description", "")) > len(row["description"]):
                row["description"] = old["description"]
            merged[row["url"]] = row
        atomic_json(path, sorted(merged.values(), key=lambda r:(r["published_at"], r["url"]), reverse=True))
    return sum(len(v) for v in by_day.values())
