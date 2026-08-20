"""Regression tests for field-history analysis methodology v1.1.0."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from analysis.booster_activity_metrics import booster_activity_metrics


ROOT = Path(__file__).resolve().parents[1]
ANALYZER = ROOT / "analysis" / "analyze_hvac_baseline.py"
BASELINE = (
    ROOT
    / "validation"
    / "field-history"
    / "2026-08-12_to_2026-08-18"
)


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


def test_hvac_modulation_rate_excludes_idle_modulations() -> None:
    start = datetime(2026, 8, 20, tzinfo=timezone.utc)
    values = [20, 40, 60, 80, 100, 80]
    actions = ["cooling", "cooling", "idle", "idle", "cooling", "cooling"]

    series = [
        {
            "time": start + timedelta(minutes=index),
            "hvac_action": actions[index],
            "bed_1_fan": values[index],
        }
        for index in range(len(values))
    ]

    result = booster_activity_metrics(series, "bed_1")

    assert result["active_modulation_changes"] == 5
    assert result["active_modulation_changes_per_hvac_hour"] == 45.0
    assert result["median_minutes_between_active_modulations"] == 1.0


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


def test_integrated_analyzer_exposes_v1_1_metrics_under_booster() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(ANALYZER),
            str(BASELINE),
            "--format",
            "json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    result = json.loads(completed.stdout)

    assert result["analysis_version"] == "1.1.0"
    assert result["method"]["booster_active_definition"] == (
        "effective_percentage > 0"
    )

    required = {
        "active_runtime_pct",
        "active_runtime_hours",
        "active_runtime_hvac_pct",
        "average_effective_pct_hvac",
        "average_pct_while_active",
        "active_episodes",
        "median_active_episode_minutes",
        "p90_active_episode_minutes",
        "longest_active_episode_minutes",
        "command_changes",
        "active_modulation_changes",
        "active_modulation_changes_per_hvac_hour",
        "median_minutes_between_active_modulations",
        "equivalent_full_speed_hours",
        "equivalent_full_speed_hours_hvac",
    }

    for bed_name in ("Bed 1", "Bed 2", "Bed 3"):
        booster = result["beds"][bed_name]["booster"]
        assert required <= booster.keys()

        bed_result = result["beds"][bed_name]
        for metric in required:
            assert metric not in bed_result
