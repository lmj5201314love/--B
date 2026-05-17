from __future__ import annotations

import html
import re
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data_utils import (  # noqa: E402
    ensure_project_dirs,
    format_date,
    format_number,
    parse_date,
    parse_float,
    read_csv_auto,
    write_csv,
)


RAW_PATH = ROOT / "data" / "raw" / "china_refined_oil_adjustments_2013_2026.csv"
OUT_PATH = ROOT / "data" / "processed" / "china_refined_oil_special_control_2016_2026.csv"
START_DATE = date(2016, 1, 27)
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


SPECIAL_PATTERNS = (
    "调控风险准备金",
    "风险准备金",
    "低于每桶40美元",
    "低于每桶 40 美元",
    "高于每桶130美元",
    "高于每桶 130 美元",
    "第六条规定",
    "继续实施调控",
    "国家继续实施调控",
    "增值税税率",
    "因增值税",
)

NORMAL_MECHANISM_PATTERNS = (
    "按照现行成品油价格形成机制",
    "根据近期国际市场油价变化情况",
    "根据国际市场油价变化情况",
    "根据《石油价格管理办法》",
    "调价金额每吨不足50元",
    "低于每吨50元",
    "不足50元",
    "未调金额纳入下次调价时累加或冲抵",
)


def fetch(url: str) -> str:
    cmd = [
        "curl.exe",
        "-s",
        "-L",
        "--tlsv1.2",
        "-A",
        USER_AGENT,
        url,
    ]
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            data = subprocess.check_output(cmd, timeout=45)
            return data.decode("utf-8", errors="ignore")
        except Exception as exc:  # pragma: no cover - network failures are environment-specific
            last_error = exc
            time.sleep(1 + attempt)
    if last_error:
        raise last_error
    return ""


def clean_html(raw_html: str) -> str:
    text = re.sub(r"(?is)<script.*?</script>", " ", raw_html)
    text = re.sub(r"(?is)<style.*?</style>", " ", text)
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    text = html.unescape(text)
    text = text.replace("\u3000", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def classify_special_control(title: str, source_url: str) -> tuple[str, str]:
    if "按机制" in title:
        return "否", "title_contains_按机制"

    text = ""
    if source_url:
        text = clean_html(fetch(source_url))
    combined = f"{title} {text}"
    compact = re.sub(r"\s+", "", combined)

    for pattern in SPECIAL_PATTERNS:
        if pattern.replace(" ", "") in compact:
            return "是", f"special_keyword:{pattern}"

    if "调控" in compact:
        return "是", "contains_调控"

    for pattern in NORMAL_MECHANISM_PATTERNS:
        if pattern.replace(" ", "") in compact:
            return "否", f"normal_mechanism_keyword:{pattern}"

    if "不作调整" in title and parse_float_from_title(title) == 0:
        return "否", "title_no_adjust_without_special_keyword"

    return "否", "default_no_special_keyword"


def parse_float_from_title(title: str) -> float | None:
    return 0 if "不作调整" in title else None


def yes_no_changed(gasoline_change: float | None, diesel_change: float | None) -> str:
    return "是" if (gasoline_change not in (None, 0) or diesel_change not in (None, 0)) else "否"


def main() -> None:
    ensure_project_dirs(ROOT)
    _, rows, _ = read_csv_auto(RAW_PATH)
    output_rows: list[dict[str, str]] = []
    basis_counts: dict[str, int] = {}

    for row in rows:
        adjust_date = parse_date(row.get("date", ""))
        if adjust_date is None or adjust_date < START_DATE:
            continue

        title = row.get("notice_title", "")
        source_url = row.get("source_url", "")
        gasoline_change = parse_float(row.get("gasoline_adjust_cny_per_ton", ""))
        diesel_change = parse_float(row.get("diesel_adjust_cny_per_ton", ""))
        is_special, basis = classify_special_control(title, source_url)
        basis_counts[basis] = basis_counts.get(basis, 0) + 1

        output_rows.append(
            {
                "date": format_date(adjust_date),
                "gasoline_change": format_number(gasoline_change),
                "diesel_change": format_number(diesel_change),
                "gasoline_price_after": format_number(
                    parse_float(row.get("beijing_gasoline_ceiling_after_cny_per_ton", ""))
                ),
                "diesel_price_after": format_number(
                    parse_float(row.get("beijing_diesel_ceiling_after_cny_per_ton", ""))
                ),
                "是否变化": yes_no_changed(gasoline_change, diesel_change),
                "是否特殊调控": is_special,
            }
        )

    output_rows.sort(key=lambda item: item["date"])
    write_csv(
        OUT_PATH,
        output_rows,
        [
            "date",
            "gasoline_change",
            "diesel_change",
            "gasoline_price_after",
            "diesel_price_after",
            "是否变化",
            "是否特殊调控",
        ],
    )

    print(f"Wrote {OUT_PATH}")
    print(f"Rows: {len(output_rows)}")
    print("Decision basis counts:")
    for basis, count in sorted(basis_counts.items(), key=lambda item: (-item[1], item[0])):
        print(f"  {basis}: {count}")


if __name__ == "__main__":
    main()
