import csv
import datetime as dt
import html
import re
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urljoin


START_DATE = dt.date(2013, 1, 1)
END_DATE = dt.date(2026, 5, 11)

XWFB_BASE = "https://www.ndrc.gov.cn/xwdt/xwfb/"
TOPIC_BASE = "https://www.ndrc.gov.cn/xwdt/ztzl/gncpyjg/"

OUT_FULL = Path("china_refined_oil_adjustments_2013_2026.csv")
OUT_GAS_SERIES = Path("china_refined_oil_beijing_gasoline_limit_series_2013_2026.csv")
OUT_DIESEL_SERIES = Path("china_refined_oil_beijing_diesel_limit_series_2013_2026.csv")
OUT_REVIEW = Path("china_refined_oil_parse_review_2013_2026.csv")

# Latest official NDRC attachment after the 2026-05-08 24:00 adjustment
# (effective from 2026-05-09 00:00):
# "各省（区、市）和中心城市汽、柴油最高零售价格", Beijing row, standard products.
LATEST_BASE_DATE = dt.date(2026, 5, 9)
LATEST_BEIJING_GASOLINE_CEILING = 10855
LATEST_BEIJING_DIESEL_CEILING = 9780

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


def fetch(url: str) -> str:
    # The NDRC site is reliable with curl on this Windows host; urllib often
    # waits on a closed TLS connection before falling back, so go straight there.
    cmd = ["curl.exe", "-s", "-L", "--tlsv1.2", "-A", USER_AGENT, url]
    last_error = None
    for attempt in range(3):
        try:
            data = subprocess.check_output(cmd, timeout=40)
            return data.decode("utf-8", errors="ignore")
        except Exception as exc:
            last_error = exc
            time.sleep(1 + attempt)
    raise last_error


def clean_text(raw_html: str) -> str:
    s = re.sub(r"(?is)<script.*?</script>", " ", raw_html)
    s = re.sub(r"(?is)<style.*?</style>", " ", s)
    s = re.sub(r"(?is)<[^>]+>", " ", s)
    s = html.unescape(s)
    s = s.replace("\u3000", " ")
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def parse_date(date_text: str, title: str = "") -> dt.date | None:
    candidates = [date_text, title]
    for value in candidates:
        m = re.search(r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})", value)
        if m:
            return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        m = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", value)
        if m:
            return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return None


def wanted_notice(title: str) -> bool:
    if "成品油" not in title or "价格" not in title:
        return False
    if not any(x in title for x in ["调整", "上调", "下调", "提高", "降低", "不作调整", "不调整"]):
        return False
    skip_words = ["答记者问", "负责同志", "超过每桶", "暂不再上调", "临时调控措施"]
    return not any(x in title for x in skip_words)


def list_notices() -> list[dict]:
    notices: list[dict] = []
    pages = [("xwfb", XWFB_BASE, "index.html")]
    pages += [("xwfb", XWFB_BASE, f"index_{i}.html") for i in range(1, 13)]
    pages += [("topic", TOPIC_BASE, "index.html")]
    pages += [("topic", TOPIC_BASE, f"index_{i}.html") for i in range(1, 10)]

    item_re = re.compile(
        r'<li><a href="(?P<href>[^"]+)"[^>]*title="(?P<title>[^"]*)"[^>]*>.*?</a><span>(?P<date>[^<]+)</span>',
        re.S,
    )

    seen = set()
    for source, base, page in pages:
        url = urljoin(base, page)
        page_html = fetch(url)
        for m in item_re.finditer(page_html):
            title = html.unescape(m.group("title")).strip()
            if not wanted_notice(title):
                continue
            notice_date = parse_date(m.group("date"), title)
            if notice_date is None or notice_date < START_DATE or notice_date > END_DATE:
                continue
            href = html.unescape(m.group("href"))
            full_url = urljoin(url, href)
            key = (notice_date.isoformat(), title)
            if key in seen:
                continue
            seen.add(key)
            notices.append(
                {
                    "notice_date": notice_date,
                    "title": title,
                    "url": full_url,
                    "list_source": source,
                }
            )

    # This official NDRC notice is absent from the old topic list but is part
    # of the 2013 adjustment sequence after the pricing-mechanism change.
    notices.append(
        {
            "notice_date": dt.date(2013, 3, 27),
            "title": "国家发展改革委关于降低国内成品油价格的通知（3月27日零时起）",
            "url": "https://www.nea.gov.cn/2013-03/27/c_132265925.htm",
            "list_source": "manual_government_source",
            "manual_gasoline_adjust": -310,
            "manual_diesel_adjust": -300,
            "manual_price_date": dt.date(2013, 3, 27),
        }
    )
    return sorted(notices, key=lambda row: row["notice_date"])


