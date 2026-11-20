"""Collect dated public product rates and keep an auditable monthly history."""

import argparse
import calendar
import csv
import io
import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from lxml import html

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data/product-rates"
BASE = "https://brand.metlife.co.kr/pn/tsmmInttr/"
SOURCES = (
    ("메트라이프", BASE + "retrieveTsmmInttrPop_1.do", "metlife_annuity"),
    ("메트라이프", BASE + "retrieveTsmmInttrMain.do", "metlife_current"),
    ("AIA생명", "https://mypage.aia.co.kr/AIAHomepage/disclosure/our-products/interest-rate/interest-rate-linked.do", "aia"),
    ("NH농협생명", "https://www.nhlife.co.kr/ho/on/HOON0038M00.nhl", "nh"),
)
SEOUL = ZoneInfo("Asia/Seoul")
HEADERS = {
    "month": "기준월", "company": "회사", "category": "공시 분류", "product": "공시 상품명",
    "cohort": "적용 계약 구분", "rate_basis": "이율 구분", "rate_percent": "공시·적용이율(%)",
    "minimum": "최저보증이율 원문", "start": "이율 적용 시작일", "end": "이율 적용 종료일",
    "previous_percent": "전월 공시이율(%)", "change_pp": "전월 차이(%p)",
    "comparison": "전월 비교 상태", "ga_status": "GA 판매 여부", "source_url": "공식 공시 URL",
}


def clean(value):
    return " ".join(value.split())


def cell_text(cell):
    lines = [""]
    for node in cell.xpath(".//text() | .//br"):
        if isinstance(node, str):
            lines[-1] += node
        else:
            lines.append("")
    return " / ".join(clean(line) for line in lines if line.strip())


def table_rows(table):
    """Carry forward multirow cells so a guarantee stays with its products."""
    spans = {}
    for tr in table.xpath("./tbody/tr"):
        row = {}
        for index, (remaining, value) in list(spans.items()):
            row[index] = value
            if remaining == 1:
                del spans[index]
            else:
                spans[index] = (remaining - 1, value)
        index = 0
        for cell in tr.xpath("./th|./td"):
            while index in row:
                index += 1
            value = cell_text(cell)
            for _ in range(int(cell.get("colspan", 1))):
                row[index] = value
                count = int(cell.get("rowspan", 1))
                if count > 1:
                    spans[index] = (count - 1, value)
                index += 1
        yield [row.get(i, "") for i in range(max(row, default=-1) + 1)]


def period(value):
    """Preserve an explicit date range, or expand a labelled calendar month."""
    value = re.sub(r"\s|월", "", value)
    months = re.fullmatch(r"(\d{4})\.(\d{1,2})", value)
    if months:
        year, month = map(int, months.groups())
        start = date(year, month, 1)
        end = start.replace(day=calendar.monthrange(year, month)[1])
    else:
        dates = re.fullmatch(r"(\d{4})\.(\d{1,2})\.(\d{1,2})[~～](\d{4})\.(\d{1,2})\.(\d{1,2})", value)
        if not dates:
            raise ValueError(f"확인할 수 없는 공시기간: {value}")
        start = date(*map(int, dates.groups()[:3]))
        end = date(*map(int, dates.groups()[3:]))
    if start > end:
        raise ValueError("적용기간 시작일이 종료일 이후입니다.")
    return start.isoformat(), end.isoformat()


def record(company, url, category, product, cohort, basis, rate, dates, minimum=""):
    if not re.fullmatch(r"\d+(?:\.\d+)?%", rate):
        raise ValueError(f"{company} {category} 이율 형식 변경")
    return dict(company=company, category=category, product=product, cohort=cohort,
                rate_basis=basis, rate_percent=float(Decimal(rate[:-1])), minimum=minimum,
                start=dates[0], end=dates[1], ga_status="확인 필요", source_url=url)


