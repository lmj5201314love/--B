from __future__ import annotations

import html
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data_utils import ensure_project_dirs, parse_date, parse_float, read_csv_auto  # noqa: E402


DATA_PATH = ROOT / "data" / "processed" / "modeling_dataset.csv"
FIGURE_DIR = ROOT / "outputs" / "figures"
WIDTH = 1100
HEIGHT = 620
MARGIN_LEFT = 76
MARGIN_RIGHT = 38
MARGIN_TOP = 56
MARGIN_BOTTOM = 76


COLORS = {
    "basket": "#1f77b4",
    "brent": "#d62728",
    "wti": "#2ca02c",
    "adjust": "#4c78a8",
    "gasoline": "#e45756",
    "diesel": "#54a24b",
    "cpi": "#f58518",
    "ppi": "#b279a2",
    "secondary": "#777777",
}


def load_rows() -> list[dict[str, str]]:
    _, rows, _ = read_csv_auto(DATA_PATH)
    return rows


def scale(value: float, src_min: float, src_max: float, dst_min: float, dst_max: float) -> float:
    if src_max == src_min:
        return (dst_min + dst_max) / 2
    return dst_min + (value - src_min) / (src_max - src_min) * (dst_max - dst_min)


def extent(values: list[float], pad_ratio: float = 0.08) -> tuple[float, float]:
    clean = [value for value in values if value is not None]
    if not clean:
        return 0.0, 1.0
    low = min(clean)
    high = max(clean)
    if low == high:
        return low - 1, high + 1
    pad = (high - low) * pad_ratio
    return low - pad, high + pad


def svg_header(title: str) -> list[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">',
        '<rect width="100%" height="100%" fill="white"/>',
        f'<text x="{WIDTH / 2}" y="30" text-anchor="middle" font-family="Arial" font-size="22" font-weight="700">{html.escape(title)}</text>',
    ]


def axes(lines: list[str], y_min: float, y_max: float, x_label: str, y_label: str) -> None:
    plot_left = MARGIN_LEFT
    plot_right = WIDTH - MARGIN_RIGHT
    plot_top = MARGIN_TOP
    plot_bottom = HEIGHT - MARGIN_BOTTOM
    lines.append(f'<line x1="{plot_left}" y1="{plot_bottom}" x2="{plot_right}" y2="{plot_bottom}" stroke="#333"/>')
    lines.append(f'<line x1="{plot_left}" y1="{plot_top}" x2="{plot_left}" y2="{plot_bottom}" stroke="#333"/>')
    for i in range(6):
        y = scale(i, 0, 5, plot_bottom, plot_top)
        value = scale(i, 0, 5, y_min, y_max)
        lines.append(f'<line x1="{plot_left - 4}" y1="{y:.1f}" x2="{plot_right}" y2="{y:.1f}" stroke="#e6e6e6"/>')
        lines.append(
            f'<text x="{plot_left - 8}" y="{y + 4:.1f}" text-anchor="end" font-family="Arial" font-size="11" fill="#555">{value:.1f}</text>'
        )
    lines.append(
        f'<text x="{(plot_left + plot_right) / 2}" y="{HEIGHT - 24}" text-anchor="middle" font-family="Arial" font-size="13">{html.escape(x_label)}</text>'
    )
    lines.append(
        f'<text x="18" y="{(plot_top + plot_bottom) / 2}" transform="rotate(-90 18 {(plot_top + plot_bottom) / 2})" text-anchor="middle" font-family="Arial" font-size="13">{html.escape(y_label)}</text>'
    )


def legend(lines: list[str], items: list[tuple[str, str]]) -> None:
    x = MARGIN_LEFT
    y = HEIGHT - 44
    for label, color in items:
        lines.append(f'<rect x="{x}" y="{y - 11}" width="16" height="4" fill="{color}"/>')
        lines.append(f'<text x="{x + 22}" y="{y - 6}" font-family="Arial" font-size="12" fill="#333">{html.escape(label)}</text>')
        x += 180


def write_svg(path: Path, lines: list[str]) -> None:
    lines.append("</svg>")
    path.write_text("\n".join(lines), encoding="utf-8")


