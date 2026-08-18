"""Structural tests for the development HVAC Test Bench."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PACKAGE = (
    ROOT
    / "dev"
    / "homeassistant"
    / "packages"
    / "hvac_balancing_test_bench.yaml"
)

DASHBOARD = (
    ROOT
    / "dev"
    / "homeassistant"
    / "dashboards"
    / "hvac_balancing_test_bench.yaml"
)

SNIPPET = (
    ROOT
    / "dev"
    / "homeassistant"
    / "configuration_snippet.yaml.example"
)


def test_test_bench_files_exist() -> None:
    """Verify all primary Phase 1.5 files exist."""

    assert PACKAGE.is_file()
    assert DASHBOARD.is_file()
    assert SNIPPET.is_file()


def test_virtual_core_entities_are_defined() -> None:
    """Verify the package defines the expected virtual HA interfaces."""

    package = PACKAGE.read_text(encoding="utf-8")

    expected = (
        "sensor.hvac_test_thermostat_temperature",
        "sensor.hvac_test_kitchen_temperature",
        "sensor.hvac_test_bed_1_temperature",
        "sensor.hvac_test_bed_2_temperature",
        "sensor.hvac_test_bed_3_temperature",
        "switch.hvac_test_ac_compressor",
        "climate.hvac_test_thermostat",
        "fan.hvac_test_bed_1_booster",
        "fan.hvac_test_bed_2_booster",
        "fan.hvac_test_bed_3_booster",
        "fan.hvac_test_central_blower",
    )

    for entity_id in expected:
        assert entity_id in package, entity_id


def test_virtual_boosters_model_real_control_surface() -> None:
    """Verify virtual boosters expose percentage and preset concepts."""

    package = PACKAGE.read_text(encoding="utf-8")

    assert "speed_count: 10" in package
    assert "set_percentage:" in package
    assert "preset_modes:" in package
    assert "- FAN" in package
    assert "- COOL" in package
    assert "- HEAT" in package
    assert "- SLEEP" in package


def test_fault_injection_controls_exist() -> None:
    """Verify failure simulation is represented in the package."""

    package = PACKAGE.read_text(encoding="utf-8")

    expected = (
        "hvac_test_thermostat_sensor_available",
        "hvac_test_kitchen_sensor_available",
        "hvac_test_bed_1_sensor_available",
        "hvac_test_bed_2_sensor_available",
        "hvac_test_bed_3_sensor_available",
        "hvac_test_ac_compressor_available",
        "hvac_test_bed_1_booster_available",
        "hvac_test_bed_2_booster_available",
        "hvac_test_bed_3_booster_available",
        "hvac_test_central_blower_available",
    )

    for helper in expected:
        assert helper in package, helper


def test_repeatable_scenarios_exist() -> None:
    """Verify deterministic scenario scripts exist."""

    package = PACKAGE.read_text(encoding="utf-8")

    expected = (
        "hvac_test_scenario_balanced:",
        "hvac_test_scenario_mild_bed_2:",
        "hvac_test_scenario_severe_upstairs:",
        "hvac_test_scenario_adaptive_i:",
        "hvac_test_scenario_bed_2_sensor_failure:",
    )

    for scenario in expected:
        assert scenario in package, scenario


def test_dashboard_uses_virtual_entities() -> None:
    """Verify the dashboard exposes the virtual test equipment."""

    dashboard = DASHBOARD.read_text(encoding="utf-8")

    assert "HVAC Balancing Test Bench" in dashboard
    assert "input_number.hvac_test_thermostat_temperature" in dashboard
    assert "input_number.hvac_test_kitchen_temperature" in dashboard
    assert "climate.hvac_test_thermostat" in dashboard
    assert "fan.hvac_test_bed_1_booster" in dashboard
    assert "fan.hvac_test_bed_2_booster" in dashboard
    assert "fan.hvac_test_bed_3_booster" in dashboard


def test_no_production_entity_ids_are_referenced() -> None:
    """Prevent accidental coupling between the Test Bench and the real house."""

    text = (
        PACKAGE.read_text(encoding="utf-8")
        + "\n"
        + DASHBOARD.read_text(encoding="utf-8")
    )

    forbidden = (
        "climate.kitchen",
        "sensor.kitchen_temp_temperature",
        "sensor.bed_1_temp_temperature",
        "sensor.bed_2_temp_temperature",
        "sensor.bed_3_temp_temperature",
        "fan.bed_1_booster",
        "fan.bed_2_booster",
        "fan.bed_3_booster",
        "nest.set_fan_timer",
    )

    for entity_id in forbidden:
        assert entity_id not in text, entity_id

def test_thermostat_and_reference_temperatures_are_separate() -> None:
    """Thermostat measurement and balancing reference must be independent."""

    package = PACKAGE.read_text(encoding="utf-8")
    dashboard = DASHBOARD.read_text(encoding="utf-8")

    assert (
        "target_sensor: sensor.hvac_test_thermostat_temperature"
        in package
    )

    assert "sensor.hvac_test_kitchen_temperature" in package

    assert (
        "input_number.hvac_test_thermostat_temperature"
        in dashboard
    )

    assert (
        "input_number.hvac_test_kitchen_temperature"
        in dashboard
    )

