"""Regression tests for field-history analysis methodology v1.1.0."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from analysis.booster_activity_metrics import booster_activity_metrics


def test_effective_percentage_drives_runtime_not_logical_fan_state() -> None:
    start = datetime(2026, 8, 20, tzinfo=timezone.utc)
    values = [0, 20, 40, 0, 50, 0]
    actions = ["cooling", "cooling", "cooling", "cooling", "idle", "idle"]

    series = [
        {
            "time": start + timedelta(minutes=index),
            "hvac_action": actions[index],
            "bed_1_fan": values[index],
            "fan_state": "on",
        }
        for index in range(len(values))
    ]

    result = booster_activity_metrics(series, "bed_1")

    assert result["active_runtime_pct"] == 50.0
    assert result["active_runtime_hours"] == 0.05
    assert result["active_runtime_hvac_pct"] == 50.0
    assert result["average_effective_pct_hvac"] == 15.0
    assert result["average_pct_while_active"] == 36.7

    assert result["active_episodes"] == 2
    assert result["median_active_episode_minutes"] == 1.5
    assert result["p90_active_episode_minutes"] == 1.9
    assert result["longest_active_episode_minutes"] == 2.0

    assert result["command_changes"] == 5
    assert result["active_modulation_changes"] == 1
    assert result["active_modulation_changes_per_hvac_hour"] == 15.0
    assert result["median_minutes_between_active_modulations"] is None

    assert result["equivalent_full_speed_hours"] == 0.018
    assert result["equivalent_full_speed_hours_hvac"] == 0.01


def test_logical_on_with_zero_percentage_has_zero_runtime() -> None:
    start = datetime(2026, 8, 20, tzinfo=timezone.utc)

    series = [
        {
            "time": start + timedelta(minutes=index),
            "hvac_action": "cooling",
            "bed_1_fan": 0,
            "fan_state": "on",
        }
        for index in range(5)
    ]

    result = booster_activity_metrics(series, "bed_1")

    assert result["active_runtime_pct"] == 0.0
    assert result["active_runtime_hours"] == 0.0
    assert result["active_runtime_hvac_pct"] == 0.0
    assert result["active_episodes"] == 0
    assert result["command_changes"] == 0
    assert result["active_modulation_changes"] == 0
    assert result["equivalent_full_speed_hours"] == 0.0
