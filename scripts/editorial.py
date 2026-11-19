"""Evidence-linked business interpretation, separate from reported article facts.

No regulatory dates, financial amounts, product terms or forecasts are invented.
The issue rules provide management interpretations; facts retain source links.
"""
from collections import Counter
from difflib import SequenceMatcher
import re

VERSION = 1

# Narrow issue rules keep a registration notice, a sales decline and a product
# launch from receiving the same broad 'check the source' recommendation.
PROFILES = [
    dict(id='professional_sales', pattern=r'보험판전사|보험판매전문회사|제판분리',
         title='판매채널의 역할과 책임 재정의', importance=8,
         meaning='판매채널 제도에 대한 논의는 영업 권한과 고객관리 책임을 함께 정리해야 한다는 과제를 보여줍니다. 채널의 외형 성장과 책임 체계의 정비를 같이 살펴야 합니다.',
         action='공식 논의의 확정 범위를 확인하고, 비교 설명·계약관리·민원 대응에서 보험사와 판매채널이 맡는 역할을 점검하세요.',
         monitor='제도 논의의 진행 단계와 권한·책임의 범위', metrics=['역할 분장','비교 설명 기준','계약관리 책임','민원 처리 경로'], owner='채널전략·준법 담당'),
    dict(id='mix', pattern=r'(?:신계약|판매.?건수|생.?손보).*수수료|수수료.*(?:판매.?건수|생.?손보)',
         title='판매 건수와 수수료 기여의 차이', importance=9,
         meaning='판매 건수와 수수료 기여가 다르면 건수 순위만으로 채널의 수익 기여를 판단하기 어렵습니다.',
         action='생보·손보를 나눠 인당 건수와 인당 수수료를 비교하고, 상품별 MIP·유지율을 더해 지원 우선순위를 정하세요.',
         monitor='판매량 순위와 수수료 순위가 다른 GA·상품군', metrics=['인당 신계약 건수','인당 수수료','상품별 MIP','계약 유지율'], owner='채널·실적 담당'),
    dict(id='productivity', pattern=r'인당|1인당|생산성|규모.*수수료',
         title='GA 규모와 생산성의 분리', importance=9,
         meaning='등록 설계사가 많은 조직과 실제로 생산성이 높은 조직은 다를 수 있습니다. 조직 규모와 활동 효율을 분리해 볼 필요가 있습니다.',
         action='주요 GA·지점을 가동률, 인당 MIP, 유지율로 다시 비교하고, 인원이 많아도 활동이 낮은 곳에는 교육·활동관리 지원을 우선 배치하세요.',
         monitor='대형 GA의 외형 성장과 실가동·인당 성과의 차이', metrics=['가동률','인당 MIP','교육 후 가동인원','계약 유지율'], owner='GA·지점 관리자'),
    dict(id='agency_notice', pattern=r'한국보험금융.*(?:등록취소|사전통지)|(?:등록취소|사전통지).*한국보험금융',
         title='거래 GA의 조직 안정성과 계약관리', importance=10,
         meaning='이 사안은 신규 영업조직의 움직임과 기존 고객의 계약관리 연속성을 함께 살펴야 하는 문제입니다. 사전통지 단계와 최종 처분은 구분해서 읽어야 합니다.',
         action='당국·보험사 공지로 진행 단계를 확인하고, 해당 채널의 고객 연락 창구와 계약관리 담당자, 이관·민원 대응 절차를 점검하세요.',
         monitor='공식 처분 단계와 고객·설계사 관리 방안', metrics=['담당자 지정률','고객 안내 현황','미처리 민원','계약 유지 현황'], owner='제휴·계약관리 담당'),
    dict(id='disclosure', pattern=r'계약체결비용|공개범위|공개 범위|비용 공개',
         title='상품별 비용 공개와 제휴 협의', importance=9,
         meaning='제휴 협의에서는 총 보상 수준뿐 아니라 비용의 정의와 공개 단위도 쟁점이 될 수 있습니다. 서로 다른 기준의 수치를 비교하면 협상이 어긋날 수 있습니다.',
         action='상품별 비용 산식·지급 시점·포함 항목을 같은 표로 맞추고, 확정된 항목과 협의 중인 항목을 나눠 현장에 전달하세요.',
         monitor='공개 항목·범위와 보험사·GA 간 협의 결과', metrics=['항목별 정의 일치 여부','미확정 조건','지급 시점'], owner='GA 본사·제휴 담당'),
    dict(id='commission_cap', pattern=r'1200%',
         title='모집 보상 총액과 비용 구성', importance=8,
         meaning='보상 한도와 관련된 보도는 지급 배수보다 비용 구성과 적용 조건을 같은 기준으로 비교해야 한다는 과제를 보여줍니다.',
         action='공식 안내를 기준으로 수수료·시책·정착지원 등 보상 항목을 구분하고, 제휴 조건과 환수·유지 조건을 함께 점검하세요.',
         monitor='보상 항목의 포함 범위와 적용 기준', metrics=['총보상 구성','정착지원 조건','환수 조건','유지율'], owner='제휴·영업기획 담당'),
    dict(id='phased_fees', pattern=r'분급|유지관리수수료|수수료 개편',
         title='보상 구조 변화와 장기 계약관리', importance=9,
         meaning='수수료 지급 시점이 달라지는 논의는 초기 모집 실적과 장기 유지관리를 함께 설계해야 한다는 과제를 보여줍니다. 초기 수입만으로 조직 운영을 판단하기 어렵습니다.',
         action='확정된 적용 기준을 확인한 뒤 모집 초기와 유지 단계의 수입·업무를 나눠 설명하고, 정착지원·교육·고객관리 계획을 함께 점검하세요.',
         monitor='적용 일정·대상과 유지 단계의 지급·환수 기준', metrics=['초기·유지 수입 구성','계약 유지율','정착률','고객관리 이행률'], owner='영업기획·육성 담당'),
    dict(id='sales_reset', pattern=r'700종신|종신.*(?:판매중단|판매중지|판매 중단)|절판',
         title='주력 종신상품 공백과 대체 판매', importance=10,
         meaning='주력상품 판매 변화가 있으면 전체 실적 변동을 상품 공백과 현장 활동의 변화로 나눠 봐야 합니다. 일시적인 판매 집중이 지속 가능한 생산성인지는 별도 확인이 필요합니다.',
         action='상품별 MIP와 비중, 핵심 GA의 가동인원을 비교하고, 대체상품 전환 이후의 신규 고객 유입과 유지율을 함께 추적하세요.',
         monitor='대체상품 출시·개정과 채널별 판매 회복의 구성', metrics=['상품별 MIP 비중','대체상품 전환 실적','가동인원','계약 유지율'], owner='상품·GA 영업 담당'),
    dict(id='liquidity', pattern=r'노후설계자금|생애자금|생활자금|(?:인출.*종신|종신.*인출)',
         title='사망보장과 생애자금 활용의 결합', importance=8,
         meaning='생애자금 활용 기능은 종신보험의 상담 논점을 사망보장과 생전 활용 조건으로 넓힙니다. 인출 가능 금액뿐 아니라 인출 후 보장·연금 변화까지 설명해야 비교가 완성됩니다.',
         action='인출 시점·한도와 인출 전후의 보장·연금, 해약 조건을 같은 가정으로 비교하고 고객 목적별 설명 사례를 준비하세요.',
         monitor='생전 활용 기능의 조건과 활용 이후 계약 변화', metrics=['인출 전후 보장','연금 변화','활용 시점·한도','설명 확인 항목'], owner='상품교육·설계 담당'),
    dict(id='ga_sales', pattern=r'GA.*(?:실적|점유율|월초|신계약|판매\s*(?:량|액|건수|실적|증가|감소|급감))|(?:실적|점유율|신계약).*GA',
         title='GA 실적의 상품·조직별 기여', importance=8,
         meaning='GA 총실적의 증감에는 주력상품 구성과 가동인원, 영업일수 등이 함께 반영될 수 있습니다. 총액 변화만으로 현장 영업력의 변화를 단정하기 어렵습니다.',
         action='상품·GA·지점별로 MIP와 가동인원을 나누고 영업일수 기준도 맞춰, 실적 변화가 발생한 구간부터 교육·프로모션을 조정하세요.',
         monitor='총실적 변화 안에서 상품·GA별 기여가 달라지는지', metrics=['상품·GA별 MIP','가동인원','영업일당 실적','상위 GA 집중도'], owner='GA 실적·영업관리 담당'),
    dict(id='ads', pattern=r'광고심의|방송광고|광고.*(?:심의|규제|모니터링)|홈쇼핑',
         title='광고·모집 문구의 관리', importance=8,
         meaning='광고 관리 이슈는 본사 홍보물과 지점·설계사가 실제로 쓰는 문구가 일치하는지 살펴볼 필요를 보여줍니다. 자료 배포 이후의 수정·재사용 과정도 관리 대상입니다.',
         action='현장에서 쓰는 카드뉴스·문자·상담 자료의 최신 심의본과 승인 이력을 확인하고, 보장 조건과 제한 사항이 빠지지 않았는지 점검하세요.',
         monitor='광고 심의 기준·공식 안내와 현장 자료의 일치', metrics=['승인본 사용률','개정본 교체 현황','설명 누락 항목','광고 관련 민원'], owner='준법·영업교육 담당'),
    dict(id='sales_quality', pattern=r'불완전판매|완전판매|소비자보호|리베이트|작성계약|정도영업|고아계약|내부통제',
         title='모집 품질과 사후관리 책임', importance=8,
         meaning='모집 품질 이슈는 신계약 규모와 함께 설명·계약관리 과정도 성과로 관리해야 한다는 점을 보여줍니다. 판매 이후의 민원·해지 부담까지 연결해 볼 필요가 있습니다.',
         action='반복되는 설명 오류와 민원 유형을 교육 사례로 바꾸고, 청약 이후 고객 확인·담당자 지정·유지관리 절차의 이행 여부를 확인하세요.',
         monitor='동일한 모집 오류와 민원의 반복 여부', metrics=['민원 유형','조기 해지','담당자 지정률','교육 후 오류 재발'], owner='준법·지점 관리자'),
    dict(id='fraud', pattern=r'보험사기|고의사고|허위입원|고의.*충돌',
         title='사기 대응과 고객 접점의 안내', importance=8,
         meaning='사기 관련 보도는 상품 판매와 별개로 사고 접점의 안내 품질이 고객 신뢰에 영향을 준다는 점을 보여줍니다. 현장은 사실관계 확인과 공식 대응 경로 안내에 집중할 필요가 있습니다.',
         action='보도된 유형을 고객 응대 교육에 활용하고, 임의 판단을 줄이도록 회사의 공식 사고 접수·자료 보존·담당 부서 연결 절차를 점검하세요.',
         monitor='반복되는 사기 유형과 회사의 공식 응대 지침', metrics=['공식 경로 연결','자료 확인 누락','고객 문의 유형'], owner='고객관리·사고 응대 담당'),
    dict(id='capital', pattern=r'K-?ICS|지급여력|기본자본|건전성|자본.*(?:확충|비율)|금리.*자본',
         title='판매 성장과 자본 부담의 균형', importance=8,
         meaning='자본·건전성 지표는 판매 성장과 다른 방향으로 움직일 수 있습니다. 단기 판매 확대를 평가할 때 장기 보장 부담과 자본 관리의 맥락도 함께 읽어야 합니다.',
         action='공시 기준과 연결·별도 범위를 맞춰 순이익·CSM·지급여력 지표를 함께 보고, 상품·영업전략 변화의 배경을 교육 자료에 반영하세요.',
         monitor='자본 지표의 공시 기준과 보완 계획', metrics=['지급여력 지표','CSM','순이익','공시 기준 범위'], owner='영업기획·경영분석 담당'),
    dict(id='earnings', pattern=r'순이익|CSM|적자|흑자|보험손익|실적.*분기|분기.*실적',
         title='실적의 규모와 이익의 구성', importance=7,
         meaning='실적의 규모와 이익의 구성은 구분해서 봐야 합니다. 보험 본업과 투자손익이 다른 방향이면 한 가지 지표만으로 판매 경쟁력을 평가하기 어렵습니다.',
         action='전년·전분기 비교의 기준 기간을 맞추고 보험손익·투자손익·CSM을 구분해, 영업 현장에 전달할 핵심 변화를 정리하세요.',
         monitor='이익 변동의 구성과 신계약 가치의 추이', metrics=['보험손익','투자손익','CSM','동일 기간 비교'], owner='경영분석·영업기획 담당'),
    dict(id='annuity', pattern=r'연금|은퇴|노후',
         title='노후소득 설계와 비교 기준', importance=7,
         meaning='연금 관련 경쟁은 연금액뿐 아니라 준비 시점과 수령 조건을 함께 설명할 때 상담 가치로 이어집니다. 서로 다른 조건의 수치를 그대로 비교하면 고객 판단이 어려워질 수 있습니다.',
         action='가입 나이·납입 기간·개시 나이·보증 조건을 맞춘 비교표를 만들고, 중도 활용 여부에 따른 수령 구조도 함께 설명하세요.',
         monitor='노후소득 기능의 조건과 고객군별 상담 반응', metrics=['동일 조건 비교','개시 시점','보증 조건','상담 후 전환'], owner='상품교육·상담 담당'),
    dict(id='recruiting', pattern=r'리쿠르팅|스카우트|정착지원|영입|이직|N잡',
         title='인력 유입과 정착의 질', importance=7,
         meaning='인력 유입의 효과는 영입 규모와 실제 활동·정착으로 나눠 평가해야 합니다. 지원 조건과 영업 기반이 맞지 않으면 모집 이후 관리 부담이 커질 수 있습니다.',
         action='영입 인원과 함께 초기 가동·교육 수료·정착 현황을 추적하고, 지원 조건의 설명과 현장 육성 계획이 연결되는지 확인하세요.',
         monitor='영입 이후의 활동·정착과 지원 조건 이행', metrics=['초기 가동률','교육 수료','정착률','지원 조건 이행'], owner='리쿠르팅·육성 담당'),
    dict(id='education', pattern=r'교육|아카데미|워크숍|특강|연수',
         title='교육 참여와 현장 실행의 연결', importance=6,
         meaning='교육의 효과는 참석 인원보다 실제 상담·활동의 변화로 확인해야 합니다. 제도·상품 지식이 현장 설명과 고객관리 행동으로 이어지는지가 핵심입니다.',
         action='교육 주제별로 상담 사례와 확인 문항을 만들고, 교육 전후 가동인원·상담 건수·반복 오류를 같은 기준으로 비교하세요.',
         monitor='교육 이후 활동과 설명 품질의 변화', metrics=['교육 전후 가동','상담 건수','설명 오류','고객관리 이행'], owner='영업교육·지점 관리자'),
    dict(id='digital', pattern=r'(?<![A-Za-z])AI(?![A-Za-z])|디지털|자동화|전산|시스템|플랫폼',
         title='디지털 도구와 상담 과정의 변화', importance=6,
         meaning='새 도구의 도입 효과는 이용 건수보다 상담 준비·계약 처리 과정이 실제로 개선되는지로 확인할 필요가 있습니다.',
         action='시범 사용 지점을 정해 상담 준비 시간과 처리 오류, 실제 활용률을 기록하고 효과가 확인된 업무부터 교육을 확대하세요.',
         monitor='도입 이후의 실제 활용과 업무 개선', metrics=['실사용률','상담 준비 시간','처리 오류','교육 후 활용'], owner='디지털·영업지원 담당'),
    dict(id='product', pattern=r'신상품|출시|종신|보장|건강보험|배타적사용권|간편|치매|유병|보험료',
         title='상품 차별화와 고객 적합성', importance=6,
         meaning='신상품의 차별점은 고객의 보장 공백과 연결될 때 상담 근거가 됩니다. 보장 확대나 가입 조건의 차이가 어떤 고객에게 유효한지 구체화할 필요가 있습니다.',
         action='기사의 차별점을 대상 고객·가입 조건·보장 범위·제한 사항으로 나눠 비교하고, 기존 상품과 달라진 설명 포인트를 정리하세요.',
         monitor='보장 차별점과 실제 가입·유지 조건', metrics=['고객군별 상담','가입 조건','보장·제한 사항','상담 후 전환'], owner='상품교육·상담 담당'),
    dict(id='brand', pattern=r'웹예능|유튜브|수상|캠페인|사회공헌|브랜드|협약|제휴',
         title='브랜드 접점과 유효 고객 유입', importance=3,
         meaning='브랜드 접점의 확대가 판매 성과로 이어지는지는 별도 확인이 필요합니다. 노출량과 유효 고객 문의를 구분해 평가해야 합니다.',
         action='채널별 문의·상담 예약·실제 상담 전환을 기록하고, 현장에서 활용할 고객 안내 내용과 후속 응대 경로를 정리하세요.',
         monitor='노출 이후의 문의·상담 전환', metrics=['유효 문의','상담 예약','상담 전환','유입 경로'], owner='마케팅·고객접점 담당'),
]

