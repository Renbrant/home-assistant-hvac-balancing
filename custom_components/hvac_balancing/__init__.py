"""Home Assistant HVAC Balancing integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import NAME, VERSION
from .runtime import HVACBalancingRuntimeData

_LOGGER = logging.getLogger(__name__)


async def async_setup(
    hass: HomeAssistant,
    config: dict[str, Any],
) -> bool:
    """Set up the HVAC Balancing integration package.

    The v0.2.0 Phase 1 skeleton intentionally performs no HVAC
    calculations and sends no actuator commands.
    """

    return True


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> bool:
    """Set up HVAC Balancing from a config entry.

    Runtime state is stored on ConfigEntry.runtime_data instead of in
    a global hass.data structure.

    Phase 1 operates only as an integration lifecycle skeleton.
    """

    entry.runtime_data = HVACBalancingRuntimeData()

    _LOGGER.info(
        "%s %s loaded in safe Phase 1 observation-only mode",
        NAME,
        VERSION,
    )

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> bool:
    """Unload an HVAC Balancing config entry.

    No listeners, timers, platforms, or physical actuators exist in
    Phase 1, so there are currently no runtime resources to release.
    """

    _LOGGER.info(
        "%s %s unloaded",
        NAME,
        VERSION,
    )

    return True
