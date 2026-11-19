"""Reconstruct dated news from publishers' public archive listings.

These are explicitly backfilled records, never fabricated past scheduled runs.
"""
import argparse
import concurrent.futures
from datetime import date, datetime, time, timedelta
import json
import logging
import math
from pathlib import Path
import re
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo
from corpus import save_candidates

from update_news import (ROOT, HEADERS, atomic_json, canonical_url, clean, news_text,
                         select_articles, enrich_public_extracts, SUMMARY_VERSION, rebuild_archive, PublicArticleBody)

SEOUL = ZoneInfo("Asia/Seoul")
PUBLISHERS = [
    {"name": "보험저널", "url": "https://www.insjournal.co.kr/news/articleList.html", "group": "specialist"},
    {"name": "한국보험신문", "url": "https://www.insnews.co.kr/news/articleList.html", "group": "specialist"},
    {"name": "보험신보", "url": "https://www.insweek.co.kr/news/articleList.html", "group": "specialist"},
    {"name": "서울파이낸스", "url": "https://www.seoulfn.com/news/articleList.html", "group": "general"},
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


def read_public(url, referer=None):
    headers = {**HEADERS, "Accept": "application/json" if referer else "text/html"}
    if referer:
        headers.update({"Referer": referer, "X-Requested-With": "XMLHttpRequest"})
    for attempt in range(2):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=20) as response:
                raw = response.read(2_000_001)
                charset = response.headers.get_content_charset() or "utf-8"
            if len(raw) > 2_000_000:
                raise ValueError("Archive list exceeds size limit")
            return raw.decode(charset, errors="replace")
        except Exception:
            if attempt:
                raise


def listing_total(page):
    matches = [r'altlist-count[^>]*>.*?<strong>([\d,]+)</strong>', r'전체기사\s*\(?\s*([\d,]+)',
               r'["\']total["\']\s*[:\]]\s*(?:=\s*)?["\']?(\d+)']
    for pattern in matches:
        match = re.search(pattern, page, re.I | re.S)
        if match:
            return int(match.group(1).replace(",", ""))
    return None


def parse_ajax(value, publisher, day):
    if value.get("result") != "success":
        raise ValueError("Public paging response unavailable")
    result = []
    for item in value.get("data", []):
        raw_date = str(item.get("pub_date", ""))
        display_day = str(item.get("viewDate", "")).strip().replace(".", "-")
        # Newspapers can write an issue several days before its displayed publication date.
        if display_day not in (day.strftime("%m-%d"), day.isoformat()):
            continue
        clock = str(item.get("viewTime", "00:00"))[:5]
        stamp = datetime.fromisoformat(day.isoformat() + "T" + clock).replace(tzinfo=SEOUL)
        if not str(item.get("idxno", "")).isdigit():
            continue
        decode = lambda key: news_text(urllib.parse.unquote(str(item.get(key, ""))))
        result.append({"title": decode("title"), "description": decode("summary"),
                       "url": urllib.parse.urljoin(publisher["url"], "articleView.html?idxno=" + str(item["idxno"])),
                       "source": publisher["name"], "source_group": publisher["group"], "published_at": stamp.isoformat()})
    return result


def verify_public_article(publisher, day, article_id):
    """Read original metadata for a missing article near a public day-list boundary."""
    url=urllib.parse.urljoin(publisher['url'],'articleView.html?idxno='+str(article_id))
    try:
        page=read_public(url)
        if re.search(r'"isAccessibleForFree"\s*:\s*(?:false|"false")',page,re.I):
            return None
        stamp=re.search(r'<meta\b[^>]*property=["\']article:published_time["\'][^>]*content=["\']([^"\']+)',page,re.I)
        title=re.search(r'<meta\b[^>]*property=["\']og:title["\'][^>]*content=["\']([^"\']+)',page,re.I)
        if not stamp or not title:
            return None
        published=datetime.fromisoformat(stamp.group(1)).astimezone(SEOUL)
        if published.date()!=day:
            return None
        parser=PublicArticleBody();parser.feed(page)
        return {'title':clean(title.group(1)).removesuffix(' - '+publisher['name']),
                'url':url,'source':publisher['name'],'source_group':publisher['group'],
                'published_at':published.isoformat(),'description':news_text(' '.join(parser.parts))[:1000],
                'date_verified_by':'article:published_time'}
    except Exception:
        return None


