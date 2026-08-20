"""Booster activity metrics for HVAC field-history analysis.

Methodology version: 1.1.0

Activity is derived exclusively from reconstructed effective percentage.
The Home Assistant fan domain state is intentionally not used for duty-cycle
or episode calculations.
"""

from __future__ import annotations

import math
import statistics
from datetime import datetime
from typing import Any, Iterable


def _clean(values: Iterable[float | None]) -> list[float]:
    return [
        float(value)
        for value in values
        if value is not None and math.isfinite(float(value))
    ]


def _mean(values: Iterable[float | None]) -> float | None:
    clean = _clean(values)
    return statistics.fmean(clean) if clean else None


def _median(values: Iterable[float | None]) -> float | None:
    clean = _clean(values)
    return statistics.median(clean) if clean else None


def _percentile(
    values: Iterable[float | None],
    fraction: float,
) -> float | None:
    clean = sorted(_clean(values))
    if not clean:
        return None
    if len(clean) == 1:
        return clean[0]

    position = (len(clean) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return clean[lower]

    weight = position - lower
    return clean[lower] * (1.0 - weight) + clean[upper] * weight


def _pct(part: int | float, total: int | float) -> float:
    return 100.0 * part / total if total else 0.0


def _rounded(value: float | None, digits: int) -> float | None:
    return None if value is None else round(float(value), digits)


def booster_activity_metrics(
    series: list[dict[str, Any]],
    prefix: str,
    resolution_minutes: int = 1,
) -> dict[str, Any]:
    """Return duty-cycle, episode, workload and active-modulation metrics.

    Definitions:
    - active: effective percentage > 0;
    - episode: contiguous active samples bounded by zero;
    - command change: any reconstructed effective-percentage change;
    - active modulation: positive-to-positive percentage change;
    - equivalent full-speed hours: integral of percentage / 100 over time.

    ``active_modulation_changes_per_hvac_hour`` preserves the validated
    paired-night normalization: all active modulation events in the monitored
    window divided by HVAC-active hours in that same window.
    """

    rows = [
        row
        for row in series
        if row.get(prefix + "_fan") is not None
    ]

    if not rows:
        return {
            "active_runtime_pct": 0.0,
            "active_runtime_hours": 0.0,
            "active_runtime_hvac_pct": 0.0,
            "average_effective_pct_hvac": None,
            "average_pct_while_active": None,
            "active_episodes": 0,
            "median_active_episode_minutes": None,
            "p90_active_episode_minutes": None,
            "longest_active_episode_minutes": None,
            "command_changes": 0,
            "active_modulation_changes": 0,
            "active_modulation_changes_per_hvac_hour": None,
            "median_minutes_between_active_modulations": None,
            "equivalent_full_speed_hours": 0.0,
            "equivalent_full_speed_hours_hvac": 0.0,
        }

    values = [float(row[prefix + "_fan"]) for row in rows]
    active_values = [value for value in values if value > 0]

    hvac_rows = [
        row
        for row in rows
        if row.get("hvac_action") in ("cooling", "heating")
    ]
    hvac_values = [float(row[prefix + "_fan"]) for row in hvac_rows]
    hvac_active_count = sum(value > 0 for value in hvac_values)

    episode_durations: list[float] = []
    episode_minutes = 0

    for value in values:
        if value > 0:
            episode_minutes += resolution_minutes
        elif episode_minutes:
            episode_durations.append(float(episode_minutes))
            episode_minutes = 0

    if episode_minutes:
        episode_durations.append(float(episode_minutes))

    command_changes = 0
    modulation_times: list[datetime] = []
    previous: float | None = None

    for row, value in zip(rows, values):
        if previous is not None and abs(value - previous) > 0.01:
            command_changes += 1
            if previous > 0 and value > 0:
                modulation_times.append(row["time"])
        previous = value

    modulation_intervals = [
        (
            modulation_times[index]
            - modulation_times[index - 1]
        ).total_seconds()
        / 60.0
        for index in range(1, len(modulation_times))
    ]

    hvac_hours = len(hvac_rows) * resolution_minutes / 60.0

    return {
        "active_runtime_pct": _rounded(
            _pct(len(active_values), len(values)),
            1,
        ),
        "active_runtime_hours": _rounded(
            len(active_values) * resolution_minutes / 60.0,
            2,
        ),
        "active_runtime_hvac_pct": _rounded(
            _pct(hvac_active_count, len(hvac_values)),
            1,
        ),
        "average_effective_pct_hvac": _rounded(_mean(hvac_values), 1),
        "average_pct_while_active": _rounded(_mean(active_values), 1),
        "active_episodes": len(episode_durations),
        "median_active_episode_minutes": _rounded(
            _median(episode_durations),
            1,
        ),
        "p90_active_episode_minutes": _rounded(
            _percentile(episode_durations, 0.90),
            1,
        ),
        "longest_active_episode_minutes": _rounded(
            max(episode_durations) if episode_durations else None,
            1,
        ),
        "command_changes": command_changes,
        "active_modulation_changes": len(modulation_times),
        "active_modulation_changes_per_hvac_hour": _rounded(
            len(modulation_times) / hvac_hours if hvac_hours else None,
            2,
        ),
        "median_minutes_between_active_modulations": _rounded(
            _median(modulation_intervals),
            1,
        ),
        "equivalent_full_speed_hours": _rounded(
            sum(values) / 100.0 * resolution_minutes / 60.0,
            3,
        ),
        "equivalent_full_speed_hours_hvac": _rounded(
            sum(hvac_values) / 100.0 * resolution_minutes / 60.0,
            3,
        ),
    }
