from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from editorial import daily_analysis,build_report,profile_for,representative_score
from build_trends import THEMES,theme_for


def article(key,title,description='공개된 자료에서 현장 변화가 확인됐다. 비교 대상은 73개사다.'):
    return {'id':key,'title':title,'description':description,'source':'테스트신문',
            'url':'https://example.com/'+key,'published_at':'2026-11-19T08:00:00+09:00'}


class EditorialTests(unittest.TestCase):
    def test_summary_preserves_numbers_and_insight_adds_a_different_decision(self):
        a=article('mix','신계약 건수는 손보가 많은데 수수료는 생보가 앞섰다')
        a['summary_parts']={'intro':'대형 GA 73곳에서 판매 건수와 수수료가 다른 흐름을 보였다.',
                            'body':'1인당 신계약은 생보 1.7건, 손보 2.7건이다.','conclusion':'추가 영향은 원문 확인이 필요합니다.'}
        result=daily_analysis(a)
        self.assertIn('73곳',result['summary']);self.assertIn('2.7건',result['summary'])
        self.assertIn('건수 순위만으로',result['insight']['meaning'])
        self.assertIn('유지율',result['insight']['action'])
        self.assertNotEqual(result['summary'],result['insight']['meaning'])
        self.assertEqual(result['insight']['source_ids'],['mix'])

    def test_registration_notice_and_advertising_have_distinct_actions(self):
        notice=daily_analysis(article('notice','한국보험금융 등록취소 사전통지'))['insight']
        ads=daily_analysis(article('ads','GA 광고심의 체크리스트'))['insight']
        self.assertIn('사전통지 단계와 최종 처분',notice['meaning'])
        self.assertIn('계약관리 담당자',notice['action'])
        self.assertIn('승인 이력',ads['action'])
        self.assertNotEqual(notice['id'],ads['id'])
        quality=profile_for(article('quality','ABL생명·GA코리아, 금융소비자보호 공동관리체계 구축…완전판매·내부통제 강화'))
        self.assertEqual(quality['id'],'sales_quality')
        self.assertIn('민원',quality['action'])

    def test_commission_cap_is_not_described_as_payment_timing(self):
        cap=profile_for(article('cap','1200%룰 시행 이후 판매 실적'))
        phased=profile_for(article('phased','4년 분급 앞두고 GA 지급 기준 논의'))
        self.assertEqual(cap['id'],'commission_cap')
        self.assertNotIn('지급 시점이 달라',cap['meaning'])
        self.assertEqual(phased['id'],'phased_fees')

    def test_sales_company_discussion_is_not_misread_as_productivity(self):
        p=profile_for(article('roles','[보험판전사發 지각변동/下] 커지는 덩치 걸맞는 GA업계 역할 기대'))
        self.assertEqual(p['id'],'professional_sales')
        self.assertNotIn('인당',p['meaning'])

    def test_report_keeps_categories_and_every_claim_points_to_a_source(self):
        articles=[article('stop','700종신 판매중단 이후 대체상품 경쟁'),
                  article('sales','GA 실적 감소와 상품별 판매 분석'),
                  article('phased','4년 분급 준비와 유지관리수수료 논의'),
                  article('prod','GA 인당 생산성 격차 확인')]
        result=build_report('monthly','2026-11-01','2026-11-19',articles,THEMES,theme_for,articles[:1])
        ids={r['id'] for r in result['references']}
        self.assertTrue(result['executive_summary'])
        self.assertTrue(result['management']);self.assertTrue(result['agenda']);self.assertTrue(result['timeline'])
        self.assertTrue(any(s['id']=='fees' for s in result['sections']))
        self.assertTrue(any(s['id']=='channel' for s in result['sections']))
        paragraphs=result['executive_summary']+result['management']+result['timeline']
        for section in result['sections']:
            paragraphs+=section['developments']+section['interpretation']+section['actions']
        for p in paragraphs+result['agenda']:
            self.assertTrue(set(p.get('source_ids',[]))<=ids)
        self.assertTrue(any('상품 공백' in p['title'] for p in result['management']))
        for p in result['executive_summary']:
            if p['kind']!='overview':self.assertTrue(p['source_ids'])

    def test_insurance_sales_relevance_outweighs_unrelated_numeric_detail(self):
        profile=profile_for(article('p','건강보험 신상품 출시'))
        general=article('drone','드론 보험 보장 확대','보장 규모는 3배에서 11배인 57억원으로 확대됐다. 총 300% 기준을 변경했다.')
        life=article('life','생명보험 신상품 보장 확대','고객 보장 범위를 재구성한 생명보험 신상품이 출시됐다. 대상 조건이 공개됐다.')
        self.assertGreater(representative_score(life,profile),representative_score(general,profile))
