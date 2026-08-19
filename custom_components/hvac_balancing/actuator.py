"""Physical actuator adapter for HVAC Balancing."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from contextlib import suppress
import logging

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


class HVACBalancingActuator:
    """Apply calculated controller decisions to physical HVAC equipment."""

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        observer: HVACBalancingObservationRuntime,
        thermostat_entity_id: str,
        zones: tuple[ObservationZoneConfig, ...],
    ) -> None:
        """Initialize active actuator runtime."""

        self.hass = hass
        self._observer = observer
        self._thermostat_entity_id = thermostat_entity_id
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
        self._assist_off_task: asyncio.Task[None] | None = None

        self._assist_requested = False

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
        """Apply only the newest controller snapshot."""

        if (
            self._apply_task is not None
            and not self._apply_task.done()
        ):
            self._apply_task.cancel()

        self._apply_task = self.hass.async_create_task(
            self._async_apply_snapshot()
        )

    async def _async_apply_snapshot(self) -> None:
        """Apply current effective speeds and central-assist request."""

        snapshot = self._observer.snapshot

        if snapshot is None:
            return

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
            )

        await self._async_apply_central_assist(
            snapshot.central_assist_required
        )

    async def _async_apply_zone_speed(
        self,
        zone: ObservationZoneConfig,
        desired_speed: int,
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

        if desired_speed == 0:
            if (
                state is None
                or state.state != STATE_OFF
            ):
                await self._async_service_call(
                    FAN_DOMAIN,
                    SERVICE_TURN_OFF,
                    {
                        ATTR_ENTITY_ID: fan_entity_id,
                    },
                )

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

        if current_preset != BOOSTER_PRESET:
            await self._async_service_call(
                FAN_DOMAIN,
                SERVICE_SET_PRESET_MODE,
                {
                    ATTR_ENTITY_ID: fan_entity_id,
                    ATTR_PRESET_MODE: BOOSTER_PRESET,
                },
            )

            await asyncio.sleep(1)

        if current_percentage != desired_percentage:
            await self._async_service_call(
                FAN_DOMAIN,
                SERVICE_SET_PERCENTAGE,
                {
                    ATTR_ENTITY_ID: fan_entity_id,
                    ATTR_PERCENTAGE: desired_percentage,
                },
            )

            await asyncio.sleep(1)

        if (
            state is None
            or state.state != STATE_ON
        ):
            await self._async_service_call(
                FAN_DOMAIN,
                SERVICE_TURN_ON,
                {
                    ATTR_ENTITY_ID: fan_entity_id,
                },
            )

    async def _async_apply_central_assist(
        self,
        required: bool,
    ) -> None:
        """Apply the second-stage central circulation request."""

        if required:
            self._cancel_assist_off()

            if not self._assist_requested:
                success = await self._async_service_call(
                    NEST_DOMAIN,
                    NEST_SERVICE_SET_FAN_TIMER,
                    {
                        ATTR_ENTITY_ID: self._thermostat_entity_id,
                        "duration": {
                            "hours": CENTRAL_ASSIST_TIMER_HOURS,
                        },
                    },
                )

                if success:
                    self._assist_requested = True

            return

        if (
            self._assist_off_task is None
            or self._assist_off_task.done()
        ):
            self._assist_off_task = self.hass.async_create_task(
                self._async_delayed_assist_off()
            )

    @callback
    def _cancel_assist_off(self) -> None:
        """Cancel a pending central-assist shutdown."""

        if (
            self._assist_off_task is not None
            and not self._assist_off_task.done()
        ):
            self._assist_off_task.cancel()

        self._assist_off_task = None

    async def _async_delayed_assist_off(self) -> None:
        """Turn Nest circulation off after the legacy five-minute grace."""

        try:
            await asyncio.sleep(
                CENTRAL_ASSIST_OFF_DELAY_SECONDS
            )

            await self._async_service_call(
                CLIMATE_DOMAIN,
                SERVICE_SET_FAN_MODE,
                {
                    ATTR_ENTITY_ID: self._thermostat_entity_id,
                    ATTR_FAN_MODE: FAN_OFF,
                },
            )

            self._assist_requested = False

        except asyncio.CancelledError:
            raise

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

        await self._async_service_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_FAN_MODE,
            {
                ATTR_ENTITY_ID: self._thermostat_entity_id,
                ATTR_FAN_MODE: FAN_OFF,
            },
        )
