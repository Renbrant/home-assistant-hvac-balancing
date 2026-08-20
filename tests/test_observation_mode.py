"""Structural tests for Phase 2 observation-only HA wiring."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

INTEGRATION = (
    ROOT
    / "custom_components"
    / "hvac_balancing"
)

DASHBOARD = (
    ROOT
    / "dev"
    / "homeassistant"
    / "dashboards"
    / "hvac_balancing_test_bench.yaml"
)


def read(relative_path: str) -> str:
    """Read one integration source file."""

    return (
        INTEGRATION / relative_path
    ).read_text(encoding="utf-8")


def test_observation_adapter_files_exist() -> None:
    """Verify observation-only HA platforms exist."""

    for name in (
        "observation.py",
        "sensor.py",
        "binary_sensor.py",
    ):
        assert (INTEGRATION / name).is_file()


def test_observation_adapter_uses_relative_zone_deadlines() -> None:
    """Verify push updates, relative deadlines, and safety watchdog."""

    source = read("observation.py")

    assert "async_track_state_change_event" in source
    assert "async_call_later" in source
    assert "async_track_time_change" in source
    assert "minute=range(0, 60, 10)" in source

    assert "minute=range(0, 60, 5)" not in source
    assert "def _async_adaptive_tick" not in source

    assert "ControllerEvent.NORMAL_UPDATE" in source
    assert "ControllerEvent.ADAPTIVE_DUE" in source
    assert "ControllerEvent.HVAC_MODE_CHANGE" in source
    assert "ControllerEvent.STARTUP" in source


def test_observation_adapter_uses_virtual_test_bench_only() -> None:
    """Verify Phase 2 HA wiring cannot read production HVAC entities."""

    source = read("observation.py")

    expected_virtual = (
        "climate.hvac_test_thermostat",
        "sensor.hvac_test_kitchen_temperature",
        "sensor.hvac_test_bed_1_temperature",
        "sensor.hvac_test_bed_2_temperature",
        "sensor.hvac_test_bed_3_temperature",
    )

    for entity_id in expected_virtual:
        assert entity_id in source

    forbidden_production = (
        "climate.kitchen",
        "sensor.kitchen_temp_temperature",
        "sensor.bed_1_temp_temperature",
        "sensor.bed_2_temp_temperature",
        "sensor.bed_3_temp_temperature",
        "fan.bed_1_booster",
        "fan.bed_2_booster",
        "fan.bed_3_booster",
    )

    for entity_id in forbidden_production:
        assert entity_id not in source


def test_observation_adapter_contains_no_actuation() -> None:
    """Verify HA adapter cannot command HVAC hardware."""

    sources = "\n".join(
        read(name)
        for name in (
            "__init__.py",
            "observation.py",
            "sensor.py",
            "binary_sensor.py",
        )
    )

    forbidden = (
        "hass.services.async_call",
        "services.async_call",
        "fan.turn_on",
        "fan.turn_off",
        "fan.set_percentage",
        "fan.set_preset_mode",
        "nest.set_fan_timer",
        "climate.set_fan_mode",
    )

    for marker in forbidden:
        assert marker not in sources


def test_observation_entities_are_push_driven() -> None:
    """Verify diagnostics subscribe through entity lifecycle callbacks."""

    sensor = read("sensor.py")
    binary_sensor = read("binary_sensor.py")

    for source in (sensor, binary_sensor):
        assert "_attr_should_poll = False" in source
        assert "async_added_to_hass" in source
        assert "async_on_remove" in source
        assert "async_write_ha_state" in source


def test_observation_metrics_are_exposed() -> None:
    """Verify the four requested zone diagnostics exist."""

    sensor = read("sensor.py")

    expected = (
        '("base_p", "Base P")',
        '("adaptive_i", "Adaptive I")',
        '("pi_target", "PI Target")',
        '("effective_percentage", "Effective Percentage")',
        '("improvement_rate", "Improvement Rate")',
        '("adaptive_action", "Adaptive Action")',
    )

    for marker in expected:
        assert marker in sensor

    binary_sensor = read("binary_sensor.py")
    assert "central_assist_required" in binary_sensor


def test_setup_uses_runtime_data_and_forwards_platforms() -> None:
    """Verify the config entry owns observation runtime."""

    source = read("__init__.py")

    assert "entry.runtime_data" in source
    assert "entry.async_on_unload" in source
    assert "async_forward_entry_setups" in source
    assert "async_unload_platforms" in source
    assert "Platform.SENSOR" in source
    assert "Platform.BINARY_SENSOR" in source


def test_dashboard_contains_python_observation_metrics() -> None:
    """Verify the Test Bench exposes Python calculations."""

    dashboard = DASHBOARD.read_text(encoding="utf-8")

    expected = (
        "sensor.hvac_balancing_test_bed_1_base_p",
        "sensor.hvac_balancing_test_bed_1_adaptive_i",
        "sensor.hvac_balancing_test_bed_1_pi_target",
        "sensor.hvac_balancing_test_bed_1_effective_percentage",
        "sensor.hvac_balancing_test_bed_2_base_p",
        "sensor.hvac_balancing_test_bed_3_base_p",
        "binary_sensor.hvac_balancing_test_central_assist",
    )

    for entity_id in expected:
        assert entity_id in dashboard

def test_observation_timing_diagnostics_exist() -> None:
    """Verify watchdog, per-zone deadlines, and exposure diagnostics."""

    observation = read("observation.py")
    sensor = read("sensor.py")
    dashboard = DASHBOARD.read_text(encoding="utf-8")

    assert "_async_timeline_heartbeat" in observation
    assert "second=range(0, 60, 10)" in observation

    assert "_async_watchdog" in observation
    assert "self.last_watchdog = now" in observation

    assert "_zone_deadline_unsubscribers" in observation
    assert "zone_deadlines" in observation
    assert "async_call_later" in observation

    expected_sensor_markers = (
        "HVACBalancingTimelineSensor",
        "HVACBalancingZoneDeadlineSensor",
        "HVACBalancingAdaptiveWindowSensor",
        '"current_time"',
        '"last_controller_update"',
        '"last_controller_event"',
        '"last_watchdog"',
        '"next_watchdog"',
        '"next_watchdog_in"',
        "_projected_cooling_exposure",
        "required_cooling_exposure_seconds",
    )

    for marker in expected_sensor_markers:
        assert marker in sensor

    expected_entities = (
        "sensor.hvac_balancing_test_current_time",
        "sensor.hvac_balancing_test_last_controller_update",
        "sensor.hvac_balancing_test_last_controller_event",
        "sensor.hvac_balancing_test_last_watchdog",
        "sensor.hvac_balancing_test_next_watchdog",
        "sensor.hvac_balancing_test_next_watchdog_in",
        "sensor.hvac_balancing_test_bed_1_adaptive_window",
        "sensor.hvac_balancing_test_bed_2_adaptive_window",
        "sensor.hvac_balancing_test_bed_3_adaptive_window",
        "sensor.hvac_balancing_test_bed_1_next_adaptive_due",
        "sensor.hvac_balancing_test_bed_2_next_adaptive_due",
        "sensor.hvac_balancing_test_bed_3_next_adaptive_due",
    )

    for entity_id in expected_entities:
        assert entity_id in dashboard

def test_timeline_heartbeat_cannot_recalculate_controller() -> None:
    """Protect controller state from display heartbeat updates."""

    observation = read("observation.py")

    start = observation.index(
        "def _async_timeline_heartbeat"
    )

    end = observation.index(
        "def _state_value",
        start,
    )

    heartbeat = observation[start:end]

    assert "_recalculate(" not in heartbeat
    assert "calculate_zone(" not in heartbeat
    assert "ControllerEvent." not in heartbeat

def test_observation_adapter_uses_cooling_exposure_strategy() -> None:
    """Verify Test Bench explicitly opts into beta.4 strategy."""

    observation = read("observation.py")

    assert "COOLING_EXPOSURE_SETTINGS" in observation
    assert "settings=COOLING_EXPOSURE_SETTINGS" in observation


def test_dashboard_exposes_cooling_exposure_diagnostics() -> None:
    """Verify beta.5 exposure, deadlines, trend, and Adaptive action."""

    dashboard = DASHBOARD.read_text(encoding="utf-8")

    assert "Adaptive Episode Scheduler" in dashboard
    assert "Controller Timing & Cooling Exposure" not in dashboard

    for bed in (1, 2, 3):
        expected = (
            f"sensor.hvac_balancing_test_bed_{bed}_adaptive_window",
            f"sensor.hvac_balancing_test_bed_{bed}_improvement_rate",
            f"sensor.hvac_balancing_test_bed_{bed}_adaptive_action",
        )

        for entity_id in expected:
            assert entity_id in dashboard

        assert (
            f"Bed {bed} - Cooling Exposure"
            in dashboard
        )


def test_cooling_exposure_display_is_heartbeat_only() -> None:
    """Verify display projection cannot mutate controller state."""

    sensor = read("sensor.py")

    start = sensor.index(
        "def _projected_cooling_exposure"
    )

    end = sensor.index(
        "class HVACBalancingAdaptiveWindowSensor",
        start,
    )

    projector = sensor[start:end]

    assert "calculate_zone(" not in projector
    assert "_recalculate(" not in projector
    assert "ZoneState(" not in projector

def test_watchdog_cannot_issue_adaptive_due() -> None:
    """Verify periodic watchdog is recovery-only."""

    observation = read("observation.py")

    start = observation.index(
        "def _async_watchdog"
    )

    end = observation.index(
        "def _async_timeline_heartbeat",
        start,
    )

    watchdog = observation[start:end]

    assert "ControllerEvent.NORMAL_UPDATE" in watchdog
    assert "ControllerEvent.ADAPTIVE_DUE" not in watchdog
    assert "ControllerEvent.ADAPTIVE_TICK" not in watchdog


def test_zone_deadline_callback_targets_exactly_one_zone() -> None:
    """Verify one expired timer cannot evaluate every zone as due."""

    observation = read("observation.py")

    assert "adaptive_due_zone=zone_key" in observation
    assert "zone.key != adaptive_due_zone" in observation
    assert "zone_event = ControllerEvent.NORMAL_UPDATE" in observation


def test_idle_cancels_relative_zone_deadlines_by_eligibility() -> None:
    """Verify deadlines run only while central HVAC is actively cooling."""

    observation = read("observation.py")

    start = observation.index(
        "def _zone_deadline_is_eligible"
    )

    end = observation.index(
        "def _sync_zone_deadlines",
        start,
    )

    eligibility = observation[start:end]

    assert "snapshot.hvac_mode != COOL_MODE" in eligibility
    assert "snapshot.hvac_action != COOLING_ACTION" in eligibility
    assert "return False" in eligibility


def test_relative_deadline_is_rebuilt_from_remaining_exposure() -> None:
    """Verify timer delay is required exposure minus accumulated cooling."""

    observation = read("observation.py")

    start = observation.index(
        "def _sync_zone_deadlines"
    )

    end = observation.index(
        "def _async_zone_adaptive_due",
        start,
    )

    scheduler = observation[start:end]

    assert "required - accumulated" in scheduler
    assert "async_call_later(" in scheduler
    assert "_cancel_zone_deadline" in scheduler


def test_global_adaptive_tick_is_absent_from_test_bench_adapter() -> None:
    """Verify beta.5 Test Bench has no global Adaptive decision tick."""

    observation = read("observation.py")

    assert "def _async_adaptive_tick" not in observation
    assert "minute=range(0, 60, 5)" not in observation
    assert "ControllerEvent.ADAPTIVE_TICK" not in observation

def test_diagnostic_times_are_normalized_to_ha_local_timezone() -> None:
    """Verify all displayed diagnostic clocks normalize through HA timezone."""

    sensor = read("sensor.py")

    assert "from homeassistant.util import dt as dt_util" in sensor
    assert "def _as_local_datetime(" in sensor
    assert "dt_util.as_local(value)" in sensor
    assert "def _local_isoformat(" in sensor

    start = sensor.index(
        "def _format_time"
    )

    end = sensor.index(
        "def _format_duration",
        start,
    )

    formatter = sensor[start:end]

    assert "_as_local_datetime(" in formatter
    assert 'strftime(' in formatter

    assert '"deadline": _local_isoformat(' in sensor
    assert '"last_controller_update": _local_isoformat(' in sensor
    assert '"next_watchdog": _local_isoformat(' in sensor
