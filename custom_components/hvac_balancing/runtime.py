"""Runtime data structures for HVAC Balancing."""

from __future__ import annotations

from dataclasses import dataclass

from .const import DEFAULT_OBSERVATION_ONLY
from .observation import HVACBalancingObservationRuntime


@dataclass(slots=True)
class HVACBalancingRuntimeData:
    """Runtime state owned by one HVAC Balancing config entry."""

    observer: HVACBalancingObservationRuntime
    observation_only: bool = DEFAULT_OBSERVATION_ONLY
