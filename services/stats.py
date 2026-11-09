"""Rolling stats, Spearman correlation, streaks, care-plan signals, and SVG charts."""

from __future__ import annotations

import math
from datetime import date, timedelta
from html import escape


def average(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def ranks(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda index: values[index])
    out = [0.0] * len(values)
    cursor = 0
    while cursor < len(order):
        end = cursor
        while end + 1 < len(order) and values[order[end + 1]] == values[order[cursor]]:
            end += 1
        rank = (cursor + 1 + end + 1) / 2
        for position in range(cursor, end + 1):
            out[order[position]] = rank
        cursor = end + 1
    return out


def pearson(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n == 0 or n != len(ys):
        return None
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    den_x = math.sqrt(sum((x - mean_x) ** 2 for x in xs))
    den_y = math.sqrt(sum((y - mean_y) ** 2 for y in ys))
    if den_x == 0 or den_y == 0:
        return None
    return num / (den_x * den_y)


def spearman(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 3 or len(xs) != len(ys):
        return None
    return pearson(ranks(xs), ranks(ys))


def paired(left: dict[date, float], right: dict[date, float]) -> tuple[list[float], list[float]]:
    keys = sorted(set(left) & set(right))
    return [left[key] for key in keys], [right[key] for key in keys]


def streak(days: set[date], today: date) -> int:
    cursor = today if today in days else today - timedelta(days=1)
    if cursor not in days:
        return 0
    count = 0
    while cursor in days:
        count += 1
        cursor -= timedelta(days=1)
    return count


def care_signals(
    moods: dict[date, float],
    sleeps: dict[date, float],
    stresses: dict[date, float],
    cycles: dict[date, float],
    stress_tags: list[str],
    *,
    today: date,
    span: int = 14,
) -> dict:
    start = today - timedelta(days=span - 1)
    mood_vals = [value for day, value in moods.items() if start <= day <= today]
    sleep_vals = [value for day, value in sleeps.items() if start <= day <= today]
    stress_vals = [value for day, value in stresses.items() if start <= day <= today]
    avg_mood = average(mood_vals)
    avg_sleep = average(sleep_vals)
    avg_stress = average(stress_vals)
    codes: list[dict] = []
    topics: list[str] = []

    def add(code: str, topic: str, value: float | None = None) -> None:
        codes.append({"code": code, "value": value})
        if topic not in topics:
            topics.append(topic)

    if len(mood_vals) < 5:
        return {
            "enough": False,
            "avg_mood": avg_mood,
            "avg_sleep": avg_sleep,
            "avg_stress": avg_stress,
            "codes": [],
            "topics": ["breathing", "journaling"],
            "samples": len(mood_vals),
        }
    if avg_mood is not None and avg_mood < 2.8:
        add("low_mood", "mood", round(avg_mood, 2))
        add("grounding", "grounding")
    if avg_sleep is not None and avg_sleep < 6.5:
        add("low_sleep", "sleep", round(avg_sleep, 2))
    if avg_stress is not None and avg_stress >= 3.5:
        add("high_stress", "stress", round(avg_stress, 2))
    if any(tag in {"work", "caregiving"} for tag in stress_tags) and avg_stress is not None and avg_stress >= 3:
        add("burnout_tags", "burnout")
    mood_x, cycle_y = paired(
        {day: value for day, value in moods.items() if start <= day <= today},
        {day: value for day, value in cycles.items() if start <= day <= today},
    )
    rho = spearman(mood_x, cycle_y) if len(mood_x) >= 8 else None
    if rho is not None and abs(rho) >= 0.3:
        add("cycle_link", "cycle", round(rho, 2))
    if not topics:
        topics = ["movement", "journaling"]
        codes.append({"code": "steady", "value": round(avg_mood, 2) if avg_mood is not None else None})
    return {
        "enough": True,
        "avg_mood": avg_mood,
        "avg_sleep": avg_sleep,
        "avg_stress": avg_stress,
        "codes": codes,
        "topics": topics[:4],
        "samples": len(mood_vals),
    }


def correlation_phrase(rho: float | None, samples: int) -> str:
    if rho is None or samples < 8:
        return "sparse"
    if rho >= 0.3:
        return "positive"
    if rho <= -0.3:
        return "negative"
    return "none"


def svg_line(points: list[tuple[str, float]], *, ymin: float, ymax: float, title: str, color: str = "#9b2458") -> str:
    """Inline chart. All text is escaped. Missing series render an empty frame."""
    width, height = 720, 240
    left, right, top, bottom = 44, 16, 28, 36
    title_esc = escape(title)
    if not points or ymax <= ymin:
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
            f'role="img" aria-label="{title_esc}" class="chart">'
            f'<rect width="{width}" height="{height}" fill="transparent"></rect>'
            f'<text x="{width / 2}" y="{height / 2}" text-anchor="middle" class="chart-empty">{title_esc}</text>'
            f"</svg>"
        )
    plot_w = width - left - right
    plot_h = height - top - bottom

    def x_at(index: int) -> float:
        if len(points) == 1:
            return left + plot_w / 2
        return left + plot_w * index / (len(points) - 1)

    def y_at(value: float) -> float:
        clamped = min(max(value, ymin), ymax)
        ratio = (clamped - ymin) / (ymax - ymin)
        return top + plot_h * (1 - ratio)

    coords = [(x_at(i), y_at(value)) for i, (_label, value) in enumerate(points)]
    polyline = " ".join(f"{x:.1f},{y:.1f}" for x, y in coords)
    dots = "".join(
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.5" fill="{color}"></circle>' for x, y in coords
    )
    grid = ""
    for step in range(5):
        value = ymin + (ymax - ymin) * step / 4
        y = y_at(value)
        label = escape(f"{value:.0f}" if float(value).is_integer() else f"{value:.1f}")
        grid += (
            f'<line x1="{left}" y1="{y:.1f}" x2="{width - right}" y2="{y:.1f}" class="grid"></line>'
            f'<text x="{left - 8}" y="{y + 4:.1f}" text-anchor="end" class="tick">{label}</text>'
        )
    first = escape(points[0][0])
    last = escape(points[-1][0])
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'role="img" aria-label="{title_esc}" class="chart">'
        f"<title>{title_esc}</title>"
        f"{grid}"
        f'<polyline fill="none" stroke="{color}" stroke-width="2.5" points="{polyline}"></polyline>'
        f"{dots}"
        f'<text x="{left}" y="{height - 10}" class="tick">{first}</text>'
        f'<text x="{width - right}" y="{height - 10}" text-anchor="end" class="tick">{last}</text>'
        f"</svg>"
    )
