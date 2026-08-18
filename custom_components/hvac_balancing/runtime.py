"""Runtime data structures for HVAC Balancing."""

from __future__ import annotations

from dataclasses import dataclass

from .const import DEFAULT_OBSERVATION_ONLY


@dataclass(slots=True)
class HVACBalancingRuntimeData:
    """Runtime state owned by one HVAC Balancing config entry.

    Phase 1 deliberately contains no actuator/controller objects.
    The integration therefore cannot command boosters or the central
    HVAC blower at this stage.
    """

    observation_only: bool = DEFAULT_OBSERVATION_ONLY
