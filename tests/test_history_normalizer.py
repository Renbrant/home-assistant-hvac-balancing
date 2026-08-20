"""Tests for raw Home Assistant HVAC history normalization."""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from analysis.normalize_hvac_history import (
    CLIMATE_ENTITY,
    REQUIRED_STATE_ENTITIES,
    flatten_history,
    normalize,
)


def _record(
    entity_id: str | None,
    state: str,
    timestamp: str,
    attributes: dict | None = None,
) -> dict:
    record = {
        "state": state,
        "last_updated": timestamp,
    }
    if entity_id is not None:
        record["entity_id"] = entity_id
    if attributes is not None:
        record["attributes"] = attributes
    return record


def _complete_payload() -> list[list[dict]]:
    start_before = "2026-08-19T04:59:00Z"
    inside = "2026-08-19T05:10:00Z"
    groups: list[list[dict]] = []

    for entity_id in sorted(REQUIRED_STATE_ENTITIES):
        attrs = None
        if entity_id.endswith("booster_adaptive_boost"):
            attrs = {
                "base_speed": 4,
                "control_direction": "cooling",
                "directional_error": 2.2,
                "reference_error": 2.4,
                "last_evaluation": "2026-08-18T22:55:00-06:00",
            }
        groups.append(
            [
                _record(entity_id, "1", start_before, attrs),
                _record(None, "2", inside, attrs),
            ]
        )

    groups.append(
        [
            _record(
                CLIMATE_ENTITY,
                "cool",
                start_before,
                {
                    "hvac_action": "idle",
                    "current_temperature": 74,
                    "temperature": 72,
                    "fan_mode": "off",
                },
            ),
            _record(
                None,
                "cool",
                inside,
                {
                    "hvac_action": "cooling",
                    "current_temperature": 74,
                    "temperature": 72,
                    "fan_mode": "on",
                },
            ),
        ]
    )
    return groups


def test_flatten_history_inherits_group_entity_id() -> None:
    payload = [
        [
            _record(
                "sensor.bed_1_temperature_delta",
                "1.5",
                "2026-08-19T04:59:00Z",
            ),
            _record(None, "1.7", "2026-08-19T05:10:00Z"),
        ]
    ]

    rows = flatten_history(payload)
    assert len(rows) == 2
    assert {row["entity_id"] for row in rows} == {
        "sensor.bed_1_temperature_delta"
    }


def test_normalize_seeds_window_and_writes_analyzer_contract(tmp_path: Path) -> None:
    raw_path = tmp_path / "pre.json"
    output_dir = tmp_path / "pre"
    raw_path.write_text(json.dumps(_complete_payload()), encoding="utf-8")

    manifest = normalize(
        raw_path=raw_path,
        output_dir=output_dir,
        label="PRE-v0.1.3",
        start=datetime(2026, 8, 19, 5, 0, tzinfo=timezone.utc),
        end=datetime(2026, 8, 19, 15, 30, tzinfo=timezone.utc),
        time_zone="America/Denver",
        ha_version="2026.8.2",
    )

    assert manifest["normalizer"]["version"] == "1.0.0"
    assert manifest["validation"]["required_start_seeds_present"] is True
    assert manifest["raw_source"]["filename"] == "pre.json"
    assert len(manifest["raw_source"]["sha256"]) == 64

    with (output_dir / "normalized" / "states.csv").open(
        encoding="utf-8", newline=""
    ) as handle:
        states = list(csv.DictReader(handle))

    bed_delta = [
        row
        for row in states
        if row["entity_id"] == "sensor.bed_1_temperature_delta"
    ]
    assert bed_delta[0] == {
        "timestamp_utc": "2026-08-19T05:00:00Z",
        "entity_id": "sensor.bed_1_temperature_delta",
        "state": "1",
        "segment_start_seed": "1",
    }
    assert bed_delta[1]["timestamp_utc"] == "2026-08-19T05:10:00Z"
    assert bed_delta[1]["state"] == "2"
    assert bed_delta[1]["segment_start_seed"] == "0"

    with (output_dir / "normalized" / "climate.csv").open(
        encoding="utf-8", newline=""
    ) as handle:
        climate = list(csv.DictReader(handle))

    assert climate[0]["timestamp_utc"] == "2026-08-19T05:00:00Z"
    assert climate[0]["hvac_mode"] == "cool"
    assert climate[0]["hvac_action"] == "idle"
    assert climate[0]["fan_mode"] == "off"
    assert climate[0]["segment_start_seed"] == "1"
    assert climate[1]["hvac_action"] == "cooling"
    assert climate[1]["fan_mode"] == "on"

    with (output_dir / "normalized" / "adaptive-controller.csv").open(
        encoding="utf-8", newline=""
    ) as handle:
        adaptive = list(csv.DictReader(handle))

    bed_1_adaptive = [
        row
        for row in adaptive
        if row["entity_id"] == "sensor.bed_1_booster_adaptive_boost"
    ]
    assert bed_1_adaptive[0]["timestamp_utc"] == "2026-08-19T05:00:00Z"
    assert bed_1_adaptive[0]["base_speed"] == "4"
    assert bed_1_adaptive[0]["control_direction"] == "cooling"
    assert bed_1_adaptive[0]["directional_error"] == "2.2"
    assert bed_1_adaptive[0]["reference_error"] == "2.4"
    assert bed_1_adaptive[0]["segment_start_seed"] == "1"


def test_normalizer_rejects_missing_required_seed(tmp_path: Path) -> None:
    raw_path = tmp_path / "raw.json"
    output_dir = tmp_path / "out"
    raw_path.write_text(
        json.dumps(
            [
                [
                    _record(
                        "sensor.bed_1_temperature_delta",
                        "1.5",
                        "2026-08-19T05:05:00Z",
                    )
                ]
            ]
        ),
        encoding="utf-8",
    )

    try:
        normalize(
            raw_path=raw_path,
            output_dir=output_dir,
            label="invalid",
            start=datetime(2026, 8, 19, 5, 0, tzinfo=timezone.utc),
            end=datetime(2026, 8, 19, 15, 30, tzinfo=timezone.utc),
            time_zone="America/Denver",
            ha_version=None,
        )
    except RuntimeError as exc:
        assert "start-window seed" in str(exc)
    else:
        raise AssertionError("Expected missing seed validation to fail")