def sign_for(verb: str) -> int:
    if verb in ["提高", "上调", "上涨"]:
        return 1
    if verb in ["降低", "下调", "下降", "调降"]:
        return -1
    raise ValueError(f"unknown verb: {verb}")


PATTERNS = [
    re.compile(
        r"实际(?P<verb>提高|上调|上涨|降低|下调|下降|调降)(?P<gas>\d+)元?[和、，,](?P<diesel>\d+)元"
    ),
    re.compile(
        r"汽[、,，]?柴油(?:（[^）]*）)?(?:最高零售)?价格(?:（[^）]*）)?每吨分别(?P<verb>提高|上调|上涨|降低|下调|下降|调降)(?P<gas>\d+)元?[和、，,](?P<diesel>\d+)元"
    ),
    re.compile(
        r"汽[、,，]?柴油价格(?:（[^）]*）)?每吨分别(?P<verb>提高|上调|上涨|降低|下调|下降|调降)(?P<gas>\d+)元?[和、，,](?P<diesel>\d+)元"
    ),
    re.compile(
        r"汽[、,，]?柴油(?:（[^）]*）)?(?:最高零售)?价格(?:（[^）]*）)?每吨均(?P<verb>提高|上调|上涨|降低|下调|下降|调降)(?P<both>\d+)元"
    ),
    re.compile(
        r"汽[、,，]?柴油(?:（[^）]*）)?(?:最高零售)?价格(?:（[^）]*）)?每吨(?P<verb>提高|上调|上涨|降低|下调|下降|调降)(?P<both>\d+)元"
    ),
    re.compile(
        r"用汽[、,，]?柴油(?:（[^）]*）)?供应价格每吨分别(?P<verb>提高|上调|上涨|降低|下调|下降|调降)(?P<gas>\d+)元?[和、，,](?P<diesel>\d+)元"
    ),
    re.compile(
        r"用汽[、,，]?柴油(?:（[^）]*）)?供应价格每吨均(?P<verb>提高|上调|上涨|降低|下调|下降|调降)(?P<both>\d+)元"
    ),
    re.compile(
        r"汽油[^。；;]*?价格每吨(?P<gverb>提高|上调|上涨|降低|下调|下降|调降)(?P<gas>\d+)元[；;，,、和\s]*柴油[^。；;]*?价格每吨(?P<dverb>提高|上调|上涨|降低|下调|下降|调降)(?P<diesel>\d+)元"
    ),
    re.compile(
        r"汽油价格每吨(?P<gverb>提高|上调|上涨|降低|下调|下降|调降)(?P<gas>\d+)元[；;，,、和\s]*柴油价格每吨(?P<dverb>提高|上调|上涨|降低|下调|下降|调降)(?P<diesel>\d+)元"
    ),
]


def parse_adjustment(text: str, title: str) -> tuple[int | None, int | None, str]:
    combined = f"{title} {text}"
    compact = re.sub(r"\s+", "", combined).replace("(", "（").replace(")", "）")
    for pattern in PATTERNS:
        m = pattern.search(compact)
        if not m:
            continue
        groups = m.groupdict()
        if groups.get("both"):
            amount = int(groups["both"]) * sign_for(groups["verb"])
            return amount, amount, "parsed"
        if groups.get("verb"):
            sign = sign_for(groups["verb"])
            return int(groups["gas"]) * sign, int(groups["diesel"]) * sign, "parsed"
        gas = int(groups["gas"]) * sign_for(groups["gverb"])
        diesel = int(groups["diesel"]) * sign_for(groups["dverb"])
        return gas, diesel, "parsed"
    if re.search(r"(不作调整|不予调整|暂不调整|不调整)", combined):
        return 0, 0, "none"
    return None, None, "needs_review"


