"""Constants for the HVAC Balancing integration."""

DOMAIN = "hvac_balancing"
NAME = "HVAC Balancing"
VERSION = "0.2.10"

RUNTIME_MODE_TEST_BENCH = "test_bench"
RUNTIME_MODE_PRODUCTION = "production_active"

CENTRAL_ASSIST_MODE_DISABLED = "disabled"
CENTRAL_ASSIST_MODE_FAN = "fan_entity"
CENTRAL_ASSIST_MODE_CLIMATE = "climate_fan_mode"
CENTRAL_ASSIST_MODE_NEST = "nest_fan_timer"
DEFAULT_CENTRAL_ASSIST_MODE = CENTRAL_ASSIST_MODE_DISABLED

CONF_RUNTIME_MODE = "runtime_mode"
CONF_ACTUATION_ENABLED = "actuation_enabled"

CONF_THERMOSTAT = "thermostat"
CONF_REFERENCE_SENSOR = "reference_sensor"

CONF_CENTRAL_ASSIST_MODE = "central_assist_mode"
CONF_CENTRAL_ASSIST_ENTITY = "central_assist_entity"
CONF_CENTRAL_ASSIST_ON_MODE = "central_assist_on_mode"
CONF_CENTRAL_ASSIST_OFF_MODE = "central_assist_off_mode"

CONF_ZONES = "zones"
CONF_ZONE_ID = "id"
CONF_ZONE_NAME = "name"
CONF_ZONE_TEMPERATURE = "temperature_sensor"
CONF_ZONE_FAN = "booster_fan"

# Config-flow-only fields.
CONF_ADD_ANOTHER_ZONE = "add_another_zone"
CONF_ZONE_TO_EDIT = "zone_to_edit"
CONF_ZONE_TO_REMOVE = "zone_to_remove"
CONF_CONFIRM_REMOVE = "confirm_remove"

DEFAULT_OBSERVATION_ONLY = True