FALLBACK = dict(id='market', title='시장 변화의 현장 적용', importance=2,
                meaning='이 보도의 현장 의미는 실제로 달라지는 고객 접점과 운영 조건을 확인해야 판단할 수 있습니다.',
                action='원문에서 변화 주체와 적용 범위를 확인하고, 담당 채널의 상담·계약관리 과정 중 바뀌는 항목을 정리하세요.',
                monitor='후속 발표와 실제 현장 적용 범위', metrics=['변경 항목','대상 고객','후속 발표'], owner='영업관리 담당')


def profile_for(article):
    title = article.get('title','')
    return next((p for p in PROFILES if re.search(p['pattern'],title,re.I)),FALLBACK)


def clean_excerpt(text):
    text=re.sub(r'\([^)]*(?:연합뉴스|뉴시스|서울=|서울 =)[^)]*\)\s*[^=]{0,35}(?:기자\s*=|=)\s*','',text)
    text=re.sub(r'\[[^\]]*(?:기자|서울파이낸스|보험저널)[^\]]*\]\s*','',text)
    return re.sub(r'\s+',' ',text).strip()


def useful(sentence):
    return len(sentence)>12 and not re.search(r'RSS|원문에서 확인|추가 (?:근거|내용|영향)|상세 사실.*제공되지|확인할 수 있는 추가',sentence)


