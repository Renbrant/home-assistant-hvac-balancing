"""Home Assistant HVAC Balancing integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .actuator import HVACBalancingActuator
from .const import (
    CONF_ACTUATION_ENABLED,
    CONF_REFERENCE_SENSOR,
    CONF_RUNTIME_MODE,
    CONF_THERMOSTAT,
    CONF_ZONE_1_FAN,
    CONF_ZONE_1_NAME,
    CONF_ZONE_1_TEMPERATURE,
    CONF_ZONE_2_FAN,
    CONF_ZONE_2_NAME,
    CONF_ZONE_2_TEMPERATURE,
    CONF_ZONE_3_FAN,
    CONF_ZONE_3_NAME,
    CONF_ZONE_3_TEMPERATURE,
    NAME,
    RUNTIME_MODE_PRODUCTION,
    RUNTIME_MODE_TEST_BENCH,
    VERSION,
)
from .observation import (
    HVACBalancingObservationRuntime,
    ObservationZoneConfig,
)
from .runtime import HVACBalancingRuntimeData


_LOGGER = logging.getLogger(__name__)

PLATFORMS = (
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
)

type HVACBalancingConfigEntry = ConfigEntry[HVACBalancingRuntimeData]


async def async_setup(
    hass: HomeAssistant,
    config: dict[str, Any],
) -> bool:
    """Set up the HVAC Balancing integration package."""

    return True


def _production_zones(
    entry: HVACBalancingConfigEntry,
) -> tuple[ObservationZoneConfig, ...]:
    """Build configured production zones."""

    return (
        ObservationZoneConfig(
            key="zone_1",
            name=entry.data[CONF_ZONE_1_NAME],
            temperature_entity_id=entry.data[
                CONF_ZONE_1_TEMPERATURE
            ],
            fan_entity_id=entry.data[
                CONF_ZONE_1_FAN
            ],
        ),
        ObservationZoneConfig(
            key="zone_2",
            name=entry.data[CONF_ZONE_2_NAME],
            temperature_entity_id=entry.data[
                CONF_ZONE_2_TEMPERATURE
            ],
            fan_entity_id=entry.data[
                CONF_ZONE_2_FAN
            ],
        ),
        ObservationZoneConfig(
            key="zone_3",
            name=entry.data[CONF_ZONE_3_NAME],
            temperature_entity_id=entry.data[
                CONF_ZONE_3_TEMPERATURE
            ],
            fan_entity_id=entry.data[
                CONF_ZONE_3_FAN
            ],
        ),
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HVACBalancingConfigEntry,
) -> bool:
    """Set up either Test Bench or gated production runtime."""

    runtime_mode = entry.data.get(
        CONF_RUNTIME_MODE,
        RUNTIME_MODE_TEST_BENCH,
    )

    observer: HVACBalancingObservationRuntime
    actuator: HVACBalancingActuator | None = None
    observation_only = True

    if runtime_mode == RUNTIME_MODE_PRODUCTION:
        actuation_enabled = bool(
            entry.data.get(
                CONF_ACTUATION_ENABLED,
                False,
            )
        )

        if not actuation_enabled:
            _LOGGER.error(
                "Production runtime refused to start because "
                "actuation_enabled is false"
            )

            return False

        zones = _production_zones(
            entry
        )

        observer = HVACBalancingObservationRuntime(
            hass,
            thermostat_entity_id=entry.data[
                CONF_THERMOSTAT
            ],
            reference_entity_id=entry.data[
                CONF_REFERENCE_SENSOR
            ],
            zones=zones,
            entity_name_prefix="HVAC Balancing",
            unique_id_prefix="production",
            observation_only=False,
            runtime_mode=RUNTIME_MODE_PRODUCTION,
        )

        actuator = HVACBalancingActuator(
            hass,
            observer=observer,
            thermostat_entity_id=entry.data[
                CONF_THERMOSTAT
            ],
            zones=zones,
        )

        observation_only = False

    if runtime_mode != RUNTIME_MODE_PRODUCTION:
        observer = HVACBalancingObservationRuntime(
            hass,
            runtime_mode=RUNTIME_MODE_TEST_BENCH,
        )

    entry.runtime_data = HVACBalancingRuntimeData(
        observer=observer,
        actuator=actuator,
        observation_only=observation_only,
        runtime_mode=runtime_mode,
    )

    entry.async_on_unload(
        observer.async_stop
    )

    if actuator is not None:
        entry.async_on_unload(
            actuator.async_stop
        )

        # Subscribe actuator before the observer STARTUP snapshot.
        actuator.async_start()

    observer.async_start()

    await hass.config_entries.async_forward_entry_setups(
        entry,
        PLATFORMS,
    )

    _LOGGER.info(
        "%s %s loaded runtime=%s observation_only=%s",
        NAME,
        VERSION,
        runtime_mode,
        observation_only,
    )

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: HVACBalancingConfigEntry,
) -> bool:
    """Unload HVAC Balancing and fail safe active outputs."""

    runtime = entry.runtime_data

    if runtime.actuator is not None:
        await runtime.actuator.async_shutdown()

    unload_ok = await hass.config_entries.async_unload_platforms(
        entry,
        PLATFORMS,
    )

    if unload_ok:
        _LOGGER.info(
            "%s %s unloaded",
            NAME,
            VERSION,
        )

    return unload_ok
