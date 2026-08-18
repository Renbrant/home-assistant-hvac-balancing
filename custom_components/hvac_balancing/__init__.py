"""Home Assistant HVAC Balancing integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import NAME, VERSION
from .observation import HVACBalancingObservationRuntime
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


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HVACBalancingConfigEntry,
) -> bool:
    """Set up HVAC Balancing in observation-only mode."""

    observer = HVACBalancingObservationRuntime(hass)

    entry.runtime_data = HVACBalancingRuntimeData(
        observer=observer,
    )

    # Home Assistant will invoke this callback if setup fails after this
    # point or after a successful config-entry unload.
    entry.async_on_unload(observer.async_stop)

    observer.async_start()

    await hass.config_entries.async_forward_entry_setups(
        entry,
        PLATFORMS,
    )

    _LOGGER.info(
        "%s %s loaded in observation-only Test Bench mode",
        NAME,
        VERSION,
    )

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: HVACBalancingConfigEntry,
) -> bool:
    """Unload HVAC Balancing and its diagnostic entities."""

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