def facts_for(article):
    """Return extractive facts only; interpretations never feed this function."""
    parts=article.get('summary_parts',{})
    if parts:
        rows=[clean_excerpt(parts.get(k,'')) for k in ('intro','body')]
        rows=[s for s in rows if useful(s)]
        if rows:return rows
    text=clean_excerpt(article.get('description') or article.get('_rss_text') or article.get('summary') or '')
    rows=[s.strip() for s in re.split(r'(?<=다\.)\s*|(?<=[!?])\s+',text)]
    rows=[s for s in rows if useful(s) and re.search(r'[.!?][’”"\']?$',s)]
    if not rows:return []
    first=rows[0]
    rest=rows[1:]
    evidence=max(rest,key=lambda s:len(re.findall(r'\d+(?:[.,]\d+)?',s)),default='')
    return [s for s in (first,evidence) if s]


def fact_paragraph(article,limit=300):
    facts=facts_for(article)
    if not facts:
        return f"‘{article['title']}’라는 내용이 보도됐습니다."
    result=facts[0]
    if len(facts)>1 and facts[1]!=facts[0] and len(result)+len(facts[1])<=limit:
        result+=' '+facts[1]
    return result


def daily_analysis(article):
    profile=profile_for(article)
    summary=fact_paragraph(article,260)
    facts=facts_for(article)
    if profile['id']=='fraud' and len(facts)>1 and re.search(r'김 모씨|황당한 일을|기획조사 골목길',facts[0]):
        summary=facts[1]
    return {'version':VERSION,'summary':summary,
            'insight':{key:profile[key] for key in ('id','title','meaning','action','monitor','metrics','owner')}|
                      {'basis':'기사의 공개 사실을 바탕으로 한 보험영업 관점의 해석','source_ids':[article['id']]}}


