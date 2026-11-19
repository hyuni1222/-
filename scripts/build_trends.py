"""Build evidence-linked weekly/monthly digests from the full collected corpus."""
from collections import Counter
from datetime import date, datetime, timedelta
from difflib import SequenceMatcher
import argparse
import json
import re
from pathlib import Path
from zoneinfo import ZoneInfo

from update_news import ROOT, atomic_json, canonical_url, has_keyword, normalized_title, structured_summary
from corpus import START
from editorial import build_report

SEOUL = ZoneInfo("Asia/Seoul")
THEMES = [
    {"id":"fees", "title":"수수료·제도 변화", "words":["수수료","분급","1200%","제판분리","보험업법","판매전문회사"],
     "focus":"수수료 체계와 판매 제도의 변화", "action":"적용 시점·대상 채널·환수 조건을 나눠 확인하고, 설계사 교육과 보상 안내에 반영할 필요가 있습니다."},
    {"id":"control", "title":"소비자보호·내부통제", "words":["내부통제","소비자보호","등록취소","불완전판매","광고심의","보험사기","금감원","금융감독원","제재"],
     "focus":"판매 과정의 설명 책임과 관리 기준", "action":"모집·광고·계약관리 단계의 준수 항목을 점검하고, 고객 안내와 현장 교육을 함께 보완할 필요가 있습니다."},
    {"id":"channel", "title":"GA·설계사·영업조직", "words":["GA","법인보험대리점","설계사","리쿠르팅","영업조직","판매채널","대리점","전속"],
     "focus":"판매채널과 영업조직의 운영", "action":"조직 규모와 인당 생산성, 계약 유지 수준을 함께 확인해 교육·활동관리의 우선순위를 정할 필요가 있습니다."},
    {"id":"product", "title":"종신·연금·상품 경쟁", "words":["종신","연금","신상품","출시","보장","배타적사용권","상품개정","보험료"],
     "focus":"상품 구성과 고객 보장 수요", "action":"신상품의 가입 조건·보장 범위·유동성 기능을 비교하고, 고객 상황에 맞는 설명 포인트를 정리할 필요가 있습니다."},
    {"id":"results", "title":"보험사 실적·건전성", "words":["실적","순이익","지급여력","K-ICS","CSM","건전성","자본","적자","흑자","수익성"],
     "focus":"보험사의 수익성과 자본 관리", "action":"판매 확대와 수익성·건전성 지표를 함께 살펴보고, 기사 속 실적 수치의 기준 기간과 산정 범위를 구분할 필요가 있습니다."},
    {"id":"strategy", "title":"보험사·시장 동향", "words":["보험","생보","손보","생명","라이프"],
     "focus":"보험사의 경영과 시장 대응", "action":"보험사의 경영·서비스 변화가 상담과 고객관리 과정에 어떤 영향을 주는지 확인할 필요가 있습니다."},
]


def theme_for(title):
    return next((theme for theme in THEMES if any(has_keyword(title,k) for k in theme["words"])), None)


def period_bounds(day, kind):
    if kind == "weekly":
        start = day - timedelta(days=day.weekday())
        return start, start + timedelta(days=6)
    start = day.replace(day=1)
    following = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
    return start, following - timedelta(days=1)


def source_ref(article):
    return {k:article[k] for k in ("id","title","url","source","published_at")}


def representatives(items, limit=3):
    """Use early, late, and distinct reporting rather than repeating one release."""
    ordered = sorted(items, key=lambda r:(r["published_at"],r["url"]))
    used_sources = {ordered[0]["source"],ordered[-1]["source"]}
    preferred = [ordered[0], ordered[-1]] + sorted(ordered, key=lambda r:(r['source'] not in used_sources,len(r.get("description",""))), reverse=True)
    chosen = []
    for row in preferred:
        title = normalized_title(row["title"])
        if any(row["url"]==r["url"] or SequenceMatcher(None,title,normalized_title(r["title"])).ratio()>.78 for r in chosen):
            continue
        chosen.append(row)
        if len(chosen)>=limit:
            break
    return sorted(chosen,key=lambda r:r["published_at"])


