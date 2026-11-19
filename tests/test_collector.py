import importlib.util
from pathlib import Path
from datetime import datetime, timezone, timedelta
import unittest

spec=importlib.util.spec_from_file_location('collector',Path(__file__).resolve().parents[1]/'scripts/update_news.py')
c=importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)

class CollectorTests(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,11,11,0,tzinfo=timezone.utc)
        self.config={'keywords':{'GA':9,'생보':7},'daily_count':5,'max_age_hours':120,'max_per_source':3,'exclude_keywords':['부고']}
    def article(self,title,url='https://example.com/a',days=0,source='테스트'):
        return {'title':title,'url':url,'source':source,'description':'<b>요약</b>','published_at':(self.now-timedelta(days=days)).isoformat()}
    def test_parse_dates_and_unsafe_links(self):
        raw=b'<rss><channel><item><title>GA News</title><link>https://example.com/1</link><pubDate>Tue, 10 Nov 2026 23:00:00 GMT</pubDate><description>&lt;b&gt;safe&lt;/b&gt;</description></item><item><title>Bad</title><link>javascript:alert(1)</link><pubDate>Tue, 10 Nov 2026 23:00:00 GMT</pubDate></item></channel></rss>'
        rows=c.parse_feed(raw,'Test');self.assertEqual(len(rows),1);self.assertEqual(rows[0]['description'],'safe')
    def test_stale_future_and_unrelated_are_excluded(self):
        items=[self.article('GA 뉴스',days=7),self.article('GA 미래',days=-1),self.article('다른 뉴스'),self.article('생보 부고')]
        self.assertEqual(c.select_articles(items,self.config,self.now),[])
    def test_duplicate_url_and_similar_title(self):
        items=[self.article('GA 수수료 변화 확인'),self.article('GA 수수료 변화 확인!',url='https://example.com/b'),self.article('생보 변화',url='https://example.com/a?utm_source=a')]
        self.assertEqual(len(c.select_articles(items,self.config,self.now)),1)
    def test_rank_and_source_diversity(self):
        items=[self.article('GA '+chr(0xac00+i)*5,url=f'https://a.test/{i}',source='A') for i in range(6)]
        items+=[self.article('생보 '+chr(0xb098+i)*5,url=f'https://b.test/{i}',source='B') for i in range(2)]
        rows=c.select_articles(items,self.config,self.now)
        self.assertEqual(len(rows),5);self.assertEqual(sum(r['source']=='A' for r in rows),3)
        self.assertTrue(all(r['summary_kind']=='rss' for r in rows))
    def test_atom_and_html_cleanup(self):
        raw=b'<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>GA</title><link href="https://example.com"/><updated>2026-11-11T00:00:00Z</updated><summary>Hello</summary></entry></feed>'
        self.assertEqual(len(c.parse_feed(raw,'Test')),1)
        self.assertEqual(c.clean('<script>bad</script><b>hello</b>'),'hello')
    def test_reject_dtd(self):
        with self.assertRaises(ValueError):c.parse_feed(b'<!DOCTYPE rss><rss/>','Test')
    def test_structured_summary_removes_promotion_and_preserves_facts(self):
        text="※유튜브 채널을 구독해주세요.(https://youtube.com/test) 보험시장의 판매 구성이 변화하고 있다. 분석한 GA는 73곳이며 생보는 1.7건, 손보는 2.7건으로 나타났다. 수익구조의 차이가 앞으로 더 커질 가능성이 있다."
        parts=c.structured_summary('보험시장 변화',text)
        self.assertEqual(set(parts),{'intro','body','conclusion'})
        self.assertNotIn('유튜브',' '.join(parts.values()))
        self.assertIn('73곳',parts['body'])
        self.assertIn('2.7건',parts['body'])
        self.assertIn('가능성',parts['conclusion'])
    def test_short_feed_does_not_invent_conclusion(self):
        parts=c.structured_summary('GA 뉴스','업계 동향에 관한 새로운 소식이 전해졌다.')
        self.assertIn('원문',parts['conclusion'])
        self.assertNotIn('전망이다',parts['conclusion'])

if __name__=='__main__':unittest.main()
