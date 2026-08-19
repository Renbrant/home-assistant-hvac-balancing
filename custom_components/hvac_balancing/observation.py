"""Observation-only Home Assistant adapter for the virtual HVAC Test Bench.

This module translates Home Assistant state changes into inputs for the pure
controller. It publishes calculated runtime data only. It contains no actuator
or service-call logic.

The hard-coded Bed 1/2/3 entity mapping in this module is temporary,
development-only Test Bench wiring. Dynamic user-configured zones are introduced
in the configuration phase of the v0.2 integration.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from homeassistant.core import (
    Event,
    EventStateChangedData,
    HomeAssistant,
    callback,
)
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_change,
)
from homeassistant.util import dt as dt_util

from .controller import (
    COOLING_EXPOSURE_SETTINGS,
    ControllerEvent,
    ZoneDecision,
    ZoneInput,
    ZoneState,
    calculate_zone,
    central_assist_required,
)


TEST_BENCH_THERMOSTAT = "climate.hvac_test_thermostat"
TEST_BENCH_REFERENCE = "sensor.hvac_test_kitchen_temperature"


@dataclass(frozen=True, slots=True)
class ObservationZoneConfig:
    """Development Test Bench zone mapping."""

    key: str
    name: str
    temperature_entity_id: str


TEST_BENCH_ZONES = (
    ObservationZoneConfig(
        key="bed_1",
        name="Bed 1",
        temperature_entity_id="sensor.hvac_test_bed_1_temperature",
    ),
    ObservationZoneConfig(
        key="bed_2",
        name="Bed 2",
        temperature_entity_id="sensor.hvac_test_bed_2_temperature",
    ),
    ObservationZoneConfig(
        key="bed_3",
        name="Bed 3",
        temperature_entity_id="sensor.hvac_test_bed_3_temperature",
    ),
)


@dataclass(frozen=True, slots=True)
class ObservationSnapshot:
    """One complete observation-only controller calculation."""

    event: ControllerEvent
    updated_at: datetime
    hvac_mode: str | None
    hvac_action: str | None
    test_bench_ready: bool
    decisions: dict[str, ZoneDecision]
    central_assist_required: bool


class HVACBalancingObservationRuntime:
    """Run the pure controller against Home Assistant virtual entities."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize observation runtime."""

        self.hass = hass

        self.snapshot: ObservationSnapshot | None = None

        # Display-only timing state.
        #
        # The heartbeat updates Test Bench timing entities but never executes
        # calculate_zone() and never mutates Adaptive controller state.
        self.display_now: datetime = dt_util.now()
        self.last_adaptive_tick: datetime | None = None

        self._zone_states: dict[str, ZoneState] = {
            zone.key: ZoneState()
            for zone in TEST_BENCH_ZONES
        }

        self._listeners: set[Callable[[], None]] = set()
        self._timeline_listeners: set[Callable[[], None]] = set()
        self._unsubscribers: list[Callable[[], None]] = []

    @property
    def zones(self) -> tuple[ObservationZoneConfig, ...]:
        """Return Test Bench zone definitions."""

        return TEST_BENCH_ZONES

    @property
    def observed_entity_ids(self) -> tuple[str, ...]:
        """Return every HA entity consumed by the observation runtime."""

        return (
            TEST_BENCH_THERMOSTAT,
            TEST_BENCH_REFERENCE,
            *(
                zone.temperature_entity_id
                for zone in TEST_BENCH_ZONES
            ),
        )

    @callback
    def async_start(self) -> None:
        """Start observation listeners and calculate the initial snapshot."""

        self._unsubscribers.append(
            async_track_state_change_event(
                self.hass,
                self.observed_entity_ids,
                self._async_state_changed,
            )
        )

        # Match the legacy time_pattern minutes: "/5" behavior rather than
        # using an interval relative to integration load time.
        self._unsubscribers.append(
            async_track_time_change(
                self.hass,
                self._async_adaptive_tick,
                minute=range(0, 60, 5),
                second=0,
            )
        )

        # Display-only heartbeat. This updates clocks/countdowns but does not
        # produce a ControllerEvent and does not recalculate any zone.
        self._unsubscribers.append(
            async_track_time_change(
                self.hass,
                self._async_timeline_heartbeat,
                second=range(0, 60, 10),
            )
        )

        self._recalculate(
            ControllerEvent.STARTUP,
            dt_util.now(),
        )

    @callback
    def async_stop(self) -> None:
        """Stop all observation listeners."""

        for unsubscribe in self._unsubscribers:
            unsubscribe()

        self._unsubscribers.clear()
        self._listeners.clear()
        self._timeline_listeners.clear()

    @callback
    def async_add_listener(
        self,
        listener: Callable[[], None],
    ) -> Callable[[], None]:
        """Subscribe an entity to observation snapshot updates."""

        self._listeners.add(listener)

        @callback
        def remove_listener() -> None:
            self._listeners.discard(listener)

        return remove_listener

    @callback
    def async_add_timeline_listener(
        self,
        listener: Callable[[], None],
    ) -> Callable[[], None]:
        """Subscribe only to display timeline updates."""

        self._timeline_listeners.add(listener)

        @callback
        def remove_listener() -> None:
            self._timeline_listeners.discard(listener)

        return remove_listener

    @callback
    def _async_state_changed(
        self,
        event: Event[EventStateChangedData],
    ) -> None:
        """Translate HA state changes into controller events."""

        controller_event = ControllerEvent.NORMAL_UPDATE

        if event.data["entity_id"] == TEST_BENCH_THERMOSTAT:
            old_state = event.data["old_state"]
            new_state = event.data["new_state"]

            old_mode = (
                old_state.state
                if old_state is not None
                else None
            )

            new_mode = (
                new_state.state
                if new_state is not None
                else None
            )

            # Attribute-only climate changes, including hvac_action changes,
            # must remain NORMAL_UPDATE. Only an actual state/mode change
            # becomes HVAC_MODE_CHANGE.
            if old_mode != new_mode:
                controller_event = ControllerEvent.HVAC_MODE_CHANGE

        self._recalculate(
            controller_event,
            dt_util.now(),
        )

    @callback
    def _async_adaptive_tick(
        self,
        now: datetime,
    ) -> None:
        """Run the five-minute Adaptive I trigger."""

        self.last_adaptive_tick = now

        self._recalculate(
            ControllerEvent.ADAPTIVE_TICK,
            now,
        )

    @callback
    def _async_timeline_heartbeat(
        self,
        now: datetime,
    ) -> None:
        """Refresh display clocks without running controller logic."""

        self.display_now = now

        for listener in tuple(self._timeline_listeners):
            listener()

    def _state_value(
        self,
        entity_id: str,
    ) -> str | None:
        """Return an HA entity state without coercing its value."""

        state = self.hass.states.get(entity_id)

        if state is None:
            return None

        return state.state

    @callback
    def _recalculate(
        self,
        event: ControllerEvent,
        now: datetime,
    ) -> None:
        """Calculate every virtual zone without commanding equipment."""

        self.display_now = now

        thermostat_state = self.hass.states.get(
            TEST_BENCH_THERMOSTAT
        )

        reference_state = self.hass.states.get(
            TEST_BENCH_REFERENCE
        )

        hvac_mode = (
            thermostat_state.state
            if thermostat_state is not None
            else None
        )

        hvac_action = (
            thermostat_state.attributes.get("hvac_action")
            if thermostat_state is not None
            else None
        )

        reference_temperature = (
            reference_state.state
            if reference_state is not None
            else None
        )

        room_states = {
            zone.key: self.hass.states.get(
                zone.temperature_entity_id
            )
            for zone in TEST_BENCH_ZONES
        }

        test_bench_ready = (
            thermostat_state is not None
            and reference_state is not None
            and all(
                state is not None
                for state in room_states.values()
            )
        )

        decisions: dict[str, ZoneDecision] = {}

        for zone in TEST_BENCH_ZONES:
            room_state = room_states[zone.key]

            room_temperature = (
                room_state.state
                if room_state is not None
                else None
            )

            decision = calculate_zone(
                ZoneInput(
                    room_temperature=room_temperature,
                    reference_temperature=reference_temperature,
                    hvac_mode=hvac_mode,
                    hvac_action=hvac_action,
                    event=event,
                ),
                self._zone_states[zone.key],
                now,
                settings=COOLING_EXPOSURE_SETTINGS,
            )

            decisions[zone.key] = decision
            self._zone_states[zone.key] = decision.next_state

        assist_required = central_assist_required(
            hvac_mode,
            decisions.values(),
        )

        self.snapshot = ObservationSnapshot(
            event=event,
            updated_at=now,
            hvac_mode=hvac_mode,
            hvac_action=hvac_action,
            test_bench_ready=test_bench_ready,
            decisions=decisions,
            central_assist_required=assist_required,
        )

        for listener in tuple(self._listeners):
            listener()

        for listener in tuple(self._timeline_listeners):
            listener()
