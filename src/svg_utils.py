from __future__ import annotations

import html
from datetime import date
from pathlib import Path

from src.data_utils import column_stats


WIDTH = 1100
HEIGHT = 620
MARGIN_LEFT = 78
MARGIN_RIGHT = 44
MARGIN_TOP = 58
MARGIN_BOTTOM = 78


def scale(value: float, src_min: float, src_max: float, dst_min: float, dst_max: float) -> float:
    if src_max == src_min:
        return (dst_min + dst_max) / 2
    return dst_min + (value - src_min) / (src_max - src_min) * (dst_max - dst_min)


def extent(values: list[float], pad_ratio: float = 0.08, include_zero: bool = False) -> tuple[float, float]:
    clean = [value for value in values if value is not None]
    if include_zero:
        clean.append(0.0)
    if not clean:
        return -1.0, 1.0
    low = min(clean)
    high = max(clean)
    if low == high:
        pad = max(abs(low) * 0.1, 1.0)
        return low - pad, high + pad
    pad = (high - low) * pad_ratio
    return low - pad, high + pad


def svg_header(title: str) -> list[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">',
        '<rect width="100%" height="100%" fill="white"/>',
        f'<text x="{WIDTH / 2}" y="30" text-anchor="middle" font-family="Arial" font-size="22" font-weight="700">{html.escape(title)}</text>',
    ]


