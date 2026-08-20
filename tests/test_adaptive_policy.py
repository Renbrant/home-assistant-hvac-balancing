"""Tests for the adaptive cooling-exposure policy."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
CORE_DIR = ROOT / "custom_components" / "hvac_balancing"

sys.path.insert(0, str(CORE_DIR))

from adaptive_policy import (  # noqa: E402
    AdaptiveAction,
    cooling_exposure_progress,
    improvement_rate_per_10m,
    required_cooling_exposure_seconds,
    select_adaptive_action,
)


class RequiredCoolingExposureTests(unittest.TestCase):
    """Verify dynamic exposure windows."""

    def test_reset_region_requires_no_window(self) -> None:
        self.assertEqual(
            required_cooling_exposure_seconds(1.30),
            0,
        )

    def test_just_above_reset_uses_twenty_minutes(self) -> None:
        self.assertEqual(
            required_cooling_exposure_seconds(1.31),
            1200,
        )

    def test_1_99_uses_twenty_minutes(self) -> None:
        self.assertEqual(
            required_cooling_exposure_seconds(1.99),
            1200,
        )

    def test_exactly_2_0_uses_fifteen_minutes(self) -> None:
        self.assertEqual(
            required_cooling_exposure_seconds(2.0),
            900,
        )

    def test_2_99_uses_fifteen_minutes(self) -> None:
        self.assertEqual(
            required_cooling_exposure_seconds(2.99),
            900,
        )

    def test_exactly_3_0_uses_ten_minutes(self) -> None:
        self.assertEqual(
            required_cooling_exposure_seconds(3.0),
            600,
        )

    def test_large_error_remains_ten_minutes(self) -> None:
        self.assertEqual(
            required_cooling_exposure_seconds(8.0),
            600,
        )


class CoolingExposureProgressTests(unittest.TestCase):
    """Verify diagnostic progress calculation."""

    def test_zero_exposure_is_zero_progress(self) -> None:
        self.assertEqual(
            cooling_exposure_progress(
                0,
                3.0,
            ),
            0.0,
        )

    def test_half_of_severe_window_is_half_progress(self) -> None:
        self.assertEqual(
            cooling_exposure_progress(
                300,
                3.0,
            ),
            0.5,
        )

    def test_progress_is_capped_at_one(self) -> None:
        self.assertEqual(
            cooling_exposure_progress(
                900,
                3.0,
            ),
            1.0,
        )

    def test_reset_region_is_immediately_complete(self) -> None:
        self.assertEqual(
            cooling_exposure_progress(
                0,
                1.3,
            ),
            1.0,
        )


class ImprovementRateTests(unittest.TestCase):
    """Verify normalization to F per 10 cooling minutes."""

    def test_no_exposure_has_no_rate(self) -> None:
        self.assertIsNone(
            improvement_rate_per_10m(
                3.0,
                2.8,
                0,
            )
        )

    def test_0_2_over_twenty_minutes_equals_0_1_per_ten(self) -> None:
        rate = improvement_rate_per_10m(
            3.0,
            2.8,
            1200,
        )

        self.assertAlmostEqual(
            rate,
            0.10,
        )

    def test_0_5_over_twenty_minutes_equals_0_25_per_ten(self) -> None:
        rate = improvement_rate_per_10m(
            3.0,
            2.5,
            1200,
        )

        self.assertAlmostEqual(
            rate,
            0.25,
        )

    def test_0_25_over_ten_minutes_equals_0_25_per_ten(self) -> None:
        rate = improvement_rate_per_10m(
            3.0,
            2.75,
            600,
        )

        self.assertAlmostEqual(
            rate,
            0.25,
        )

    def test_worsening_error_is_negative(self) -> None:
        rate = improvement_rate_per_10m(
            3.0,
            3.1,
            600,
        )

        self.assertAlmostEqual(
            rate,
            -0.10,
        )


class AdaptiveActionTests(unittest.TestCase):
    """Verify Adaptive I decision thresholds."""

    def test_balanced_region_resets(self) -> None:
        self.assertEqual(
            select_adaptive_action(
                error=1.3,
                improvement_rate=0.0,
            ),
            AdaptiveAction.RESET,
        )

    def test_unwind_region_decreases(self) -> None:
        self.assertEqual(
            select_adaptive_action(
                error=1.4,
                improvement_rate=-1.0,
            ),
            AdaptiveAction.DECREASE,
        )

    def test_missing_rate_holds(self) -> None:
        self.assertEqual(
            select_adaptive_action(
                error=2.5,
                improvement_rate=None,
            ),
            AdaptiveAction.HOLD,
        )

    def test_poor_improvement_increases(self) -> None:
        self.assertEqual(
            select_adaptive_action(
                error=2.5,
                improvement_rate=0.099,
            ),
            AdaptiveAction.INCREASE,
        )

    def test_exact_poor_boundary_holds(self) -> None:
        self.assertEqual(
            select_adaptive_action(
                error=2.5,
                improvement_rate=0.10,
            ),
            AdaptiveAction.HOLD,
        )

    def test_moderate_improvement_holds(self) -> None:
        self.assertEqual(
            select_adaptive_action(
                error=2.5,
                improvement_rate=0.20,
            ),
            AdaptiveAction.HOLD,
        )

    def test_just_below_good_boundary_holds(self) -> None:
        self.assertEqual(
            select_adaptive_action(
                error=2.5,
                improvement_rate=0.249,
            ),
            AdaptiveAction.HOLD,
        )

    def test_good_improvement_decreases(self) -> None:
        self.assertEqual(
            select_adaptive_action(
                error=2.5,
                improvement_rate=0.25,
            ),
            AdaptiveAction.DECREASE,
        )

    def test_worsening_error_increases(self) -> None:
        self.assertEqual(
            select_adaptive_action(
                error=3.2,
                improvement_rate=-0.1,
            ),
            AdaptiveAction.INCREASE,
        )


if __name__ == "__main__":
    unittest.main()
