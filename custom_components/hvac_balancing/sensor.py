"""Observation-only diagnostic sensors for HVAC Balancing."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
)
from homeassistant.util import dt as dt_util

from .controller import (
    COOLING_ACTION,
    COOL_MODE,
    ZoneDecision,
)
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
    ("improvement_rate", "Improvement Rate"),
    ("adaptive_action", "Adaptive Action"),
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
                metric="last_watchdog",
                name="Last Watchdog",
            ),
            HVACBalancingTimelineSensor(
                observer=observer,
                metric="next_watchdog",
                name="Next Watchdog",
            ),
            HVACBalancingTimelineSensor(
                observer=observer,
                metric="next_watchdog_in",
                name="Next Watchdog In",
            ),
            *(
                HVACBalancingZoneDeadlineSensor(
                    observer=observer,
                    zone=zone,
                )
                for zone in observer.zones
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
            f"{self._observer.entity_name_prefix} {zone.name} {metric_name}"
        )

        self._attr_unique_id = (
            f"{self._observer.unique_id_prefix}_{zone.key}_{metric}"
        )

        if metric == "effective_percentage":
            self._attr_native_unit_of_measurement = PERCENTAGE

        if metric == "improvement_rate":
            self._attr_native_unit_of_measurement = "?F/10 min"

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
    def native_value(self) -> int | float | str | None:
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

        if self._metric == "improvement_rate":
            return decision.improvement_rate_per_10m

        if self._metric == "adaptive_action":
            return decision.adaptive_action

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
            "observation_only": self._observer.observation_only,
            "controller_event": snapshot.event.value,
            "adaptive_due_zone": snapshot.adaptive_due_zone,
            "hvac_mode": snapshot.hvac_mode,
            "hvac_action": snapshot.hvac_action,
            "temperature_delta": decision.temperature_delta,
            "directional_error": decision.directional_error,
            "base_p": decision.base_target,
            "adaptive_i": decision.adaptive_boost,
            "effective_speed": decision.effective_speed,
            "effective_percentage": decision.effective_percentage,
            "reference_error": decision.reference_error,
            "cooling_exposure_seconds": (
                decision.cooling_exposure_seconds
            ),
            "required_cooling_exposure_seconds": (
                decision.required_cooling_exposure_seconds
            ),
            "cooling_exposure_progress_pct": round(
                decision.cooling_exposure_progress * 100,
                1,
            ),
            "improvement_rate_per_10m": (
                decision.improvement_rate_per_10m
            ),
            "adaptive_action": decision.adaptive_action,
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

def _as_local_datetime(
    value: object,
) -> datetime | None:
    """Normalize one diagnostic datetime to Home Assistant local time."""

    if not isinstance(value, datetime):
        return None

    return dt_util.as_local(value)


def _format_time(value: object) -> str:
    """Format a datetime in Home Assistant local time."""

    local_value = _as_local_datetime(
        value
    )

    if local_value is None:
        return "Unknown"

    return local_value.strftime(
        "%H:%M:%S"
    )


def _local_isoformat(
    value: datetime | None,
) -> str | None:
    """Return a local-time ISO timestamp for diagnostic attributes."""

    if value is None:
        return None

    return dt_util.as_local(
        value
    ).isoformat()


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


def _next_ten_minute_watchdog(now):
    """Return the next local wall-clock ten-minute watchdog boundary."""

    minute_floor = now.replace(
        second=0,
        microsecond=0,
    )

    remainder = minute_floor.minute % 10

    minutes = (
        10
        if remainder == 0
        else 10 - remainder
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
            f"{self._observer.entity_name_prefix} {name}"
        )

        self._attr_unique_id = (
            f"{self._observer.unique_id_prefix}_timeline_{metric}"
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
        next_watchdog = _next_ten_minute_watchdog(
            now
        )

        if self._metric == "current_time":
            return _format_time(now)

        if self._metric == "last_controller_update":
            return _format_time(
                snapshot.updated_at
            )

        if self._metric == "last_controller_event":
            return snapshot.event.value

        if self._metric == "last_watchdog":
            if self._observer.last_watchdog is None:
                return "Not yet"

            return _format_time(
                self._observer.last_watchdog
            )

        if self._metric == "next_watchdog":
            return _format_time(
                next_watchdog
            )

        if self._metric == "next_watchdog_in":
            seconds = int(
                (
                    next_watchdog
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
        next_watchdog = _next_ten_minute_watchdog(
            now
        )

        return {
            "observation_only": self._observer.observation_only,
            "current_time": _local_isoformat(
                now
            ),
            "last_controller_update": _local_isoformat(
                snapshot.updated_at
            ),
            "last_controller_event": snapshot.event.value,
            "adaptive_due_zone": snapshot.adaptive_due_zone,
            "last_watchdog": _local_isoformat(
                self._observer.last_watchdog
            ),
            "next_watchdog": _local_isoformat(
                next_watchdog
            ),
            "seconds_to_next_watchdog": max(
                int(
                    (
                        next_watchdog
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



class HVACBalancingZoneDeadlineSensor(SensorEntity):
    """Display one zone's independently scheduled Adaptive deadline."""

    _attr_should_poll = False

    def __init__(
        self,
        *,
        observer: HVACBalancingObservationRuntime,
        zone: ObservationZoneConfig,
    ) -> None:
        """Initialize relative Adaptive deadline diagnostic."""

        self._observer = observer
        self._zone = zone

        self._attr_name = (
            f"{self._observer.entity_name_prefix} "
            f"{zone.name} Next Adaptive Due"
        )

        self._attr_unique_id = (
            f"{self._observer.unique_id_prefix}_{zone.key}_next_adaptive_due"
        )

    @property
    def available(self) -> bool:
        """Return whether the runtime has produced this zone."""

        snapshot = self._observer.snapshot

        return (
            snapshot is not None
            and self._zone.key in snapshot.decisions
        )

    @property
    def native_value(self) -> str | None:
        """Return absolute due time, Paused, or Not scheduled."""

        snapshot = self._observer.snapshot

        if snapshot is None:
            return None

        decision = snapshot.decisions.get(
            self._zone.key
        )

        if decision is None:
            return None

        deadline = self._observer.zone_deadlines.get(
            self._zone.key
        )

        if deadline is not None:
            return _format_time(
                deadline
            )

        if (
            snapshot.hvac_mode == COOL_MODE
            and snapshot.hvac_action != COOLING_ACTION
            and decision.reference_error is not None
            and decision.required_cooling_exposure_seconds > 0
            and decision.adaptive_action
            not in (
                "reset",
                "no_headroom",
                "invalid_input",
                "invalid_reset",
                "inactive",
            )
        ):
            return "Paused"

        if decision.adaptive_action == "no_headroom":
            return "No headroom"

        return "Not scheduled"

    @property
    def extra_state_attributes(
        self,
    ) -> dict[str, Any] | None:
        """Expose relative deadline diagnostics."""

        snapshot = self._observer.snapshot

        if snapshot is None:
            return None

        decision = snapshot.decisions.get(
            self._zone.key
        )

        if decision is None:
            return None

        now = self._observer.display_now

        deadline = self._observer.zone_deadlines.get(
            self._zone.key
        )

        seconds_to_due = None

        if deadline is not None:
            seconds_to_due = max(
                int(
                    (
                        deadline
                        - now
                    ).total_seconds()
                ),
                0,
            )

        return {
            "observation_only": self._observer.observation_only,
            "zone": self._zone.key,
            "deadline": _local_isoformat(
                deadline
            ),
            "seconds_to_due": seconds_to_due,
            "hvac_mode": snapshot.hvac_mode,
            "hvac_action": snapshot.hvac_action,
            "cooling_exposure_seconds": (
                decision.cooling_exposure_seconds
            ),
            "required_cooling_exposure_seconds": (
                decision.required_cooling_exposure_seconds
            ),
            "reference_error": decision.reference_error,
            "adaptive_i": decision.adaptive_boost,
            "adaptive_action": decision.adaptive_action,
        }

    async def async_added_to_hass(self) -> None:
        """Subscribe to display timeline updates."""

        await super().async_added_to_hass()

        self.async_on_remove(
            self._observer.async_add_timeline_listener(
                self._handle_timeline_update
            )
        )

    @callback
    def _handle_timeline_update(self) -> None:
        """Refresh relative deadline display."""

        self.async_write_ha_state()

