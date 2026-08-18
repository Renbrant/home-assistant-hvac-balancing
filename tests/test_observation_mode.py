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


def test_observation_adapter_uses_current_event_helpers() -> None:
    """Verify push updates and aligned five-minute ticks."""

    source = read("observation.py")

    assert "async_track_state_change_event" in source
    assert "async_track_time_change" in source
    assert "minute=range(0, 60, 5)" in source

    assert "ControllerEvent.NORMAL_UPDATE" in source
    assert "ControllerEvent.ADAPTIVE_TICK" in source
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
