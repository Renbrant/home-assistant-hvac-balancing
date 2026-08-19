"""Controller tests for effective cooling exposure."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
CORE_DIR = ROOT / "custom_components" / "hvac_balancing"

sys.path.insert(0, str(CORE_DIR))

from controller import (  # noqa: E402
    COOLING_EXPOSURE_SETTINGS,
    ControllerEvent,
    ControllerSettings,
    ZoneDecision,
    ZoneInput,
    ZoneState,
    calculate_zone,
)


T0 = datetime(
    2026,
    8,
    19,
    0,
    0,
    0,
    tzinfo=timezone.utc,
)


def exposure_zone(
    *,
    room: object = 78.0,
    reference: object = 75.0,
    mode: str | None = "cool",
    action: str | None = "cooling",
    event: ControllerEvent = ControllerEvent.NORMAL_UPDATE,
    previous: ZoneState | None = None,
    now: datetime = T0,
) -> ZoneDecision:
    """Evaluate one zone using the new strategy."""

    if previous is None:
        previous = ZoneState()

    return calculate_zone(
        ZoneInput(
            room_temperature=room,
            reference_temperature=reference,
            hvac_mode=mode,
            hvac_action=action,
            event=event,
        ),
        previous,
        now,
        settings=COOLING_EXPOSURE_SETTINGS,
    )


class ExposureInitializationTests(unittest.TestCase):
    """Verify observation initialization."""

    def test_startup_initializes_reference_without_exposure(self) -> None:
        decision = exposure_zone(
            event=ControllerEvent.STARTUP,
        )

        self.assertEqual(
            decision.reference_error,
            3.0,
        )

        self.assertEqual(
            decision.cooling_exposure_seconds,
            0.0,
        )

        self.assertEqual(
            decision.required_cooling_exposure_seconds,
            600.0,
        )

        self.assertEqual(
            decision.adaptive_action,
            "initialize",
        )

    def test_first_five_cooling_minutes_accumulate(self) -> None:
        start = exposure_zone(
            event=ControllerEvent.STARTUP,
        )

        decision = exposure_zone(
            event=ControllerEvent.NORMAL_UPDATE,
            previous=start.next_state,
            now=T0 + timedelta(minutes=5),
        )

        self.assertEqual(
            decision.cooling_exposure_seconds,
            300.0,
        )

        self.assertEqual(
            decision.adaptive_boost,
            0,
        )

        self.assertEqual(
            decision.cooling_exposure_progress,
            0.5,
        )

        self.assertEqual(
            decision.adaptive_action,
            "observing",
        )


class SevereExposureTests(unittest.TestCase):
    """Verify severe imbalance responds after 10 cooling minutes."""

    def test_severe_error_increases_after_ten_cooling_minutes(self) -> None:
        start = exposure_zone(
            event=ControllerEvent.STARTUP,
        )

        five = exposure_zone(
            event=ControllerEvent.ADAPTIVE_DUE,
            previous=start.next_state,
            now=T0 + timedelta(minutes=5),
        )

        ten = exposure_zone(
            event=ControllerEvent.ADAPTIVE_DUE,
            previous=five.next_state,
            now=T0 + timedelta(minutes=10),
        )

        self.assertEqual(
            ten.adaptive_boost,
            1,
        )

        self.assertEqual(
            ten.pi_target,
            9,
        )

        self.assertEqual(
            ten.adaptive_action,
            "increase",
        )

        self.assertEqual(
            ten.improvement_rate_per_10m,
            0.0,
        )

        self.assertEqual(
            ten.cooling_exposure_seconds,
            0.0,
        )


class IdlePauseTests(unittest.TestCase):
    """Verify idle wall time does not consume cooling exposure."""

    def test_cooling_idle_cooling_counts_only_cooling_time(self) -> None:
        start = exposure_zone(
            event=ControllerEvent.STARTUP,
        )

        idle = exposure_zone(
            action="idle",
            event=ControllerEvent.NORMAL_UPDATE,
            previous=start.next_state,
            now=T0 + timedelta(minutes=5),
        )

        self.assertEqual(
            idle.cooling_exposure_seconds,
            300.0,
        )

        resumed = exposure_zone(
            action="cooling",
            event=ControllerEvent.NORMAL_UPDATE,
            previous=idle.next_state,
            now=T0 + timedelta(minutes=15),
        )

        # Ten idle minutes contribute zero.
        self.assertEqual(
            resumed.cooling_exposure_seconds,
            300.0,
        )

        due = exposure_zone(
            action="cooling",
            event=ControllerEvent.ADAPTIVE_DUE,
            previous=resumed.next_state,
            now=T0 + timedelta(minutes=20),
        )

        # 20 wall minutes, but exactly 10 useful cooling minutes.
        self.assertEqual(
            due.adaptive_boost,
            1,
        )

        self.assertEqual(
            due.adaptive_action,
            "increase",
        )

    def test_cooling_idle_cooling_preserves_reference(self) -> None:
        start = exposure_zone(
            event=ControllerEvent.STARTUP,
        )

        idle = exposure_zone(
            action="idle",
            previous=start.next_state,
            now=T0 + timedelta(minutes=5),
        )

        resumed = exposure_zone(
            action="cooling",
            previous=idle.next_state,
            now=T0 + timedelta(minutes=15),
        )

        self.assertEqual(
            resumed.reference_error,
            3.0,
        )

        self.assertEqual(
            resumed.last_evaluation,
            T0,
        )


class InvalidDataExposureTests(unittest.TestCase):
    """Verify unavailable temperature time is not counted as evidence."""

    def test_invalid_sensor_interval_pauses_exposure(self) -> None:
        start = exposure_zone(
            event=ControllerEvent.STARTUP,
        )

        failed = exposure_zone(
            room="unavailable",
            event=ControllerEvent.NORMAL_UPDATE,
            previous=start.next_state,
            now=T0 + timedelta(minutes=5),
        )

        self.assertEqual(
            failed.cooling_exposure_seconds,
            300.0,
        )

        recovered = exposure_zone(
            event=ControllerEvent.NORMAL_UPDATE,
            previous=failed.next_state,
            now=T0 + timedelta(minutes=15),
        )

        # The ten-minute unavailable interval contributes zero.
        self.assertEqual(
            recovered.cooling_exposure_seconds,
            300.0,
        )

        due = exposure_zone(
            event=ControllerEvent.ADAPTIVE_DUE,
            previous=recovered.next_state,
            now=T0 + timedelta(minutes=20),
        )

        self.assertEqual(
            due.adaptive_boost,
            1,
        )


class VariableExposureWindowTests(unittest.TestCase):
    """Verify exposure requirement changes with severity."""

    def test_medium_error_requires_fifteen_cooling_minutes(self) -> None:
        start = exposure_zone(
            room=77.5,
            event=ControllerEvent.STARTUP,
        )

        ten = exposure_zone(
            room=77.5,
            event=ControllerEvent.ADAPTIVE_DUE,
            previous=start.next_state,
            now=T0 + timedelta(minutes=10),
        )

        self.assertEqual(
            ten.required_cooling_exposure_seconds,
            900.0,
        )

        self.assertEqual(
            ten.cooling_exposure_seconds,
            600.0,
        )

        self.assertEqual(
            ten.adaptive_boost,
            0,
        )

        fifteen = exposure_zone(
            room=77.5,
            event=ControllerEvent.ADAPTIVE_DUE,
            previous=ten.next_state,
            now=T0 + timedelta(minutes=15),
        )

        self.assertEqual(
            fifteen.adaptive_boost,
            1,
        )

    def test_mild_error_requires_twenty_cooling_minutes(self) -> None:
        start = exposure_zone(
            room=76.6,
            event=ControllerEvent.STARTUP,
        )

        fifteen = exposure_zone(
            room=76.6,
            event=ControllerEvent.ADAPTIVE_DUE,
            previous=start.next_state,
            now=T0 + timedelta(minutes=15),
        )

        self.assertEqual(
            fifteen.required_cooling_exposure_seconds,
            1200.0,
        )

        self.assertEqual(
            fifteen.adaptive_boost,
            0,
        )

        twenty = exposure_zone(
            room=76.6,
            event=ControllerEvent.ADAPTIVE_DUE,
            previous=fifteen.next_state,
            now=T0 + timedelta(minutes=20),
        )

        self.assertEqual(
            twenty.adaptive_boost,
            1,
        )


class NormalizedTrendTests(unittest.TestCase):
    """Verify Adaptive decisions use normalized improvement rate."""

    def test_good_improvement_decreases_one(self) -> None:
        previous = ZoneState(
            base_target=8,
            adaptive_boost=2,
            reference_error=3.30,
            last_evaluation=T0,
            cooling_exposure_seconds=300.0,
            last_observed_at=T0 + timedelta(minutes=5),
            observed_hvac_mode="cool",
            observed_hvac_action="cooling",
            observed_valid_temperatures=True,
        )

        decision = exposure_zone(
            room=78.05,
            previous=previous,
            event=ControllerEvent.ADAPTIVE_DUE,
            now=T0 + timedelta(minutes=10),
        )

        self.assertEqual(
            decision.improvement_rate_per_10m,
            0.25,
        )

        self.assertEqual(
            decision.adaptive_action,
            "decrease",
        )

        self.assertEqual(
            decision.adaptive_boost,
            1,
        )

    def test_worsening_error_increases_one(self) -> None:
        previous = ZoneState(
            base_target=8,
            adaptive_boost=0,
            reference_error=3.00,
            last_evaluation=T0,
            cooling_exposure_seconds=300.0,
            last_observed_at=T0 + timedelta(minutes=5),
            observed_hvac_mode="cool",
            observed_hvac_action="cooling",
            observed_valid_temperatures=True,
        )

        decision = exposure_zone(
            room=78.10,
            previous=previous,
            event=ControllerEvent.ADAPTIVE_DUE,
            now=T0 + timedelta(minutes=10),
        )

        self.assertEqual(
            decision.improvement_rate_per_10m,
            -0.1,
        )

        self.assertEqual(
            decision.adaptive_action,
            "increase",
        )

        self.assertEqual(
            decision.adaptive_boost,
            1,
        )


class ExposureAntiWindupTests(unittest.TestCase):
    """Verify immediate Adaptive anti-windup."""

    def test_normal_update_at_base_ten_resets_adaptive_episode(self) -> None:
        previous = ZoneState(
            base_target=6,
            adaptive_boost=2,
            reference_error=2.60,
            last_evaluation=T0,
            cooling_exposure_seconds=300.0,
            last_observed_at=T0,
            observed_hvac_mode="cool",
            observed_hvac_action="cooling",
            observed_valid_temperatures=True,
        )

        decision = exposure_zone(
            room=78.6,
            previous=previous,
            event=ControllerEvent.NORMAL_UPDATE,
            now=T0 + timedelta(minutes=1),
        )

        self.assertEqual(
            decision.base_target,
            10,
        )

        self.assertEqual(
            decision.adaptive_boost,
            0,
        )

        self.assertEqual(
            decision.pi_target,
            10,
        )

        self.assertEqual(
            decision.cooling_exposure_seconds,
            0.0,
        )

        self.assertEqual(
            decision.adaptive_action,
            "no_headroom",
        )

    def test_adaptive_due_at_base_ten_remains_no_headroom(self) -> None:
        previous = ZoneState(
            base_target=10,
            adaptive_boost=2,
            reference_error=3.60,
            last_evaluation=T0,
            cooling_exposure_seconds=300.0,
            last_observed_at=T0,
            observed_hvac_mode="cool",
            observed_hvac_action="cooling",
            observed_valid_temperatures=True,
        )

        decision = exposure_zone(
            room=78.6,
            previous=previous,
            event=ControllerEvent.ADAPTIVE_DUE,
            now=T0 + timedelta(minutes=5),
        )

        self.assertEqual(
            decision.adaptive_boost,
            0,
        )

        self.assertEqual(
            decision.cooling_exposure_seconds,
            0.0,
        )

        self.assertEqual(
            decision.adaptive_action,
            "no_headroom",
        )

    def test_adaptive_due_reports_saturated_when_pi_is_already_max(self) -> None:
        """Report saturation without changing already-maxed Adaptive I."""

        previous = ZoneState(
            base_target=8,
            adaptive_boost=2,
            reference_error=3.00,
            last_evaluation=T0,
            cooling_exposure_seconds=300.0,
            last_observed_at=T0 + timedelta(minutes=5),
            observed_hvac_mode="cool",
            observed_hvac_action="cooling",
            observed_valid_temperatures=True,
        )

        decision = exposure_zone(
            room=78.10,
            previous=previous,
            event=ControllerEvent.ADAPTIVE_DUE,
            now=T0 + timedelta(minutes=10),
        )

        self.assertEqual(
            decision.base_target,
            8,
        )

        self.assertEqual(
            decision.adaptive_boost,
            2,
        )

        self.assertEqual(
            decision.pi_target,
            10,
        )

        self.assertEqual(
            decision.adaptive_action,
            "saturated",
        )

        self.assertEqual(
            decision.cooling_exposure_seconds,
            0.0,
        )


class ExposureResetTests(unittest.TestCase):
    """Verify true mode changes and invalid strategies fail safely."""

    def test_mode_change_out_of_cool_resets_exposure(self) -> None:
        previous = ZoneState(
            base_target=8,
            adaptive_boost=1,
            reference_error=3.0,
            last_evaluation=T0,
            cooling_exposure_seconds=300.0,
            last_observed_at=T0,
            observed_hvac_mode="cool",
            observed_hvac_action="cooling",
            observed_valid_temperatures=True,
        )

        decision = exposure_zone(
            mode="off",
            action="idle",
            event=ControllerEvent.HVAC_MODE_CHANGE,
            previous=previous,
            now=T0 + timedelta(minutes=5),
        )

        self.assertEqual(
            decision.adaptive_boost,
            0,
        )

        self.assertEqual(
            decision.cooling_exposure_seconds,
            0.0,
        )

        self.assertIsNone(
            decision.reference_error
        )

    def test_unknown_strategy_is_rejected(self) -> None:
        settings = ControllerSettings(
            adaptive_strategy="not_a_strategy",
        )

        with self.assertRaises(ValueError):
            calculate_zone(
                ZoneInput(
                    room_temperature=78.0,
                    reference_temperature=75.0,
                    hvac_mode="cool",
                    hvac_action="cooling",
                ),
                ZoneState(),
                T0,
                settings=settings,
            )


class RelativeDeadlineSemanticsTests(unittest.TestCase):
    """Verify global ticks cannot drive the new Adaptive strategy."""

    def test_legacy_global_tick_is_ignored_by_cooling_exposure(self) -> None:
        start = exposure_zone(
            event=ControllerEvent.STARTUP,
        )

        ignored = exposure_zone(
            event=ControllerEvent.ADAPTIVE_TICK,
            previous=start.next_state,
            now=T0 + timedelta(minutes=10),
        )

        self.assertEqual(
            ignored.cooling_exposure_seconds,
            600.0,
        )

        self.assertEqual(
            ignored.adaptive_boost,
            0,
        )

        self.assertEqual(
            ignored.adaptive_action,
            "legacy_tick_ignored",
        )

        due = exposure_zone(
            event=ControllerEvent.ADAPTIVE_DUE,
            previous=ignored.next_state,
            now=T0 + timedelta(minutes=10),
        )

        self.assertEqual(
            due.adaptive_boost,
            1,
        )

        self.assertEqual(
            due.adaptive_action,
            "increase",
        )

    def test_early_relative_deadline_does_not_change_adaptive(self) -> None:
        start = exposure_zone(
            event=ControllerEvent.STARTUP,
        )

        early = exposure_zone(
            event=ControllerEvent.ADAPTIVE_DUE,
            previous=start.next_state,
            now=T0 + timedelta(minutes=7),
        )

        self.assertEqual(
            early.adaptive_boost,
            0,
        )

        self.assertEqual(
            early.cooling_exposure_seconds,
            420.0,
        )

        self.assertEqual(
            early.adaptive_action,
            "deadline_early",
        )


class ImmediateThermalResetTests(unittest.TestCase):
    """Verify an already-balanced room immediately loses cooling demand."""

    def _previous_with_adaptive(self) -> ZoneState:
        return ZoneState(
            base_target=8,
            adaptive_boost=2,
            reference_error=3.0,
            last_evaluation=T0,
            cooling_exposure_seconds=300.0,
            last_observed_at=T0 + timedelta(minutes=5),
            observed_hvac_mode="cool",
            observed_hvac_action="cooling",
            observed_valid_temperatures=True,
        )

    def test_normal_temperature_update_resets_adaptive_below_1_3(self) -> None:
        decision = exposure_zone(
            room=75.5,
            previous=self._previous_with_adaptive(),
            event=ControllerEvent.NORMAL_UPDATE,
            now=T0 + timedelta(minutes=6),
        )

        self.assertEqual(
            decision.directional_error,
            0.5,
        )

        self.assertEqual(
            decision.base_target,
            0,
        )

        self.assertEqual(
            decision.adaptive_boost,
            0,
        )

        self.assertEqual(
            decision.pi_target,
            0,
        )

        self.assertEqual(
            decision.effective_percentage,
            0,
        )

        self.assertEqual(
            decision.cooling_exposure_seconds,
            0.0,
        )

        self.assertIsNone(
            decision.reference_error
        )

        self.assertEqual(
            decision.adaptive_action,
            "reset",
        )

    def test_overcooled_room_has_zero_effective_demand(self) -> None:
        decision = exposure_zone(
            room=73.1,
            previous=self._previous_with_adaptive(),
            event=ControllerEvent.NORMAL_UPDATE,
            now=T0 + timedelta(minutes=6),
        )

        self.assertLess(
            decision.directional_error,
            0,
        )

        self.assertEqual(
            decision.adaptive_boost,
            0,
        )

        self.assertEqual(
            decision.pi_target,
            0,
        )

        self.assertEqual(
            decision.effective_speed,
            0,
        )

        self.assertEqual(
            decision.effective_percentage,
            0,
        )

        self.assertEqual(
            decision.adaptive_action,
            "reset",
        )


class TrendDiagnosticTests(unittest.TestCase):
    """Verify very short samples do not display misleading huge rates."""

    def test_projected_rate_waits_for_minimum_exposure(self) -> None:
        previous = ZoneState(
            base_target=8,
            adaptive_boost=0,
            reference_error=3.0,
            last_evaluation=T0,
            cooling_exposure_seconds=0.0,
            last_observed_at=T0,
            observed_hvac_mode="cool",
            observed_hvac_action="cooling",
            observed_valid_temperatures=True,
        )

        decision = exposure_zone(
            room=78.1,
            previous=previous,
            event=ControllerEvent.NORMAL_UPDATE,
            now=T0 + timedelta(seconds=30),
        )

        self.assertIsNone(
            decision.improvement_rate_per_10m
        )

        self.assertEqual(
            decision.adaptive_action,
            "observing",
        )


if __name__ == "__main__":
    unittest.main()