def aia_rates(doc, company, url):
    """Use the product names, contract cohorts and rate columns on AIA's statement."""
    for table in doc.xpath("//table[caption and thead]"):
        caption = clean(table.xpath("string(./caption)"))
        headings = [clean(th.text_content()) for th in table.xpath("./thead/tr[1]/th")]
        if not headings or headings[0] not in {"적용월", "적용기간"}:
            continue
        if "상품명" in headings and "적용이율" in headings:
            product_index, rate_index = headings.index("상품명"), headings.index("적용이율")
            for row in table_rows(table):
                if len(row) != len(headings):
                    continue
                names = [name for name in row[product_index].split(" / ")
                         if re.search("연금보험|연금전환특약|종신보험", name)]
                if not names or row[rate_index] in {"", "-"}:
                    continue
                cohort = re.split(r"\s+-\s+적용", caption, maxsplit=1)[0]
                is_foreign = all(re.search("달러|위안화", name) for name in names)
                if all("종신보험" in name for name in names):
                    category = "외화 종신보험" if is_foreign else "종신보험"
                else:
                    category = "외화 연금보험" if is_foreign else "연금보험·연금전환특약"
                yield record(company, url, category, " / ".join(names), cohort, "적용이율",
                             row[rate_index], period(row[0]))
            continue

        product = clean(re.split(r"\s+-\s+적용", caption, maxsplit=1)[0].replace("상세", ""))
        if re.search(r"GOLDEN TIME 연금보험(?:III|IV|V|Ⅲ|Ⅳ|Ⅴ|Ⅵ)\s|AIA 달러로 받는 연금보험", product):
            indexes = [i for i, name in enumerate(headings) if "이율확정형" in name]
            category = "외화 연금보험"
        elif "종신보험" in product:
            indexes = [i for i, name in enumerate(headings) if name == "적용이율"]
            category = "외화 종신보험" if "달러" in product else "종신보험"
        else:
            continue
        for row in table_rows(table):
            if len(row) != len(headings):
                continue
            for i in indexes:
                if row[i] not in {"", "-"}:
                    yield record(company, url, category, product, "", headings[i], row[i], period(row[0]))


def nh_rates(doc, company, url):
    """Read the two dated columns directly from the monthly disclosure headers."""
    for table in doc.xpath("//table[caption and thead]"):
        caption = clean(table.xpath("string(./caption)"))
        labels = [clean(th.text_content()) for th in table.xpath("./thead/tr[1]/th")]
        date_cells = table.xpath("./thead/tr[2]/th")
        if not caption.startswith("신공시이율") or labels != ["상품군", "배당여부", "적용이율", "적용상품", "적용기간"]:
            continue
        if len(date_cells) != 2:
            raise ValueError("NH 공시 연월 열이 바뀌었습니다.")
        periods = [period(th.text_content()) for th in date_cells]
        for row in table_rows(table):
            if len(row) != 6 or row[-1] != "1개월":
                continue
            group, dividend, prior, current, products, _ = row
            if group == "보장":
                products = " / ".join(name for name in products.split(" / ") if "종신보험" in name)
                category = "종신보험"
            elif group in {"연금", "연금 저축", "연금저축"}:
                category = "연금보험·연금전환특약" if group == "연금" else "연금저축보험"
            else:
                continue
            if not products:
                continue
            for rate, dates in zip((prior, current), periods):
                if rate not in {"", "-"}:
                    yield record(company, url, category, products, f"{caption} · {dividend}",
                                 "적용이율", rate, dates)


def parse_metlife_rates(doc, company, url, parser):
    records = []
    for table in doc.xpath("//table[thead//th[contains(., '공시이율')]]"):
        caption = clean(table.xpath("string(./caption)"))
        if parser == "metlife_annuity":
            if not caption.startswith("2017.04.01 이후"):
                continue
            category, cohort = "연금보험·연금전환특약", "2017-04-01 이후 계약 공시 구간"
            period = doc.xpath("//*[contains(text(), '적용기간')][not(ancestor::table)]")[0]
            dates = re.findall(r"(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일", clean(period.text_content()))
        else:
            labels = {"4": "보장성보험", "5": "외화 연금보험", "7": "외화 보장성보험"}
            match = re.match(r"상품별 공시이율\s*([457])\s*\(", caption)
            if not match:
                continue
            category, cohort = labels[match[1]], ""
            previous = table.getprevious()
            dates = re.findall(r"(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일", previous.text_content())
        if len(dates) != 2:
            raise ValueError(f"{category} 적용기간 형식 변경")
        start, end = [date(*map(int, item)).isoformat() for item in dates]
        if start > end:
            raise ValueError("적용기간 시작일이 종료일 이후입니다.")
        for row in table_rows(table):
            if len(row) < 3 or not row[0]:
                continue
            if parser == "metlife_current" and category.endswith("보장성보험") and "종신" not in row[0]:
                continue
            records.append(record(company, url, category, row[0], cohort,
                                  "공시이율", row[1], (start, end), row[2]))
    return records


def parse_rates(body, company, url, parser):
    doc = html.fromstring(body, parser=html.HTMLParser(encoding="utf-8"))
    if parser == "aia":
        rows = list(aia_rates(doc, company, url))
    elif parser == "nh":
        rows = list(nh_rates(doc, company, url))
    else:
        rows = parse_metlife_rates(doc, company, url, parser)
    if not rows:
        raise ValueError("공시 표에서 읽을 수 있는 행이 없습니다.")
    return rows


def source_rows(company, url, parser):
    request = Request(url, headers={"User-Agent": "MorningBriefPublicDisclosure/1.0"})
    for attempt in range(2):
        try:
            with urlopen(request, timeout=25) as response:
                body = response.read(2_000_001)
            break
        except (TimeoutError, URLError) as error:
            reason = error.reason if isinstance(error, URLError) else error
            if attempt or not isinstance(reason, TimeoutError):
                raise
    if len(body) > 2_000_000:
        raise ValueError("공시 페이지 크기 제한 초과")
    return parse_rates(body, company, url, parser)