def write_svg(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines.append("</svg>")
    path.write_text("\n".join(lines), encoding="utf-8")


def add_axes(lines: list[str], y_min: float, y_max: float, x_label: str, y_label: str) -> None:
    left = MARGIN_LEFT
    right = WIDTH - MARGIN_RIGHT
    top = MARGIN_TOP
    bottom = HEIGHT - MARGIN_BOTTOM
    lines.append(f'<line x1="{left}" y1="{bottom}" x2="{right}" y2="{bottom}" stroke="#333"/>')
    lines.append(f'<line x1="{left}" y1="{top}" x2="{left}" y2="{bottom}" stroke="#333"/>')
    for index in range(6):
        y = scale(index, 0, 5, bottom, top)
        value = scale(index, 0, 5, y_min, y_max)
        lines.append(f'<line x1="{left - 4}" y1="{y:.1f}" x2="{right}" y2="{y:.1f}" stroke="#e7e7e7"/>')
        lines.append(
            f'<text x="{left - 8}" y="{y + 4:.1f}" text-anchor="end" font-family="Arial" font-size="11" fill="#555">{value:.1f}</text>'
        )
    lines.append(
        f'<text x="{(left + right) / 2}" y="{HEIGHT - 24}" text-anchor="middle" font-family="Arial" font-size="13">{html.escape(x_label)}</text>'
    )
    lines.append(
        f'<text x="18" y="{(top + bottom) / 2}" transform="rotate(-90 18 {(top + bottom) / 2})" text-anchor="middle" font-family="Arial" font-size="13">{html.escape(y_label)}</text>'
    )


def add_legend(lines: list[str], items: list[tuple[str, str]], start_x: int = MARGIN_LEFT) -> None:
    x = start_x
    y = HEIGHT - 48
    for label, color in items:
        lines.append(f'<rect x="{x}" y="{y - 11}" width="18" height="5" fill="{color}"/>')
        lines.append(f'<text x="{x + 24}" y="{y - 6}" font-family="Arial" font-size="12" fill="#333">{html.escape(label)}</text>')
        x += max(145, len(label) * 8 + 48)


def line_chart_date(
    path: Path,
    title: str,
    series: list[tuple[str, list[tuple[date, float]], str]],
    y_label: str,
) -> None:
    all_dates = [point_date for _, points, _ in series for point_date, _ in points]
    all_values = [value for _, points, _ in series for _, value in points]
    y_min, y_max = extent(all_values, include_zero=True)
    x_min = min(point.toordinal() for point in all_dates)
    x_max = max(point.toordinal() for point in all_dates)
    left = MARGIN_LEFT
    right = WIDTH - MARGIN_RIGHT
    top = MARGIN_TOP
    bottom = HEIGHT - MARGIN_BOTTOM
    lines = svg_header(title)
    add_axes(lines, y_min, y_max, "Date", y_label)
    zero_y = scale(0, y_min, y_max, bottom, top)
    lines.append(f'<line x1="{left}" y1="{zero_y:.1f}" x2="{right}" y2="{zero_y:.1f}" stroke="#999" stroke-dasharray="4 4"/>')
    for label, points, color in series:
        coordinates = []
        for point_date, value in sorted(points):
            x = scale(point_date.toordinal(), x_min, x_max, left, right)
            y = scale(value, y_min, y_max, bottom, top)
            coordinates.append(f"{x:.1f},{y:.1f}")
        if coordinates:
            lines.append(f'<polyline fill="none" stroke="{color}" stroke-width="1.9" points="{" ".join(coordinates)}"/>')
    for index in range(6):
        ordinal = int(scale(index, 0, 5, x_min, x_max))
        x = scale(ordinal, x_min, x_max, left, right)
        label = date.fromordinal(ordinal).strftime("%Y-%m")
        lines.append(f'<text x="{x:.1f}" y="{bottom + 22}" text-anchor="middle" font-family="Arial" font-size="11" fill="#555">{label}</text>')
    add_legend(lines, [(label, color) for label, _, color in series])
    write_svg(path, lines)


def scatter_chart(
    path: Path,
    title: str,
    points: list[tuple[float, float, str]],
    x_label: str,
    y_label: str,
    color_map: dict[str, str],
    draw_equal_line: bool = False,
) -> None:
    x_values = [x for x, _, _ in points]
    y_values = [y for _, y, _ in points]
    if draw_equal_line:
        combined = x_values + y_values
        x_min, x_max = extent(combined, include_zero=True)
        y_min, y_max = x_min, x_max
    else:
        x_min, x_max = extent(x_values, include_zero=True)
        y_min, y_max = extent(y_values, include_zero=True)
    left = MARGIN_LEFT
    right = WIDTH - MARGIN_RIGHT
    top = MARGIN_TOP
    bottom = HEIGHT - MARGIN_BOTTOM
    lines = svg_header(title)
    add_axes(lines, y_min, y_max, x_label, y_label)
    if draw_equal_line:
        x1 = scale(x_min, x_min, x_max, left, right)
        y1 = scale(x_min, y_min, y_max, bottom, top)
        x2 = scale(x_max, x_min, x_max, left, right)
        y2 = scale(x_max, y_min, y_max, bottom, top)
        lines.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#777" stroke-dasharray="5 5"/>')
    for x_value, y_value, group in points:
        x = scale(x_value, x_min, x_max, left, right)
        y = scale(y_value, y_min, y_max, bottom, top)
        color = color_map.get(group, "#4c78a8")
        lines.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="{color}" opacity="0.72"/>')
    add_legend(lines, [(label, color) for label, color in color_map.items()])
    write_svg(path, lines)


def box_strip_chart(
    path: Path,
    title: str,
    categories: list[tuple[str, list[float], str]],
    y_label: str,
    include_zero: bool = True,
) -> None:
    all_values = [value for _, values, _ in categories for value in values]
    y_min, y_max = extent(all_values, include_zero=include_zero)
    left = MARGIN_LEFT
    right = WIDTH - MARGIN_RIGHT
    top = MARGIN_TOP
    bottom = HEIGHT - MARGIN_BOTTOM
    lines = svg_header(title)
    add_axes(lines, y_min, y_max, "Group", y_label)
    zero_y = scale(0, y_min, y_max, bottom, top)
    lines.append(f'<line x1="{left}" y1="{zero_y:.1f}" x2="{right}" y2="{zero_y:.1f}" stroke="#999" stroke-dasharray="4 4"/>')

    count = max(len(categories), 1)
    slot = (right - left) / count
    for index, (label, values, color) in enumerate(categories):
        x_center = left + slot * (index + 0.5)
        lines.append(f'<text x="{x_center:.1f}" y="{bottom + 24}" text-anchor="middle" font-family="Arial" font-size="12">{html.escape(label)}</text>')
        if not values:
            continue
        stats = column_stats(values)
        q1 = stats["q1"]
        q3 = stats["q3"]
        med = stats["median"]
        low = stats["min"]
        high = stats["max"]
        box_width = min(120, slot * 0.46)
        if None not in (q1, q3, med, low, high):
            y_q1 = scale(float(q1), y_min, y_max, bottom, top)
            y_q3 = scale(float(q3), y_min, y_max, bottom, top)
            y_med = scale(float(med), y_min, y_max, bottom, top)
            y_low = scale(float(low), y_min, y_max, bottom, top)
            y_high = scale(float(high), y_min, y_max, bottom, top)
            lines.append(f'<line x1="{x_center:.1f}" y1="{y_low:.1f}" x2="{x_center:.1f}" y2="{y_high:.1f}" stroke="{color}" stroke-width="2"/>')
            lines.append(
                f'<rect x="{x_center - box_width / 2:.1f}" y="{min(y_q1, y_q3):.1f}" width="{box_width:.1f}" height="{abs(y_q3 - y_q1):.1f}" fill="{color}" opacity="0.24" stroke="{color}"/>'
            )
            lines.append(f'<line x1="{x_center - box_width / 2:.1f}" y1="{y_med:.1f}" x2="{x_center + box_width / 2:.1f}" y2="{y_med:.1f}" stroke="{color}" stroke-width="2.5"/>')
        for value_index, value in enumerate(values):
            jitter = ((value_index % 11) - 5) * min(5.5, slot / 36)
            y = scale(value, y_min, y_max, bottom, top)
            lines.append(f'<circle cx="{x_center + jitter:.1f}" cy="{y:.1f}" r="3" fill="{color}" opacity="0.45"/>')
    write_svg(path, lines)
