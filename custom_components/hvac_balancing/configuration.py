"""Dynamic configuration helpers for HVAC Balancing."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
import re
from typing import Any
import unicodedata

from .const import (
    CENTRAL_ASSIST_MODE_CLIMATE,
    CENTRAL_ASSIST_MODE_DISABLED,
    CENTRAL_ASSIST_MODE_FAN,
    CENTRAL_ASSIST_MODE_NEST,
    CONF_CENTRAL_ASSIST_ENTITY,
    CONF_CENTRAL_ASSIST_MODE,
    CONF_CENTRAL_ASSIST_OFF_MODE,
    CONF_CENTRAL_ASSIST_ON_MODE,
    CONF_REFERENCE_SENSOR,
    CONF_THERMOSTAT,
    DEFAULT_CENTRAL_ASSIST_MODE,
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
    "temperature_delta",
    "base_p",
    "adaptive_i",
    "pi_target",
    "effective_percentage",
    "improvement_rate",
    "adaptive_action",
    "next_adaptive_due",
    "adaptive_window",
)


# Historical Home Assistant entity compatibility.
#
# These five controller metrics existed as v0.1.3 YAML/Jinja template
# sensors. Production v0.2 deliberately retains their public entity IDs
# and friendly names so Recorder history, dashboards, and references can
# continue across the implementation boundary.
#
# This mapping is generic by zone name; it does not hard-code Bed 1/2/3.
LEGACY_COMPATIBLE_SENSOR_METADATA = {
    "temperature_delta": (
        "temperature_delta",
        "Temperature Delta",
    ),
    "base_p": (
        "booster_target_speed",
        "Booster Target Speed",
    ),
    "adaptive_i": (
        "booster_adaptive_boost",
        "Booster Adaptive Boost",
    ),
    "pi_target": (
        "booster_pi_target_speed",
        "Booster PI Target Speed",
    ),
    "effective_percentage": (
        "booster_effective_percentage",
        "Booster Effective Percentage",
    ),
}


def _legacy_zone_object_id(
    zone_name: str,
) -> str | None:
    """Return a stable HA-compatible object-id prefix from a zone name."""

    normalized = unicodedata.normalize(
        "NFKD",
        zone_name,
    )

    ascii_name = normalized.encode(
        "ascii",
        "ignore",
    ).decode(
        "ascii"
    )

    object_id = re.sub(
        r"[^a-z0-9]+",
        "_",
        ascii_name.lower(),
    ).strip("_")

    if not object_id:
        return None

    return object_id


def legacy_compatible_sensor_entity_id(
    zone_name: str,
    metric: str,
) -> str | None:
    """Return the legacy-compatible production sensor entity ID."""

    metadata = LEGACY_COMPATIBLE_SENSOR_METADATA.get(
        metric
    )

    if metadata is None:
        return None

    object_id = _legacy_zone_object_id(
        zone_name
    )

    if object_id is None:
        return None

    suffix, _ = metadata

    return f"sensor.{object_id}_{suffix}"


def legacy_compatible_sensor_name(
    zone_name: str,
    metric: str,
) -> str | None:
    """Return the v0.1.3-compatible friendly name for one metric."""

    metadata = LEGACY_COMPATIBLE_SENSOR_METADATA.get(
        metric
    )

    if metadata is None:
        return None

    _, metric_name = metadata

    return f"{zone_name} {metric_name}"


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


@dataclass(frozen=True, slots=True)
class CentralAssistConfig:
    """Normalized Central Assist actuation configuration."""

    mode: str
    fan_entity_id: str | None = None
    fan_mode_on: str | None = None
    fan_mode_off: str | None = None


def central_assist_config(
    config: Mapping[str, Any],
) -> CentralAssistConfig:
    """Normalize installation-specific Central Assist actuation."""

    mode = config.get(
        CONF_CENTRAL_ASSIST_MODE,
        DEFAULT_CENTRAL_ASSIST_MODE,
    )

    valid_modes = {
        CENTRAL_ASSIST_MODE_DISABLED,
        CENTRAL_ASSIST_MODE_FAN,
        CENTRAL_ASSIST_MODE_CLIMATE,
        CENTRAL_ASSIST_MODE_NEST,
    }

    if not isinstance(mode, str):
        raise ValueError(
            "invalid_central_assist_mode"
        )

    if mode not in valid_modes:
        raise ValueError(
            "invalid_central_assist_mode"
        )

    if mode == CENTRAL_ASSIST_MODE_FAN:
        fan_entity_id = config.get(
            CONF_CENTRAL_ASSIST_ENTITY
        )

        if not isinstance(fan_entity_id, str):
            raise ValueError(
                "missing_central_assist_fan"
            )

        fan_entity_id = fan_entity_id.strip()

        if not fan_entity_id.startswith("fan."):
            raise ValueError(
                "invalid_central_assist_fan"
            )

        return CentralAssistConfig(
            mode=mode,
            fan_entity_id=fan_entity_id,
        )

    if mode == CENTRAL_ASSIST_MODE_CLIMATE:
        fan_mode_on = config.get(
            CONF_CENTRAL_ASSIST_ON_MODE
        )

        fan_mode_off = config.get(
            CONF_CENTRAL_ASSIST_OFF_MODE
        )

        if not isinstance(fan_mode_on, str):
            raise ValueError(
                "missing_central_assist_on_mode"
            )

        if not isinstance(fan_mode_off, str):
            raise ValueError(
                "missing_central_assist_off_mode"
            )

        fan_mode_on = fan_mode_on.strip()
        fan_mode_off = fan_mode_off.strip()

        if not fan_mode_on:
            raise ValueError(
                "missing_central_assist_on_mode"
            )

        if not fan_mode_off:
            raise ValueError(
                "missing_central_assist_off_mode"
            )

        return CentralAssistConfig(
            mode=mode,
            fan_mode_on=fan_mode_on,
            fan_mode_off=fan_mode_off,
        )

    return CentralAssistConfig(
        mode=mode
    )


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
