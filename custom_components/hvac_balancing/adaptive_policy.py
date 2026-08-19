"""Adaptive cooling-exposure policy for HVAC Balancing v0.2.

This module contains no Home Assistant imports, entity access, service calls,
or actuator behavior.

It defines how much actual cooling exposure is required before Adaptive I may
make a decision and normalizes measured improvement to degrees F per 10 minutes
of effective cooling.

The policy is intentionally separate from controller.py until its behavior has
been independently validated.
"""

from __future__ import annotations

from enum import Enum


RESET_ERROR = 1.3
UNWIND_ERROR = 1.5

MILD_ERROR_LIMIT = 2.0
MEDIUM_ERROR_LIMIT = 3.0

MILD_EXPOSURE_SECONDS = 20 * 60
MEDIUM_EXPOSURE_SECONDS = 15 * 60
SEVERE_EXPOSURE_SECONDS = 10 * 60

POOR_IMPROVEMENT_RATE = 0.10
GOOD_IMPROVEMENT_RATE = 0.25

TEN_MINUTES_SECONDS = 10 * 60


class AdaptiveAction(str, Enum):
    """Adaptive I action selected after sufficient cooling exposure."""

    RESET = "reset"
    INCREASE = "increase"
    HOLD = "hold"
    DECREASE = "decrease"


def required_cooling_exposure_seconds(error: float) -> int:
    """Return required effective cooling exposure for the current error.

    <= 1.3 F:
        No observation window is required because Adaptive state resets.

    > 1.3 F and < 2.0 F:
        20 minutes of effective cooling.

    >= 2.0 F and < 3.0 F:
        15 minutes of effective cooling.

    >= 3.0 F:
        10 minutes of effective cooling.
    """

    if error <= RESET_ERROR:
        return 0

    if error < MILD_ERROR_LIMIT:
        return MILD_EXPOSURE_SECONDS

    if error < MEDIUM_ERROR_LIMIT:
        return MEDIUM_EXPOSURE_SECONDS

    return SEVERE_EXPOSURE_SECONDS


def cooling_exposure_progress(
    exposure_seconds: float,
    error: float,
) -> float:
    """Return observation progress from 0.0 through 1.0."""

    required = required_cooling_exposure_seconds(error)

    if required <= 0:
        return 1.0

    safe_exposure = max(float(exposure_seconds), 0.0)

    return min(
        safe_exposure / required,
        1.0,
    )


def improvement_rate_per_10m(
    reference_error: float,
    current_error: float,
    cooling_exposure_seconds: float,
) -> float | None:
    """Return error improvement normalized to F per 10 cooling minutes.

    Positive values mean the room/reference error improved.
    Zero means no improvement.
    Negative values mean the imbalance became worse.
    """

    exposure = float(cooling_exposure_seconds)

    if exposure <= 0:
        return None

    improvement = (
        float(reference_error)
        - float(current_error)
    )

    ten_minute_units = (
        exposure
        / TEN_MINUTES_SECONDS
    )

    return (
        improvement
        / ten_minute_units
    )


def select_adaptive_action(
    *,
    error: float,
    improvement_rate: float | None,
) -> AdaptiveAction:
    """Select the Adaptive I action after exposure eligibility is met."""

    if error <= RESET_ERROR:
        return AdaptiveAction.RESET

    if error < UNWIND_ERROR:
        return AdaptiveAction.DECREASE

    if improvement_rate is None:
        return AdaptiveAction.HOLD

    if improvement_rate < POOR_IMPROVEMENT_RATE:
        return AdaptiveAction.INCREASE

    if improvement_rate >= GOOD_IMPROVEMENT_RATE:
        return AdaptiveAction.DECREASE

    return AdaptiveAction.HOLD
