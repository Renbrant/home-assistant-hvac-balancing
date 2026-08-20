"""Parity tests for the pure HVAC Balancing controller."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import math
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
CORE_DIR = ROOT / "custom_components" / "hvac_balancing"

sys.path.insert(0, str(CORE_DIR))

from controller import (  # noqa: E402
    ControllerEvent,
    ZoneDecision,
    ZoneInput,
    ZoneState,
    base_target_with_hysteresis,
    calculate_zone,
    central_assist_required,
    falling_target,
    rising_target,
)


T0 = datetime(
    2026,
    8,
    18,
    12,
    0,
    0,
    tzinfo=timezone.utc,
)


def zone(
    *,
    room: object = 77.6,
    reference: object = 75.0,
    mode: str | None = "cool",
    action: str | None = "idle",
    event: ControllerEvent = ControllerEvent.NORMAL_UPDATE,
    previous: ZoneState | None = None,
    now: datetime = T0,
) -> ZoneDecision:
    """Convenience wrapper for one-zone tests."""

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
    )


class RisingCurveTests(unittest.TestCase):

    def test_rising_curve_boundaries(self) -> None:
        cases = (
            (1.49, 0),
            (1.50, 2),
            (1.99, 2),
            (2.00, 4),
            (2.49, 4),
            (2.50, 6),
            (2.99, 6),
            (3.00, 8),
            (3.49, 8),
            (3.50, 10),
            (8.00, 10),
        )

        for error, expected in cases:
            with self.subTest(error=error):
                self.assertEqual(
                    rising_target(error),
                    expected,
                )


class FallingCurveTests(unittest.TestCase):

    def test_falling_curve_boundaries(self) -> None:
        cases = (
            (1.29, 0),
            (1.30, 0),
            (1.31, 2),
            (1.80, 2),
            (1.81, 4),
            (2.30, 4),
            (2.31, 6),
            (2.80, 6),
            (2.81, 8),
            (3.30, 8),
            (3.31, 10),
        )

        for error, expected in cases:
            with self.subTest(error=error):
                self.assertEqual(
                    falling_target(error),
                    expected,
                )


class HysteresisTests(unittest.TestCase):

    def test_speed_four_holds_at_1_9(self) -> None:
        self.assertEqual(
            base_target_with_hysteresis(1.9, 4),
            4,
        )

    def test_speed_four_drops_at_1_8(self) -> None:
        self.assertEqual(
            base_target_with_hysteresis(1.8, 4),
            2,
        )

    def test_speed_eight_holds_at_2_9(self) -> None:
        self.assertEqual(
            base_target_with_hysteresis(2.9, 8),
            8,
        )

    def test_speed_eight_drops_at_2_8(self) -> None:
        self.assertEqual(
            base_target_with_hysteresis(2.8, 8),
            6,
        )

    def test_rising_demand_ignores_falling_curve(self) -> None:
        self.assertEqual(
            base_target_with_hysteresis(3.0, 4),
            8,
        )


class DirectionAndSafetyTests(unittest.TestCase):

    def test_cool_uses_room_minus_reference(self) -> None:
        decision = zone(
            room=78.0,
            reference=75.0,
        )

        self.assertEqual(decision.directional_error, 3.0)
        self.assertEqual(decision.base_target, 8)

    def test_diagnostic_delta_is_independent_of_base_math(self) -> None:
        decision = zone(
            room=76.499,
            reference=75.0,
        )

        self.assertEqual(decision.temperature_delta, 1.5)
        self.assertEqual(decision.base_target, 0)

    def test_heat_produces_zero_demand(self) -> None:
        decision = zone(
            room=60.0,
            reference=80.0,
            mode="heat",
            previous=ZoneState(
                base_target=10,
                adaptive_boost=4,
            ),
        )

        self.assertEqual(decision.base_target, 0)
        self.assertEqual(decision.adaptive_boost, 0)
        self.assertEqual(decision.pi_target, 0)
        self.assertEqual(decision.effective_speed, 0)

    def test_heat_cool_produces_zero_demand(self) -> None:
        decision = zone(
            room=90.0,
            reference=60.0,
            mode="heat_cool",
        )

        self.assertEqual(decision.pi_target, 0)
        self.assertEqual(decision.effective_percentage, 0)

    def test_invalid_room_temperature_fails_safe(self) -> None:
        decision = zone(
            room=None,
            reference=75.0,
            previous=ZoneState(
                base_target=8,
                adaptive_boost=2,
                reference_error=3.0,
                last_evaluation=T0,
            ),
        )

        self.assertFalse(decision.valid_temperatures)

        # NORMAL_UPDATE does not execute the Adaptive I template.
        self.assertEqual(decision.adaptive_boost, 2)
        self.assertEqual(decision.reference_error, 3.0)
        self.assertEqual(decision.last_evaluation, T0)

        # v0.2 safety override: invalid temperatures cannot command airflow.
        self.assertEqual(decision.pi_target, 0)
        self.assertEqual(decision.effective_speed, 0)

    def test_invalid_reference_temperature_fails_safe(self) -> None:
        decision = zone(
            room=77.0,
            reference="unavailable",
        )

        self.assertFalse(decision.valid_temperatures)
        self.assertEqual(decision.effective_percentage, 0)

    def test_invalid_temperature_adaptive_tick_clears_state(self) -> None:
        previous = ZoneState(
            base_target=6,
            adaptive_boost=2,
            reference_error=2.6,
            last_evaluation=T0,
        )

        decision = zone(
            room="unavailable",
            reference=75.0,
            event=ControllerEvent.ADAPTIVE_TICK,
            previous=previous,
            now=T0 + timedelta(minutes=5),
        )

        self.assertEqual(decision.adaptive_boost, 0)
        self.assertIsNone(decision.reference_error)
        self.assertIsNone(decision.last_evaluation)
        self.assertEqual(decision.pi_target, 0)
        self.assertEqual(decision.effective_speed, 0)

    def test_nan_temperature_fails_safe(self) -> None:
        decision = zone(
            room=math.nan,
            reference=75.0,
        )

        self.assertFalse(decision.valid_temperatures)
        self.assertEqual(decision.pi_target, 0)


class EffectiveTargetTests(unittest.TestCase):

    def test_active_cooling_enforces_speed_one_minimum(self) -> None:
        decision = zone(
            room=75.5,
            reference=75.0,
            action="cooling",
        )

        self.assertEqual(decision.pi_target, 0)
        self.assertEqual(decision.effective_speed, 1)
        self.assertEqual(decision.effective_percentage, 10)
        self.assertEqual(
            decision.reason,
            "active_cooling_minimum",
        )

    def test_idle_cool_uses_pi_target(self) -> None:
        decision = zone(
            room=77.6,
            reference=75.0,
            action="idle",
        )

        self.assertEqual(decision.pi_target, 6)
        self.assertEqual(decision.effective_speed, 6)
        self.assertEqual(decision.effective_percentage, 60)

    def test_non_cool_ignores_active_cooling_action(self) -> None:
        decision = zone(
            room=80.0,
            reference=70.0,
            mode="off",
            action="cooling",
        )

        self.assertEqual(decision.effective_speed, 0)


class ObservationWindowTests(unittest.TestCase):

    def test_first_adaptive_tick_initializes_window(self) -> None:
        decision = zone(
            room=77.6,
            reference=75.0,
            event=ControllerEvent.ADAPTIVE_TICK,
            previous=ZoneState(
                base_target=6,
            ),
        )

        self.assertEqual(decision.adaptive_boost, 0)
        self.assertEqual(decision.reference_error, 2.6)
        self.assertEqual(decision.last_evaluation, T0)

    def test_19m59s_does_not_evaluate(self) -> None:
        previous = ZoneState(
            base_target=6,
            adaptive_boost=2,
            reference_error=2.7,
            last_evaluation=T0,
        )

        decision = zone(
            room=77.6,
            reference=75.0,
            event=ControllerEvent.ADAPTIVE_TICK,
            previous=previous,
            now=T0 + timedelta(minutes=19, seconds=59),
        )

        self.assertEqual(decision.adaptive_boost, 2)
        self.assertEqual(decision.reference_error, 2.7)
        self.assertEqual(decision.last_evaluation, T0)

    def test_20m00s_evaluates(self) -> None:
        previous = ZoneState(
            base_target=6,
            adaptive_boost=1,
            reference_error=2.7,
            last_evaluation=T0,
        )

        now = T0 + timedelta(minutes=20)

        decision = zone(
            room=77.6,
            reference=75.0,
            event=ControllerEvent.ADAPTIVE_TICK,
            previous=previous,
            now=now,
        )

        self.assertEqual(decision.adaptive_boost, 2)
        self.assertEqual(decision.reference_error, 2.6)
        self.assertEqual(decision.last_evaluation, now)

    def test_reference_error_is_sampled_to_two_decimals(self) -> None:
        decision = zone(
            room=77.676,
            reference=75.0,
            event=ControllerEvent.ADAPTIVE_TICK,
            previous=ZoneState(
                base_target=6,
            ),
        )

        self.assertEqual(decision.reference_error, 2.68)


class AdaptiveResponseTests(unittest.TestCase):

    def test_poor_improvement_adds_one(self) -> None:
        previous = ZoneState(
            base_target=6,
            adaptive_boost=1,
            reference_error=2.7,
            last_evaluation=T0,
        )

        decision = zone(
            room=77.6,
            reference=75.0,
            event=ControllerEvent.ADAPTIVE_TICK,
            previous=previous,
            now=T0 + timedelta(minutes=20),
        )

        self.assertEqual(decision.adaptive_boost, 2)

    def test_negative_improvement_also_adds_one(self) -> None:
        previous = ZoneState(
            base_target=6,
            adaptive_boost=1,
            reference_error=2.5,
            last_evaluation=T0,
        )

        decision = zone(
            room=77.7,
            reference=75.0,
            event=ControllerEvent.ADAPTIVE_TICK,
            previous=previous,
            now=T0 + timedelta(minutes=20),
        )

        self.assertEqual(decision.adaptive_boost, 2)

    def test_moderate_improvement_holds(self) -> None:
        previous = ZoneState(
            base_target=6,
            adaptive_boost=2,
            reference_error=2.9,
            last_evaluation=T0,
        )

        decision = zone(
            room=77.6,
            reference=75.0,
            event=ControllerEvent.ADAPTIVE_TICK,
            previous=previous,
            now=T0 + timedelta(minutes=20),
        )

        self.assertEqual(decision.adaptive_boost, 2)

    def test_good_improvement_removes_one(self) -> None:
        previous = ZoneState(
            base_target=6,
            adaptive_boost=2,
            reference_error=3.2,
            last_evaluation=T0,
        )

        decision = zone(
            room=77.6,
            reference=75.0,
            event=ControllerEvent.ADAPTIVE_TICK,
            previous=previous,
            now=T0 + timedelta(minutes=20),
        )

        self.assertEqual(decision.adaptive_boost, 1)

    def test_exact_0_2_improvement_holds(self) -> None:
        previous = ZoneState(
            base_target=6,
            adaptive_boost=2,
            reference_error=2.8,
            last_evaluation=T0,
        )

        decision = zone(
            room=77.6,
            reference=75.0,
            event=ControllerEvent.ADAPTIVE_TICK,
            previous=previous,
            now=T0 + timedelta(minutes=20),
        )

        self.assertEqual(decision.adaptive_boost, 2)

    def test_exact_0_5_improvement_removes_one(self) -> None:
        previous = ZoneState(
            base_target=6,
            adaptive_boost=2,
            reference_error=3.1,
            last_evaluation=T0,
        )

        decision = zone(
            room=77.6,
            reference=75.0,
            event=ControllerEvent.ADAPTIVE_TICK,
            previous=previous,
            now=T0 + timedelta(minutes=20),
        )

        self.assertEqual(decision.adaptive_boost, 1)


class AdaptiveResetAndUnwindTests(unittest.TestCase):

    def test_error_1_3_resets_everything(self) -> None:
        previous = ZoneState(
            base_target=2,
            adaptive_boost=3,
            reference_error=1.8,
            last_evaluation=T0,
        )

        decision = zone(
            room=76.3,
            reference=75.0,
            event=ControllerEvent.ADAPTIVE_TICK,
            previous=previous,
            now=T0 + timedelta(minutes=5),
        )

        self.assertEqual(decision.adaptive_boost, 0)
        self.assertIsNone(decision.reference_error)
        self.assertIsNone(decision.last_evaluation)

    def test_error_1_3_normal_update_preserves_adaptive_state(self) -> None:
        previous = ZoneState(
            base_target=2,
            adaptive_boost=3,
            reference_error=1.8,
            last_evaluation=T0,
        )

        decision = zone(
            room=76.3,
            reference=75.0,
            event=ControllerEvent.NORMAL_UPDATE,
            previous=previous,
            now=T0 + timedelta(minutes=1),
        )

        # Base P reacts immediately.
        self.assertEqual(decision.base_target, 0)

        # Adaptive I remains stored until the next adaptive trigger.
        self.assertEqual(decision.adaptive_boost, 3)
        self.assertEqual(decision.reference_error, 1.8)
        self.assertEqual(decision.last_evaluation, T0)
        self.assertEqual(decision.pi_target, 3)

    def test_1_4_holds_before_window_is_due(self) -> None:
        previous = ZoneState(
            base_target=2,
            adaptive_boost=3,
            reference_error=1.6,
            last_evaluation=T0,
        )

        decision = zone(
            room=76.4,
            reference=75.0,
            event=ControllerEvent.ADAPTIVE_TICK,
            previous=previous,
            now=T0 + timedelta(minutes=10),
        )

        self.assertEqual(decision.base_target, 2)
        self.assertEqual(decision.adaptive_boost, 3)

    def test_1_4_unwinds_one_when_due(self) -> None:
        previous = ZoneState(
            base_target=2,
            adaptive_boost=3,
            reference_error=1.6,
            last_evaluation=T0,
        )

        decision = zone(
            room=76.4,
            reference=75.0,
            event=ControllerEvent.ADAPTIVE_TICK,
            previous=previous,
            now=T0 + timedelta(minutes=20),
        )

        self.assertEqual(decision.base_target, 2)
        self.assertEqual(decision.adaptive_boost, 2)


class AntiWindupTests(unittest.TestCase):

    def test_normal_update_preserves_adaptive_when_base_rises(self) -> None:
        previous = ZoneState(
            base_target=4,
            adaptive_boost=4,
            reference_error=2.5,
            last_evaluation=T0,
        )

        decision = zone(
            room=78.1,
            reference=75.0,
            event=ControllerEvent.NORMAL_UPDATE,
            previous=previous,
            now=T0 + timedelta(minutes=1),
        )

        self.assertEqual(decision.base_target, 8)

        # Adaptive template has not executed yet.
        self.assertEqual(decision.adaptive_boost, 4)

        # Final PI target remains protected by its Speed-10 cap.
        self.assertEqual(decision.pi_target, 10)

    def test_adaptive_tick_clamps_existing_adaptive_to_headroom(self) -> None:
        previous = ZoneState(
            base_target=4,
            adaptive_boost=4,
            reference_error=2.5,
            last_evaluation=T0,
        )

        decision = zone(
            room=78.1,
            reference=75.0,
            event=ControllerEvent.ADAPTIVE_TICK,
            previous=previous,
            now=T0 + timedelta(minutes=5),
        )

        self.assertEqual(decision.base_target, 8)
        self.assertEqual(decision.adaptive_boost, 2)
        self.assertEqual(decision.pi_target, 10)

    def test_base_ten_forces_adaptive_zero(self) -> None:
        previous = ZoneState(
            base_target=8,
            adaptive_boost=2,
            reference_error=3.4,
            last_evaluation=T0,
        )

        decision = zone(
            room=78.5,
            reference=75.0,
            event=ControllerEvent.ADAPTIVE_TICK,
            previous=previous,
        )

        self.assertEqual(decision.base_target, 10)
        self.assertEqual(decision.adaptive_boost, 0)
        self.assertEqual(decision.pi_target, 10)

    def test_pi_target_never_exceeds_ten(self) -> None:
        previous = ZoneState(
            base_target=8,
            adaptive_boost=9,
            reference_error=3.0,
            last_evaluation=T0,
        )

        decision = zone(
            room=78.1,
            reference=75.0,
            previous=previous,
        )

        self.assertLessEqual(decision.pi_target, 10)


class ModeChangeRegressionTests(unittest.TestCase):

    def test_cooling_idle_cooling_preserves_window(self) -> None:
        previous = ZoneState(
            base_target=6,
            adaptive_boost=2,
            reference_error=2.7,
            last_evaluation=T0,
        )

        idle = zone(
            room=77.6,
            reference=75.0,
            mode="cool",
            action="idle",
            event=ControllerEvent.NORMAL_UPDATE,
            previous=previous,
            now=T0 + timedelta(minutes=5),
        )

        self.assertEqual(idle.adaptive_boost, 2)
        self.assertEqual(idle.reference_error, 2.7)
        self.assertEqual(idle.last_evaluation, T0)

        cooling = zone(
            room=77.6,
            reference=75.0,
            mode="cool",
            action="cooling",
            event=ControllerEvent.NORMAL_UPDATE,
            previous=idle.next_state,
            now=T0 + timedelta(minutes=10),
        )

        self.assertEqual(cooling.adaptive_boost, 2)
        self.assertEqual(cooling.reference_error, 2.7)
        self.assertEqual(cooling.last_evaluation, T0)

    def test_normal_update_does_not_consume_due_window(self) -> None:
        previous = ZoneState(
            base_target=6,
            adaptive_boost=1,
            reference_error=2.7,
            last_evaluation=T0,
        )

        decision = zone(
            room=77.6,
            reference=75.0,
            event=ControllerEvent.NORMAL_UPDATE,
            previous=previous,
            now=T0 + timedelta(minutes=30),
        )

        self.assertEqual(decision.adaptive_boost, 1)
        self.assertEqual(decision.reference_error, 2.7)
        self.assertEqual(decision.last_evaluation, T0)

    def test_true_mode_change_out_of_cool_clears_state(self) -> None:
        previous = ZoneState(
            base_target=6,
            adaptive_boost=2,
            reference_error=2.7,
            last_evaluation=T0,
        )

        decision = zone(
            room=77.6,
            reference=75.0,
            mode="off",
            event=ControllerEvent.HVAC_MODE_CHANGE,
            previous=previous,
            now=T0 + timedelta(minutes=5),
        )

        self.assertEqual(decision.base_target, 0)
        self.assertEqual(decision.adaptive_boost, 0)
        self.assertIsNone(decision.reference_error)
        self.assertIsNone(decision.last_evaluation)

    def test_true_mode_change_into_cool_starts_fresh_window(self) -> None:
        previous = ZoneState()

        now = T0 + timedelta(minutes=5)

        decision = zone(
            room=77.6,
            reference=75.0,
            mode="cool",
            action="idle",
            event=ControllerEvent.HVAC_MODE_CHANGE,
            previous=previous,
            now=now,
        )

        self.assertEqual(decision.base_target, 6)
        self.assertEqual(decision.adaptive_boost, 0)
        self.assertEqual(decision.reference_error, 2.6)
        self.assertEqual(decision.last_evaluation, now)


class StartupTests(unittest.TestCase):

    def test_startup_initializes_missing_observation_window(self) -> None:
        decision = zone(
            room=77.6,
            reference=75.0,
            event=ControllerEvent.STARTUP,
            previous=ZoneState(
                base_target=6,
            ),
        )

        self.assertEqual(decision.reference_error, 2.6)
        self.assertEqual(decision.last_evaluation, T0)


class CentralAssistTests(unittest.TestCase):

    def test_below_eight_is_false(self) -> None:
        decision = zone(
            room=77.6,
            reference=75.0,
        )

        self.assertFalse(
            central_assist_required(
                "cool",
                [decision],
            )
        )

    def test_exactly_eight_is_true(self) -> None:
        decision = zone(
            room=78.0,
            reference=75.0,
        )

        self.assertEqual(decision.pi_target, 8)

        self.assertTrue(
            central_assist_required(
                "cool",
                [decision],
            )
        )

    def test_above_eight_is_true(self) -> None:
        previous = ZoneState(
            base_target=8,
            adaptive_boost=2,
        )

        decision = zone(
            room=78.1,
            reference=75.0,
            previous=previous,
        )

        self.assertEqual(decision.pi_target, 10)

        self.assertTrue(
            central_assist_required(
                "cool",
                [decision],
            )
        )

    def test_non_cool_is_false_even_with_high_target(self) -> None:
        synthetic = ZoneDecision(
            valid_temperatures=True,
            temperature_delta=5.0,
            directional_error=5.0,
            control_direction="cooling",
            base_target=10,
            adaptive_boost=0,
            pi_target=10,
            effective_speed=10,
            effective_percentage=100,
            reference_error=5.0,
            last_evaluation=T0,
            balancing_active=True,
            reason="balancing",
        )

        self.assertFalse(
            central_assist_required(
                "off",
                [synthetic],
            )
        )

    def test_any_zone_at_eight_requests_assist(self) -> None:
        low = zone(
            room=76.6,
            reference=75.0,
        )

        high = zone(
            room=78.0,
            reference=75.0,
        )

        self.assertTrue(
            central_assist_required(
                "cool",
                [low, high],
            )
        )


class ZoneIndependenceTests(unittest.TestCase):

    def test_zone_state_is_independent(self) -> None:
        zone_a_state = ZoneState(
            base_target=6,
            adaptive_boost=2,
            reference_error=2.7,
            last_evaluation=T0,
        )

        zone_b_state = ZoneState(
            base_target=2,
            adaptive_boost=0,
            reference_error=1.6,
            last_evaluation=T0,
        )

        zone_a = zone(
            room=77.6,
            reference=75.0,
            event=ControllerEvent.ADAPTIVE_TICK,
            previous=zone_a_state,
            now=T0 + timedelta(minutes=20),
        )

        zone_b = zone(
            room=76.6,
            reference=75.0,
            event=ControllerEvent.ADAPTIVE_TICK,
            previous=zone_b_state,
            now=T0 + timedelta(minutes=20),
        )

        self.assertNotEqual(
            zone_a.next_state,
            zone_b.next_state,
        )

        self.assertEqual(
            zone_b_state.adaptive_boost,
            0,
        )


if __name__ == "__main__":
    unittest.main()
