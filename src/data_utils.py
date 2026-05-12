from __future__ import annotations

import csv
import math
import re
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from statistics import mean, median
from typing import Any, Iterable


DATE_FORMATS = (
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%Y.%m.%d",
    "%Y-%m",
    "%Y/%m",
    "%Y.%m",
)


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def ensure_project_dirs(root: Path | None = None) -> None:
    root = root or project_root()
    for relative in (
        "data/raw",
        "data/processed",
        "outputs/tables",
        "outputs/figures",
        "reports",
        "scripts",
        "src",
    ):
        (root / relative).mkdir(parents=True, exist_ok=True)


def read_text_lines(path: Path) -> list[str]:
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return path.read_text(encoding=encoding).splitlines()
        except UnicodeDecodeError:
            continue
    return path.read_text(errors="replace").splitlines()


def parse_date(value: Any) -> date | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    for fmt in DATE_FORMATS:
        try:
            parsed = datetime.strptime(text, fmt).date()
            if fmt in ("%Y-%m", "%Y/%m", "%Y.%m"):
                return parsed.replace(day=1)
            return parsed
        except ValueError:
            pass
    try:
        return datetime.fromisoformat(text).date()
    except ValueError:
        return None


def format_date(value: date | None) -> str:
    return value.isoformat() if value else ""


def month_key(value: date | str | None) -> str:
    parsed = value if isinstance(value, date) else parse_date(value)
    return parsed.strftime("%Y-%m") if parsed else ""


