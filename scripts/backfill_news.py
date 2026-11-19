"""Reconstruct dated news from publishers' public archive listings.

These are explicitly backfilled records, never fabricated past scheduled runs.
"""
import argparse
import concurrent.futures
from datetime import date, datetime, time, timedelta
import json
import logging
from pathlib import Path
import re
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

from update_news import (ROOT, HEADERS, atomic_json, canonical_url, clean, news_text,
                         select_articles, enrich_public_extracts, SUMMARY_VERSION, rebuild_archive)

SEOUL = ZoneInfo("Asia/Seoul")
PUBLISHERS = [
    {"name": "보험저널", "url": "https://www.insjournal.co.kr/news/articleList.html", "group": "specialist"},
    {"name": "한국보험신문", "url": "https://www.insnews.co.kr/news/articleList.html", "group": "specialist"},
    {"name": "보험신보", "url": "https://www.insweek.co.kr/news/articleList.html", "group": "specialist"},
    {"name": "서울파이낸스", "url": "https://www.seoulfn.com/news/articleList.html", "group": "general", "section": "S2N5"},
]


def parse_listing(page: str, publisher: dict, day: date) -> list[dict]:
    section = re.search(r'<(section|article)\b[^>]*\bid=["\']section-list["\'][^>]*>(.*?)</\1>', page, re.I | re.S)
    if not section:
        raise ValueError("Publisher archive list not found")
    result = []
    for block in re.findall(r'<li\b[^>]*>(.*?)</li>', section.group(2), re.I | re.S):
        title = re.search(r'<h[234]\b[^>]*class=["\'][^"\']*\b(?:titles|altlist-subject)\b[^"\']*["\'][^>]*>(.*?)</h[234]>', block, re.I | re.S)
        link = re.search(r'href=["\']([^"\']*articleView\.html\?[^"\']+)["\']', block, re.I)
        stamp = re.search(r'(20\d{2})[.-](\d{2})[.-](\d{2})\s+(\d{2}):(\d{2})', clean(block))
        if not stamp:
            # New publisher templates omit the year within a day-filtered list.
            # Only accept that form if the returned page retains the requested range.
            if not re.search(r'sc_sdate[^\n]{0,20}'+re.escape(day.isoformat()), page):
                continue
            short_stamp = re.search(r'(?<![\d.-])(\d{2})-(\d{2})\s+(\d{2}):(\d{2})(?!\d)', clean(block))
            stamp_values = (day.year, *map(int, short_stamp.groups())) if short_stamp else None
        else:
            stamp_values = tuple(map(int, stamp.groups()))
        if not title or not link or not stamp_values:
            continue
        y, m, d, h, minute = stamp_values
        published = datetime(y, m, d, h, minute, tzinfo=SEOUL)
        if published.date() != day:
            continue
        lead = re.search(r'<(?:p|div)\b[^>]*class=["\'][^"\']*\b(?:lead|altlist-summary)\b[^"\']*["\'][^>]*>(.*?)</(?:p|div)>', block, re.I | re.S)
        url = canonical_url(urllib.parse.urljoin(publisher["url"], link.group(1).replace("&amp;", "&")))
        if urllib.parse.urlsplit(url).hostname != urllib.parse.urlsplit(publisher["url"]).hostname:
            continue
        result.append({"title": clean(title.group(1)), "url": url, "source": publisher["name"],
                       "source_group": publisher["group"], "published_at": published.isoformat(),
                       "description": news_text(lead.group(1)) if lead else ""})
    return result


