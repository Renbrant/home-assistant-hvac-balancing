"""Unit tests for dynamic HVAC Balancing configuration."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest


ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "custom_components" / "hvac_balancing"


def load_module(
    module_name: str,
    path: Path,
):
    """Load one module without executing the integration package __init__."""

    spec = importlib.util.spec_from_file_location(
        module_name,
        path,
    )

    if spec is None:
        raise RuntimeError(
            f"Unable to create module spec for {path}"
        )

    if spec.loader is None:
        raise RuntimeError(
            f"Unable to create module loader for {path}"
        )

    module = importlib.util.module_from_spec(
        spec
    )

    sys.modules[module_name] = module
    spec.loader.exec_module(module)

    return module


# Python normally executes custom_components.hvac_balancing.__init__ before
# importing a submodule. The real __init__ correctly imports Home Assistant,
# but our workstation's isolated unit-test Python intentionally does not have
# Home Assistant installed.
#
# Create lightweight package namespaces so the pure configuration module and
# constants can be tested without importing the HA runtime.
custom_components_package = ModuleType(
    "custom_components"
)

custom_components_package.__path__ = [
    str(
        ROOT
        / "custom_components"
    )
]

hvac_balancing_package = ModuleType(
    "custom_components.hvac_balancing"
)

hvac_balancing_package.__path__ = [
    str(INTEGRATION)
]

sys.modules[
    "custom_components"
] = custom_components_package

sys.modules[
    "custom_components.hvac_balancing"
] = hvac_balancing_package


const = load_module(
    "custom_components.hvac_balancing.const",
    INTEGRATION / "const.py",
)

configuration = load_module(
    "custom_components.hvac_balancing.configuration",
    INTEGRATION / "configuration.py",
)


merged_entry_config = configuration.merged_entry_config
normalize_zone_records = configuration.normalize_zone_records
production_core_config = configuration.production_core_config
validate_zone_records = configuration.validate_zone_records
stale_production_zone_unique_ids = (
    configuration.stale_production_zone_unique_ids
)

CONF_REFERENCE_SENSOR = const.CONF_REFERENCE_SENSOR
CONF_THERMOSTAT = const.CONF_THERMOSTAT
CONF_ZONE_FAN = const.CONF_ZONE_FAN
CONF_ZONE_ID = const.CONF_ZONE_ID
CONF_ZONE_NAME = const.CONF_ZONE_NAME
CONF_ZONE_TEMPERATURE = const.CONF_ZONE_TEMPERATURE
CONF_ZONES = const.CONF_ZONES


def zone(
    zone_id: str,
    temperature: str,
    fan: str,
    name: str | None = None,
) -> dict[str, str]:
    """Create one test zone record."""

    return {
        CONF_ZONE_ID: zone_id,
        CONF_ZONE_NAME: name or zone_id,
        CONF_ZONE_TEMPERATURE: temperature,
        CONF_ZONE_FAN: fan,
    }


class DynamicZoneValidationTests(unittest.TestCase):
    """Verify arbitrary zone collections and mapping safety."""

    def test_one_zone_is_valid(self) -> None:
        zones = [
            zone(
                "zone-a",
                "sensor.room_a",
                "fan.room_a",
            )
        ]

        self.assertIsNone(
            validate_zone_records(
                zones,
                "sensor.reference",
            )
        )

    def test_five_zones_are_valid(self) -> None:
        zones = [
            zone(
                f"zone-{index}",
                f"sensor.room_{index}",
                f"fan.room_{index}",
            )
            for index in range(5)
        ]

        self.assertIsNone(
            validate_zone_records(
                zones,
                "sensor.reference",
            )
        )

    def test_zero_zones_is_rejected(self) -> None:
        self.assertEqual(
            validate_zone_records(
                [],
                "sensor.reference",
            ),
            "minimum_one_zone",
        )

    def test_duplicate_temperature_is_rejected(self) -> None:
        zones = [
            zone(
                "a",
                "sensor.same",
                "fan.a",
            ),
            zone(
                "b",
                "sensor.same",
                "fan.b",
            ),
        ]

        self.assertEqual(
            validate_zone_records(
                zones,
                "sensor.reference",
            ),
            "duplicate_zone_temperature",
        )

    def test_duplicate_fan_is_rejected(self) -> None:
        zones = [
            zone(
                "a",
                "sensor.a",
                "fan.same",
            ),
            zone(
                "b",
                "sensor.b",
                "fan.same",
            ),
        ]

        self.assertEqual(
            validate_zone_records(
                zones,
                "sensor.reference",
            ),
            "duplicate_zone_fan",
        )

    def test_duplicate_stable_id_is_rejected(self) -> None:
        zones = [
            zone(
                "same",
                "sensor.a",
                "fan.a",
            ),
            zone(
                "same",
                "sensor.b",
                "fan.b",
            ),
        ]

        self.assertEqual(
            validate_zone_records(
                zones,
                "sensor.reference",
            ),
            "duplicate_zone_id",
        )

    def test_reference_cannot_also_be_zone_sensor(self) -> None:
        zones = [
            zone(
                "a",
                "sensor.reference",
                "fan.a",
            )
        ]

        self.assertEqual(
            validate_zone_records(
                zones,
                "sensor.reference",
            ),
            "reference_matches_zone",
        )


class ConfigurationNormalizationTests(unittest.TestCase):
    """Verify persisted configuration is strict and predictable."""

    def test_normalize_preserves_arbitrary_zone_count(self) -> None:
        raw = [
            zone(
                f"id-{index}",
                f"sensor.temp_{index}",
                f"fan.booster_{index}",
            )
            for index in range(7)
        ]

        normalized = normalize_zone_records(
            raw
        )

        self.assertEqual(
            len(normalized),
            7,
        )

    def test_malformed_zone_record_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            normalize_zone_records(
                [
                    {
                        CONF_ZONE_ID: "a",
                        CONF_ZONE_NAME: "Room",
                    }
                ]
            )

    def test_merged_options_override_setup_mapping(self) -> None:
        entry = SimpleNamespace(
            data={
                CONF_THERMOSTAT: "climate.old",
                CONF_REFERENCE_SENSOR: "sensor.old",
                CONF_ZONES: [
                    zone(
                        "a",
                        "sensor.a",
                        "fan.a",
                    )
                ],
            },
            options={
                CONF_THERMOSTAT: "climate.new",
                CONF_REFERENCE_SENSOR: "sensor.new",
                CONF_ZONES: [
                    zone(
                        "b",
                        "sensor.b",
                        "fan.b",
                    )
                ],
            },
        )

        merged = merged_entry_config(
            entry
        )

        self.assertEqual(
            merged[CONF_THERMOSTAT],
            "climate.new",
        )

        self.assertEqual(
            merged[CONF_REFERENCE_SENSOR],
            "sensor.new",
        )

        self.assertEqual(
            merged[CONF_ZONES][0][CONF_ZONE_ID],
            "b",
        )

    def test_production_core_requires_thermostat_and_reference(self) -> None:
        with self.assertRaises(ValueError):
            production_core_config({})

        thermostat, reference = production_core_config(
            {
                CONF_THERMOSTAT: "climate.central",
                CONF_REFERENCE_SENSOR: "sensor.reference",
            }
        )

        self.assertEqual(
            thermostat,
            "climate.central",
        )

        self.assertEqual(
            reference,
            "sensor.reference",
        )


class ProductionEntityRegistryCleanupTests(unittest.TestCase):
    """Verify removed dynamic zones do not leave diagnostic entities behind."""

    def test_removed_zone_diagnostics_are_all_stale(self) -> None:
        active_zone = "active123"
        removed_zone = "removed456"

        active_ids = {
            f"production_{active_zone}_{suffix}"
            for suffix
            in configuration.PRODUCTION_ZONE_ENTITY_SUFFIXES
        }

        removed_ids = {
            f"production_{removed_zone}_{suffix}"
            for suffix
            in configuration.PRODUCTION_ZONE_ENTITY_SUFFIXES
        }

        global_ids = {
            "production_timeline_current_time",
            "production_timeline_last_controller_update",
            "production_central_assist",
        }

        stale = stale_production_zone_unique_ids(
            (
                active_ids
                | removed_ids
                | global_ids
            ),
            {active_zone},
        )

        self.assertEqual(
            stale,
            removed_ids,
        )

        self.assertEqual(
            len(stale),
            8,
        )

    def test_global_and_active_entities_are_preserved(self) -> None:
        active_zone = "abcdef123456"

        unique_ids = {
            f"production_{active_zone}_base_p",
            f"production_{active_zone}_adaptive_window",
            "production_timeline_current_time",
            "production_timeline_next_watchdog",
            "production_central_assist",
            "unrelated_integration_entity",
        }

        stale = stale_production_zone_unique_ids(
            unique_ids,
            {active_zone},
        )

        self.assertEqual(
            stale,
            set(),
        )


if __name__ == "__main__":
    unittest.main()
