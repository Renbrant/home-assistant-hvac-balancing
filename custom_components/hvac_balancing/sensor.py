"""Observation-only diagnostic sensors for HVAC Balancing."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
)

from .controller import ZoneDecision
from .observation import (
    HVACBalancingObservationRuntime,
    ObservationSnapshot,
    ObservationZoneConfig,
)
from .runtime import HVACBalancingRuntimeData


METRICS = (
    ("base_p", "Base P"),
    ("adaptive_i", "Adaptive I"),
    ("pi_target", "PI Target"),
    ("effective_percentage", "Effective Percentage"),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[HVACBalancingRuntimeData],
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up observation-only controller sensors."""

    observer = entry.runtime_data.observer

    async_add_entities(
        HVACBalancingObservationSensor(
            observer=observer,
            zone=zone,
            metric=metric,
            metric_name=metric_name,
        )
        for zone in observer.zones
        for metric, metric_name in METRICS
    )


class HVACBalancingObservationSensor(SensorEntity):
    """One calculated observation-only controller metric."""

    _attr_should_poll = False

    def __init__(
        self,
        *,
        observer: HVACBalancingObservationRuntime,
        zone: ObservationZoneConfig,
        metric: str,
        metric_name: str,
    ) -> None:
        """Initialize diagnostic sensor."""

        self._observer = observer
        self._zone = zone
        self._metric = metric

        self._attr_name = (
            f"HVAC Balancing Test {zone.name} {metric_name}"
        )

        self._attr_unique_id = (
            f"test_{zone.key}_{metric}"
        )

        if metric == "effective_percentage":
            self._attr_native_unit_of_measurement = PERCENTAGE

    @property
    def _snapshot(self) -> ObservationSnapshot | None:
        return self._observer.snapshot

    @property
    def _decision(self) -> ZoneDecision | None:
        snapshot = self._snapshot

        if snapshot is None:
            return None

        return snapshot.decisions.get(self._zone.key)

    @property
    def available(self) -> bool:
        """Return whether the virtual Test Bench is loaded."""

        snapshot = self._snapshot

        return (
            snapshot is not None
            and snapshot.test_bench_ready
            and self._decision is not None
        )

    @property
    def native_value(self) -> int | None:
        """Return the requested controller metric."""

        decision = self._decision

        if decision is None:
            return None

        if self._metric == "base_p":
            return decision.base_target

        if self._metric == "adaptive_i":
            return decision.adaptive_boost

        if self._metric == "pi_target":
            return decision.pi_target

        if self._metric == "effective_percentage":
            return decision.effective_percentage

        return None

    @property
    def extra_state_attributes(
        self,
    ) -> dict[str, Any] | None:
        """Expose detailed diagnostics on the PI Target sensor."""

        if self._metric != "pi_target":
            return None

        snapshot = self._snapshot
        decision = self._decision

        if snapshot is None or decision is None:
            return None

        return {
            "observation_only": True,
            "controller_event": snapshot.event.value,
            "hvac_mode": snapshot.hvac_mode,
            "hvac_action": snapshot.hvac_action,
            "temperature_delta": decision.temperature_delta,
            "directional_error": decision.directional_error,
            "base_p": decision.base_target,
            "adaptive_i": decision.adaptive_boost,
            "effective_speed": decision.effective_speed,
            "effective_percentage": decision.effective_percentage,
            "reference_error": decision.reference_error,
            "last_evaluation": (
                decision.last_evaluation.isoformat()
                if decision.last_evaluation is not None
                else None
            ),
            "valid_temperatures": decision.valid_temperatures,
            "control_direction": decision.control_direction,
            "reason": decision.reason,
            "updated_at": snapshot.updated_at.isoformat(),
        }

    async def async_added_to_hass(self) -> None:
        """Subscribe to observation updates."""

        await super().async_added_to_hass()

        self.async_on_remove(
            self._observer.async_add_listener(
                self._handle_observer_update
            )
        )

    @callback
    def _handle_observer_update(self) -> None:
        """Write the latest calculated value to Home Assistant."""

        self.async_write_ha_state()
