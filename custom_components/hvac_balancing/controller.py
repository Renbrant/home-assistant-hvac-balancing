"""Pure HVAC Balancing controller.

This module contains the validated v0.1.3 parity engine plus an
opt-in cooling-exposure Adaptive I strategy for v0.2 development.

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

try:
    from .adaptive_policy import (
        AdaptiveAction,
        cooling_exposure_progress as exposure_progress_for_error,
        improvement_rate_per_10m as normalized_improvement_rate,
        required_cooling_exposure_seconds as required_exposure_for_error,
        select_adaptive_action,
    )
except ImportError:
    # Direct-module unit tests add the integration directory to sys.path.
    from adaptive_policy import (
        AdaptiveAction,
        cooling_exposure_progress as exposure_progress_for_error,
        improvement_rate_per_10m as normalized_improvement_rate,
        required_cooling_exposure_seconds as required_exposure_for_error,
        select_adaptive_action,
    )


COOL_MODE = "cool"
COOLING_ACTION = "cooling"

ADAPTIVE_STRATEGY_LEGACY = "legacy_wall_clock"
ADAPTIVE_STRATEGY_COOLING_EXPOSURE = "cooling_exposure"


class ControllerEvent(str, Enum):
    """Reason for evaluating a zone."""

    NORMAL_UPDATE = "normal_update"
    ADAPTIVE_TICK = "adaptive_tick"
    HVAC_MODE_CHANGE = "hvac_mode_change"
    STARTUP = "startup"


@dataclass(frozen=True)
class ControllerSettings:
    """HVAC Balancing controller settings."""

    adaptive_strategy: str = ADAPTIVE_STRATEGY_LEGACY
    adaptive_interval_seconds: float = 1200.0
    adaptive_reset_error: float = 1.3
    adaptive_unwind_error: float = 1.5
    poor_improvement_threshold: float = 0.2
    good_improvement_threshold: float = 0.5
    max_speed: int = 10
    minimum_cooling_speed: int = 1
    central_assist_threshold: int = 8


DEFAULT_SETTINGS = ControllerSettings()

COOLING_EXPOSURE_SETTINGS = ControllerSettings(
    adaptive_strategy=ADAPTIVE_STRATEGY_COOLING_EXPOSURE,
)


@dataclass(frozen=True)
class ZoneState:
    """Persistent controller state for one balancing zone."""

    base_target: int = 0
    adaptive_boost: int = 0
    reference_error: float | None = None
    last_evaluation: datetime | None = None

    # Effective thermal opportunity accumulated for the new strategy.
    cooling_exposure_seconds: float = 0.0

    # Previous observation metadata is required to correctly attribute the
    # interval that elapsed before the current controller event.
    last_observed_at: datetime | None = None
    observed_hvac_mode: str | None = None
    observed_hvac_action: str | None = None
    observed_valid_temperatures: bool = False


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

    # Cooling-exposure strategy diagnostics.
    cooling_exposure_seconds: float = 0.0
    required_cooling_exposure_seconds: float = 0.0
    cooling_exposure_progress: float = 0.0
    improvement_rate_per_10m: float | None = None
    adaptive_action: str = "legacy_wall_clock"

    # Observation metadata persisted into ZoneState.
    last_observed_at: datetime | None = None
    observed_hvac_mode: str | None = None
    observed_hvac_action: str | None = None
    observed_valid_temperatures: bool = False

    @property
    def next_state(self) -> ZoneState:
        """Return persistent state for the next calculation."""

        return ZoneState(
            base_target=self.base_target,
            adaptive_boost=self.adaptive_boost,
            reference_error=self.reference_error,
            last_evaluation=self.last_evaluation,
            cooling_exposure_seconds=self.cooling_exposure_seconds,
            last_observed_at=self.last_observed_at,
            observed_hvac_mode=self.observed_hvac_mode,
            observed_hvac_action=self.observed_hvac_action,
            observed_valid_temperatures=self.observed_valid_temperatures,
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


@dataclass(frozen=True)
class _ExposureAdaptiveResult:
    """Internal result for the cooling-exposure Adaptive strategy."""

    adaptive_boost: int
    reference_error: float | None
    last_evaluation: datetime | None

    cooling_exposure_seconds: float
    required_cooling_exposure_seconds: float
    cooling_exposure_progress: float

    improvement_rate_per_10m: float | None
    adaptive_action: str


def _accumulated_cooling_exposure(
    *,
    now: datetime,
    previous: ZoneState,
) -> float:
    """Accumulate only intervals with valid active cooling evidence.

    The interval ending at ``now`` belongs to the PREVIOUS observation.

    This is critical for transitions such as:

        cooling -> idle -> cooling

    The cooling interval before the transition is counted, while the idle
    interval is preserved as elapsed wall-clock time but contributes zero
    thermal exposure.
    """

    stored = _finite_float(
        previous.cooling_exposure_seconds
    )

    exposure = max(
        stored if stored is not None else 0.0,
        0.0,
    )

    elapsed = _elapsed_seconds(
        now,
        previous.last_observed_at,
    )

    if elapsed is None:
        return exposure

    previous_interval_was_usable = (
        previous.observed_valid_temperatures
        and previous.observed_hvac_mode == COOL_MODE
        and previous.observed_hvac_action == COOLING_ACTION
    )

    if previous_interval_was_usable:
        exposure += elapsed

    return exposure


def _cooling_exposure_adaptive(
    *,
    valid_temperatures: bool,
    hvac_mode: str | None,
    error: float | None,
    base_target: int,
    previous: ZoneState,
    event: ControllerEvent,
    now: datetime,
    accumulated_exposure: float,
    settings: ControllerSettings,
) -> _ExposureAdaptiveResult:
    """Evaluate Adaptive I from actual effective cooling exposure."""

    exposure = max(
        accumulated_exposure,
        0.0,
    )

    if hvac_mode != COOL_MODE:
        return _ExposureAdaptiveResult(
            adaptive_boost=0,
            reference_error=None,
            last_evaluation=None,
            cooling_exposure_seconds=0.0,
            required_cooling_exposure_seconds=0.0,
            cooling_exposure_progress=0.0,
            improvement_rate_per_10m=None,
            adaptive_action="inactive",
        )

    # NORMAL_UPDATE still must not consume an Adaptive decision. It may,
    # however, account for elapsed cooling exposure because temporal evidence
    # is independent from the decision cadence.
    if not valid_temperatures or error is None:
        if event == ControllerEvent.NORMAL_UPDATE:
            return _ExposureAdaptiveResult(
                adaptive_boost=max(
                    previous.adaptive_boost,
                    0,
                ),
                reference_error=previous.reference_error,
                last_evaluation=previous.last_evaluation,
                cooling_exposure_seconds=exposure,
                required_cooling_exposure_seconds=0.0,
                cooling_exposure_progress=0.0,
                improvement_rate_per_10m=None,
                adaptive_action="invalid_input",
            )

        return _ExposureAdaptiveResult(
            adaptive_boost=0,
            reference_error=None,
            last_evaluation=None,
            cooling_exposure_seconds=0.0,
            required_cooling_exposure_seconds=0.0,
            cooling_exposure_progress=0.0,
            improvement_rate_per_10m=None,
            adaptive_action="invalid_reset",
        )

    required = float(
        required_exposure_for_error(error)
    )

    progress = exposure_progress_for_error(
        exposure,
        error,
    )

    projected_rate = None

    if (
        previous.reference_error is not None
        and exposure > 0
    ):
        projected_rate = normalized_improvement_rate(
            previous.reference_error,
            error,
            exposure,
        )

    if event == ControllerEvent.NORMAL_UPDATE:
        return _ExposureAdaptiveResult(
            adaptive_boost=max(
                previous.adaptive_boost,
                0,
            ),
            reference_error=previous.reference_error,
            last_evaluation=previous.last_evaluation,
            cooling_exposure_seconds=exposure,
            required_cooling_exposure_seconds=required,
            cooling_exposure_progress=progress,
            improvement_rate_per_10m=projected_rate,
            adaptive_action=(
                "observing"
                if previous.reference_error is not None
                else "awaiting_reference"
            ),
        )

    headroom = max(
        settings.max_speed - base_target,
        0,
    )

    current = min(
        max(previous.adaptive_boost, 0),
        headroom,
    )

    if error <= settings.adaptive_reset_error:
        return _ExposureAdaptiveResult(
            adaptive_boost=0,
            reference_error=None,
            last_evaluation=None,
            cooling_exposure_seconds=0.0,
            required_cooling_exposure_seconds=0.0,
            cooling_exposure_progress=1.0,
            improvement_rate_per_10m=None,
            adaptive_action=AdaptiveAction.RESET.value,
        )

    if event == ControllerEvent.HVAC_MODE_CHANGE:
        return _ExposureAdaptiveResult(
            adaptive_boost=0,
            reference_error=round(error, 2),
            last_evaluation=now,
            cooling_exposure_seconds=0.0,
            required_cooling_exposure_seconds=required,
            cooling_exposure_progress=0.0,
            improvement_rate_per_10m=None,
            adaptive_action="mode_change_reset",
        )

    # There is no Adaptive headroom while Base P already requests Speed 10.
    # Start fresh when headroom later becomes available.
    if base_target >= settings.max_speed:
        return _ExposureAdaptiveResult(
            adaptive_boost=0,
            reference_error=round(error, 2),
            last_evaluation=now,
            cooling_exposure_seconds=0.0,
            required_cooling_exposure_seconds=required,
            cooling_exposure_progress=0.0,
            improvement_rate_per_10m=None,
            adaptive_action="no_headroom",
        )

    if (
        previous.reference_error is None
        or previous.last_evaluation is None
    ):
        return _ExposureAdaptiveResult(
            adaptive_boost=current,
            reference_error=round(error, 2),
            last_evaluation=now,
            cooling_exposure_seconds=0.0,
            required_cooling_exposure_seconds=required,
            cooling_exposure_progress=0.0,
            improvement_rate_per_10m=None,
            adaptive_action="initialize",
        )

    if exposure < required:
        return _ExposureAdaptiveResult(
            adaptive_boost=current,
            reference_error=previous.reference_error,
            last_evaluation=previous.last_evaluation,
            cooling_exposure_seconds=exposure,
            required_cooling_exposure_seconds=required,
            cooling_exposure_progress=progress,
            improvement_rate_per_10m=projected_rate,
            adaptive_action="observing",
        )

    rate = normalized_improvement_rate(
        previous.reference_error,
        error,
        exposure,
    )

    action = select_adaptive_action(
        error=error,
        improvement_rate=rate,
    )

    updated = current

    if action == AdaptiveAction.RESET:
        updated = 0

    if action == AdaptiveAction.INCREASE:
        updated = min(
            current + 1,
            headroom,
        )

    if action == AdaptiveAction.DECREASE:
        updated = max(
            current - 1,
            0,
        )

    return _ExposureAdaptiveResult(
        adaptive_boost=updated,
        reference_error=round(error, 2),
        last_evaluation=now,
        cooling_exposure_seconds=0.0,
        required_cooling_exposure_seconds=required,
        cooling_exposure_progress=0.0,
        improvement_rate_per_10m=rate,
        adaptive_action=action.value,
    )


def _legacy_adaptive_boost(
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


def _legacy_updated_observation_history(
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

    accumulated_exposure = _accumulated_cooling_exposure(
        now=now,
        previous=previous,
    )

    cooling_exposure_seconds = accumulated_exposure
    required_cooling_exposure_seconds = 0.0
    cooling_exposure_progress = 0.0
    improvement_rate_per_10m = None
    adaptive_action = ADAPTIVE_STRATEGY_LEGACY

    if (
        settings.adaptive_strategy
        == ADAPTIVE_STRATEGY_COOLING_EXPOSURE
    ):
        exposure_result = _cooling_exposure_adaptive(
            valid_temperatures=valid_temperatures,
            hvac_mode=zone_input.hvac_mode,
            error=error,
            base_target=base_target,
            previous=previous,
            event=zone_input.event,
            now=now,
            accumulated_exposure=accumulated_exposure,
            settings=settings,
        )

        adaptive_boost = exposure_result.adaptive_boost
        reference_error = exposure_result.reference_error
        last_evaluation = exposure_result.last_evaluation

        cooling_exposure_seconds = (
            exposure_result.cooling_exposure_seconds
        )

        required_cooling_exposure_seconds = (
            exposure_result.required_cooling_exposure_seconds
        )

        cooling_exposure_progress = (
            exposure_result.cooling_exposure_progress
        )

        improvement_rate_per_10m = (
            exposure_result.improvement_rate_per_10m
        )

        adaptive_action = exposure_result.adaptive_action

    if (
        settings.adaptive_strategy
        == ADAPTIVE_STRATEGY_LEGACY
    ):
        adaptive_boost = _legacy_adaptive_boost(
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
            _legacy_updated_observation_history(
                valid_temperatures=valid_temperatures,
                hvac_mode=zone_input.hvac_mode,
                error=error,
                previous=previous,
                event=zone_input.event,
                now=now,
                settings=settings,
            )
        )

    if settings.adaptive_strategy not in (
        ADAPTIVE_STRATEGY_LEGACY,
        ADAPTIVE_STRATEGY_COOLING_EXPOSURE,
    ):
        raise ValueError(
            "Unsupported adaptive strategy: "
            f"{settings.adaptive_strategy}"
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
        cooling_exposure_seconds=round(
            cooling_exposure_seconds,
            3,
        ),
        required_cooling_exposure_seconds=(
            required_cooling_exposure_seconds
        ),
        cooling_exposure_progress=round(
            cooling_exposure_progress,
            4,
        ),
        improvement_rate_per_10m=(
            round(improvement_rate_per_10m, 4)
            if improvement_rate_per_10m is not None
            else None
        ),
        adaptive_action=adaptive_action,
        last_observed_at=now,
        observed_hvac_mode=zone_input.hvac_mode,
        observed_hvac_action=zone_input.hvac_action,
        observed_valid_temperatures=valid_temperatures,
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