def line_chart(path: Path, title: str, series: list[tuple[str, list[tuple[date, float]], str]], y_label: str) -> None:
    all_dates = [item[0] for _, points, _ in series for item in points]
    all_values = [item[1] for _, points, _ in series for item in points]
    x_min = min(all_dates).toordinal()
    x_max = max(all_dates).toordinal()
    y_min, y_max = extent(all_values)
    plot_left = MARGIN_LEFT
    plot_right = WIDTH - MARGIN_RIGHT
    plot_top = MARGIN_TOP
    plot_bottom = HEIGHT - MARGIN_BOTTOM
    lines = svg_header(title)
    axes(lines, y_min, y_max, "Date", y_label)
    for label, points, color in series:
        coordinates = []
        for point_date, value in points:
            x = scale(point_date.toordinal(), x_min, x_max, plot_left, plot_right)
            y = scale(value, y_min, y_max, plot_bottom, plot_top)
            coordinates.append(f"{x:.1f},{y:.1f}")
        if coordinates:
            lines.append(f'<polyline fill="none" stroke="{color}" stroke-width="1.8" points="{" ".join(coordinates)}"/>')
    for i in range(6):
        ordinal = int(scale(i, 0, 5, x_min, x_max))
        x = scale(ordinal, x_min, x_max, plot_left, plot_right)
        label = date.fromordinal(ordinal).strftime("%Y-%m")
        lines.append(f'<text x="{x:.1f}" y="{plot_bottom + 22}" text-anchor="middle" font-family="Arial" font-size="11" fill="#555">{label}</text>')
    legend(lines, [(label, color) for label, _, color in series])
    write_svg(path, lines)


def bar_chart(path: Path, title: str, points: list[tuple[date, float]], y_label: str) -> None:
    y_min, y_max = extent([value for _, value in points])
    y_min = min(y_min, 0)
    y_max = max(y_max, 0)
    x_min = min(point[0].toordinal() for point in points)
    x_max = max(point[0].toordinal() for point in points)
    plot_left = MARGIN_LEFT
    plot_right = WIDTH - MARGIN_RIGHT
    plot_top = MARGIN_TOP
    plot_bottom = HEIGHT - MARGIN_BOTTOM
    zero_y = scale(0, y_min, y_max, plot_bottom, plot_top)
    bar_width = max(2, (plot_right - plot_left) / max(len(points), 1) * 0.55)
    lines = svg_header(title)
    axes(lines, y_min, y_max, "Date", y_label)
    lines.append(f'<line x1="{plot_left}" y1="{zero_y:.1f}" x2="{plot_right}" y2="{zero_y:.1f}" stroke="#444"/>')
    for point_date, value in points:
        x = scale(point_date.toordinal(), x_min, x_max, plot_left, plot_right)
        y = scale(value, y_min, y_max, plot_bottom, plot_top)
        color = "#d95f02" if value < 0 else "#1b9e77"
        height = abs(zero_y - y)
        top = min(y, zero_y)
        lines.append(f'<rect x="{x - bar_width / 2:.1f}" y="{top:.1f}" width="{bar_width:.1f}" height="{height:.1f}" fill="{color}" opacity="0.82"/>')
    legend(lines, [("Up adjustment", "#1b9e77"), ("Down adjustment", "#d95f02")])
    write_svg(path, lines)


def scatter_chart(path: Path, title: str, points: list[tuple[float, float]], x_label: str, y_label: str) -> None:
    x_min, x_max = extent([x for x, _ in points])
    y_min, y_max = extent([y for _, y in points])
    plot_left = MARGIN_LEFT
    plot_right = WIDTH - MARGIN_RIGHT
    plot_top = MARGIN_TOP
    plot_bottom = HEIGHT - MARGIN_BOTTOM
    lines = svg_header(title)
    axes(lines, y_min, y_max, x_label, y_label)
    for x_value, y_value in points:
        x = scale(x_value, x_min, x_max, plot_left, plot_right)
        y = scale(y_value, y_min, y_max, plot_bottom, plot_top)
        lines.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="{COLORS["adjust"]}" opacity="0.72"/>')
    write_svg(path, lines)


