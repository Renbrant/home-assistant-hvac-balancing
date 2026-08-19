"""Runtime data structures for HVAC Balancing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .const import (
    DEFAULT_OBSERVATION_ONLY,
    RUNTIME_MODE_TEST_BENCH,
)
from .observation import HVACBalancingObservationRuntime

if TYPE_CHECKING:
    from .actuator import HVACBalancingActuator


@dataclass(slots=True)
class HVACBalancingRuntimeData:
    """Runtime state owned by one HVAC Balancing config entry."""

    observer: HVACBalancingObservationRuntime
    actuator: HVACBalancingActuator | None = None
    observation_only: bool = DEFAULT_OBSERVATION_ONLY
    runtime_mode: str = RUNTIME_MODE_TEST_BENCH
