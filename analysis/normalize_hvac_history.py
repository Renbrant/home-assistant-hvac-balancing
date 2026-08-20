#!/usr/bin/env python3
"""Normalize raw Home Assistant History API JSON for HVAC analysis.

The raw API response is intentionally not copied into the repository. This tool
creates the minimal reproducible dataset consumed by ``analyze_hvac_baseline``:

- manifest.json
- normalized/states.csv
- normalized/climate.csv
- normalized/adaptive-controller.csv

Supported raw shapes include a flat list of state objects and the normal Home
Assistant history list-of-lists response. Entity IDs omitted from later records
inside a history group are inherited from the group's first explicit entity ID.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

NORMALIZER_VERSION = "1.0.1"

BEDS = ("bed_1", "bed_2", "bed_3")

REQUIRED_STATE_ENTITIES = {
    *(f"sensor.{bed}_temperature_delta" for bed in BEDS),
    *(f"sensor.{bed}_booster_target_speed" for bed in BEDS),
    *(f"sensor.{bed}_booster_pi_target_speed" for bed in BEDS),
    *(f"sensor.{bed}_booster_effective_percentage" for bed in BEDS),
    *(f"sensor.{bed}_booster_adaptive_boost" for bed in BEDS),
}

OPTIONAL_REFERENCE_ENTITIES = {
    "sensor.kitchen_temp_temperature",
    *(f"sensor.{bed}_temp_temperature" for bed in BEDS),
    "sensor.ac_power_total",
    "sensor.furnace_power_total",
}

CLIMATE_ENTITY = "climate.kitchen"
TRACKED_ENTITIES = REQUIRED_STATE_ENTITIES | OPTIONAL_REFERENCE_ENTITIES | {
    CLIMATE_ENTITY
}
ADAPTIVE_ENTITIES = {
    f"sensor.{bed}_booster_adaptive_boost" for bed in BEDS
}

STATE_COLUMNS = (
    "timestamp_utc",
    "entity_id",
    "state",
    "segment_start_seed",
)
CLIMATE_COLUMNS = (
    "timestamp_utc",
    "hvac_mode",
    "hvac_action",
    "current_temperature",
    "target_temperature",
    "target_temp_low",
    "target_temp_high",
    "fan_mode",
    "segment_start_seed",
)
ADAPTIVE_COLUMNS = (
    "timestamp_utc",
    "entity_id",
    "adaptive_boost",
    "base_speed",
    "control_direction",
    "directional_error",
    "reference_error",
    "last_evaluation",
    "segment_start_seed",
)


def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def iso_utc(value: datetime) -> str:
    value = value.astimezone(timezone.utc)
    if value.microsecond:
        return value.isoformat().replace("+00:00", "Z")
    return value.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def safe_scalar(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float) and not math.isfinite(value):
        return ""
    return str(value)


def raw_timestamp(record: dict[str, Any]) -> datetime | None:
    return parse_time(
        record.get("last_updated")
        or record.get("last_changed")
        or record.get("timestamp")
        or record.get("timestamp_utc")
    )


def extract_groups(payload: Any) -> list[list[dict[str, Any]]]:
    """Return history groups while preserving group-level entity context."""

    if isinstance(payload, dict):
        for key in ("result", "history", "states", "data"):
            candidate = payload.get(key)
            if isinstance(candidate, list):
                return extract_groups(candidate)
        raise RuntimeError("Unsupported raw JSON object shape")

    if not isinstance(payload, list):
        raise RuntimeError("Raw history JSON must be a list or supported object")

    if not payload:
        return []

    if all(isinstance(item, dict) for item in payload):
        return [[item] for item in payload]

    groups: list[list[dict[str, Any]]] = []
    for item in payload:
        if isinstance(item, list):
            records = [record for record in item if isinstance(record, dict)]
            if records:
                groups.append(records)
        elif isinstance(item, dict):
            groups.append([item])
        else:
            raise RuntimeError("Unsupported item inside raw history JSON")
    return groups


def flatten_history(payload: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    for group in extract_groups(payload):
        group_entity = next(
            (
                str(record["entity_id"])
                for record in group
                if record.get("entity_id")
            ),
            None,
        )

        for record in group:
            entity_id = record.get("entity_id") or group_entity
            if not entity_id:
                continue
            if entity_id not in TRACKED_ENTITIES:
                continue

            timestamp = raw_timestamp(record)
            if timestamp is None:
                continue

            rows.append(
                {
                    "entity_id": str(entity_id),
                    "time": timestamp,
                    "state": record.get("state"),
                    "attributes": record.get("attributes") or {},
                }
            )

    rows.sort(key=lambda row: (row["entity_id"], row["time"]))

    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for row in rows:
        key = (
            row["entity_id"],
            iso_utc(row["time"]),
            safe_scalar(row["state"]),
            json.dumps(row["attributes"], sort_keys=True, default=str),
        )
        if key not in seen:
            deduped.append(row)
            seen.add(key)
    return deduped


def window_rows(
    rows: list[dict[str, Any]],
    start: datetime,
    end: datetime,
) -> list[dict[str, Any]]:
    """Seed each entity at start and retain events strictly inside the window."""

    by_entity: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_entity[row["entity_id"]].append(row)

    output: list[dict[str, Any]] = []
    for entity_id, entity_rows in by_entity.items():
        seed_candidates = [row for row in entity_rows if row["time"] <= start]
        if seed_candidates:
            seed_source = seed_candidates[-1]
            seed = dict(seed_source)
            seed["time"] = start
            seed["segment_start_seed"] = 1
            output.append(seed)

        for row in entity_rows:
            if start < row["time"] < end:
                event = dict(row)
                event["segment_start_seed"] = 0
                output.append(event)
            elif row["time"] == start and not seed_candidates:
                event = dict(row)
                event["segment_start_seed"] = 1
                output.append(event)

    output.sort(key=lambda row: (row["time"], row["entity_id"]))
    return output


def require_analysis_seeds(rows: list[dict[str, Any]]) -> None:
    seeded = {
        row["entity_id"]
        for row in rows
        if row.get("segment_start_seed") == 1
    }
    required = REQUIRED_STATE_ENTITIES | {CLIMATE_ENTITY}
    missing = sorted(required - seeded)
    if missing:
        raise RuntimeError(
            "Raw history does not provide a start-window seed for required "
            "entities: " + ", ".join(missing)
        )


def write_csv(path: Path, fieldnames: Iterable[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames))
        writer.writeheader()
        writer.writerows(rows)


def build_states(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output = []
    for row in rows:
        if row["entity_id"] == CLIMATE_ENTITY:
            continue
        output.append(
            {
                "timestamp_utc": iso_utc(row["time"]),
                "entity_id": row["entity_id"],
                "state": safe_scalar(row["state"]),
                "segment_start_seed": row["segment_start_seed"],
            }
        )
    return output


def build_climate(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output = []
    for row in rows:
        if row["entity_id"] != CLIMATE_ENTITY:
            continue
        attrs = row["attributes"]
        output.append(
            {
                "timestamp_utc": iso_utc(row["time"]),
                "hvac_mode": safe_scalar(row["state"]).lower(),
                "hvac_action": safe_scalar(attrs.get("hvac_action")).lower(),
                "current_temperature": safe_scalar(
                    attrs.get("current_temperature")
                ),
                "target_temperature": safe_scalar(attrs.get("temperature")),
                "target_temp_low": safe_scalar(attrs.get("target_temp_low")),
                "target_temp_high": safe_scalar(attrs.get("target_temp_high")),
                "fan_mode": safe_scalar(attrs.get("fan_mode")).lower(),
                "segment_start_seed": row["segment_start_seed"],
            }
        )
    return output


def build_adaptive(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output = []
    for row in rows:
        if row["entity_id"] not in ADAPTIVE_ENTITIES:
            continue
        attrs = row["attributes"]
        output.append(
            {
                "timestamp_utc": iso_utc(row["time"]),
                "entity_id": row["entity_id"],
                "adaptive_boost": safe_scalar(row["state"]),
                "base_speed": safe_scalar(attrs.get("base_speed")),
                "control_direction": safe_scalar(
                    attrs.get("control_direction")
                ),
                "directional_error": safe_scalar(
                    attrs.get("directional_error")
                ),
                "reference_error": safe_scalar(attrs.get("reference_error")),
                "last_evaluation": safe_scalar(attrs.get("last_evaluation")),
                "segment_start_seed": row["segment_start_seed"],
            }
        )
    return output


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def normalize(
    raw_path: Path,
    output_dir: Path,
    label: str,
    start: datetime,
    end: datetime,
    time_zone: str,
    ha_version: str | None,
) -> dict[str, Any]:
    if end <= start:
        raise RuntimeError("End time must be after start time")

    raw_bytes = raw_path.read_bytes()
    payload = json.loads(raw_bytes.decode("utf-8-sig"))
    flat = flatten_history(payload)
    if not flat:
        raise RuntimeError("No tracked HVAC history records were found")

    normalized = window_rows(flat, start, end)
    require_analysis_seeds(normalized)

    states = build_states(normalized)
    climate = build_climate(normalized)
    adaptive = build_adaptive(normalized)

    normalized_dir = output_dir / "normalized"
    write_csv(normalized_dir / "states.csv", STATE_COLUMNS, states)
    write_csv(normalized_dir / "climate.csv", CLIMATE_COLUMNS, climate)
    write_csv(
        normalized_dir / "adaptive-controller.csv",
        ADAPTIVE_COLUMNS,
        adaptive,
    )

    entity_counts = Counter(row["entity_id"] for row in normalized)
    seeded = sorted(
        row["entity_id"]
        for row in normalized
        if row["segment_start_seed"] == 1
    )

    manifest = {
        "project": "Home Assistant HVAC Balancing",
        "github_issue": 6,
        "purpose": "Matched paired-night field validation",
        "dataset_label": label,
        "collection_method": "Home Assistant REST History API",
        "home_assistant": {
            "version": ha_version,
            "time_zone": time_zone,
        },
        "window": {
            "start_utc": iso_utc(start),
            "end_utc": iso_utc(end),
        },
        "normalizer": {
            "version": NORMALIZER_VERSION,
            "raw_api_responses_committed": False,
            "start_state_seeded_from_latest_known_state": True,
            "seed_timestamp_clamped_to_window_start": True,
            "duplicate_identical_history_records_removed": True,
        },
        "raw_source": {
            "filename": raw_path.name,
            "size_bytes": len(raw_bytes),
            "sha256": hashlib.sha256(raw_bytes).hexdigest().upper(),
        },
        "counts": {
            "tracked_rows_after_dedup": len(flat),
            "window_rows": len(normalized),
            "states_rows": len(states),
            "climate_rows": len(climate),
            "adaptive_rows": len(adaptive),
        },
        "validation": {
            "required_start_seeds_present": True,
            "seeded_entities": seeded,
        },
        "entity_row_counts": dict(sorted(entity_counts.items())),
        "normalized_files": {},
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "manifest.json"

    for relative in (
        "normalized/states.csv",
        "normalized/climate.csv",
        "normalized/adaptive-controller.csv",
    ):
        path = output_dir / relative
        manifest["normalized_files"][relative] = {
            "size_bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }

    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Normalize Home Assistant HVAC history JSON into analyzer input"
    )
    parser.add_argument("raw_json", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--label", required=True)
    parser.add_argument("--start-utc", required=True)
    parser.add_argument("--end-utc", required=True)
    parser.add_argument("--time-zone", default="America/Denver")
    parser.add_argument("--ha-version")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    start = parse_time(args.start_utc)
    end = parse_time(args.end_utc)
    if start is None or end is None:
        raise RuntimeError("Invalid start/end timestamp")

    manifest = normalize(
        args.raw_json,
        args.output_dir,
        args.label,
        start,
        end,
        args.time_zone,
        args.ha_version,
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=os.sys.stderr)
        raise SystemExit(1)