def representative_score(article,profile):
    text=' '.join(facts_for(article))
    specific=len(re.findall(r'\d+(?:[.,]\d+)?(?:%|배|건|명|만원|억원|조원)',text))
    field_relevance=10 if re.search(r'GA|설계사|생명|생보|종신|연금|영업조직|수수료',article['title'],re.I) else 0
    if re.search(r'GA',article['title'],re.I):field_relevance+=5
    if re.search(r'실적|판매.*(?:급감|감소|하락)',article['title']):field_relevance+=3
    return profile['importance']*3+field_relevance+min(specific,5)*2+min(len(text),240)/80


def issue_groups(articles):
    grouped={}
    for article in articles:
        p=profile_for(article)
        grouped.setdefault(p['id'],{'profile':p,'articles':[]})['articles'].append(article)
    return sorted(grouped.values(),key=lambda g:(g['profile']['importance']*4+min(len(g['articles']),6),g['profile']['importance']),reverse=True)


def choose_evidence(group,limit=2):
    ranked=sorted(group['articles'],key=lambda a:(representative_score(a,group['profile']),a['published_at']),reverse=True)
    selected=[]
    for a in ranked:
        norm=re.sub(r'[^a-z0-9가-힣]','',a['title'].lower())
        if any(SequenceMatcher(None,norm,re.sub(r'[^a-z0-9가-힣]','',b['title'].lower())).ratio()>.74 for b in selected):continue
        selected.append(a)
        if len(selected)>=limit:break
    return sorted(selected,key=lambda a:a['published_at'])


