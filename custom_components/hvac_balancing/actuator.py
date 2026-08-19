"""Physical actuator adapter for HVAC Balancing."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from contextlib import suppress
import logging
import time

from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.components.climate.const import (
    ATTR_FAN_MODE,
    FAN_OFF,
    SERVICE_SET_FAN_MODE,
)
from homeassistant.components.fan import (
    ATTR_PERCENTAGE,
    ATTR_PRESET_MODE,
    DOMAIN as FAN_DOMAIN,
    SERVICE_SET_PERCENTAGE,
    SERVICE_SET_PRESET_MODE,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError

from .configuration import CentralAssistConfig
from .const import (
    CENTRAL_ASSIST_MODE_CLIMATE,
    CENTRAL_ASSIST_MODE_DISABLED,
    CENTRAL_ASSIST_MODE_FAN,
    CENTRAL_ASSIST_MODE_NEST,
)
from .observation import (
    HVACBalancingObservationRuntime,
    ObservationZoneConfig,
)


_LOGGER = logging.getLogger(__name__)

BOOSTER_PRESET = "FAN"

NEST_DOMAIN = "nest"
NEST_SERVICE_SET_FAN_TIMER = "set_fan_timer"

CENTRAL_ASSIST_TIMER_HOURS = 12
CENTRAL_ASSIST_OFF_DELAY_SECONDS = 5 * 60
CENTRAL_ASSIST_REFRESH_SECONDS = 60 * 60


class HVACBalancingActuator:
    """Apply calculated controller decisions to physical HVAC equipment."""

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        observer: HVACBalancingObservationRuntime,
        thermostat_entity_id: str,
        central_assist: CentralAssistConfig,
        zones: tuple[ObservationZoneConfig, ...],
    ) -> None:
        """Initialize active actuator runtime."""

        self.hass = hass
        self._observer = observer
        self._thermostat_entity_id = thermostat_entity_id
        self._central_assist = central_assist
        self._zones = tuple(zones)

        if any(
            zone.fan_entity_id is None
            for zone in self._zones
        ):
            raise ValueError(
                "Production zones require fan_entity_id"
            )

        self._unsubscribe: Callable[[], None] | None = None
        self._apply_task: asyncio.Task[None] | None = None
        self._apply_pending = False

        self._assist_off_task: asyncio.Task[None] | None = None
        self._assist_requested = False
        self._assist_last_refresh_monotonic: float | None = None

        # Cache commands we successfully sent instead of trusting potentially
        # stale Xtend/Tuya feedback as the sole source of truth.
        self._last_commanded_speeds: dict[str, int | None] = {
            zone.key: None
            for zone in self._zones
        }

    @callback
    def async_start(self) -> None:
        """Subscribe to calculated controller snapshots."""

        if self._unsubscribe is not None:
            return

        self._unsubscribe = self._observer.async_add_listener(
            self._handle_controller_update
        )

    @callback
    def async_stop(self) -> None:
        """Stop listeners and pending asynchronous work."""

        if self._unsubscribe is not None:
            self._unsubscribe()
            self._unsubscribe = None

        self._apply_pending = False

        if (
            self._apply_task is not None
            and not self._apply_task.done()
        ):
            self._apply_task.cancel()

        if (
            self._assist_off_task is not None
            and not self._assist_off_task.done()
        ):
            self._assist_off_task.cancel()

    @callback
    def _handle_controller_update(self) -> None:
        """Queue the newest snapshot without cancelling physical commands."""

        if (
            self._apply_task is not None
            and not self._apply_task.done()
        ):
            self._apply_pending = True
            return

        self._apply_task = self.hass.async_create_task(
            self._async_apply_loop()
        )

    async def _async_apply_loop(self) -> None:
        """Apply snapshots serially and coalesce intermediate updates."""

        while True:
            self._apply_pending = False

            await self._async_apply_snapshot()

            if not self._apply_pending:
                return

    async def _async_apply_snapshot(self) -> None:
        """Apply current effective speeds and central-assist request."""

        snapshot = self._observer.snapshot

        if snapshot is None:
            return

        force_reconcile = (
            snapshot.event.value == "startup"
            or self._observer.last_watchdog
            == snapshot.updated_at
        )

        for zone in self._zones:
            decision = snapshot.decisions.get(
                zone.key
            )

            desired_speed = 0

            if (
                decision is not None
                and decision.valid_temperatures
            ):
                desired_speed = int(
                    decision.effective_speed
                )

            await self._async_apply_zone_speed(
                zone,
                desired_speed,
                force=force_reconcile,
            )

        await self._async_apply_central_assist(
            snapshot.central_assist_required
        )

    async def _async_apply_zone_speed(
        self,
        zone: ObservationZoneConfig,
        desired_speed: int,
        *,
        force: bool,
    ) -> None:
        """Apply one 0-10 controller speed to one booster."""

        fan_entity_id = zone.fan_entity_id

        if fan_entity_id is None:
            return

        desired_speed = min(
            max(int(desired_speed), 0),
            10,
        )

        state = self.hass.states.get(
            fan_entity_id
        )

        last_commanded = self._last_commanded_speeds.get(
            zone.key
        )

        if desired_speed == 0:
            state_matches = (
                state is not None
                and state.state == STATE_OFF
            )

            if (
                not force
                and last_commanded == 0
                and state_matches
            ):
                return

            success = await self._async_service_call(
                FAN_DOMAIN,
                SERVICE_TURN_OFF,
                {
                    ATTR_ENTITY_ID: fan_entity_id,
                },
            )

            if success:
                self._last_commanded_speeds[
                    zone.key
                ] = 0

            return

        desired_percentage = desired_speed * 10

        current_preset = (
            state.attributes.get(
                ATTR_PRESET_MODE
            )
            if state is not None
            else None
        )

        current_percentage = (
            state.attributes.get(
                ATTR_PERCENTAGE
            )
            if state is not None
            else None
        )

        state_matches = (
            state is not None
            and state.state == STATE_ON
            and current_preset == BOOSTER_PRESET
            and current_percentage == desired_percentage
        )

        if (
            not force
            and last_commanded == desired_speed
            and state_matches
        ):
            return

        # Preserve the proven native Xtend/Tuya command sequence.
        success = await self._async_service_call(
            FAN_DOMAIN,
            SERVICE_SET_PRESET_MODE,
            {
                ATTR_ENTITY_ID: fan_entity_id,
                ATTR_PRESET_MODE: BOOSTER_PRESET,
            },
        )

        if not success:
            return

        await asyncio.sleep(1)

        success = await self._async_service_call(
            FAN_DOMAIN,
            SERVICE_SET_PERCENTAGE,
            {
                ATTR_ENTITY_ID: fan_entity_id,
                ATTR_PERCENTAGE: desired_percentage,
            },
        )

        if not success:
            return

        await asyncio.sleep(1)

        success = await self._async_service_call(
            FAN_DOMAIN,
            SERVICE_TURN_ON,
            {
                ATTR_ENTITY_ID: fan_entity_id,
            },
        )

        if success:
            self._last_commanded_speeds[
                zone.key
            ] = desired_speed

    async def _async_apply_central_assist(
        self,
        required: bool,
    ) -> None:
        """Apply Central Assist using the configured installation adapter."""

        mode = self._central_assist.mode

        if mode == CENTRAL_ASSIST_MODE_DISABLED:
            self._cancel_assist_off()
            return

        if required:
            self._cancel_assist_off()

            if mode == CENTRAL_ASSIST_MODE_NEST:
                now_monotonic = time.monotonic()

                refresh_due = (
                    not self._assist_requested
                    or self._assist_last_refresh_monotonic is None
                    or (
                        now_monotonic
                        - self._assist_last_refresh_monotonic
                    )
                    >= CENTRAL_ASSIST_REFRESH_SECONDS
                )

                if not refresh_due:
                    return

                success = await self._async_request_central_assist()

                if success:
                    self._assist_requested = True
                    self._assist_last_refresh_monotonic = (
                        now_monotonic
                    )

                return

            # Reconcile against the actual Home Assistant state rather than
            # trusting the in-memory ownership flag as proof that airflow is
            # still active. If the state already matches but HVAC Balancing
            # did not start it, leave it unowned so we never turn off another
            # automation's or a manual Central Assist request.
            if self._central_assist_state_matches():
                return

            success = await self._async_request_central_assist()

            if success:
                self._assist_requested = True
                self._assist_last_refresh_monotonic = None

            return

        # Never turn off Central Assist that HVAC Balancing did not start.
        if not self._assist_requested:
            self._cancel_assist_off()
            return

        if (
            self._assist_off_task is None
            or self._assist_off_task.done()
        ):
            self._assist_off_task = self.hass.async_create_task(
                self._async_delayed_assist_off()
            )

    def _central_assist_state_matches(self) -> bool:
        """Return whether the configured Central Assist is actually active."""

        mode = self._central_assist.mode

        if mode == CENTRAL_ASSIST_MODE_FAN:
            fan_entity_id = self._central_assist.fan_entity_id

            if fan_entity_id is None:
                return False

            state = self.hass.states.get(
                fan_entity_id
            )

            return (
                state is not None
                and state.state == STATE_ON
            )

        if mode == CENTRAL_ASSIST_MODE_CLIMATE:
            fan_mode_on = self._central_assist.fan_mode_on

            if fan_mode_on is None:
                return False

            state = self.hass.states.get(
                self._thermostat_entity_id
            )

            if state is None:
                return False

            return (
                state.attributes.get(
                    ATTR_FAN_MODE
                )
                == fan_mode_on
            )

        return False

    async def _async_request_central_assist(self) -> bool:
        """Start Central Assist through the selected adapter."""

        mode = self._central_assist.mode

        if mode == CENTRAL_ASSIST_MODE_FAN:
            fan_entity_id = self._central_assist.fan_entity_id

            if fan_entity_id is None:
                return False

            return await self._async_service_call(
                FAN_DOMAIN,
                SERVICE_TURN_ON,
                {
                    ATTR_ENTITY_ID: fan_entity_id,
                },
            )

        if mode == CENTRAL_ASSIST_MODE_CLIMATE:
            fan_mode_on = self._central_assist.fan_mode_on

            if fan_mode_on is None:
                return False

            return await self._async_service_call(
                CLIMATE_DOMAIN,
                SERVICE_SET_FAN_MODE,
                {
                    ATTR_ENTITY_ID: self._thermostat_entity_id,
                    ATTR_FAN_MODE: fan_mode_on,
                },
            )

        if mode == CENTRAL_ASSIST_MODE_NEST:
            return await self._async_service_call(
                NEST_DOMAIN,
                NEST_SERVICE_SET_FAN_TIMER,
                {
                    ATTR_ENTITY_ID: self._thermostat_entity_id,
                    "duration": {
                        "hours": CENTRAL_ASSIST_TIMER_HOURS,
                    },
                },
            )

        return False

    async def _async_release_owned_central_assist(self) -> bool:
        """Stop only Central Assist previously started by this actuator."""

        mode = self._central_assist.mode

        if mode == CENTRAL_ASSIST_MODE_FAN:
            fan_entity_id = self._central_assist.fan_entity_id

            if fan_entity_id is None:
                return False

            return await self._async_service_call(
                FAN_DOMAIN,
                SERVICE_TURN_OFF,
                {
                    ATTR_ENTITY_ID: fan_entity_id,
                },
            )

        if mode == CENTRAL_ASSIST_MODE_CLIMATE:
            fan_mode_off = self._central_assist.fan_mode_off

            if fan_mode_off is None:
                return False

            return await self._async_service_call(
                CLIMATE_DOMAIN,
                SERVICE_SET_FAN_MODE,
                {
                    ATTR_ENTITY_ID: self._thermostat_entity_id,
                    ATTR_FAN_MODE: fan_mode_off,
                },
            )

        if mode == CENTRAL_ASSIST_MODE_NEST:
            return await self._async_service_call(
                CLIMATE_DOMAIN,
                SERVICE_SET_FAN_MODE,
                {
                    ATTR_ENTITY_ID: self._thermostat_entity_id,
                    ATTR_FAN_MODE: FAN_OFF,
                },
            )

        return False

    @callback
    def _cancel_assist_off(self) -> None:
        """Cancel a pending Central Assist shutdown."""

        if (
            self._assist_off_task is not None
            and not self._assist_off_task.done()
        ):
            self._assist_off_task.cancel()

        self._assist_off_task = None

    async def _async_delayed_assist_off(self) -> None:
        """Turn owned Central Assist off after the five-minute grace."""

        current_task = asyncio.current_task()

        try:
            await asyncio.sleep(
                CENTRAL_ASSIST_OFF_DELAY_SECONDS
            )

            success = await self._async_release_owned_central_assist()

            if success:
                self._assist_requested = False
                self._assist_last_refresh_monotonic = None

        except asyncio.CancelledError:
            raise

        finally:
            if self._assist_off_task is current_task:
                self._assist_off_task = None

    async def _async_service_call(
        self,
        domain: str,
        service: str,
        data: dict[str, object],
    ) -> bool:
        """Execute one HA service call and log failures."""

        try:
            await self.hass.services.async_call(
                domain,
                service,
                data,
                blocking=True,
            )

        except HomeAssistantError as err:
            _LOGGER.error(
                "HVAC Balancing actuator service failed: %s.%s: %s",
                domain,
                service,
                err,
            )

            return False

        return True

    async def async_shutdown(self) -> None:
        """Fail safe on integration unload: stop all controlled outputs."""

        self.async_stop()

        tasks = (
            self._apply_task,
            self._assist_off_task,
        )

        for task in tasks:
            if task is None:
                continue

            with suppress(
                asyncio.CancelledError
            ):
                await task

        for zone in self._zones:
            if zone.fan_entity_id is None:
                continue

            await self._async_service_call(
                FAN_DOMAIN,
                SERVICE_TURN_OFF,
                {
                    ATTR_ENTITY_ID: zone.fan_entity_id,
                },
            )

        if self._assist_requested:
            success = await self._async_release_owned_central_assist()

            if success:
                self._assist_requested = False
                self._assist_last_refresh_monotonic = None
