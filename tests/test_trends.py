from datetime import date, datetime
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from backfill_news import collect_day,parse_ajax,verify_public_article
from build_trends import build,period_bounds,representatives,theme_for
from corpus import save_candidates

SEOUL=ZoneInfo('Asia/Seoul')


class TrendTests(unittest.TestCase):
    def test_calendar_boundaries_include_partial_first_week_and_leap_month(self):
        self.assertEqual(period_bounds(date(2026,10,1),'weekly'),(date(2026,9,28),date(2026,10,4)))
        self.assertEqual(period_bounds(date(2024,2,17),'monthly'),(date(2024,2,1),date(2024,2,29)))

    def test_public_issue_date_is_used_instead_of_draft_date(self):
        publisher={'name':'보험신보','url':'https://example.com/news/articleList.html','group':'specialist'}
        value={'result':'success','data':[{'idxno':1,'pub_date':'2026-10-01','viewDate':'10-05','viewTime':'00:00','title':'GA 기사','summary':'공개 요약'},
                                         {'idxno':2,'pub_date':'2026-10-05','viewDate':'10-06','viewTime':'00:00','title':'다른 날'}]}
        rows=parse_ajax(value,publisher,date(2026,10,5))
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['published_at'],'2026-10-05T00:00:00+09:00')

    def test_missing_article_requires_original_date_and_public_access(self):
        publisher={'name':'보험신보','url':'https://example.com/news/articleList.html','group':'specialist'}
        page='''<meta property="article:published_time" content="2026-10-19T00:00:00+09:00"><meta property="og:title" content="GA 영업 교육 - 보험신보"><div itemprop="articleBody">공개 기사 요약이다.</div>'''
        with patch('backfill_news.read_public',return_value=page):
            self.assertEqual(verify_public_article(publisher,date(2026,10,19),1)['title'],'GA 영업 교육')
            self.assertIsNone(verify_public_article(publisher,date(2026,10,20),1))
        with patch('backfill_news.read_public',return_value=page+'<script>{"isAccessibleForFree":false}</script>'):
            self.assertIsNone(verify_public_article(publisher,date(2026,10,19),1))

    def test_first_page_is_retained_and_exact_multiple_stops_at_declared_total(self):
        publisher={'name':'보험신보','url':'https://example.com/news/articleList.html','group':'specialist'}
        listing='<small class="altlist-count">총 <strong>40</strong></small><article id="section-list" class="altlist-body"><ul>'+''.join(
            f'<li><h2 class="titles"><a href="/news/articleView.html?idxno={i}">GA 뉴스 {i}</a></h2><time>2026.10.05 08:00</time></li>' for i in range(20))+'</ul></article>'
        page2=json.dumps({'result':'success','data':[{'idxno':i,'pub_date':'2026-10-01','viewDate':'10-05','viewTime':'00:00','title':f'GA 뉴스 {i}'} for i in range(20,40)]})
        with tempfile.TemporaryDirectory() as folder,patch('backfill_news.read_public',side_effect=[listing,page2]) as fetch:
            result=collect_day(publisher,date(2026,10,5),20,Path(folder))
            self.assertTrue(result['complete'])
            self.assertEqual(len(result['articles']),40)
            self.assertEqual(fetch.call_count,2)

    def test_corpus_keeps_more_than_five_articles_and_deduplicates_urls(self):
        now=datetime(2026,11,19,10,tzinfo=SEOUL)
        rows=[{'title':f'보험 뉴스 {i}','url':f'https://example.com/{i}','source':'매체','published_at':'2026-10-01T08:00:00+09:00','description':'발행 기사 요약'} for i in range(12)]
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            save_candidates(root,rows+rows,{'context_keywords':['보험']},now)
            self.assertEqual(len(json.loads((root/'data/articles/2026-10-01.json').read_text())),12)

    def test_trends_preserve_coverage_and_never_count_a_duplicate_twice(self):
        now=datetime(2026,11,19,10,tzinfo=SEOUL)
        row={'id':'a','title':'GA 수수료 분급 제도','url':'https://example.com/a','source':'매체','published_at':'2026-10-01T08:00:00+09:00','description':'수수료 지급 방식이 달라졌다. 제도 적용 일정이 공개됐다.'}
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'data/articles').mkdir(parents=True)
            (root/'config.json').write_text(json.dumps({'exclude_keywords':[]}))
            (root/'data/articles/2026-10-01.json').write_text(json.dumps([row,row]))
            (root/'data/backfill-report.json').write_text(json.dumps({'days':[{'date':'2026-10-01','warnings':[]}]}))
            result=build(root,now)
            self.assertEqual(result['article_count'],1)
            self.assertEqual(len(result['weekly']),8)
            self.assertEqual(len(result['monthly']),2)
            october=json.loads((root/'data/trends/monthly/2026-10.json').read_text())
            self.assertEqual(october['article_count'],1)
            self.assertFalse(october['in_progress'])
            first=json.loads((root/'data/trends/weekly/2026-09-28.json').read_text())
            self.assertEqual(first['start'],'2026-10-01')
            self.assertTrue(first['partial'])
            self.assertEqual(first['themes'][0]['evidence'][0]['url'],row['url'])

    def test_keyword_ga_does_not_match_mega(self):
        self.assertEqual(theme_for('GA 영업조직')['id'],'channel')
        self.assertIsNone(theme_for('MEGA 커피 경쟁'))
