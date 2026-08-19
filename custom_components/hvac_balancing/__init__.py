"""Home Assistant HVAC Balancing integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .actuator import HVACBalancingActuator
from .configuration import (
    build_observation_zones,
    central_assist_config,
    merged_entry_config,
    production_core_config,
    stale_production_zone_unique_ids,
    validate_zone_records,
)
from .const import (
    CONF_ACTUATION_ENABLED,
    CONF_RUNTIME_MODE,
    CONF_ZONES,
    DOMAIN,
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


def _async_cleanup_stale_production_zone_entities(
    hass: HomeAssistant,
    entry: HVACBalancingConfigEntry,
    zones: tuple[ObservationZoneConfig, ...],
) -> None:
    """Remove registry diagnostics belonging to zones no longer configured."""

    registry = er.async_get(
        hass
    )

    registry_entries = [
        registry_entry
        for registry_entry
        in er.async_entries_for_config_entry(
            registry,
            entry.entry_id,
        )
        if registry_entry.platform == DOMAIN
    ]

    stale_unique_ids = stale_production_zone_unique_ids(
        (
            registry_entry.unique_id
            for registry_entry in registry_entries
        ),
        (
            zone.key
            for zone in zones
        ),
    )

    if not stale_unique_ids:
        return

    for registry_entry in registry_entries:
        if registry_entry.unique_id not in stale_unique_ids:
            continue

        _LOGGER.info(
            "Removing stale HVAC Balancing entity %s (%s)",
            registry_entry.entity_id,
            registry_entry.unique_id,
        )

        registry.async_remove(
            registry_entry.entity_id
        )


async def async_setup(
    hass: HomeAssistant,
    config: dict[str, Any],
) -> bool:
    """Set up the HVAC Balancing integration package."""

    return True


async def _async_update_listener(
    hass: HomeAssistant,
    entry: HVACBalancingConfigEntry,
) -> None:
    """Reload runtime after the user changes integration options."""

    await hass.config_entries.async_reload(
        entry.entry_id
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HVACBalancingConfigEntry,
) -> bool:
    """Set up Test Bench or dynamically configured production runtime."""

    runtime_mode = entry.data.get(
        CONF_RUNTIME_MODE,
        RUNTIME_MODE_TEST_BENCH,
    )

    if runtime_mode not in (
        RUNTIME_MODE_TEST_BENCH,
        RUNTIME_MODE_PRODUCTION,
    ):
        _LOGGER.error(
            "Unsupported HVAC Balancing runtime mode: %s",
            runtime_mode,
        )

        return False

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

        config = merged_entry_config(
            entry
        )

        try:
            thermostat_entity_id, reference_entity_id = (
                production_core_config(
                    config
                )
            )

            assist_config = central_assist_config(
                config
            )

            raw_zones = config.get(
                CONF_ZONES,
                [],
            )

            zones = build_observation_zones(
                raw_zones
            )

        except ValueError as err:
            _LOGGER.error(
                "Invalid HVAC Balancing production configuration: %s",
                err,
            )

            return False

        zone_error = validate_zone_records(
            raw_zones,
            reference_entity_id,
        )

        if zone_error is not None:
            _LOGGER.error(
                "Invalid HVAC Balancing zone configuration: %s",
                zone_error,
            )

            return False

        _async_cleanup_stale_production_zone_entities(
            hass,
            entry,
            zones,
        )

        observer = HVACBalancingObservationRuntime(
            hass,
            thermostat_entity_id=thermostat_entity_id,
            reference_entity_id=reference_entity_id,
            zones=zones,
            entity_name_prefix="HVAC Balancing",
            unique_id_prefix="production",
            observation_only=False,
            runtime_mode=RUNTIME_MODE_PRODUCTION,
        )

        actuator = HVACBalancingActuator(
            hass,
            entry_id=entry.entry_id,
            observer=observer,
            thermostat_entity_id=thermostat_entity_id,
            central_assist=assist_config,
            zones=zones,
        )

        # Restore persisted ownership before the STARTUP controller snapshot.
        await actuator.async_prepare()

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
        entry.add_update_listener(
            _async_update_listener
        )
    )

    entry.async_on_unload(
        observer.async_stop
    )

    if actuator is not None:
        entry.async_on_unload(
            actuator.async_stop
        )

        # Subscribe before STARTUP so first calculated outputs are applied.
        actuator.async_start()

    observer.async_start()

    await hass.config_entries.async_forward_entry_setups(
        entry,
        PLATFORMS,
    )

    _LOGGER.info(
        "%s %s loaded runtime=%s zones=%s observation_only=%s",
        NAME,
        VERSION,
        runtime_mode,
        len(observer.zones),
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
