"""Dynamic configuration helpers for HVAC Balancing."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from .const import (
    CONF_REFERENCE_SENSOR,
    CONF_THERMOSTAT,
    CONF_ZONE_FAN,
    CONF_ZONE_ID,
    CONF_ZONE_NAME,
    CONF_ZONE_TEMPERATURE,
    CONF_ZONES,
)


REQUIRED_ZONE_KEYS = (
    CONF_ZONE_ID,
    CONF_ZONE_NAME,
    CONF_ZONE_TEMPERATURE,
    CONF_ZONE_FAN,
)


PRODUCTION_ZONE_ENTITY_SUFFIXES = (
    "base_p",
    "adaptive_i",
    "pi_target",
    "effective_percentage",
    "improvement_rate",
    "adaptive_action",
    "next_adaptive_due",
    "adaptive_window",
)


def production_zone_id_from_unique_id(
    unique_id: str,
) -> str | None:
    """Return a production zone ID for one managed diagnostic unique ID."""

    prefix = "production_"

    if not unique_id.startswith(prefix):
        return None

    for suffix in PRODUCTION_ZONE_ENTITY_SUFFIXES:
        marker = f"_{suffix}"

        if not unique_id.endswith(marker):
            continue

        zone_id = unique_id[
            len(prefix):
            -len(marker)
        ]

        if zone_id:
            return zone_id

    return None


def stale_production_zone_unique_ids(
    unique_ids: Iterable[str],
    active_zone_ids: Iterable[str],
) -> set[str]:
    """Return managed diagnostic IDs belonging to removed production zones."""

    active = set(
        active_zone_ids
    )

    stale: set[str] = set()

    for unique_id in unique_ids:
        zone_id = production_zone_id_from_unique_id(
            unique_id
        )

        if zone_id is None:
            continue

        if zone_id in active:
            continue

        stale.add(
            unique_id
        )

    return stale


def merged_entry_config(entry: Any) -> dict[str, Any]:
    """Merge immutable setup data with user-editable options."""

    config = dict(entry.data)
    config.update(entry.options)

    return config


def normalize_zone_records(
    raw_zones: object,
) -> list[dict[str, str]]:
    """Return validated string-only zone records.

    Structural corruption is rejected rather than silently ignored.
    """

    if not isinstance(raw_zones, (list, tuple)):
        raise ValueError("zones_must_be_a_sequence")

    normalized: list[dict[str, str]] = []

    for raw_zone in raw_zones:
        if not isinstance(raw_zone, Mapping):
            raise ValueError("zone_must_be_a_mapping")

        record: dict[str, str] = {}

        for key in REQUIRED_ZONE_KEYS:
            value = raw_zone.get(key)

            if not isinstance(value, str):
                raise ValueError(
                    f"zone_field_not_string:{key}"
                )

            value = value.strip()

            if not value:
                raise ValueError(
                    f"zone_field_empty:{key}"
                )

            record[key] = value

        normalized.append(record)

    return normalized


def validate_zone_records(
    zones: Sequence[Mapping[str, str]],
    reference_sensor: str,
) -> str | None:
    """Return a config-flow error key, or None when valid."""

    if not zones:
        return "minimum_one_zone"

    zone_ids = [
        zone[CONF_ZONE_ID]
        for zone in zones
    ]

    temperature_ids = [
        zone[CONF_ZONE_TEMPERATURE]
        for zone in zones
    ]

    fan_ids = [
        zone[CONF_ZONE_FAN]
        for zone in zones
    ]

    if len(set(zone_ids)) != len(zone_ids):
        return "duplicate_zone_id"

    if len(set(temperature_ids)) != len(temperature_ids):
        return "duplicate_zone_temperature"

    if len(set(fan_ids)) != len(fan_ids):
        return "duplicate_zone_fan"

    if reference_sensor in temperature_ids:
        return "reference_matches_zone"

    return None


def production_core_config(
    config: Mapping[str, Any],
) -> tuple[str, str]:
    """Return thermostat and reference sensor or reject bad config."""

    thermostat = config.get(CONF_THERMOSTAT)
    reference = config.get(CONF_REFERENCE_SENSOR)

    if not isinstance(thermostat, str):
        raise ValueError("missing_thermostat")

    if not thermostat:
        raise ValueError("missing_thermostat")

    if not isinstance(reference, str):
        raise ValueError("missing_reference_sensor")

    if not reference:
        raise ValueError("missing_reference_sensor")

    return thermostat, reference


def build_observation_zones(
    raw_zones: object,
):
    """Build runtime zones from dynamic config records."""

    from .observation import ObservationZoneConfig

    records = normalize_zone_records(
        raw_zones
    )

    return tuple(
        ObservationZoneConfig(
            key=record[CONF_ZONE_ID],
            name=record[CONF_ZONE_NAME],
            temperature_entity_id=record[
                CONF_ZONE_TEMPERATURE
            ],
            fan_entity_id=record[
                CONF_ZONE_FAN
            ],
        )
        for record in records
    )
