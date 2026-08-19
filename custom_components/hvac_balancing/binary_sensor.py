"""Central-assist diagnostic for HVAC Balancing."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
)

from .observation import HVACBalancingObservationRuntime
from .runtime import HVACBalancingRuntimeData


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[HVACBalancingRuntimeData],
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up central-assist diagnostic."""

    async_add_entities(
        [
            HVACBalancingCentralAssistSensor(
                entry.runtime_data.observer
            )
        ]
    )


class HVACBalancingCentralAssistSensor(BinarySensorEntity):
    """Report the controller central-assist request."""

    _attr_should_poll = False

    def __init__(
        self,
        observer: HVACBalancingObservationRuntime,
    ) -> None:
        """Initialize central-assist diagnostic."""

        self._observer = observer

        self._attr_name = (
            f"{observer.entity_name_prefix} Central Assist"
        )

        self._attr_unique_id = (
            f"{observer.unique_id_prefix}_central_assist"
        )

    @property
    def available(self) -> bool:
        """Return whether the controller runtime is loaded."""

        snapshot = self._observer.snapshot

        return (
            snapshot is not None
            and snapshot.test_bench_ready
        )

    @property
    def is_on(self) -> bool | None:
        """Return the calculated central-assist request."""

        snapshot = self._observer.snapshot

        if snapshot is None:
            return None

        return snapshot.central_assist_required

    @property
    def extra_state_attributes(
        self,
    ) -> dict[str, Any] | None:
        """Return central controller diagnostics."""

        snapshot = self._observer.snapshot

        if snapshot is None:
            return None

        return {
            "observation_only": self._observer.observation_only,
            "runtime_mode": self._observer.runtime_mode,
            "controller_event": snapshot.event.value,
            "hvac_mode": snapshot.hvac_mode,
            "hvac_action": snapshot.hvac_action,
            "updated_at": snapshot.updated_at.isoformat(),
        }

    async def async_added_to_hass(self) -> None:
        """Subscribe to controller updates."""

        await super().async_added_to_hass()

        self.async_on_remove(
            self._observer.async_add_listener(
                self._handle_observer_update
            )
        )

    @callback
    def _handle_observer_update(self) -> None:
        """Write the latest calculated value."""

        self.async_write_ha_state()