def build_period(kind, start, end, articles, today, coverage, previous_articles=()):
    first = max(start,date.fromisoformat(START))
    last = min(end,today)
    counts = Counter(theme_for(row["title"])["id"] for row in articles if theme_for(row["title"]))
    themes = []
    for theme in THEMES:
        subset = [r for r in articles if theme_for(r["title"]) and theme_for(r["title"])["id"]==theme["id"]]
        if not subset:
            continue
        picks = representatives(subset)
        # Facts remain directly attributable to a particular linked publication.
        evidence = []
        for article in picks:
            fact = structured_summary(article["title"],article.get("description", ""))["intro"]
            if not re.search(r'[.!?][’”"\']?$',fact):
                fact = f"‘{fact}’ 소식이 보도됐습니다."
            evidence.append({**source_ref(article),"fact":fact})
        days = len({r["published_at"][:10] for r in subset})
        themes.append({"id":theme["id"],"title":theme["title"],"count":len(subset),
                       "summary_parts":{"intro":f"{theme['focus']} 관련 보도가 {days}일에 걸쳐 {len(subset)}건 수집됐습니다.",
                                        "body":" ".join(f"{r['published_at'][5:10].replace('-','/')} {r['fact']}" for r in ([evidence[0],evidence[-1]] if len(evidence)>1 else evidence)),
                                        "conclusion":theme["action"]}, "evidence":evidence,
                       "sources":sorted({r["source"] for r in subset})})
    themes.sort(key=lambda t:t["count"],reverse=True)
    sources = Counter(r["source"] for r in articles)
    expected = (last-first).days+1
    checked = sum((first+timedelta(days=i)).isoformat() in coverage for i in range(expected))
    issues = [day for day,record in coverage.items() if first.isoformat()<=day<=last.isoformat() and record.get("warnings")]
    partial = end>=today or start<date.fromisoformat(START)
    label = (f"{first.month}월 {first.day}일 ~ {last.month}월 {last.day}일" if kind=="weekly" else f"{start.year}년 {start.month}월")
    focus = [t for t in themes if t['id']!='strategy'][:2] or themes[:2]
    overview = {"intro":f"{label}에는 "+" · ".join(t['title'] for t in focus)+f" 관련 보도를 중심으로 흐름을 정리했습니다. 분석 대상은 {len(sources)}개 매체의 {len(articles)}건입니다." if themes else f"{label}에 선정 기준에 맞는 기사를 확인하지 못했습니다.",
                "body":" ".join(t['evidence'][-1]['fact'] for t in focus) if themes else "날짜별 수집 결과와 공개된 기사 목록을 확인하세요.",
                "conclusion":focus[0]['summary_parts']['conclusion'] if focus else "공개된 원문을 확인하세요."}
    period = {"id":start.isoformat() if kind=="weekly" else start.strftime("%Y-%m"),"kind":kind,"label":label,
            "period_start":start.isoformat(),"period_end":end.isoformat(),"start":first.isoformat(),"end":last.isoformat(),
            "in_progress":end>=today,"partial":partial,"article_count":len(articles),"source_count":len(sources),
            "sources":dict(sources.most_common()),"coverage_days":checked,"expected_days":expected,"warning_days":issues,
            "summary_parts":overview,"themes":themes,
            "articles":[source_ref(r) for r in sorted(articles,key=lambda r:r["published_at"],reverse=True)]}
    period['report']=build_report(kind,first.isoformat(),last.isoformat(),articles,THEMES,theme_for,previous_articles)
    return period


def build(root=ROOT, now=None):
    now = now or datetime.now(SEOUL)
    today = now.astimezone(SEOUL).date()
    config = json.loads((root/"config.json").read_text())
    if (root/'data/latest.json').exists():
        from build_daily_analysis import build as build_daily
        build_daily(root)
    corpus = {}
    for path in sorted((root/"data/articles").glob("????-??-??.json")):
        for row in json.loads(path.read_text()):
            if not START<=row["published_at"][:10]<=today.isoformat():
                continue
            url = canonical_url(row["url"])
            old = corpus.get(url)
            if not old:
                corpus[url] = row
            else:
                old['published_at'] = min(old['published_at'],row['published_at'])
                if len(row.get('description',''))>len(old.get('description','')):
                    old['description'] = row['description']
    stored_count = len(corpus)
    corpus = {url:row for url,row in corpus.items() if theme_for(row['title']) and
              not re.search(r'\[(?:인사|부고|동정)\]|보험주|마감시황',row['title']) and
              not any(k.casefold() in row['title'].casefold() for k in config.get('exclude_keywords',[]))}
    coverage_path = root/"data/coverage.json"
    coverage = json.loads(coverage_path.read_text()) if coverage_path.exists() else {}
    report_path = root/"data/backfill-report.json"
    if report_path.exists():
        for record in json.loads(report_path.read_text()).get("days",[]):
            coverage[record["date"]] = record
    atomic_json(coverage_path,coverage)
    result = {"updated_at":now.isoformat(timespec="seconds"),"collection_start":START,"collection_end":today.isoformat(),
              "stored_articles":stored_count,
              "article_count":len(corpus),"coverage_days":len(coverage),"sources":dict(Counter(r["source"] for r in corpus.values())),
              "method":"원문 근거를 쟁점별로 묶어 주요 변화·영업적 의미·대응 과제를 작성했습니다. 해석과 대응은 보험영업 관점의 판단이며, 기사에서 확인된 사실과 구분해 읽을 수 있습니다. 보도 건수는 수집 범위의 집계입니다.",
              "weekly":[],"monthly":[]}
    for kind in ("weekly","monthly"):
        groups = {}
        cursor = date.fromisoformat(START)
        while cursor<=today:
            start,end=period_bounds(cursor,kind)
            groups[start] = {"end":end,"articles":[]}
            cursor=end+timedelta(days=1)
        for row in corpus.values():
            start,_=period_bounds(date.fromisoformat(row["published_at"][:10]),kind)
            groups[start]["articles"].append(row)
        for start,group in sorted(groups.items(),reverse=True):
            previous_start,_=period_bounds(start-timedelta(days=1),kind)
            previous_articles=groups.get(previous_start,{}).get('articles',[])
            period = build_period(kind,start,group["end"],group["articles"],today,coverage,previous_articles)
            filename = f"data/trends/{kind}/{period['id']}.json"
            atomic_json(root/filename,period)
            result[kind].append({k:period[k] for k in ("id","label","start","end","in_progress","partial","article_count","source_count")}|{"file":filename})
    atomic_json(root/"data/trends.json",result)
    print(f"Trends: {len(corpus)} articles, {len(result['weekly'])} weeks, {len(result['monthly'])} months")
    return result


if __name__ == "__main__":
    build()
