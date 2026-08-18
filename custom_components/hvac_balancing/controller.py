"""Pure HVAC Balancing controller.

This module contains the v0.1.3 parity calculation engine.

It intentionally contains no platform imports, entity lookups, service calls,
or actuator code. Inputs are plain Python values and outputs are immutable
decision objects.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import math
from typing import Iterable


COOL_MODE = "cool"
COOLING_ACTION = "cooling"


class ControllerEvent(str, Enum):
    """Reason for evaluating a zone."""

    NORMAL_UPDATE = "normal_update"
    ADAPTIVE_TICK = "adaptive_tick"
    HVAC_MODE_CHANGE = "hvac_mode_change"
    STARTUP = "startup"


@dataclass(frozen=True)
class ControllerSettings:
    """v0.1.3 parity settings."""

    adaptive_interval_seconds: float = 1200.0
    adaptive_reset_error: float = 1.3
    adaptive_unwind_error: float = 1.5
    poor_improvement_threshold: float = 0.2
    good_improvement_threshold: float = 0.5
    max_speed: int = 10
    minimum_cooling_speed: int = 1
    central_assist_threshold: int = 8


DEFAULT_SETTINGS = ControllerSettings()


@dataclass(frozen=True)
class ZoneState:
    """Persistent controller state for one balancing zone."""

    base_target: int = 0
    adaptive_boost: int = 0
    reference_error: float | None = None
    last_evaluation: datetime | None = None


@dataclass(frozen=True)
class ZoneInput:
    """Current inputs for one balancing zone."""

    room_temperature: object
    reference_temperature: object
    hvac_mode: str | None
    hvac_action: str | None
    event: ControllerEvent = ControllerEvent.NORMAL_UPDATE


@dataclass(frozen=True)
class ZoneDecision:
    """Complete result of evaluating one balancing zone."""

    valid_temperatures: bool
    temperature_delta: float | None
    directional_error: float | None
    control_direction: str

    base_target: int
    adaptive_boost: int
    pi_target: int

    effective_speed: int
    effective_percentage: int

    reference_error: float | None
    last_evaluation: datetime | None

    balancing_active: bool
    reason: str

    @property
    def next_state(self) -> ZoneState:
        """Return persistent state for the next calculation."""

        return ZoneState(
            base_target=self.base_target,
            adaptive_boost=self.adaptive_boost,
            reference_error=self.reference_error,
            last_evaluation=self.last_evaluation,
        )


def _finite_float(value: object) -> float | None:
    """Convert an input to a finite float or return None."""

    if value is None or isinstance(value, bool):
        return None

    try:
        result = float(value)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(result):
        return None

    return result


def rising_target(error: float) -> int:
    """Return the v0.1.3 increasing-demand Base P target."""

    if error < 1.5:
        return 0

    if error < 2.0:
        return 2

    if error < 2.5:
        return 4

    if error < 3.0:
        return 6

    if error < 3.5:
        return 8

    return 10


def falling_target(error: float) -> int:
    """Return the v0.1.3 decreasing-demand hysteresis target."""

    if error <= 1.3:
        return 0

    if error <= 1.8:
        return 2

    if error <= 2.3:
        return 4

    if error <= 2.8:
        return 6

    if error <= 3.3:
        return 8

    return 10


def base_target_with_hysteresis(
    error: float,
    previous_target: int,
) -> int:
    """Apply the exact v0.1.3 Base P hysteresis selection rule."""

    rising = rising_target(error)
    falling = falling_target(error)

    if rising > previous_target:
        return rising

    if rising < previous_target:
        return falling

    return previous_target


def _elapsed_seconds(
    now: datetime,
    previous: datetime | None,
) -> float | None:
    """Return elapsed seconds or None when no previous timestamp exists."""

    if previous is None:
        return None

    try:
        elapsed = (now - previous).total_seconds()
    except TypeError:
        return 0.0

    return max(elapsed, 0.0)


def _evaluation_due(
    now: datetime,
    previous: datetime | None,
    settings: ControllerSettings,
) -> bool:
    """Return whether the adaptive observation window is due."""

    elapsed = _elapsed_seconds(now, previous)

    if elapsed is None:
        return False

    return elapsed >= settings.adaptive_interval_seconds


def _adaptive_boost(
    *,
    valid_temperatures: bool,
    hvac_mode: str | None,
    error: float | None,
    base_target: int,
    previous: ZoneState,
    event: ControllerEvent,
    now: datetime,
    settings: ControllerSettings,
) -> int:
    """Calculate the next v0.1.3 Adaptive I value."""

    if hvac_mode != COOL_MODE:
        return 0

    # The v0.1.3 Adaptive I sensor is trigger-based. Ordinary temperature
    # changes and hvac_action attribute changes do not execute its state
    # machine. Preserve the stored Adaptive I value until an adaptive event.
    if event == ControllerEvent.NORMAL_UPDATE:
        return max(previous.adaptive_boost, 0)

    if not valid_temperatures or error is None:
        return 0

    headroom = max(settings.max_speed - base_target, 0)
    current = min(previous.adaptive_boost, headroom)
    current = max(current, 0)

    if event == ControllerEvent.HVAC_MODE_CHANGE:
        return 0

    if base_target >= settings.max_speed:
        return 0

    if error <= settings.adaptive_reset_error:
        return 0

    due = _evaluation_due(
        now,
        previous.last_evaluation,
        settings,
    )

    if not due:
        return current

    if error < settings.adaptive_unwind_error:
        return max(current - 1, 0)

    if previous.reference_error is None:
        return current

    improvement = previous.reference_error - error

    if improvement < settings.poor_improvement_threshold:
        return min(current + 1, headroom)

    if improvement >= settings.good_improvement_threshold:
        return max(current - 1, 0)

    return current


def _updated_observation_history(
    *,
    valid_temperatures: bool,
    hvac_mode: str | None,
    error: float | None,
    previous: ZoneState,
    event: ControllerEvent,
    now: datetime,
    settings: ControllerSettings,
) -> tuple[float | None, datetime | None]:
    """Update reference_error and last_evaluation with v0.1.3 semantics."""

    if hvac_mode != COOL_MODE:
        return None, None

    # NORMAL_UPDATE does not trigger the v0.1.3 Adaptive I template.
    # Preserve both observation attributes exactly until an adaptive event.
    if event == ControllerEvent.NORMAL_UPDATE:
        return (
            previous.reference_error,
            previous.last_evaluation,
        )

    if not valid_temperatures or error is None:
        return None, None

    if error <= settings.adaptive_reset_error:
        return None, None

    if event == ControllerEvent.HVAC_MODE_CHANGE:
        return round(error, 2), now

    if previous.last_evaluation is None:
        return round(error, 2), now

    if _evaluation_due(
        now,
        previous.last_evaluation,
        settings,
    ):
        return round(error, 2), now

    return (
        previous.reference_error,
        previous.last_evaluation,
    )


def calculate_zone(
    zone_input: ZoneInput,
    previous: ZoneState,
    now: datetime,
    settings: ControllerSettings = DEFAULT_SETTINGS,
) -> ZoneDecision:
    """Evaluate one independent balancing zone."""

    room = _finite_float(zone_input.room_temperature)
    reference = _finite_float(zone_input.reference_temperature)

    valid_temperatures = room is not None and reference is not None

    raw_delta: float | None = None

    if valid_temperatures:
        assert room is not None
        assert reference is not None
        raw_delta = room - reference

    temperature_delta = (
        round(raw_delta, 1)
        if raw_delta is not None
        else None
    )

    supported_mode = zone_input.hvac_mode == COOL_MODE

    error: float | None = None

    if valid_temperatures and supported_mode:
        assert raw_delta is not None
        error = raw_delta

    control_direction = (
        "cooling"
        if supported_mode
        else "none"
    )

    base_target = 0

    if valid_temperatures and supported_mode:
        assert error is not None

        base_target = base_target_with_hysteresis(
            error,
            previous.base_target,
        )

    adaptive_boost = _adaptive_boost(
        valid_temperatures=valid_temperatures,
        hvac_mode=zone_input.hvac_mode,
        error=error,
        base_target=base_target,
        previous=previous,
        event=zone_input.event,
        now=now,
        settings=settings,
    )

    reference_error, last_evaluation = (
        _updated_observation_history(
            valid_temperatures=valid_temperatures,
            hvac_mode=zone_input.hvac_mode,
            error=error,
            previous=previous,
            event=zone_input.event,
            now=now,
            settings=settings,
        )
    )

    # Invalid temperature input is a deliberate v0.2 safety override.
    # Stored Adaptive I may remain intact until its next scheduled evaluation,
    # but no positive PI demand is exposed while input data is invalid.
    if valid_temperatures and supported_mode:
        pi_target = min(
            base_target + adaptive_boost,
            settings.max_speed,
        )
    else:
        pi_target = 0

    effective_speed = 0

    if valid_temperatures and supported_mode:
        effective_speed = pi_target

        if zone_input.hvac_action == COOLING_ACTION:
            effective_speed = max(
                pi_target,
                settings.minimum_cooling_speed,
            )

    effective_percentage = effective_speed * 10

    balancing_active = (
        valid_temperatures
        and supported_mode
        and pi_target > 0
    )

    reason = "balanced"

    if not valid_temperatures:
        reason = "invalid_temperature"

    if valid_temperatures and not supported_mode:
        reason = "unsupported_hvac_mode"

    if (
        valid_temperatures
        and supported_mode
        and pi_target > 0
    ):
        reason = "balancing"

    if (
        valid_temperatures
        and supported_mode
        and pi_target == 0
        and zone_input.hvac_action == COOLING_ACTION
    ):
        reason = "active_cooling_minimum"

    return ZoneDecision(
        valid_temperatures=valid_temperatures,
        temperature_delta=temperature_delta,
        directional_error=(
            round(error, 2)
            if error is not None
            else None
        ),
        control_direction=control_direction,
        base_target=base_target,
        adaptive_boost=adaptive_boost,
        pi_target=pi_target,
        effective_speed=effective_speed,
        effective_percentage=effective_percentage,
        reference_error=reference_error,
        last_evaluation=last_evaluation,
        balancing_active=balancing_active,
        reason=reason,
    )


def central_assist_required(
    hvac_mode: str | None,
    decisions: Iterable[ZoneDecision],
    settings: ControllerSettings = DEFAULT_SETTINGS,
) -> bool:
    """Return whether second-stage central blower assistance is required."""

    if hvac_mode != COOL_MODE:
        return False

    return any(
        decision.pi_target >= settings.central_assist_threshold
        for decision in decisions
    )