def macro_chart(path: Path, rows: list[dict[str, str]]) -> None:
    monthly_adjust: dict[str, float] = defaultdict(float)
    monthly_macro: dict[str, dict[str, float]] = {}
    for row in rows:
        month = row.get("month", "")
        if not month:
            continue
        adjust = parse_float(row.get("avg_adjust_cny_per_ton", ""))
        if adjust is not None:
            monthly_adjust[month] += adjust
        cpi = parse_float(row.get("cpi_yoy_pct", ""))
        ppi = parse_float(row.get("ppi_yoy_pct", ""))
        if cpi is not None or ppi is not None:
            monthly_macro[month] = {"cpi_yoy_pct": cpi, "ppi_yoy_pct": ppi}

    months = sorted(set(monthly_adjust) | set(monthly_macro))
    dates = [parse_date(month + "-01") for month in months]
    macro_values = [
        value
        for month in months
        for value in (monthly_macro.get(month, {}).get("cpi_yoy_pct"), monthly_macro.get(month, {}).get("ppi_yoy_pct"))
        if value is not None
    ]
    adjust_values = [monthly_adjust.get(month, 0.0) for month in months]
    y_min, y_max = extent(macro_values)
    adj_min, adj_max = extent(adjust_values)
    adj_min = min(adj_min, 0)
    adj_max = max(adj_max, 0)
    x_min = min(point.toordinal() for point in dates if point is not None)
    x_max = max(point.toordinal() for point in dates if point is not None)
    plot_left = MARGIN_LEFT
    plot_right = WIDTH - MARGIN_RIGHT
    plot_top = MARGIN_TOP
    plot_bottom = HEIGHT - MARGIN_BOTTOM
    zero_y = scale(0, adj_min, adj_max, plot_bottom, plot_top)
    bar_width = max(2, (plot_right - plot_left) / max(len(months), 1) * 0.55)
    lines = svg_header("CPI/PPI vs Monthly Fuel Adjustment")
    axes(lines, y_min, y_max, "Month", "CPI/PPI YoY (%)")
    lines.append(f'<line x1="{plot_left}" y1="{zero_y:.1f}" x2="{plot_right}" y2="{zero_y:.1f}" stroke="#aaaaaa" stroke-dasharray="4 4"/>')
    for month, point_date in zip(months, dates):
        if point_date is None:
            continue
        x = scale(point_date.toordinal(), x_min, x_max, plot_left, plot_right)
        value = monthly_adjust.get(month, 0.0)
        y = scale(value, adj_min, adj_max, plot_bottom, plot_top)
        top = min(y, zero_y)
        lines.append(
            f'<rect x="{x - bar_width / 2:.1f}" y="{top:.1f}" width="{bar_width:.1f}" height="{abs(zero_y - y):.1f}" fill="{COLORS["secondary"]}" opacity="0.28"/>'
        )
    for column, color, label in (
        ("cpi_yoy_pct", COLORS["cpi"], "CPI YoY"),
        ("ppi_yoy_pct", COLORS["ppi"], "PPI YoY"),
    ):
        coords = []
        for month, point_date in zip(months, dates):
            value = monthly_macro.get(month, {}).get(column)
            if value is None or point_date is None:
                continue
            x = scale(point_date.toordinal(), x_min, x_max, plot_left, plot_right)
            y = scale(value, y_min, y_max, plot_bottom, plot_top)
            coords.append(f"{x:.1f},{y:.1f}")
        lines.append(f'<polyline fill="none" stroke="{color}" stroke-width="2" points="{" ".join(coords)}"/>')
    legend(lines, [("Monthly net adjustment", COLORS["secondary"]), ("CPI YoY", COLORS["cpi"]), ("PPI YoY", COLORS["ppi"])])
    write_svg(path, lines)


def main() -> None:
    ensure_project_dirs(ROOT)
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    rows = load_rows()

    oil_series = []
    for label, column, color in (
        ("Basket", "basket_window_avg", COLORS["basket"]),
        ("Brent", "brent_window_avg", COLORS["brent"]),
        ("WTI", "wti_window_avg", COLORS["wti"]),
    ):
        points = []
        for row in rows:
            parsed = parse_date(row.get("notice_date", "") or row.get("date", ""))
            value = parse_float(row.get(column, ""))
            if parsed is not None and value is not None:
                points.append((parsed, value))
        oil_series.append((label, points, color))
    line_chart(FIGURE_DIR / "oil_price_time_series.svg", "International Oil Price Window Averages", oil_series, "USD per barrel")

    adjust_points = []
    for row in rows:
        parsed = parse_date(row.get("date", ""))
        value = parse_float(row.get("avg_adjust_cny_per_ton", ""))
        if parsed is not None and value is not None:
            adjust_points.append((parsed, value))
    bar_chart(FIGURE_DIR / "fuel_adjustment_bar.svg", "Average Gasoline/Diesel Adjustment", adjust_points, "CNY per ton")

    ceiling_series = []
    for label, column, color in (
        ("Gasoline ceiling", "beijing_gasoline_ceiling_after_cny_per_ton", COLORS["gasoline"]),
        ("Diesel ceiling", "beijing_diesel_ceiling_after_cny_per_ton", COLORS["diesel"]),
    ):
        points = []
        for row in rows:
            parsed = parse_date(row.get("date", ""))
            value = parse_float(row.get(column, ""))
            if parsed is not None and value is not None:
                points.append((parsed, value))
        ceiling_series.append((label, points, color))
    line_chart(FIGURE_DIR / "beijing_ceiling_time_series.svg", "Beijing Fuel Ceiling Price Series", ceiling_series, "CNY per ton")

    scatter_points = []
    for row in rows:
        x_value = parse_float(row.get("brent_wti_weighted_window_change", ""))
        y_value = parse_float(row.get("avg_adjust_cny_per_ton", ""))
        if x_value is not None and y_value is not None:
            scatter_points.append((x_value, y_value))
    scatter_chart(
        FIGURE_DIR / "oil_change_vs_fuel_adjust_scatter.svg",
        "Oil Window Change vs Fuel Adjustment",
        scatter_points,
        "Weighted Brent/WTI window change (USD per barrel)",
        "Average adjustment (CNY per ton)",
    )

    macro_chart(FIGURE_DIR / "macro_vs_monthly_adjustment.svg", rows)
    print(f"Wrote SVG figures to {FIGURE_DIR}")


if __name__ == "__main__":
    main()
