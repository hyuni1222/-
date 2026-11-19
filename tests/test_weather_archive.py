from datetime import date, datetime
import json
from pathlib import Path
import sys
import tempfile
import unittest
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from backfill_news import parse_listing
from update_news import rebuild_archive
from update_weather import normalize_weather


class WeatherArchiveTests(unittest.TestCase):
    def setUp(self):
        self.day = date(2026, 11, 11)
        self.publisher = {"name": "테스트", "url": "https://example.com/news/articleList.html", "group": "general"}

    def test_archive_templates_filter_exact_day_and_external_links(self):
        page = '''<section id="section-list"><ul>
        <li><h2 class="titles"><a href="/news/articleView.html?idxno=1">보험 뉴스</a></h2><p class="lead">공개 요약</p><em>2026.11.11 08:00</em></li>
        <li><h2 class="titles"><a href="/news/articleView.html?idxno=2">다른 날</a></h2><em>2026.11.12 08:00</em></li>
        <li><h2 class="titles"><a href="https://external.com/news/articleView.html?idxno=3">외부</a></h2><em>2026.11.11 08:00</em></li>
        </ul></section>'''
        rows = parse_listing(page, self.publisher, self.day)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["published_at"], "2026-11-11T08:00:00+09:00")
        self.assertEqual(rows[0]["description"], "공개 요약")

    def test_short_year_template_requires_returned_date_range(self):
        body = '''<article id="section-list"><ul><li><h2 class="altlist-subject"><a href="/news/articleView.html?idxno=1">보험</a></h2><div class="altlist-info">11-11 09:00</div></li></ul></article>'''
        self.assertEqual(parse_listing(body, self.publisher, self.day), [])
        page = 'sc_sdate=2026-11-11&sc_edate=2026-11-11' + body
        self.assertEqual(len(parse_listing(page, self.publisher, self.day)), 1)
        self.assertEqual(parse_listing(page, self.publisher, date(2026, 11, 12)), [])

    def test_rebuilding_archive_keeps_backfill_markers_and_zero_count(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            editions = root / "data/editions"
            editions.mkdir(parents=True)
            (editions / "2026-11-11.json").write_text(json.dumps({"date":"2026-11-11", "title":"없음", "articles":[], "backfilled":True, "collected_at":"2026-11-19T09:00:00+09:00", "updated_at":"2026-11-19T09:00:00+09:00"}))
            rebuild_archive(root)
            row = json.loads((root / "data/archive.json").read_text())[0]
            self.assertTrue(row["backfilled"])
            self.assertEqual(row["count"], 0)
            self.assertEqual(row["collected_at"], "2026-11-19T09:00:00+09:00")

    def test_weather_uses_seoul_today_and_rejects_stale_or_invalid_forecast(self):
        now = datetime(2026,11,19,0,30,tzinfo=ZoneInfo("UTC"))
        raw = {"current":{"time":"2026-11-19T09:30", "temperature_2m":1.0, "weather_code":1, "is_day":1},"daily":{"time":["2026-11-19"],"temperature_2m_min":[-1.3],"temperature_2m_max":[4.7]}}
        value = normalize_weather(raw, now)
        self.assertEqual(value["date"], "2026-11-19")
        self.assertEqual(value["minimum"], -1.3)
        raw["daily"]["time"] = ["2026-11-18"]
        with self.assertRaises(ValueError): normalize_weather(raw, now)
        raw["daily"]["time"] = ["2026-11-19"]
        raw["daily"]["temperature_2m_min"] = [10]
        with self.assertRaises(ValueError): normalize_weather(raw, now)