def ref(article):
    return {k:article[k] for k in ('id','title','url','source','published_at')}


def paragraph(text,articles=(),kind='fact'):
    return {'text':text,'source_ids':[a['id'] for a in articles],'kind':kind}


def category_report(theme,articles,kind='weekly'):
    groups=issue_groups(articles)
    # Two narrow issues provide a readable argument within each retained category.
    selected=groups[:2]
    developments=[];interpretations=[];actions=[];references=[]
    for group in selected:
        p=group['profile'];evidence=choose_evidence(group,2 if kind=='monthly' else 1)
        for article in evidence:
            developments.append(paragraph(fact_paragraph(article),[article]))
            references.append(ref(article))
        interpretations.append(paragraph(p['meaning'],evidence,'interpretation'))
        actions.append({'owner':p['owner'],'task':p['action'],'metrics':p['metrics'],'source_ids':[a['id'] for a in evidence]})
    return {'id':theme['id'],'title':theme['title'],'article_count':len(articles),
            'angle':' · '.join(g['profile']['title'] for g in selected),
            'developments':developments,'interpretation':interpretations,'actions':actions,
            'references':list({r['id']:r for r in references}.values())}


def management_reading(groups):
    by_id={g['profile']['id']:g for g in groups}
    readings=[]
    combinations=[
        (('sales_reset','ga_sales'),'상품 공백과 조직 활동을 나눠 진단',
         '주력 종신상품의 판매 변화와 GA 실적 보도가 함께 나타났습니다. 이 경우 실적 변동을 조직 역량의 변화로만 읽기보다, 상품 공백·가동인원·거래 GA별 기여로 나눠 진단하는 것이 유용합니다. 대체상품 전환 속도와 기존 계약의 유지 수준을 함께 확인해야 단기 물량 회복과 지속 가능한 성장을 구분할 수 있습니다.'),
        (('phased_fees','productivity'),'초기 모집과 유지 단계의 성과를 함께 관리',
         '보상 구조 변화와 GA 생산성 격차가 동시에 다뤄졌습니다. 초기 신계약 확보만을 목표로 한 관리에서 가동·유지·정착을 함께 보는 관리로 점검 범위를 넓힐 필요가 있습니다. 교육과 프로모션의 효과도 참가 인원이나 당월 총액 외에 인당 성과와 이후 유지 현황으로 확인하는 것이 합리적입니다.'),
        (('agency_notice','ads'),'채널 안정성과 모집 품질을 같은 관리선에 두기',
         '거래 GA의 조직 안정성 이슈와 광고·모집 문구 관리 이슈가 함께 보도됐습니다. 두 사안은 고객 접점의 책임 소재를 분명히 해야 한다는 공통 과제를 갖습니다. 영업 지원을 확대할 때 고객관리 담당자와 승인된 자료의 사용 여부도 함께 점검해야 합니다.'),
        (('sales_reset','liquidity'),'상품 교체보다 설명 체계의 재정비가 먼저',
         '주력상품 판매 변화와 생전 자금 활용 기능을 내세운 종신보험이 함께 다뤄졌습니다. 상품 교체를 이름이나 환급 수준의 비교로 끝내기보다, 고객이 자금을 활용한 뒤 남는 보장과 계약 조건까지 설명할 수 있는지가 중요합니다. 교육 사례와 비교표도 이 조건을 중심으로 다시 구성할 필요가 있습니다.'),
    ]
    for ids,title,text in combinations:
        if all(i in by_id for i in ids):
            evidence=[choose_evidence(by_id[i],1)[0] for i in ids]
            readings.append({'title':title,**paragraph(text,evidence,'interpretation')})
    if not readings:
        for group in groups[:2]:
            p=group['profile'];evidence=choose_evidence(group,1)
            readings.append({'title':p['title'],**paragraph(p['meaning']+' '+p['action'],evidence,'interpretation')})
    return readings[:3]