def parse_float(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if text == "" or text.lower() in {"na", "nan", "none", "null", "--", "-"}:
        return None
    text = text.replace(",", "").replace("%", "")
    try:
        number = float(text)
    except ValueError:
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def format_number(value: float | int | None, digits: int = 6) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return ""
        text = f"{value:.{digits}f}".rstrip("0").rstrip(".")
        return "0" if text == "-0" else text
    return str(value)


def safe_divide(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator


def row_looks_like_header(row: list[str]) -> bool:
    lowered = [cell.strip().lower() for cell in row]
    if any(cell in {"date", "month", "notice_date", "price"} for cell in lowered):
        return True
    if lowered and parse_date(lowered[0]) is not None:
        return False
    alpha_cells = sum(bool(re.search(r"[A-Za-z_]", cell)) for cell in row)
    return alpha_cells >= max(1, len(row) // 2)


def _dedupe_headers(headers: list[str]) -> list[str]:
    counts: Counter[str] = Counter()
    result: list[str] = []
    for index, header in enumerate(headers, start=1):
        clean = header.strip() or f"column_{index}"
        counts[clean] += 1
        if counts[clean] > 1:
            clean = f"{clean}_{counts[clean]}"
        result.append(clean)
    return result


def read_csv_auto(path: Path) -> tuple[list[str], list[dict[str, str]], list[str]]:
    lines = read_text_lines(path)
    raw_rows = [row for row in csv.reader(lines) if any(cell.strip() for cell in row)]
    if not raw_rows:
        return [], [], []

    metadata: list[str] = []
    first_row = raw_rows[0]
    data_rows = raw_rows
    if len(first_row) == 1 and len(raw_rows) > 1 and len(raw_rows[1]) > 1:
        metadata.append(first_row[0])
        data_rows = raw_rows[1:]

    if not data_rows:
        return [], [], metadata

    if row_looks_like_header(data_rows[0]):
        headers = _dedupe_headers(data_rows[0])
        values = data_rows[1:]
    else:
        max_width = max(len(row) for row in data_rows)
        headers = [f"column_{index}" for index in range(1, max_width + 1)]
        values = data_rows

    rows: list[dict[str, str]] = []
    for row in values:
        padded = row + [""] * (len(headers) - len(row))
        rows.append({header: padded[index].strip() for index, header in enumerate(headers)})
    return headers, rows, metadata


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({name: row.get(name, "") for name in fieldnames})


def numeric_columns(headers: list[str], rows: list[dict[str, str]], threshold: float = 0.8) -> list[str]:
    columns: list[str] = []
    for header in headers:
        non_missing = [row.get(header, "") for row in rows if str(row.get(header, "")).strip()]
        if not non_missing:
            continue
        parsed = [parse_float(value) for value in non_missing]
        valid = sum(value is not None for value in parsed)
        if valid / len(non_missing) >= threshold:
            columns.append(header)
    return columns


def date_columns(headers: list[str], rows: list[dict[str, str]], threshold: float = 0.8) -> list[str]:
    columns: list[str] = []
    for header in headers:
        non_missing = [row.get(header, "") for row in rows if str(row.get(header, "")).strip()]
        if not non_missing:
            continue
        parsed = [parse_date(value) for value in non_missing]
        valid = sum(value is not None for value in parsed)
        header_hint = "date" in header.lower() or header.lower() == "month"
        if valid / len(non_missing) >= threshold or (header_hint and valid > 0):
            columns.append(header)
    return columns


def column_stats(values: Iterable[float]) -> dict[str, float | int | None]:
    clean = sorted(value for value in values if value is not None and not math.isnan(value))
    if not clean:
        return {
            "count": 0,
            "mean": None,
            "std": None,
            "min": None,
            "q1": None,
            "median": None,
            "q3": None,
            "max": None,
        }
    avg = mean(clean)
    if len(clean) > 1:
        variance = sum((value - avg) ** 2 for value in clean) / (len(clean) - 1)
        std = math.sqrt(variance)
    else:
        std = 0.0

    def percentile(pct: float) -> float:
        if len(clean) == 1:
            return clean[0]
        position = (len(clean) - 1) * pct
        lower = math.floor(position)
        upper = math.ceil(position)
        if lower == upper:
            return clean[int(position)]
        return clean[lower] + (clean[upper] - clean[lower]) * (position - lower)

    return {
        "count": len(clean),
        "mean": avg,
        "std": std,
        "min": clean[0],
        "q1": percentile(0.25),
        "median": median(clean),
        "q3": percentile(0.75),
        "max": clean[-1],
    }


def iqr_outlier_count(values: Iterable[float], multiplier: float = 3.0) -> tuple[int, float | None, float | None]:
    clean = sorted(value for value in values if value is not None and not math.isnan(value))
    if len(clean) < 8:
        return 0, None, None
    stats = column_stats(clean)
    q1 = stats["q1"]
    q3 = stats["q3"]
    if q1 is None or q3 is None:
        return 0, None, None
    iqr = q3 - q1
    lower = q1 - multiplier * iqr
    upper = q3 + multiplier * iqr
    count = sum(value < lower or value > upper for value in clean)
    return count, lower, upper


def sign(value: float | None, eps: float = 1e-9) -> int:
    if value is None or abs(value) <= eps:
        return 0
    return 1 if value > 0 else -1


def linear_regression(xs: list[float], ys: list[float]) -> tuple[float, float]:
    if len(xs) != len(ys) or len(xs) < 2:
        raise ValueError("At least two paired observations are required.")
    x_mean = mean(xs)
    y_mean = mean(ys)
    denom = sum((x - x_mean) ** 2 for x in xs)
    if denom == 0:
        raise ValueError("The explanatory variable has zero variance.")
    slope = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys)) / denom
    intercept = y_mean - slope * x_mean
    return slope, intercept


def mae(actual: list[float], predicted: list[float]) -> float:
    return mean(abs(a - p) for a, p in zip(actual, predicted))


def rmse(actual: list[float], predicted: list[float]) -> float:
    return math.sqrt(mean((a - p) ** 2 for a, p in zip(actual, predicted)))


def direction_accuracy(actual: list[float], predicted: list[float]) -> float:
    if not actual:
        return 0.0
    correct = sum(sign(a) == sign(p) for a, p in zip(actual, predicted))
    return correct / len(actual)