def recover_list_gaps(publisher,day,records,total):
    if publisher['name']!='보험신보' or total is None or not 0<total-len(records)<=12:
        return []
    ids={int(urllib.parse.parse_qs(urllib.parse.urlsplit(r['url']).query)['idxno'][0]) for r in records}
    if not ids or max(ids)-min(ids)>200:
        return []
    # Some older lists repeat page 2. Check bounded gaps and the small adjoining
    # tail, accepting only original metadata that confirms the requested date.
    missing=list(range(min(ids)-1,min(ids)-min(32,(total-len(records))*3)-1,-1))
    missing += [i for i in range(min(ids),max(ids)+1) if i not in ids]
    recovered=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for offset in range(0,len(missing),4):
            rows=list(pool.map(lambda i:verify_public_article(publisher,day,i),missing[offset:offset+4]))
            recovered.extend(r for r in rows if r)
            if len(recovered)>=total-len(records):
                break
    return recovered


def collect_day(publisher: dict, day: date, pages: int, cache_dir: Path) -> dict:
    cache = cache_dir / f"{day.isoformat()}-{publisher['name']}.json"
    previous = None
    if cache.exists():
        previous = json.loads(cache.read_text())
        version = 3 if publisher["name"] == "보험저널" else 5
        if (previous.get("collector_version") == version and previous.get("complete")
            and (previous.get('listed_total') is None or len(previous.get('articles',[]))>=previous['listed_total'])
            and day < datetime.now(SEOUL).date()):
            return previous
    records, listing_urls, seen = [], [], set()
    try:
        first_page, total, ajax = None, None, False
        exhausted = False
        for page_number in range(1, pages + 1):
            query = {"sc_sdate": day.isoformat(), "sc_edate": day.isoformat(), "view_type": "sm", "page": page_number}
            if publisher.get("section"):
                query["sc_sub_section_code"] = publisher["section"]
            url = publisher["url"] + "?" + urllib.parse.urlencode(query)
            if first_page is None:
                first_page = read_public(url)
                total = listing_total(first_page)
                ajax = "altlist-body" in first_page
                if previous and previous.get('complete') and total is not None and day < datetime.now(SEOUL).date():
                    # Older caches used database draft dates for the first page.
                    # Recheck the displayed publication dates; reuse later-page excerpts
                    # only when the union reaches the publisher's declared total.
                    combined = {r['url']:r for r in previous['articles']}
                    for row in parse_listing(first_page,publisher,day):
                        old = combined.get(row['url'])
                        if old and len(old.get('description',''))>len(row.get('description','')):
                            row['description'] = old['description']
                        combined[row['url']] = row
                    if len(combined)==total:
                        upgraded = {**previous,'articles':list(combined.values()),'listed_total':total,
                                    'collector_version':version,'listing_urls':list(dict.fromkeys([url]+previous.get('listing_urls',[])))}
                        atomic_json(cache,upgraded)
                        return upgraded
            if ajax and page_number > 1:
                params = {**query, "total": total or 0, "list_per_page": 20, "page_per_page": 10, "box_idxno": 0}
                url = urllib.parse.urljoin(publisher["url"], "ajaxArticlePaging.php") + "?" + urllib.parse.urlencode(params)
                value = json.loads(read_public(url, publisher["url"] + "?" + urllib.parse.urlencode(query)))
                rows = parse_ajax(value, publisher, day)
                batch_size = len(value.get("data", []))
            else:
                page = first_page if page_number == 1 else read_public(url)
                rows = parse_listing(page, publisher, day)
                batch_size = len(rows)
            listing_urls.append(url)
            fresh = [r for r in rows if r["url"] not in seen]
            if not fresh:
                if rows:
                    break
                exhausted=True
                break
            records.extend(fresh)
            seen.update(r["url"] for r in fresh)
            if batch_size < 20:
                exhausted = True
                break
            if total is not None and len(records) >= total:
                exhausted = True
                break
        recovered=recover_list_gaps(publisher,day,records,total)
        if recovered:
            records.extend(recovered)
            listing_urls.extend(r['url'] for r in recovered)
            exhausted=len(records)>=total
        if not exhausted:
            raise ValueError("Archive page limit reached before completion")
        if total is not None and len(records)<total:
            raise ValueError(f"Archive count mismatch: {len(records)} of {total}")
        value = {"source": publisher["name"], "day": day.isoformat(), "success": True, "complete": True,
                 "collector_version": 3 if publisher["name"] == "보험저널" else 5,
                 "listed_total": total,
                 "listing_urls": listing_urls, "articles": records}
        atomic_json(cache, value)
        return value
    except Exception as error:
        return {"source": publisher["name"], "day": day.isoformat(), "success": False,
                "listing_urls": listing_urls, "articles": records, "complete": False, "error": str(error)[:120]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=date.fromisoformat)
    parser.add_argument("--end", type=date.fromisoformat)
    parser.add_argument("--recent-days", type=int)
    parser.add_argument("--pages", type=int, default=20)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--skip-enrichment", action="store_true")
    args = parser.parse_args()
    now = datetime.now(SEOUL)
    if args.recent_days:
        if not 1 <= args.recent_days <= 7:
            raise ValueError("recent-days must be between 1 and 7")
        args.end = now.date()
        args.start = args.end - timedelta(days=args.recent_days-1)
    if not args.start or not args.end:
        parser.error("Provide --start and --end, or --recent-days")
    if args.start > args.end or args.end > now.date() or (args.end - args.start).days > 365:
        raise ValueError("Backfill range must be at most 366 past/current dates")
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
    enrich_jobs = []
    pending_editions = []
    for day in days:
        key = day.isoformat()
        groups = batches[key]
        candidates = list({r["url"]: r for group in groups for r in group["articles"]}.values())
        saved = save_candidates(ROOT, candidates, config, now)
        corpus_path = ROOT / 'data/articles' / (key+'.json')
        if not corpus_path.exists():
            atomic_json(corpus_path,[])
        cutoff = min(now, datetime.combine(day + timedelta(days=1), time.min, SEOUL))
        selection_config = {**config, "max_age_hours": 24}
        articles = select_articles(candidates, selection_config, cutoff)
        prior_path = ROOT/'data/editions'/(key+'.json')
        if prior_path.exists():
            prior_rows = {a['url']:a for a in json.loads(prior_path.read_text()).get('articles',[])}
            for article in articles:
                old = prior_rows.get(article['url'])
                if old and old.get('summary_basis')=='public_article_excerpt' and old['title']==article['title']:
                    for field in ('summary','summary_parts','summary_basis','source_digest'):
                        if field in old:article[field]=old[field]
                    article['_rss_text']=' '.join(article['summary_parts'].values())
        warnings = [g["source"] + " 목록 수집 실패" for g in groups if not g["success"]]
        successes = sorted({g["source"] for g in groups if g["success"]})
        entry = {"date": key, "candidates": len(candidates), "verified_articles": len(articles),
                 "stored_articles": saved, "coverage": [{k:v for k,v in g.items() if k != "articles"} for g in groups],
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
            pending_editions.append((key, edition))
            entry.update(displayed_articles=len(articles), display_mode="backfilled")
        report["days"].append(entry)
    if not args.skip_enrichment:
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(lambda pair: enrich_public_extracts(pair[1]["articles"], config["feeds"]), pending_editions))
    for key, edition in pending_editions:
        for article in edition["articles"]:
            article.pop("_rss_text", None)
        save_candidates(ROOT,edition['articles'],config,now)
        atomic_json(ROOT / "data/editions" / (key + ".json"), edition)
    rebuild_archive(ROOT)
    atomic_json(ROOT / "data/backfill-report.json", report)
    print("Backfill dates:", len(report["days"]), "displayed articles:", sum(d["displayed_articles"] for d in report["days"]), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