def build_report(kind,start,end,articles,themes,theme_for,previous_articles=()):
    groups=issue_groups(articles)
    if not groups:return {'version':VERSION,'executive_summary':[],'sections':[],'management':[],'agenda':[],'timeline':[],'references':[],'continuity':[]}
    previous_ids={profile_for(a)['id'] for a in previous_articles}
    leaders=groups[:3]
    executive=[];references=[]
    opening='이번 주' if kind=='weekly' else '이번 달'
    names=' · '.join(g['profile']['title'] for g in leaders)
    executive.append(paragraph(f"{opening} 보험영업에서 우선 점검할 쟁점은 {names}입니다. 아래 분석은 해당 기간에 확인된 보도와 원문 근거를 묶어 정리했습니다.",kind='overview'))
    for group in leaders:
        evidence=choose_evidence(group,1);article=evidence[0];p=group['profile']
        executive.append(paragraph(fact_paragraph(article)+' '+p['meaning'],evidence,'fact_and_interpretation'))
        references.extend(ref(a) for a in evidence)
    sections=[]
    for theme in themes:
        subset=[a for a in articles if theme_for(a['title']) and theme_for(a['title'])['id']==theme['id']]
        if not subset:continue
        section=category_report(theme,subset,kind);sections.append(section);references.extend(section['references'])
    # Article counts describe coverage, not market growth; editorial priority is
    # based on issue specificity and relevance rather than generic-news volume.
    sections.sort(key=lambda s:max((g['profile']['importance'] for g in issue_groups([a for a in articles if theme_for(a['title'])['id']==s['id']])),default=0),reverse=True)
    agenda=[]
    for group in groups[:4]:
        p=group['profile'];evidence=choose_evidence(group,1)
        agenda.append({'issue':p['title'],'owner':p['owner'],'task':p['action'],'watch':p['monitor'],
                       'metrics':p['metrics'],'source_ids':[a['id'] for a in evidence]})
        references.extend(ref(a) for a in evidence)
    timeline=[]
    if kind=='monthly':
        weeks={}
        for a in articles:
            # ISO week numbers preserve real ordering across the month boundary.
            from datetime import date
            day=date.fromisoformat(a['published_at'][:10]);weeks.setdefault(day.isocalendar()[:2],[]).append(a)
        for _,rows in sorted(weeks.items()):
            group=issue_groups(rows)[0];evidence=choose_evidence(group,1);article=evidence[0]
            timeline.append({'start':min(a['published_at'][:10] for a in rows),'end':max(a['published_at'][:10] for a in rows),
                             'title':group['profile']['title'],**paragraph(fact_paragraph(article),evidence)})
            references.extend(ref(a) for a in evidence)
    management=management_reading(groups)
    for group in groups:
        references.extend(ref(a) for a in choose_evidence(group,1))
    return {'version':VERSION,'title':'보험영업 주간 리포트' if kind=='weekly' else '보험영업 월간 리포트',
            'executive_summary':executive,'sections':sections,'management':management,'agenda':agenda,'timeline':timeline,
            'continuity':[g['profile']['title'] for g in leaders if g['profile']['id'] in previous_ids],
            'references':list({r['id']:r for r in references}.values())}