def collect_day(publisher: dict, day: date, pages: int, cache_dir: Path) -> dict:
    cache = cache_dir / f"{day.isoformat()}-{publisher['name']}.json"
    if cache.exists():
        return json.loads(cache.read_text())
    records, listing_urls, seen = [], [], set()
    try:
        for page_number in range(1, pages + 1):
            query = {"sc_sdate": day.isoformat(), "sc_edate": day.isoformat(), "view_type": "sm", "page": page_number}
            if publisher.get("section"):
                query["sc_sub_section_code"] = publisher["section"]
            url = publisher["url"] + "?" + urllib.parse.urlencode(query)
            request = urllib.request.Request(url, headers={**HEADERS, "Accept": "text/html"})
            with urllib.request.urlopen(request, timeout=20) as response:
                raw = response.read(2_000_001)
                charset = response.headers.get_content_charset() or "utf-8"
            if len(raw) > 2_000_000:
                raise ValueError("Archive list exceeds size limit")
            rows = parse_listing(raw.decode(charset, errors="replace"), publisher, day)
            listing_urls.append(url)
            fresh = [r for r in rows if r["url"] not in seen]
            if not fresh:
                break
            records.extend(fresh)
            seen.update(r["url"] for r in fresh)
            if len(rows) < 20:
                break
        value = {"source": publisher["name"], "day": day.isoformat(), "success": True,
                 "listing_urls": listing_urls, "articles": records}
        atomic_json(cache, value)
        return value
    except Exception as error:
        return {"source": publisher["name"], "day": day.isoformat(), "success": False,
                "listing_urls": listing_urls, "articles": records, "error": type(error).__name__}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=date.fromisoformat, required=True)
    parser.add_argument("--end", type=date.fromisoformat, required=True)
    parser.add_argument("--pages", type=int, default=2)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    now = datetime.now(SEOUL)
    if args.start > args.end or args.end > now.date() or (args.end - args.start).days > 31:
        raise ValueError("Backfill range must be at most 32 past/current dates")
    config = json.loads((ROOT / "config.json").read_text())
    days = [args.start + timedelta(days=i) for i in range((args.end - args.start).days + 1)]
    batches = {d.isoformat(): [] for d in days}
    cache_dir = ROOT / ".cache" / "backfill"
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        jobs = [pool.submit(collect_day, p, d, args.pages, cache_dir) for d in days for p in PUBLISHERS]
        for job in concurrent.futures.as_completed(jobs):
            batch = job.result()
            batches[batch["day"]].append(batch)
            print(batch["day"], batch["source"], len(batch["articles"]), "OK" if batch["success"] else batch["error"], flush=True)
    latest = json.loads((ROOT / "data/latest.json").read_text())
    report = {"start": args.start.isoformat(), "end": args.end.isoformat(), "collected_at": now.isoformat(timespec="seconds"),
              "method": "publisher_archive_calendar_day", "scheduled_run_evidence": False, "days": []}
    for day in days:
        key = day.isoformat()
        groups = batches[key]
        candidates = list({r["url"]: r for group in groups for r in group["articles"]}.values())
        cutoff = min(now, datetime.combine(day + timedelta(days=1), time.min, SEOUL))
        selection_config = {**config, "max_age_hours": 24}
        articles = select_articles(candidates, selection_config, cutoff)
        enrich_public_extracts(articles, config["feeds"])
        for article in articles:
            article.pop("_rss_text", None)
        warnings = [g["source"] + " 목록 수집 실패" for g in groups if not g["success"]]
        successes = sorted({g["source"] for g in groups if g["success"]})
        entry = {"date": key, "candidates": len(candidates), "verified_articles": len(articles),
                 "successful_sources": successes, "warnings": warnings,
                 "listing_urls": [u for g in groups for u in g["listing_urls"]]}
        # Today's genuine live edition stays authoritative; the report records its separate archive check.
        if key == latest["date"] and day == now.date():
            entry.update(displayed_articles=len(latest["articles"]), display_mode="existing_live_edition")
        else:
            edition = {"date": key, "updated_at": now.isoformat(timespec="seconds"), "collected_at": now.isoformat(timespec="seconds"),
                       "summary_version": SUMMARY_VERSION, "title": articles[0]["title"] if articles else f"{key} · 확인된 보험 관련 기사 없음",
                       "demo": False, "mode": "rss", "backfilled": True, "collection_method": "publisher_archive_calendar_day",
                       "article_window": {"start": key + "T00:00:00+09:00", "end": cutoff.isoformat()},
                       "sources": successes, "warnings": warnings, "articles": articles,
                       "collection": {"configured": sorted(p["name"] for p in PUBLISHERS), "succeeded": successes,
                                      "selected": sorted({a["source"] for a in articles}), "items_received": len(candidates)}}
            atomic_json(ROOT / "data/editions" / (key + ".json"), edition)
            entry.update(displayed_articles=len(articles), display_mode="backfilled")
        report["days"].append(entry)
    rebuild_archive(ROOT)
    atomic_json(ROOT / "data/backfill-report.json", report)
    print("Backfill dates:", len(report["days"]), "displayed articles:", sum(d["displayed_articles"] for d in report["days"]), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
