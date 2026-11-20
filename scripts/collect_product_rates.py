"""Collect dated public product rates and keep an auditable monthly history."""

import argparse
import calendar
import csv
import io
import json
import re
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from lxml import html

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data/product-rates"
BASE = "https://brand.metlife.co.kr/pn/tsmmInttr/"
SOURCES = (
    ("메트라이프", BASE + "retrieveTsmmInttrPop_1.do", "metlife_annuity"),
    ("메트라이프", BASE + "retrieveTsmmInttrMain.do", "metlife_current"),
)
SEOUL = ZoneInfo("Asia/Seoul")
HEADERS = {
    "month": "기준월", "company": "회사", "category": "공시 분류", "product": "공시 상품명",
    "cohort": "적용 계약 구분", "rate_percent": "공시이율(%)",
    "minimum": "최저보증이율 원문", "start": "이율 적용 시작일", "end": "이율 적용 종료일",
    "previous_percent": "전월 공시이율(%)", "change_pp": "전월 차이(%p)",
    "comparison": "전월 비교 상태", "ga_status": "GA 판매 여부", "source_url": "공식 공시 URL",
}


def clean(value):
    return " ".join(value.split())


def cell_text(cell):
    return " / ".join(clean(line) for fragment in re.split(
        r"<br\s*/?>", html.tostring(cell, encoding="unicode"), flags=re.I
    ) if (line := html.fragment_fromstring(fragment, create_parent=True).text_content()).strip())


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


def parse_rates(body, company, url, parser):
    doc = html.fromstring(body)
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
            try:
                rate = Decimal(row[1].strip().removesuffix("%"))
                if not rate.is_finite() or not row[1].endswith("%"):
                    raise ValueError
            except (ArithmeticError, ValueError) as error:
                raise ValueError(f"{category} 공시이율 형식 변경") from error
            if parser == "metlife_current" and category.endswith("보장성보험") and "종신" not in row[0]:
                continue
            records.append(dict(company=company, category=category, product=row[0], cohort=cohort,
                                rate_percent=float(rate), minimum=row[2], start=start, end=end,
                                ga_status="확인 필요", source_url=url))
    if not records:
        raise ValueError("공시 표에서 읽을 수 있는 행이 없습니다.")
    return records


def source_rows(company, url, parser):
    request = Request(url, headers={"User-Agent": "MorningBriefPublicDisclosure/1.0"})
    with urlopen(request, timeout=30) as response:
        body = response.read(2_000_001)
    if len(body) > 2_000_000:
        raise ValueError("공시 페이지 크기 제한 초과")
    return parse_rates(body, company, url, parser)


def identity(row):
    return tuple(row[key] for key in ("company", "category", "product", "cohort", "source_url"))


def month_rows(rows, month, previous):
    first = date.fromisoformat(month + "-01")
    last = first.replace(day=calendar.monthrange(first.year, first.month)[1]).isoformat()
    prior_end = (first - timedelta(days=1)).isoformat()
    prior = {}
    for row in previous:
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
            row, month=month, previous_percent=before, change_pp=change,
            comparison="비교 완료" if before is not None else "전월 동일 공시값 미확인",
        ))
    return sorted(result, key=lambda row: (*identity(row), row["start"], row["end"]))


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
    rows = []
    for company, url, source_parser in SOURCES:
        rows.extend(source_rows(company, url, source_parser))
    snapshot = month_rows(rows, args.month, prior)
    if len({row["source_url"] for row in snapshot}) != len(SOURCES):
        raise SystemExit(f"{args.month} 적용기간에 해당하는 공시가 아직 모두 나오지 않았습니다. 저장된 파일을 유지합니다.")
    write_snapshot(args.month, snapshot)
    print(f"{args.month}: {len(snapshot)} public disclosure rows saved")


if __name__ == "__main__":
    main()
