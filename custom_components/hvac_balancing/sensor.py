"""Observation-only diagnostic sensors for HVAC Balancing."""

from __future__ import annotations

from datetime import timedelta
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

    async_add_entities(
        [
            HVACBalancingTimelineSensor(
                observer=observer,
                metric="current_time",
                name="Current Time",
            ),
            HVACBalancingTimelineSensor(
                observer=observer,
                metric="last_controller_update",
                name="Last Controller Update",
            ),
            HVACBalancingTimelineSensor(
                observer=observer,
                metric="last_controller_event",
                name="Last Controller Event",
            ),
            HVACBalancingTimelineSensor(
                observer=observer,
                metric="last_adaptive_tick",
                name="Last Adaptive Tick",
            ),
            HVACBalancingTimelineSensor(
                observer=observer,
                metric="next_adaptive_tick",
                name="Next Adaptive Tick",
            ),
            HVACBalancingTimelineSensor(
                observer=observer,
                metric="next_tick_in",
                name="Next Adaptive Tick In",
            ),
            *(
                HVACBalancingAdaptiveWindowSensor(
                    observer=observer,
                    zone=zone,
                )
                for zone in observer.zones
            ),
        ]
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

def _format_time(value: object) -> str:
    """Format a datetime for Test Bench display."""

    if hasattr(value, "strftime"):
        return value.strftime("%H:%M:%S")

    return "Unknown"


def _format_duration(total_seconds: int) -> str:
    """Format positive seconds as MM:SS."""

    total_seconds = max(
        int(total_seconds),
        0,
    )

    minutes, seconds = divmod(
        total_seconds,
        60,
    )

    return f"{minutes:02d}:{seconds:02d}"


def _next_five_minute_tick(now):
    """Return the next local wall-clock five-minute boundary."""

    minute_floor = now.replace(
        second=0,
        microsecond=0,
    )

    remainder = minute_floor.minute % 5

    minutes = (
        5
        if remainder == 0
        else 5 - remainder
    )

    return minute_floor + timedelta(
        minutes=minutes
    )


class HVACBalancingTimelineSensor(SensorEntity):
    """Display-only controller timeline diagnostic."""

    _attr_should_poll = False

    def __init__(
        self,
        *,
        observer: HVACBalancingObservationRuntime,
        metric: str,
        name: str,
    ) -> None:
        """Initialize timeline sensor."""

        self._observer = observer
        self._metric = metric

        self._attr_name = (
            f"HVAC Balancing Test {name}"
        )

        self._attr_unique_id = (
            f"test_timeline_{metric}"
        )

    @property
    def available(self) -> bool:
        """Return whether runtime has produced a snapshot."""

        return self._observer.snapshot is not None

    @property
    def native_value(self) -> str | None:
        """Return requested timeline value."""

        snapshot = self._observer.snapshot

        if snapshot is None:
            return None

        now = self._observer.display_now
        next_tick = _next_five_minute_tick(now)

        if self._metric == "current_time":
            return _format_time(now)

        if self._metric == "last_controller_update":
            return _format_time(
                snapshot.updated_at
            )

        if self._metric == "last_controller_event":
            return snapshot.event.value

        if self._metric == "last_adaptive_tick":
            if self._observer.last_adaptive_tick is None:
                return "Not yet"

            return _format_time(
                self._observer.last_adaptive_tick
            )

        if self._metric == "next_adaptive_tick":
            return _format_time(next_tick)

        if self._metric == "next_tick_in":
            seconds = int(
                (
                    next_tick
                    - now
                ).total_seconds()
            )

            return _format_duration(seconds)

        return None

    @property
    def extra_state_attributes(
        self,
    ) -> dict[str, Any] | None:
        """Expose exact timeline information."""

        snapshot = self._observer.snapshot

        if snapshot is None:
            return None

        now = self._observer.display_now
        next_tick = _next_five_minute_tick(now)

        return {
            "observation_only": True,
            "current_time": now.isoformat(),
            "last_controller_update": snapshot.updated_at.isoformat(),
            "last_controller_event": snapshot.event.value,
            "last_adaptive_tick": (
                self._observer.last_adaptive_tick.isoformat()
                if self._observer.last_adaptive_tick is not None
                else None
            ),
            "next_adaptive_tick": next_tick.isoformat(),
            "seconds_to_next_tick": max(
                int(
                    (
                        next_tick
                        - now
                    ).total_seconds()
                ),
                0,
            ),
        }

    async def async_added_to_hass(self) -> None:
        """Subscribe only to timeline notifications."""

        await super().async_added_to_hass()

        self.async_on_remove(
            self._observer.async_add_timeline_listener(
                self._handle_timeline_update
            )
        )

    @callback
    def _handle_timeline_update(self) -> None:
        """Write latest timeline value."""

        self.async_write_ha_state()


class HVACBalancingAdaptiveWindowSensor(SensorEntity):
    """Display remaining time in one zone Adaptive I observation window."""

    _attr_should_poll = False

    ADAPTIVE_INTERVAL_SECONDS = 1200

    def __init__(
        self,
        *,
        observer: HVACBalancingObservationRuntime,
        zone: ObservationZoneConfig,
    ) -> None:
        """Initialize Adaptive window sensor."""

        self._observer = observer
        self._zone = zone

        self._attr_name = (
            f"HVAC Balancing Test "
            f"{zone.name} Adaptive Window"
        )

        self._attr_unique_id = (
            f"test_{zone.key}_adaptive_window"
        )

    @property
    def available(self) -> bool:
        """Return whether this zone exists in current snapshot."""

        snapshot = self._observer.snapshot

        return (
            snapshot is not None
            and self._zone.key in snapshot.decisions
        )

    @property
    def native_value(self) -> str | None:
        """Return countdown, Due, or Not started."""

        snapshot = self._observer.snapshot

        if snapshot is None:
            return None

        decision = snapshot.decisions.get(
            self._zone.key
        )

        if decision is None:
            return None

        last_evaluation = decision.last_evaluation

        if last_evaluation is None:
            return "Not started"

        elapsed = (
            self._observer.display_now
            - last_evaluation
        ).total_seconds()

        remaining = (
            self.ADAPTIVE_INTERVAL_SECONDS
            - elapsed
        )

        if remaining <= 0:
            return "Due"

        return _format_duration(
            int(remaining)
        )

    @property
    def extra_state_attributes(
        self,
    ) -> dict[str, Any] | None:
        """Expose detailed observation-window timing."""

        snapshot = self._observer.snapshot

        if snapshot is None:
            return None

        decision = snapshot.decisions.get(
            self._zone.key
        )

        if decision is None:
            return None

        last_evaluation = decision.last_evaluation

        seconds_remaining = None

        if last_evaluation is not None:
            elapsed = (
                self._observer.display_now
                - last_evaluation
            ).total_seconds()

            seconds_remaining = max(
                int(
                    self.ADAPTIVE_INTERVAL_SECONDS
                    - elapsed
                ),
                0,
            )

        return {
            "observation_only": True,
            "zone": self._zone.key,
            "adaptive_i": decision.adaptive_boost,
            "reference_error": decision.reference_error,
            "last_evaluation": (
                last_evaluation.isoformat()
                if last_evaluation is not None
                else None
            ),
            "seconds_remaining": seconds_remaining,
        }

    async def async_added_to_hass(self) -> None:
        """Subscribe only to timeline notifications."""

        await super().async_added_to_hass()

        self.async_on_remove(
            self._observer.async_add_timeline_listener(
                self._handle_timeline_update
            )
        )

    @callback
    def _handle_timeline_update(self) -> None:
        """Write latest Adaptive countdown."""

        self.async_write_ha_state()