def _projected_cooling_exposure(
    *,
    observer: HVACBalancingObservationRuntime,
    snapshot: ObservationSnapshot,
    decision: ZoneDecision,
) -> float:
    """Project live cooling exposure without executing controller logic."""

    exposure = max(
        float(decision.cooling_exposure_seconds),
        0.0,
    )

    actively_collecting = (
        snapshot.hvac_mode == COOL_MODE
        and snapshot.hvac_action == COOLING_ACTION
        and decision.valid_temperatures
        and decision.required_cooling_exposure_seconds > 0
        and decision.adaptive_action not in (
            "inactive",
            "invalid_input",
            "invalid_reset",
            "awaiting_reference",
            "no_headroom",
        )
    )

    if not actively_collecting:
        return exposure

    elapsed = (
        observer.display_now
        - snapshot.updated_at
    ).total_seconds()

    return exposure + max(
        elapsed,
        0.0,
    )


class HVACBalancingAdaptiveWindowSensor(SensorEntity):
    """Display effective cooling exposure for one Test Bench zone.

    The historic unique ID is deliberately retained so the existing beta.3
    entity registry continues using sensor.hvac_balancing_test_*_adaptive_window.
    """

    _attr_should_poll = False

    def __init__(
        self,
        *,
        observer: HVACBalancingObservationRuntime,
        zone: ObservationZoneConfig,
    ) -> None:
        """Initialize Cooling Exposure diagnostic."""

        self._observer = observer
        self._zone = zone

        self._attr_name = (
            f"{self._observer.entity_name_prefix} "
            f"{zone.name} Adaptive Window"
        )

        self._attr_unique_id = (
            f"{self._observer.unique_id_prefix}_{zone.key}_adaptive_window"
        )

    @property
    def available(self) -> bool:
        """Return whether this zone exists in the current snapshot."""

        snapshot = self._observer.snapshot

        return (
            snapshot is not None
            and self._zone.key in snapshot.decisions
        )

    @property
    def native_value(self) -> str | None:
        """Return effective cooling exposure versus dynamic requirement."""

        snapshot = self._observer.snapshot

        if snapshot is None:
            return None

        decision = snapshot.decisions.get(
            self._zone.key
        )

        if decision is None:
            return None

        action = decision.adaptive_action

        if action == "inactive":
            return "Inactive"

        if action in (
            "invalid_input",
            "invalid_reset",
        ):
            return "Invalid input"

        if action == "awaiting_reference":
            return "Awaiting reference"

        if action == "no_headroom":
            return "No headroom"

        required = max(
            float(
                decision.required_cooling_exposure_seconds
            ),
            0.0,
        )

        if required <= 0:
            return "Not required"

        exposure = _projected_cooling_exposure(
            observer=self._observer,
            snapshot=snapshot,
            decision=decision,
        )

        shown_exposure = min(
            exposure,
            required,
        )

        state = (
            f"{_format_duration(int(shown_exposure))}"
            f" / "
            f"{_format_duration(int(required))}"
        )

        if exposure >= required:
            return f"{state} READY"

        return state

    @property
    def extra_state_attributes(
        self,
    ) -> dict[str, Any] | None:
        """Expose detailed effective-cooling diagnostics."""

        snapshot = self._observer.snapshot

        if snapshot is None:
            return None

        decision = snapshot.decisions.get(
            self._zone.key
        )

        if decision is None:
            return None

        required = max(
            float(
                decision.required_cooling_exposure_seconds
            ),
            0.0,
        )

        exposure = _projected_cooling_exposure(
            observer=self._observer,
            snapshot=snapshot,
            decision=decision,
        )

        remaining = max(
            required - exposure,
            0.0,
        )

        progress = 0.0

        if required > 0:
            progress = min(
                exposure / required,
                1.0,
            )

        return {
            "observation_only": self._observer.observation_only,
            "adaptive_strategy": "cooling_exposure",
            "zone": self._zone.key,
            "hvac_mode": snapshot.hvac_mode,
            "hvac_action": snapshot.hvac_action,
            "directional_error": decision.directional_error,
            "adaptive_i": decision.adaptive_boost,
            "adaptive_action": decision.adaptive_action,
            "reference_error": decision.reference_error,
            "improvement_rate_per_10m": (
                decision.improvement_rate_per_10m
            ),
            "stored_cooling_exposure_seconds": (
                decision.cooling_exposure_seconds
            ),
            "projected_cooling_exposure_seconds": round(
                exposure,
                1,
            ),
            "required_cooling_exposure_seconds": required,
            "remaining_cooling_exposure_seconds": round(
                remaining,
                1,
            ),
            "cooling_exposure_progress_pct": round(
                progress * 100,
                1,
            ),
            "ready_for_adaptive_due": (
                required > 0
                and exposure >= required
            ),
            "last_evaluation": (
                decision.last_evaluation.isoformat()
                if decision.last_evaluation is not None
                else None
            ),
        }

    async def async_added_to_hass(self) -> None:
        """Subscribe only to display timeline updates."""

        await super().async_added_to_hass()

        self.async_on_remove(
            self._observer.async_add_timeline_listener(
                self._handle_timeline_update
            )
        )

    @callback
    def _handle_timeline_update(self) -> None:
        """Refresh live cooling-exposure display only."""

        self.async_write_ha_state()
