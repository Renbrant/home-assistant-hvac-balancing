"""Structural safety tests for beta.7 active production runtime."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "custom_components" / "hvac_balancing"


def read(name: str) -> str:
    return (
        INTEGRATION / name
    ).read_text(encoding="utf-8")


def test_actuation_is_isolated_to_actuator_module() -> None:
    observation = read("observation.py")
    actuator = read("actuator.py")

    assert "hass.services.async_call" not in observation
    assert "services.async_call" not in observation

    assert "self.hass.services.async_call" in actuator
    assert "SERVICE_SET_PERCENTAGE" in actuator
    assert "SERVICE_SET_PRESET_MODE" in actuator
    assert "SERVICE_TURN_ON" in actuator
    assert "SERVICE_TURN_OFF" in actuator


def test_existing_entries_default_to_safe_test_bench() -> None:
    init = read("__init__.py")

    assert (
        "entry.data.get("
        in init
    )

    assert "RUNTIME_MODE_TEST_BENCH" in init
    assert "runtime_mode == RUNTIME_MODE_PRODUCTION" in init


def test_production_requires_explicit_actuation_gate() -> None:
    flow = read("config_flow.py")
    init = read("__init__.py")

    assert "CONF_ACTUATION_ENABLED" in flow
    assert "actuation_confirmation_required" in flow
    assert "default=False" in flow

    assert "if not actuation_enabled:" in init
    assert "return False" in init


def test_production_entity_ids_are_user_configured() -> None:
    sources = "\n".join(
        read(name)
        for name in (
            "__init__.py",
            "actuator.py",
            "const.py",
            "config_flow.py",
            "observation.py",
        )
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
    )

    for entity_id in forbidden:
        assert entity_id not in sources


def test_generic_runtime_accepts_injected_entity_mapping() -> None:
    observation = read("observation.py")

    assert "thermostat_entity_id:" in observation
    assert "reference_entity_id:" in observation
    assert "zones:" in observation

    assert "self.thermostat_entity_id" in observation
    assert "self.reference_entity_id" in observation
    assert "self._zones" in observation


def test_test_bench_defaults_are_preserved() -> None:
    observation = read("observation.py")

    assert (
        "thermostat_entity_id: str = TEST_BENCH_THERMOSTAT"
        in observation
    )

    assert (
        "reference_entity_id: str = TEST_BENCH_REFERENCE"
        in observation
    )

    assert (
        "zones: tuple[ObservationZoneConfig, ...] = TEST_BENCH_ZONES"
        in observation
    )


def test_actuator_uses_controller_effective_speed() -> None:
    actuator = read("actuator.py")

    assert "decision.effective_speed" in actuator
    assert "desired_percentage = desired_speed * 10" in actuator


def test_invalid_temperature_cannot_create_positive_actuation() -> None:
    actuator = read("actuator.py")

    assert "desired_speed = 0" in actuator
    assert "decision.valid_temperatures" in actuator


def test_central_assist_matches_existing_control_surface() -> None:
    actuator = read("actuator.py")

    assert 'NEST_SERVICE_SET_FAN_TIMER = "set_fan_timer"' in actuator
    assert "CENTRAL_ASSIST_TIMER_HOURS = 12" in actuator
    assert "CENTRAL_ASSIST_OFF_DELAY_SECONDS = 5 * 60" in actuator

    assert "SERVICE_SET_FAN_MODE" in actuator
    assert "FAN_OFF" in actuator


def test_unload_has_fail_safe_shutdown() -> None:
    init = read("__init__.py")
    actuator = read("actuator.py")

    assert "await runtime.actuator.async_shutdown()" in init
    assert "async def async_shutdown" in actuator
    assert "SERVICE_TURN_OFF" in actuator
    assert "SERVICE_SET_FAN_MODE" in actuator


def test_actuator_subscribes_before_startup_snapshot() -> None:
    init = read("__init__.py")

    actuator_start = init.index(
        "actuator.async_start()"
    )

    observer_start = init.index(
        "observer.async_start()"
    )

    assert actuator_start < observer_start


def test_production_diagnostics_have_separate_identity() -> None:
    init = read("__init__.py")
    sensor = read("sensor.py")
    binary_sensor = read("binary_sensor.py")

    assert 'entity_name_prefix="HVAC Balancing"' in init
    assert 'unique_id_prefix="production"' in init

    assert "entity_name_prefix" in sensor
    assert "unique_id_prefix" in sensor

    assert "entity_name_prefix" in binary_sensor
    assert "unique_id_prefix" in binary_sensor


def test_legacy_yaml_is_not_part_of_active_runtime() -> None:
    actuator = read("actuator.py")
    init = read("__init__.py")

    forbidden = (
        "sensor.bed_1_booster_pi_target_speed",
        "sensor.bed_2_booster_pi_target_speed",
        "sensor.bed_3_booster_pi_target_speed",
    )

    combined = actuator + "\n" + init

    for entity_id in forbidden:
        assert entity_id not in combined

def test_compatible_test_bench_entry_does_not_require_version_migration() -> None:
    """Keep ConfigFlow v1 because legacy empty entries remain supported."""

    flow = read("config_flow.py")

    assert "VERSION = 1" in flow
    assert "VERSION = 2" not in flow


def test_actuator_coalesces_updates_without_cancelling_inflight_commands() -> None:
    """A new controller snapshot must not cancel physical service calls."""

    actuator = read("actuator.py")

    start = actuator.index(
        "def _handle_controller_update"
    )

    end = actuator.index(
        "async def _async_apply_loop",
        start,
    )

    handler = actuator[start:end]

    assert "_apply_pending = True" in handler
    assert ".cancel()" not in handler

    assert "async def _async_apply_loop" in actuator


def test_central_assist_only_turns_off_circulation_it_owns() -> None:
    """Manual Nest fan operation must not be cancelled by an idle controller."""

    actuator = read("actuator.py")

    start = actuator.index(
        "async def _async_apply_central_assist"
    )

    end = actuator.index(
        "@callback\n    def _cancel_assist_off",
        start,
    )

    assist = actuator[start:end]

    assert "if not self._assist_requested:" in assist
    assert "CENTRAL_ASSIST_REFRESH_SECONDS" in assist
    assert "_assist_last_refresh_monotonic" in assist

    shutdown_start = actuator.index(
        "async def async_shutdown"
    )

    shutdown = actuator[shutdown_start:]

    assert "if self._assist_requested:" in shutdown


def test_booster_reconciliation_uses_command_cache_and_watchdog() -> None:
    """Do not depend solely on potentially stale Tuya feedback."""

    actuator = read("actuator.py")

    assert "_last_commanded_speeds" in actuator
    assert "force_reconcile" in actuator
    assert (
        "self._observer.last_watchdog"
        in actuator
    )

    assert (
        "SERVICE_SET_PRESET_MODE"
        in actuator
    )

    assert (
        "SERVICE_SET_PERCENTAGE"
        in actuator
    )

    assert (
        "SERVICE_TURN_ON"
        in actuator
    )


def test_production_flow_rejects_ambiguous_zone_mappings() -> None:
    """Prevent multiple logical zones from commanding the same hardware."""

    flow = read("config_flow.py")
    strings = read("strings.json")

    assert "duplicate_zone_temperature" in flow
    assert "duplicate_zone_fan" in flow
    assert "reference_matches_zone" in flow

    assert "duplicate_zone_temperature" in strings
    assert "duplicate_zone_fan" in strings
    assert "reference_matches_zone" in strings
