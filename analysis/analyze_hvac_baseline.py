#!/usr/bin/env python3
"""Reproducible HVAC field-history analyzer.

Implements the quantitative methodology documented in
``validation/methodology/HVAC_CALIBRATION_METHODOLOGY.md``.

The analyzer uses only the Python standard library and operates on normalized
field-history datasets stored under ``validation/field-history``.

Analysis methodology version: 1.1.0
"""

from __future__ import annotations

import argparse
import bisect
import csv
import json
import math
import os
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

from booster_activity_metrics import booster_activity_metrics

ANALYSIS_VERSION = "1.1.0"
RESOLUTION_MINUTES = 1
RESPONSE_START_STEP_MINUTES = 5
RESPONSE_HORIZON_MINUTES = 20
RESPONSE_CHECKPOINTS_MINUTES = (0, 5, 10, 15, 20)
ADAPTIVE_CLIMATE_COINCIDENCE_SECONDS = 2.0

BEDS = {
    "Bed 1": {
        "delta": "sensor.bed_1_temperature_delta",
        "base": "sensor.bed_1_booster_target_speed",
        "pi": "sensor.bed_1_booster_pi_target_speed",
        "fan": "sensor.bed_1_booster_effective_percentage",
        "adaptive": "sensor.bed_1_booster_adaptive_boost",
    },
    "Bed 2": {
        "delta": "sensor.bed_2_temperature_delta",
        "base": "sensor.bed_2_booster_target_speed",
        "pi": "sensor.bed_2_booster_pi_target_speed",
        "fan": "sensor.bed_2_booster_effective_percentage",
        "adaptive": "sensor.bed_2_booster_adaptive_boost",
    },
    "Bed 3": {
        "delta": "sensor.bed_3_temperature_delta",
        "base": "sensor.bed_3_booster_target_speed",
        "pi": "sensor.bed_3_booster_pi_target_speed",
        "fan": "sensor.bed_3_booster_effective_percentage",
        "adaptive": "sensor.bed_3_booster_adaptive_boost",
    },
}