def parse_price_date(text: str, title: str, notice_date: dt.date) -> dt.date:
    combined = f"{title} {text}"
    compact = re.sub(r"\s+", "", combined).replace("０", "0")
    m = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日(24时|零时|0时)", compact)
    if not m:
        m2 = re.search(r"(\d{1,2})月(\d{1,2})日(24时|零时|0时)", compact)
        if m2:
            base = dt.date(notice_date.year, int(m2.group(1)), int(m2.group(2)))
            return base + dt.timedelta(days=1) if m2.group(3) == "24时" else base
        return notice_date
    base = dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return base + dt.timedelta(days=1) if m.group(4) == "24时" else base


def add_beijing_ceiling(rows: list[dict]) -> None:
    rows_desc = sorted(rows, key=lambda row: row["date"], reverse=True)
    gas_after = LATEST_BEIJING_GASOLINE_CEILING
    diesel_after = LATEST_BEIJING_DIESEL_CEILING
    for row in rows_desc:
        row["beijing_gasoline_ceiling_after_cny_per_ton"] = gas_after
        row["beijing_diesel_ceiling_after_cny_per_ton"] = diesel_after
        gas_after -= row["gasoline_adjust_cny_per_ton"]
        diesel_after -= row["diesel_adjust_cny_per_ton"]


def write_outputs(rows: list[dict]) -> None:
    full_fields = [
        "date",
        "notice_date",
        "gasoline_adjust_cny_per_ton",
        "diesel_adjust_cny_per_ton",
        "beijing_gasoline_ceiling_after_cny_per_ton",
        "beijing_diesel_ceiling_after_cny_per_ton",
        "notice_title",
        "source_url",
    ]
    with OUT_FULL.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=full_fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row[field] for field in full_fields})

    with OUT_GAS_SERIES.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        for row in rows:
            writer.writerow(
                [
                    row["date"],
                    row["beijing_gasoline_ceiling_after_cny_per_ton"],
                ]
            )

    with OUT_DIESEL_SERIES.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        for row in rows:
            writer.writerow(
                [
                    row["date"],
                    row["beijing_diesel_ceiling_after_cny_per_ton"],
                ]
            )


def main() -> int:
    notices = list_notices()
    rows: list[dict] = []
    review: list[dict] = []

    for idx, notice in enumerate(notices, start=1):
        if idx % 25 == 0:
            print(f"Fetched {idx}/{len(notices)} notices...", file=sys.stderr)
        try:
            if "manual_gasoline_adjust" in notice:
                text = ""
                gas = notice["manual_gasoline_adjust"]
                diesel = notice["manual_diesel_adjust"]
                price_date = notice["manual_price_date"]
                status = "manual"
            else:
                raw = fetch(notice["url"])
                text = clean_text(raw)
                gas, diesel, status = parse_adjustment(text, notice["title"])
                price_date = parse_price_date(text, notice["title"], notice["notice_date"])
        except Exception as exc:
            gas, diesel, status = None, None, f"error: {exc}"
            text = ""
            price_date = notice["notice_date"]

        if gas is None or diesel is None:
            review.append(
                {
                    "date": price_date.isoformat(),
                    "notice_date": notice["notice_date"].isoformat(),
                    "title": notice["title"],
                    "url": notice["url"],
                    "status": status,
                    "text_excerpt": text[:500],
                }
            )
            continue

        rows.append(
            {
                "date": price_date.isoformat(),
                "notice_date": notice["notice_date"].isoformat(),
                "gasoline_adjust_cny_per_ton": gas,
                "diesel_adjust_cny_per_ton": diesel,
                "notice_title": notice["title"],
                "source_url": notice["url"],
            }
        )

    rows = sorted(rows, key=lambda row: row["date"])
    if not any(row["date"] == LATEST_BASE_DATE.isoformat() for row in rows):
        raise RuntimeError(f"latest base date {LATEST_BASE_DATE} not found in parsed rows")
    add_beijing_ceiling(rows)
    write_outputs(rows)

    with OUT_REVIEW.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=["date", "notice_date", "title", "url", "status", "text_excerpt"]
        )
        writer.writeheader()
        writer.writerows(review)

    print(f"notices={len(notices)} rows={len(rows)} review={len(review)}")
    print(f"wrote: {OUT_FULL}")
    print(f"wrote: {OUT_GAS_SERIES}")
    print(f"wrote: {OUT_DIESEL_SERIES}")
    print(f"wrote: {OUT_REVIEW}")
    return 0 if not review else 2


if __name__ == "__main__":
    raise SystemExit(main())