def identity(row):
    return (
        row["company"], row["category"], row["product"], row["cohort"],
        row.get("rate_basis", "공시이율"), row["source_url"],
    )


def sort_key(row):
    return (*identity(row), row["start"], row["end"])


def month_rows(rows, month, previous):
    first = date.fromisoformat(month + "-01")
    last = first.replace(day=calendar.monthrange(first.year, first.month)[1]).isoformat()
    prior_end = (first - timedelta(days=1)).isoformat()
    prior = {}
    current_prior_keys = {
        identity(row) for row in rows if row["start"] <= prior_end <= row["end"]
    }
    history = [row for row in previous if identity(row) not in current_prior_keys]
    for row in [*history, *rows]:
        if row["start"] <= prior_end <= row["end"]:
            prior.setdefault(identity(row), set()).add(row["rate_percent"])
    result = []
    for row in rows:
        if row["end"] < first.isoformat() or row["start"] > last:
            continue
        possible = prior.get(identity(row), set())
        before = next(iter(possible)) if len(possible) == 1 else None
        change = None if before is None else float(
            Decimal(str(row["rate_percent"])) - Decimal(str(before))
        )
        result.append(dict(
            row, month=month, rate_basis=row.get("rate_basis", "공시이율"),
            previous_percent=before, change_pp=change,
            comparison="비교 완료" if before is not None else "전월 동일 공시값 미확인",
        ))
    return sorted(result, key=sort_key)


def write_snapshot(month, rows):
    OUTPUT.mkdir(parents=True, exist_ok=True)
    target = OUTPUT / f"{month}.json"
    payload = json.dumps(rows, ensure_ascii=False, indent=2) + "\n"
    csv_buffer = io.StringIO(newline="")
    csv_buffer.write("\ufeff")
    writer = csv.writer(csv_buffer)
    writer.writerow(HEADERS.values())
    for row in rows:
        values = [row[key] for key in HEADERS]
        writer.writerow("'" + v if isinstance(v, str) and v.startswith(("=", "+", "-", "@")) else v for v in values)
    for path, content in ((target, payload), (target.with_suffix(".csv"), csv_buffer.getvalue())):
        temporary = path.with_suffix(f"{path.suffix}.tmp")
        temporary.write_bytes(content.encode("utf-8"))
        temporary.replace(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--month", default=datetime.now(SEOUL).strftime("%Y-%m"))
    args = parser.parse_args()
    month = date.fromisoformat(args.month + "-01")
    previous = OUTPUT / ((month - timedelta(days=1)).strftime("%Y-%m") + ".json")
    prior = json.loads(previous.read_text(encoding="utf-8")) if previous.exists() else []
    existing = OUTPUT / f"{args.month}.json"
    saved = json.loads(existing.read_text(encoding="utf-8")) if existing.exists() else []
    rows, report = [], []
    with ThreadPoolExecutor(max_workers=len(SOURCES)) as executor:
        requests = [executor.submit(source_rows, *source) for source in SOURCES]
        for (company, url, _), request in zip(SOURCES, requests):
            stored = [
                dict(row, rate_basis=row.get("rate_basis", "공시이율"))
                for row in saved if row["source_url"] == url
            ]
            try:
                fresh = request.result()
                effective = month_rows(fresh, args.month, prior)
                if not effective:
                    raise ValueError("해당 월 공시 없음")
            except Exception as error:
                rows.extend(stored)
                report.append(dict(company=company, source_url=url, rows=len(stored),
                                   status="기존 자료 유지" if stored else "당월 확인 필요",
                                   reason=type(error).__name__))
                print(f"::warning::{company} 공시 확인 실패 ({type(error).__name__})")
                continue

            # Some sources display only the current half-month. Preserve an earlier
            # non-overlapping period for a contract that is still in the same table.
            current_keys = {identity(row) for row in effective}
            carried = [
                old for old in stored if identity(old) in current_keys
                and not any(identity(new) == identity(old) and old["start"] <= new["end"]
                            and new["start"] <= old["end"] for new in effective)
            ]
            rows.extend(effective + carried)
            report.append(dict(company=company, source_url=url, rows=len(effective) + len(carried),
                               status="당월 수집 완료"))
    if not any(entry["status"] == "당월 수집 완료" for entry in report):
        raise SystemExit(f"{args.month}: 당월 공식 공시를 읽지 못했습니다. 기존 파일을 유지합니다.")
    snapshot = sorted(rows, key=sort_key)
    write_snapshot(args.month, snapshot)
    status = OUTPUT / f"{args.month}-status.json"
    temporary = status.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(status)
    print(f"{args.month}: {len(snapshot)} public disclosure rows from {len({row['company'] for row in snapshot})} insurers")


if __name__ == "__main__":
    main()