def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def safe_float(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def values_only(values: Iterable[float | None]) -> list[float]:
    return [
        value
        for value in values
        if value is not None and math.isfinite(value)
    ]


def mean(values: Iterable[float | None]) -> float | None:
    clean = values_only(values)
    return statistics.fmean(clean) if clean else None


def median(values: Iterable[float | None]) -> float | None:
    clean = values_only(values)
    return statistics.median(clean) if clean else None


def percentile(values: Iterable[float | None], fraction: float) -> float | None:
    clean = sorted(values_only(values))
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


def pct(part: int | float, total: int | float) -> float:
    return 100.0 * part / total if total else 0.0


def rounded(value: float | None, digits: int = 2) -> float | None:
    return None if value is None else round(float(value), digits)


def require_file(path: str) -> None:
    if not os.path.isfile(path):
        raise RuntimeError(f"Required dataset file not found: {path}")


def load_manifest(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def load_state_events(
    path: str,
    tracked: set[str],
) -> dict[str, list[tuple[datetime, float]]]:
    events: dict[str, list[tuple[datetime, float]]] = defaultdict(list)

    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"timestamp_utc", "entity_id", "state"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise RuntimeError(
                "states.csv missing columns: " + ", ".join(sorted(missing))
            )

        for row in reader:
            entity_id = row["entity_id"]
            if entity_id not in tracked:
                continue

            timestamp = parse_time(row["timestamp_utc"])
            value = safe_float(row["state"])
            if timestamp is not None and value is not None:
                events[entity_id].append((timestamp, value))

    for entity_id in events:
        events[entity_id].sort(key=lambda item: item[0])

    return events


def load_climate_events(path: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"timestamp_utc", "hvac_mode", "hvac_action", "fan_mode"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise RuntimeError(
                "climate.csv missing columns: " + ", ".join(sorted(missing))
            )

        for row in reader:
            timestamp = parse_time(row["timestamp_utc"])
            if timestamp is None:
                continue

            rows.append(
                {
                    "time": timestamp,
                    "hvac_mode": (row.get("hvac_mode") or "").lower(),
                    "hvac_action": (row.get("hvac_action") or "").lower(),
                    "fan_mode": (row.get("fan_mode") or "").lower(),
                }
            )

    rows.sort(key=lambda row: row["time"])
    return rows


def load_adaptive_rows(path: str) -> list[dict[str, str]]:
    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"timestamp_utc", "entity_id", "adaptive_boost"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise RuntimeError(
                "adaptive-controller.csv missing columns: "
                + ", ".join(sorted(missing))
            )
        return list(reader)


def directional_error(
    delta: float | None,
    hvac_mode: str,
    hvac_action: str,
) -> float | None:
    if delta is None:
        return None

    if hvac_mode == "cool":
        return max(delta, 0.0)

    if hvac_mode == "heat":
        return max(-delta, 0.0)

    if hvac_mode == "heat_cool":
        if hvac_action == "cooling":
            return max(delta, 0.0)
        if hvac_action == "heating":
            return max(-delta, 0.0)

        # Mirrors the current Base-P behavior being investigated in Issue #4.
        return 0.0

    return None


def build_series(
    start: datetime,
    end: datetime,
    state_events: dict[str, list[tuple[datetime, float]]],
    climate_events: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    tracked = list(
        dict.fromkeys(
            entity
            for info in BEDS.values()
            for entity in info.values()
        )
    )

    positions = {entity: 0 for entity in tracked}
    current: dict[str, float | None] = {entity: None for entity in tracked}
    climate_position = 0
    climate_current = {"hvac_mode": "", "hvac_action": "", "fan_mode": ""}
    series: list[dict[str, Any]] = []

    timestamp = start
    while timestamp < end:
        for entity_id in tracked:
            source = state_events.get(entity_id, [])
            position = positions[entity_id]

            while position < len(source) and source[position][0] <= timestamp:
                current[entity_id] = source[position][1]
                position += 1

            positions[entity_id] = position

        while (
            climate_position < len(climate_events)
            and climate_events[climate_position]["time"] <= timestamp
        ):
            climate_current = climate_events[climate_position]
            climate_position += 1

        record: dict[str, Any] = {
            "time": timestamp,
            "hvac_mode": climate_current["hvac_mode"],
            "hvac_action": climate_current["hvac_action"],
            "fan_mode": climate_current["fan_mode"],
        }

        for bed_name, info in BEDS.items():
            prefix = bed_name.lower().replace(" ", "_")
            delta = current[info["delta"]]

            record[prefix + "_delta"] = delta
            record[prefix + "_abs_delta"] = (
                abs(delta) if delta is not None else None
            )
            record[prefix + "_error"] = directional_error(
                delta,
                record["hvac_mode"],
                record["hvac_action"],
            )
            record[prefix + "_base"] = current[info["base"]]
            record[prefix + "_pi"] = current[info["pi"]]
            record[prefix + "_fan"] = current[info["fan"]]
            record[prefix + "_adaptive"] = current[info["adaptive"]]

        series.append(record)
        timestamp += timedelta(minutes=RESOLUTION_MINUTES)

    return series


def error_bands(values: Iterable[float | None]) -> dict[str, float]:
    clean = values_only(values)
    counts = {
        "<1.0": 0,
        "1.0-1.5": 0,
        "1.5-2.0": 0,
        "2.0-2.5": 0,
        "2.5-3.0": 0,
        ">=3.0": 0,
    }

    for value in clean:
        if value < 1.0:
            counts["<1.0"] += 1
        elif value < 1.5:
            counts["1.0-1.5"] += 1
        elif value < 2.0:
            counts["1.5-2.0"] += 1
        elif value < 2.5:
            counts["2.0-2.5"] += 1
        elif value < 3.0:
            counts["2.5-3.0"] += 1
        else:
            counts[">=3.0"] += 1

    return {
        key: round(pct(count, len(clean)), 1)
        for key, count in counts.items()
    }


def response_by_level(
    series: list[dict[str, Any]],
    prefix: str,
    control: str,
) -> dict[str, Any]:
    results: dict[int, list[float]] = defaultdict(list)
    horizon = RESPONSE_HORIZON_MINUTES

    for index in range(
        0,
        len(series) - horizon,
        RESPONSE_START_STEP_MINUTES,
    ):
        positions = [
            index + offset
            for offset in RESPONSE_CHECKPOINTS_MINUTES
        ]

        actions = [series[position]["hvac_action"] for position in positions]
        if not all(action in ("cooling", "heating") for action in actions):
            continue

        levels = [
            series[position][prefix + "_" + control]
            for position in positions
        ]
        if any(value is None for value in levels):
            continue

        normalized = [int(round(value)) for value in levels]
        if len(set(normalized)) != 1:
            continue

        start_error = series[index][prefix + "_error"]
        end_error = series[index + horizon][prefix + "_error"]
        if start_error is None or end_error is None:
            continue

        results[normalized[0]].append(start_error - end_error)

    return {
        str(level): {
            "windows": len(values),
            "median_improvement_20m": rounded(median(values), 2),
            "mean_improvement_20m": rounded(mean(values), 2),
        }
        for level, values in sorted(results.items())
    }


def adaptive_transition_stats(
    adaptive_rows: list[dict[str, str]],
    climate_events: list[dict[str, Any]],
) -> dict[str, Any]:
    climate_times = [row["time"] for row in climate_events]

    def nearest_distance(timestamp: datetime) -> float | None:
        position = bisect.bisect_left(climate_times, timestamp)
        candidates: list[datetime] = []

        if position < len(climate_times):
            candidates.append(climate_times[position])
        if position > 0:
            candidates.append(climate_times[position - 1])
        if not candidates:
            return None

        return min(
            abs((candidate - timestamp).total_seconds())
            for candidate in candidates
        )

    output: dict[str, Any] = {}

    for bed_name, info in BEDS.items():
        rows = [
            row
            for row in adaptive_rows
            if row.get("entity_id") == info["adaptive"]
        ]
        rows.sort(
            key=lambda row: parse_time(row.get("timestamp_utc"))
            or datetime.min.replace(tzinfo=timezone.utc)
        )

        previous: float | None = None
        increases = 0
        decreases = 0
        resets = 0
        near = 0

        for row in rows:
            timestamp = parse_time(row.get("timestamp_utc"))
            value = safe_float(row.get("adaptive_boost"))
            if timestamp is None or value is None:
                continue

            if previous is not None:
                if value > previous:
                    increases += 1
                elif value < previous:
                    decreases += 1

                if previous > 0 and value == 0:
                    resets += 1
                    distance = nearest_distance(timestamp)
                    if (
                        distance is not None
                        and distance <= ADAPTIVE_CLIMATE_COINCIDENCE_SECONDS
                    ):
                        near += 1

            previous = value

        output[bed_name] = {
            "increases": increases,
            "decreases": decreases,
            "resets_positive_to_zero": resets,
            "resets_near_climate_event": near,
            "coincidence_pct": round(pct(near, resets), 1),
        }

    return output


def analyze_nest(
    series: list[dict[str, Any]],
    climate_events: list[dict[str, Any]],
    end_time: datetime,
) -> dict[str, Any]:
    episodes: list[tuple[datetime, datetime]] = []
    previous_fan: str | None = None
    episode_start: datetime | None = None

    for row in climate_events:
        current_fan = row["fan_mode"]

        if current_fan == "on" and previous_fan != "on":
            episode_start = row["time"]

        if (
            previous_fan == "on"
            and current_fan != "on"
            and episode_start is not None
        ):
            episodes.append((episode_start, row["time"]))
            episode_start = None

        previous_fan = current_fan

    if episode_start is not None:
        episodes.append((episode_start, end_time))

    durations = [
        (end - start).total_seconds() / 60.0
        for start, end in episodes
    ]

    fan_on_minutes = sum(
        1
        for row in series
        if row["fan_mode"] == "on"
    )

    series_times = [row["time"] for row in series]
    fan_start_pi: list[float] = []
    fan_start_error: list[float] = []

    for start, _ in episodes:
        index = bisect.bisect_right(series_times, start) - 1
        if index < 0 or index >= len(series):
            continue

        row = series[index]
        pi_values: list[float] = []
        error_values: list[float] = []

        for bed_name in BEDS:
            prefix = bed_name.lower().replace(" ", "_")
            pi_value = row[prefix + "_pi"]
            error_value = row[prefix + "_error"]

            if pi_value is not None:
                pi_values.append(pi_value)
            if error_value is not None:
                error_values.append(error_value)

        if pi_values:
            fan_start_pi.append(max(pi_values))
        if error_values:
            fan_start_error.append(max(error_values))

    starts_at_8 = sum(1 for value in fan_start_pi if value >= 8)

    return {
        "episodes": len(episodes),
        "runtime_hours": rounded(fan_on_minutes / 60.0, 2),
        "percent_baseline": rounded(pct(fan_on_minutes, len(series)), 1),
        "median_episode_minutes": rounded(median(durations), 1),
        "p90_episode_minutes": rounded(percentile(durations, 0.90), 1),
        "longest_episode_minutes": rounded(
            max(durations) if durations else None,
            1,
        ),
        "starts_with_max_pi_ge_8_pct": rounded(
            pct(starts_at_8, len(fan_start_pi)),
            1,
        ),
        "median_max_pi_at_start": rounded(median(fan_start_pi), 1),
        "median_worst_error_at_start": rounded(median(fan_start_error), 2),
    }


def analyze_bed(
    bed_name: str,
    series: list[dict[str, Any]],
    transitions: dict[str, Any],
) -> dict[str, Any]:
    prefix = bed_name.lower().replace(" ", "_")

    records = [
        row
        for row in series
        if row[prefix + "_error"] is not None
    ]
    errors = [row[prefix + "_error"] for row in records]
    abs_deltas = [row[prefix + "_abs_delta"] for row in records]

    active = [
        row
        for row in records
        if row["hvac_action"] in ("cooling", "heating")
    ]
    balancing = [
        row
        for row in records
        if row[prefix + "_fan"] is not None
        and row[prefix + "_fan"] > 0
    ]

    fan_values = [
        row[prefix + "_fan"]
        for row in records
        if row[prefix + "_fan"] is not None
    ]
    adaptive_values = [
        row[prefix + "_adaptive"]
        for row in records
        if row[prefix + "_adaptive"] is not None
    ]

    high_fan = [
        row
        for row in records
        if row[prefix + "_fan"] is not None
        and row[prefix + "_fan"] >= 80
    ]
    full_fan = [
        row
        for row in records
        if row[prefix + "_fan"] is not None
        and row[prefix + "_fan"] >= 100
    ]
    high_fan_high_error = [
        row
        for row in high_fan
        if row[prefix + "_error"] >= 2.0
    ]
    adaptive_positive = [
        value
        for value in adaptive_values
        if value > 0
    ]

    booster_activity = booster_activity_metrics(
        series,
        prefix,
        RESOLUTION_MINUTES,
    )

    transition = transitions[bed_name]

    return {
        "directional": {
            "mean": rounded(mean(errors), 2),
            "median": rounded(median(errors), 2),
            "p90": rounded(percentile(errors, 0.90), 2),
            "maximum": rounded(max(errors) if errors else None, 2),
            "mean_absolute_room_delta": rounded(mean(abs_deltas), 2),
        },
        "bands": {
            "all_time": error_bands(errors),
            "hvac_active": error_bands(
                row[prefix + "_error"]
                for row in active
            ),
            "balancing_active": error_bands(
                row[prefix + "_error"]
                for row in balancing
            ),
        },
        "booster": {
            **booster_activity,
            "average_effective_pct": rounded(mean(fan_values), 1),
            "time_ge_80_pct": rounded(pct(len(high_fan), len(records)), 1),
            "time_100_pct": rounded(pct(len(full_fan), len(records)), 1),
            "time_ge_80_and_error_ge_2_pct": rounded(
                pct(len(high_fan_high_error), len(records)),
                1,
            ),
            "high_fan_still_error_ge_2_pct": rounded(
                pct(len(high_fan_high_error), len(high_fan)),
                1,
            ),
        },
        "adaptive": {
            "time_weighted_average": rounded(mean(adaptive_values), 2),
            "maximum": rounded(
                max(adaptive_values) if adaptive_values else None,
                0,
            ),
            "time_positive_pct": rounded(
                pct(len(adaptive_positive), len(adaptive_values)),
                1,
            ),
            **transition,
        },
        "base_response": response_by_level(series, prefix, "base"),
        "pi_response": response_by_level(series, prefix, "pi"),
    }


def analyze(dataset: str) -> dict[str, Any]:
    dataset = os.path.abspath(dataset)

    manifest_file = os.path.join(dataset, "manifest.json")
    states_file = os.path.join(dataset, "normalized", "states.csv")
    climate_file = os.path.join(dataset, "normalized", "climate.csv")
    adaptive_file = os.path.join(
        dataset,
        "normalized",
        "adaptive-controller.csv",
    )

    for path in (
        manifest_file,
        states_file,
        climate_file,
        adaptive_file,
    ):
        require_file(path)

    manifest = load_manifest(manifest_file)
    start = parse_time(manifest["window"]["start_utc"])
    end = parse_time(manifest["window"]["end_utc"])

    if start is None or end is None or end <= start:
        raise RuntimeError("Invalid analysis window in manifest.json")

    tracked = {
        entity
        for info in BEDS.values()
        for entity in info.values()
    }

    state_events = load_state_events(states_file, tracked)
    missing_history = [
        entity
        for entity in tracked
        if not state_events.get(entity)
    ]
    if missing_history:
        raise RuntimeError(
            "Required analysis entities have no state history: "
            + ", ".join(sorted(missing_history))
        )

    climate_events = load_climate_events(climate_file)
    if not climate_events:
        raise RuntimeError("No climate history was available")

    adaptive_rows = load_adaptive_rows(adaptive_file)
    series = build_series(start, end, state_events, climate_events)
    if not series:
        raise RuntimeError("Time-series reconstruction produced no samples")

    transitions = adaptive_transition_stats(adaptive_rows, climate_events)
    beds = {
        bed_name: analyze_bed(bed_name, series, transitions)
        for bed_name in BEDS
    }

    return {
        "analysis_version": ANALYSIS_VERSION,
        "method": {
            "resolution_minutes": RESOLUTION_MINUTES,
            "response_window_minutes": RESPONSE_HORIZON_MINUTES,
            "response_start_step_minutes": RESPONSE_START_STEP_MINUTES,
            "response_checkpoints_minutes": list(RESPONSE_CHECKPOINTS_MINUTES),
            "booster_active_definition": "effective_percentage > 0",
            "adaptive_climate_coincidence_seconds": (
                ADAPTIVE_CLIMATE_COINCIDENCE_SECONDS
            ),
        },
        "dataset": {
            "path": dataset,
            "start_utc": start.isoformat(),
            "end_utc": end.isoformat(),
            "duration_hours": rounded(
                (end - start).total_seconds() / 3600.0,
                2,
            ),
            "reconstructed_samples": len(series),
        },
        "beds": beds,
        "nest": analyze_nest(series, climate_events, end),
    }


def fmt(value: float | None, digits: int = 2) -> str:
    return "n/a" if value is None else f"{value:.{digits}f}"


def render_response(title: str, response: dict[str, Any]) -> None:
    print(title)
    print(
        "  Level | Windows | Median improvement /20m | Mean improvement /20m"
    )

    for level in sorted(response, key=int):
        row = response[level]
        print(
            f"  {int(level):>5} | {row['windows']:>7} | "
            f"{fmt(row['median_improvement_20m']):>22} F | "
            f"{fmt(row['mean_improvement_20m']):>20} F"
        )


def render_text(result: dict[str, Any]) -> None:
    print()
    print("=" * 60)
    print(" HVAC BASELINE QUANTITATIVE ANALYSIS")
    print("=" * 60)
    print()
    print("Analysis engine version:", result["analysis_version"])
    print("Duration:", fmt(result["dataset"]["duration_hours"]), "hours")
    print(
        "Reconstructed resolution:",
        result["method"]["resolution_minutes"],
        "minute",
    )
    print(
        "Reconstructed samples:",
        result["dataset"]["reconstructed_samples"],
    )
    print()

    for bed_name in BEDS:
        bed = result["beds"][bed_name]
        directional = bed["directional"]

        print("-" * 60)
        print(bed_name.upper())
        print("-" * 60)
        print("Mean directional error:", fmt(directional["mean"]), "F")
        print("Median directional error:", fmt(directional["median"]), "F")
        print("P90 directional error:", fmt(directional["p90"]), "F")
        print("Maximum directional error:", fmt(directional["maximum"]), "F")
        print(
            "Mean absolute room delta:",
            fmt(directional["mean_absolute_room_delta"]),
            "F",
        )
        print()

        for context, title in (
            ("all_time", "All-time error bands"),
            ("hvac_active", "HVAC-active error bands"),
            ("balancing_active", "Balancing-active error bands"),
        ):
            bands = bed["bands"][context]
            print(title + ":")
            print(
                f"  <1.0: {bands['<1.0']:.1f}% | "
                f"1.0-1.5: {bands['1.0-1.5']:.1f}% | "
                f"1.5-2.0: {bands['1.5-2.0']:.1f}%"
            )
            print(
                f"  2.0-2.5: {bands['2.0-2.5']:.1f}% | "
                f"2.5-3.0: {bands['2.5-3.0']:.1f}% | "
                f">=3.0: {bands['>=3.0']:.1f}%"
            )
            print()

        booster = bed["booster"]
        print("Booster utilization:")
        print(
            f"  Average effective command: "
            f"{booster['average_effective_pct']:.1f}%"
        )
        print(f"  Time >=80%: {booster['time_ge_80_pct']:.1f}%")
        print(f"  Time at 100%: {booster['time_100_pct']:.1f}%")
        print(
            f"  >=80% AND error >=2F: "
            f"{booster['time_ge_80_and_error_ge_2_pct']:.1f}%"
        )
        print(
            f"  During >=80% fan, error still >=2F: "
            f"{booster['high_fan_still_error_ge_2_pct']:.1f}%"
        )
        print()

        print("Booster activity / workload:")
        print(
            f"  Active runtime (>0%): {booster['active_runtime_pct']:.1f}%"
        )
        print(
            "  Active runtime:",
            fmt(booster["active_runtime_hours"], 2),
            "hours",
        )
        print(
            f"  Active during HVAC: {booster['active_runtime_hvac_pct']:.1f}%"
        )
        print(
            "  Average command during HVAC:",
            fmt(booster["average_effective_pct_hvac"], 1) + "%",
        )
        print(
            "  Average command while active:",
            fmt(booster["average_pct_while_active"], 1) + "%",
        )
        print("  Active episodes:", booster["active_episodes"])
        print(
            "  Median active episode:",
            fmt(booster["median_active_episode_minutes"], 1),
            "minutes",
        )
        print(
            "  P90 active episode:",
            fmt(booster["p90_active_episode_minutes"], 1),
            "minutes",
        )
        print(
            "  Longest active episode:",
            fmt(booster["longest_active_episode_minutes"], 1),
            "minutes",
        )
        print("  Command changes:", booster["command_changes"])
        print(
            "  Active speed modulations:",
            booster["active_modulation_changes"],
        )
        print(
            "  HVAC-scoped active modulations / HVAC hour:",
            fmt(booster["active_modulation_changes_per_hvac_hour"], 2),
        )
        print(
            "  Median minutes between active modulations (whole window):",
            fmt(booster["median_minutes_between_active_modulations"], 1),
        )
        print(
            "  Equivalent full-speed hours:",
            fmt(booster["equivalent_full_speed_hours"], 3),
        )
        print(
            "  Equivalent full-speed hours during HVAC:",
            fmt(booster["equivalent_full_speed_hours_hvac"], 3),
        )
        print()

        adaptive = bed["adaptive"]
        print("Adaptive I:")
        print(
            "  Time-weighted average:",
            fmt(adaptive["time_weighted_average"]),
        )
        print("  Maximum:", fmt(adaptive["maximum"], 0))
        print(f"  Time > 0: {adaptive['time_positive_pct']:.1f}%")
        print("  Increase transitions:", adaptive["increases"])
        print("  Decrease transitions:", adaptive["decreases"])
        print(
            "  Positive-to-zero resets:",
            adaptive["resets_positive_to_zero"],
        )
        print(
            "  Resets within 2 sec of climate event:",
            adaptive["resets_near_climate_event"],
        )
        print(
            f"  Climate-event coincidence: "
            f"{adaptive['coincidence_pct']:.1f}%"
        )
        print()

        render_response("Base P:", bed["base_response"])
        print()
        render_response("PI Target:", bed["pi_response"])
        print()

    nest = result["nest"]
    print("=" * 60)
    print(" NEST / CENTRAL BLOWER ASSIST")
    print("=" * 60)
    print()
    print("fan_mode=on episodes:", nest["episodes"])
    print(
        "Approximate fan_mode=on runtime:",
        fmt(nest["runtime_hours"]),
        "hours",
    )
    print(f"Percent of baseline: {nest['percent_baseline']:.1f}%")
    print(
        "Median fan-on episode:",
        fmt(nest["median_episode_minutes"], 1),
        "minutes",
    )
    print(
        "P90 fan-on episode:",
        fmt(nest["p90_episode_minutes"], 1),
        "minutes",
    )
    print(
        "Longest fan-on episode:",
        fmt(nest["longest_episode_minutes"], 1),
        "minutes",
    )
    print(
        f"Fan starts with max PI >=8: "
        f"{nest['starts_with_max_pi_ge_8_pct']:.1f}%"
    )
    print(
        "Median max PI at start:",
        fmt(nest["median_max_pi_at_start"], 1),
    )
    print(
        "Median worst bedroom error at start:",
        fmt(nest["median_worst_error_at_start"]),
        "F",
    )
    print()
    print("=" * 60)
    print(" ANALYSIS COMPLETE")
    print("=" * 60)
    print()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze normalized Home Assistant HVAC field-history data."
    )
    parser.add_argument(
        "dataset",
        help="Path to a field-history dataset directory",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format (default: text)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = analyze(args.dataset)

    if args.format == "json":
        json.dump(result, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
    else:
        render_text(result)

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
