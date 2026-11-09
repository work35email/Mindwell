import math

from services.stats import care_signals, spearman, streak
from datetime import date, timedelta


def test_spearman_perfect_and_inverse():
    up = [1, 2, 3, 4, 5]
    assert abs(spearman(up, up) - 1) < 1e-9
    assert abs(spearman(up, [5, 4, 3, 2, 1]) + 1) < 1e-9
    assert spearman([1, 1, 1], [1, 2, 3]) is None


def test_streak_stops_at_a_gap():
    today = date(2026, 11, 9)
    days = {today, today - timedelta(days=1), today - timedelta(days=2), today - timedelta(days=4)}
    assert streak(days, today) == 3
    assert streak(set(), today) == 0


def test_care_plan_flags_low_sleep():
    today = date(2026, 11, 9)
    moods = {today - timedelta(days=index): 4 for index in range(10)}
    sleeps = {today - timedelta(days=index): 5 for index in range(10)}
    stresses = {today - timedelta(days=index): 2 for index in range(10)}
    signals = care_signals(moods, sleeps, stresses, {}, [], today=today)
    assert signals["enough"]
    assert "sleep" in signals["topics"]
    assert any(item["code"] == "low_sleep" for item in signals["codes"])
    assert not math.isnan(signals["avg_sleep"])
