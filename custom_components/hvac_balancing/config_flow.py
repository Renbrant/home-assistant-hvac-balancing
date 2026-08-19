"""Config and options flows for HVAC Balancing."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .configuration import (
    merged_entry_config,
    normalize_zone_records,
    validate_zone_records,
)
from .const import (
    CENTRAL_ASSIST_MODE_CLIMATE,
    CENTRAL_ASSIST_MODE_DISABLED,
    CENTRAL_ASSIST_MODE_FAN,
    CENTRAL_ASSIST_MODE_NEST,
    CONF_ACTUATION_ENABLED,
    CONF_CENTRAL_ASSIST_ENTITY,
    CONF_CENTRAL_ASSIST_MODE,
    CONF_CENTRAL_ASSIST_OFF_MODE,
    CONF_CENTRAL_ASSIST_ON_MODE,
    CONF_ADD_ANOTHER_ZONE,
    CONF_CONFIRM_REMOVE,
    CONF_REFERENCE_SENSOR,
    CONF_RUNTIME_MODE,
    CONF_THERMOSTAT,
    CONF_ZONE_FAN,
    CONF_ZONE_ID,
    CONF_ZONE_NAME,
    CONF_ZONE_TEMPERATURE,
    CONF_ZONE_TO_EDIT,
    CONF_ZONE_TO_REMOVE,
    CONF_ZONES,
    DEFAULT_CENTRAL_ASSIST_MODE,
    DOMAIN,
    NAME,
    RUNTIME_MODE_PRODUCTION,
    RUNTIME_MODE_TEST_BENCH,
)


def _entity_selector(domain: str) -> EntitySelector:
    """Return a single-entity selector for one HA domain."""

    return EntitySelector(
        EntitySelectorConfig(
            domain=domain
        )
    )


CENTRAL_ASSIST_OPTIONS = [
    SelectOptionDict(
        value=CENTRAL_ASSIST_MODE_DISABLED,
        label="Disabled",
    ),
    SelectOptionDict(
        value=CENTRAL_ASSIST_MODE_FAN,
        label="Fan entity",
    ),
    SelectOptionDict(
        value=CENTRAL_ASSIST_MODE_CLIMATE,
        label="Climate fan mode",
    ),
    SelectOptionDict(
        value=CENTRAL_ASSIST_MODE_NEST,
        label="Nest fan timer",
    ),
]


def _central_assist_mode_schema(
    default: str = DEFAULT_CENTRAL_ASSIST_MODE,
) -> vol.Schema:
    """Return the Central Assist strategy selector."""

    return vol.Schema(
        {
            vol.Required(
                CONF_CENTRAL_ASSIST_MODE,
                default=default,
            ): SelectSelector(
                SelectSelectorConfig(
                    options=CENTRAL_ASSIST_OPTIONS,
                    mode=SelectSelectorMode.DROPDOWN,
                )
            )
        }
    )


def _central_assist_fan_schema(
    default: str | None = None,
) -> vol.Schema:
    """Return Central Assist fan-entity configuration."""

    configured_default: Any = vol.UNDEFINED

    if default:
        configured_default = default

    return vol.Schema(
        {
            vol.Required(
                CONF_CENTRAL_ASSIST_ENTITY,
                default=configured_default,
            ): _entity_selector("fan")
        }
    )


def _central_assist_climate_schema(
    fan_mode_on: str = "on",
    fan_mode_off: str = "off",
) -> vol.Schema:
    """Return generic climate fan-mode configuration."""

    return vol.Schema(
        {
            vol.Required(
                CONF_CENTRAL_ASSIST_ON_MODE,
                default=fan_mode_on,
            ): str,
            vol.Required(
                CONF_CENTRAL_ASSIST_OFF_MODE,
                default=fan_mode_off,
            ): str,
        }
    )


def _production_schema() -> vol.Schema:
    """Return system-level production configuration."""

    return vol.Schema(
        {
            vol.Required(CONF_THERMOSTAT): _entity_selector(
                "climate"
            ),
            vol.Required(CONF_REFERENCE_SENSOR): _entity_selector(
                "sensor"
            ),
            vol.Required(
                CONF_ACTUATION_ENABLED,
                default=False,
            ): bool,
        }
    )


def _zone_schema(
    defaults: dict[str, Any] | None = None,
    *,
    include_add_another: bool,
) -> vol.Schema:
    """Return one dynamic zone form."""

    values = defaults or {}

    schema: dict[Any, Any] = {
        vol.Required(
            CONF_ZONE_NAME,
            default=values.get(
                CONF_ZONE_NAME,
                "Zone",
            ),
        ): str,
        vol.Required(
            CONF_ZONE_TEMPERATURE,
            default=values.get(
                CONF_ZONE_TEMPERATURE,
                vol.UNDEFINED,
            ),
        ): _entity_selector("sensor"),
        vol.Required(
            CONF_ZONE_FAN,
            default=values.get(
                CONF_ZONE_FAN,
                vol.UNDEFINED,
            ),
        ): _entity_selector("fan"),
    }

    if include_add_another:
        schema[
            vol.Required(
                CONF_ADD_ANOTHER_ZONE,
                default=True,
            )
        ] = bool

    return vol.Schema(schema)


def _zone_record(
    user_input: dict[str, Any],
    *,
    zone_id: str,
) -> dict[str, str]:
    """Build one normalized zone record from form data."""

    return {
        CONF_ZONE_ID: zone_id,
        CONF_ZONE_NAME: str(
            user_input[CONF_ZONE_NAME]
        ).strip(),
        CONF_ZONE_TEMPERATURE: str(
            user_input[CONF_ZONE_TEMPERATURE]
        ),
        CONF_ZONE_FAN: str(
            user_input[CONF_ZONE_FAN]
        ),
    }


class HVACBalancingConfigFlow(
    ConfigFlow,
    domain=DOMAIN,
):
    """Handle HVAC Balancing initial configuration."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize setup wizard state."""

        self._production_data: dict[str, Any] = {}
        self._central_assist_data: dict[str, Any] = {
            CONF_CENTRAL_ASSIST_MODE: DEFAULT_CENTRAL_ASSIST_MODE,
        }
        self._zones: list[dict[str, str]] = []

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> "HVACBalancingOptionsFlow":
        """Return the runtime reconfiguration flow."""

        return HVACBalancingOptionsFlow(
            config_entry
        )

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Choose Test Bench or production runtime."""

        if self._async_current_entries():
            return self.async_abort(
                reason="single_instance_allowed"
            )

        return self.async_show_menu(
            step_id="user",
            menu_options=[
                "test_bench",
                "production",
            ],
        )

    async def async_step_test_bench(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Create the safe virtual Test Bench."""

        if user_input is not None:
            return self.async_create_entry(
                title=f"{NAME} Test Bench",
                data={
                    CONF_RUNTIME_MODE: RUNTIME_MODE_TEST_BENCH,
                },
            )

        return self.async_show_form(
            step_id="test_bench",
            data_schema=vol.Schema({}),
        )

    async def async_step_production(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Configure thermostat/reference before adding zones."""

        errors: dict[str, str] = {}

        if user_input is not None:
            if not user_input.get(
                CONF_ACTUATION_ENABLED,
                False,
            ):
                errors["base"] = (
                    "actuation_confirmation_required"
                )

            if not errors:
                self._production_data = {
                    CONF_THERMOSTAT: user_input[
                        CONF_THERMOSTAT
                    ],
                    CONF_REFERENCE_SENSOR: user_input[
                        CONF_REFERENCE_SENSOR
                    ],
                    CONF_ACTUATION_ENABLED: True,
                }

                self._zones = []
                self._central_assist_data = {
                    CONF_CENTRAL_ASSIST_MODE: DEFAULT_CENTRAL_ASSIST_MODE,
                }

                return await self.async_step_production_central_assist()

        return self.async_show_form(
            step_id="production",
            data_schema=_production_schema(),
            errors=errors,
        )

    async def async_step_production_central_assist(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Choose how Central Assist is physically actuated."""

        if user_input is not None:
            mode = str(
                user_input[
                    CONF_CENTRAL_ASSIST_MODE
                ]
            )

            self._central_assist_data = {
                CONF_CENTRAL_ASSIST_MODE: mode,
            }

            if mode == CENTRAL_ASSIST_MODE_FAN:
                return await self.async_step_production_central_assist_fan()

            if mode == CENTRAL_ASSIST_MODE_CLIMATE:
                return await self.async_step_production_central_assist_climate()

            return await self.async_step_production_zone()

        return self.async_show_form(
            step_id="production_central_assist",
            data_schema=_central_assist_mode_schema(),
        )

    async def async_step_production_central_assist_fan(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Choose a fan entity for Central Assist."""

        if user_input is not None:
            self._central_assist_data[
                CONF_CENTRAL_ASSIST_ENTITY
            ] = str(
                user_input[
                    CONF_CENTRAL_ASSIST_ENTITY
                ]
            )

            return await self.async_step_production_zone()

        return self.async_show_form(
            step_id="production_central_assist_fan",
            data_schema=_central_assist_fan_schema(),
        )

    async def async_step_production_central_assist_climate(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Configure generic climate fan modes for Central Assist."""

        if user_input is not None:
            self._central_assist_data[
                CONF_CENTRAL_ASSIST_ON_MODE
            ] = str(
                user_input[
                    CONF_CENTRAL_ASSIST_ON_MODE
                ]
            ).strip()

            self._central_assist_data[
                CONF_CENTRAL_ASSIST_OFF_MODE
            ] = str(
                user_input[
                    CONF_CENTRAL_ASSIST_OFF_MODE
                ]
            ).strip()

            return await self.async_step_production_zone()

        return self.async_show_form(
            step_id="production_central_assist_climate",
            data_schema=_central_assist_climate_schema(),
        )

    async def async_step_production_zone(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Add as many balancing zones as the user needs."""

        errors: dict[str, str] = {}

        if user_input is not None:
            zone = _zone_record(
                user_input,
                zone_id=uuid4().hex[:12],
            )

            proposed = [
                *self._zones,
                zone,
            ]

            error = validate_zone_records(
                proposed,
                self._production_data[
                    CONF_REFERENCE_SENSOR
                ],
            )

            if error is not None:
                errors["base"] = error

            if not errors:
                self._zones = proposed

                add_another = bool(
                    user_input.get(
                        CONF_ADD_ANOTHER_ZONE,
                        False,
                    )
                )

                if add_another:
                    return self.async_show_form(
                        step_id="production_zone",
                        data_schema=_zone_schema(
                            include_add_another=True
                        ),
                    )

                return self.async_create_entry(
                    title=f"{NAME} Production",
                    data={
                        CONF_RUNTIME_MODE: RUNTIME_MODE_PRODUCTION,
                        **self._production_data,
                        **self._central_assist_data,
                        CONF_ZONES: self._zones,
                    },
                )

        return self.async_show_form(
            step_id="production_zone",
            data_schema=_zone_schema(
                user_input,
                include_add_another=True,
            ),
            errors=errors,
        )


class HVACBalancingOptionsFlow(OptionsFlow):
    """Edit production entities and dynamic zones after setup."""

    def __init__(
        self,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize from merged entry data/options."""

        self._entry = config_entry

        config = merged_entry_config(
            config_entry
        )

        self._runtime_mode = config_entry.data.get(
            CONF_RUNTIME_MODE,
            RUNTIME_MODE_TEST_BENCH,
        )

        self._thermostat = str(
            config.get(
                CONF_THERMOSTAT,
                "",
            )
        )

        self._reference_sensor = str(
            config.get(
                CONF_REFERENCE_SENSOR,
                "",
            )
        )

        self._central_assist_mode = str(
            config.get(
                CONF_CENTRAL_ASSIST_MODE,
                DEFAULT_CENTRAL_ASSIST_MODE,
            )
        )

        self._central_assist_entity = str(
            config.get(
                CONF_CENTRAL_ASSIST_ENTITY,
                "",
            )
        )

        self._central_assist_on_mode = str(
            config.get(
                CONF_CENTRAL_ASSIST_ON_MODE,
                "on",
            )
        )

        self._central_assist_off_mode = str(
            config.get(
                CONF_CENTRAL_ASSIST_OFF_MODE,
                "off",
            )
        )

        self._zones = normalize_zone_records(
            config.get(
                CONF_ZONES,
                [],
            )
        )

        self._selected_zone_id: str | None = None

    def _finish(self) -> ConfigFlowResult:
        """Store complete editable configuration in entry options."""

        data: dict[str, Any] = {
            CONF_THERMOSTAT: self._thermostat,
            CONF_REFERENCE_SENSOR: self._reference_sensor,
            CONF_CENTRAL_ASSIST_MODE: self._central_assist_mode,
            CONF_ZONES: self._zones,
        }

        if self._central_assist_mode == CENTRAL_ASSIST_MODE_FAN:
            data[
                CONF_CENTRAL_ASSIST_ENTITY
            ] = self._central_assist_entity

        if self._central_assist_mode == CENTRAL_ASSIST_MODE_CLIMATE:
            data[
                CONF_CENTRAL_ASSIST_ON_MODE
            ] = self._central_assist_on_mode

            data[
                CONF_CENTRAL_ASSIST_OFF_MODE
            ] = self._central_assist_off_mode

        return self.async_create_entry(
            title="",
            data=data,
        )

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Show production reconfiguration menu."""

        if self._runtime_mode != RUNTIME_MODE_PRODUCTION:
            return self.async_abort(
                reason="test_bench_has_no_options"
            )

        return self.async_show_menu(
            step_id="init",
            menu_options=[
                "system",
                "central_assist",
                "add_zone",
                "edit_zone",
                "remove_zone",
            ],
        )

    async def async_step_system(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Change thermostat or reference temperature sensor."""

        errors: dict[str, str] = {}

        if user_input is not None:
            new_reference = str(
                user_input[
                    CONF_REFERENCE_SENSOR
                ]
            )

            error = validate_zone_records(
                self._zones,
                new_reference,
            )

            if error is not None:
                errors["base"] = error

            if not errors:
                self._thermostat = str(
                    user_input[
                        CONF_THERMOSTAT
                    ]
                )

                self._reference_sensor = new_reference

                return self._finish()

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_THERMOSTAT,
                    default=self._thermostat,
                ): _entity_selector("climate"),
                vol.Required(
                    CONF_REFERENCE_SENSOR,
                    default=self._reference_sensor,
                ): _entity_selector("sensor"),
            }
        )

        return self.async_show_form(
            step_id="system",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_central_assist(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Change the Central Assist actuation strategy."""

        if user_input is not None:
            self._central_assist_mode = str(
                user_input[
                    CONF_CENTRAL_ASSIST_MODE
                ]
            )

            if self._central_assist_mode == CENTRAL_ASSIST_MODE_FAN:
                return await self.async_step_central_assist_fan()

            if self._central_assist_mode == CENTRAL_ASSIST_MODE_CLIMATE:
                return await self.async_step_central_assist_climate()

            self._central_assist_entity = ""
            self._central_assist_on_mode = "on"
            self._central_assist_off_mode = "off"

            return self._finish()

        return self.async_show_form(
            step_id="central_assist",
            data_schema=_central_assist_mode_schema(
                self._central_assist_mode
            ),
        )

    async def async_step_central_assist_fan(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Configure a dedicated Central Assist fan entity."""

        if user_input is not None:
            self._central_assist_entity = str(
                user_input[
                    CONF_CENTRAL_ASSIST_ENTITY
                ]
            )

            self._central_assist_on_mode = "on"
            self._central_assist_off_mode = "off"

            return self._finish()

        return self.async_show_form(
            step_id="central_assist_fan",
            data_schema=_central_assist_fan_schema(
                self._central_assist_entity
                or None
            ),
        )

    async def async_step_central_assist_climate(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Configure generic climate fan modes."""

        if user_input is not None:
            self._central_assist_on_mode = str(
                user_input[
                    CONF_CENTRAL_ASSIST_ON_MODE
                ]
            ).strip()

            self._central_assist_off_mode = str(
                user_input[
                    CONF_CENTRAL_ASSIST_OFF_MODE
                ]
            ).strip()

            self._central_assist_entity = ""

            return self._finish()

        return self.async_show_form(
            step_id="central_assist_climate",
            data_schema=_central_assist_climate_schema(
                self._central_assist_on_mode,
                self._central_assist_off_mode,
            ),
        )

    async def async_step_add_zone(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Add one zone without reinstalling the integration."""

        errors: dict[str, str] = {}

        if user_input is not None:
            zone = _zone_record(
                user_input,
                zone_id=uuid4().hex[:12],
            )

            proposed = [
                *self._zones,
                zone,
            ]

            error = validate_zone_records(
                proposed,
                self._reference_sensor,
            )

            if error is not None:
                errors["base"] = error

            if not errors:
                self._zones = proposed

                return self._finish()

        return self.async_show_form(
            step_id="add_zone",
            data_schema=_zone_schema(
                user_input,
                include_add_another=False,
            ),
            errors=errors,
        )

    async def async_step_edit_zone(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Choose which existing zone to edit."""

        if user_input is not None:
            self._selected_zone_id = str(
                user_input[
                    CONF_ZONE_TO_EDIT
                ]
            )

            return await self.async_step_edit_zone_detail()

        choices = {
            zone[CONF_ZONE_ID]: zone[CONF_ZONE_NAME]
            for zone in self._zones
        }

        return self.async_show_form(
            step_id="edit_zone",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_ZONE_TO_EDIT
                    ): vol.In(choices)
                }
            ),
        )

    async def async_step_edit_zone_detail(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Edit one selected zone while preserving its stable ID."""

        target = None

        for zone in self._zones:
            if zone[CONF_ZONE_ID] == self._selected_zone_id:
                target = zone
                break

        if target is None:
            return self.async_abort(
                reason="unknown_zone"
            )

        errors: dict[str, str] = {}

        if user_input is not None:
            edited = _zone_record(
                user_input,
                zone_id=target[CONF_ZONE_ID],
            )

            proposed = [
                edited
                if zone[CONF_ZONE_ID] == target[CONF_ZONE_ID]
                else zone
                for zone in self._zones
            ]

            error = validate_zone_records(
                proposed,
                self._reference_sensor,
            )

            if error is not None:
                errors["base"] = error

            if not errors:
                self._zones = proposed

                return self._finish()

        return self.async_show_form(
            step_id="edit_zone_detail",
            data_schema=_zone_schema(
                target,
                include_add_another=False,
            ),
            errors=errors,
        )

    async def async_step_remove_zone(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Remove one zone while always retaining at least one."""

        if len(self._zones) <= 1:
            return self.async_abort(
                reason="minimum_one_zone"
            )

        errors: dict[str, str] = {}

        if user_input is not None:
            confirmed = bool(
                user_input.get(
                    CONF_CONFIRM_REMOVE,
                    False,
                )
            )

            if not confirmed:
                errors["base"] = (
                    "remove_confirmation_required"
                )

            if not errors:
                zone_id = str(
                    user_input[
                        CONF_ZONE_TO_REMOVE
                    ]
                )

                proposed = [
                    zone
                    for zone in self._zones
                    if zone[CONF_ZONE_ID] != zone_id
                ]

                error = validate_zone_records(
                    proposed,
                    self._reference_sensor,
                )

                if error is not None:
                    errors["base"] = error

                if not errors:
                    self._zones = proposed

                    return self._finish()

        choices = {
            zone[CONF_ZONE_ID]: zone[CONF_ZONE_NAME]
            for zone in self._zones
        }

        return self.async_show_form(
            step_id="remove_zone",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_ZONE_TO_REMOVE
                    ): vol.In(choices),
                    vol.Required(
                        CONF_CONFIRM_REMOVE,
                        default=False,
                    ): bool,
                }
            ),
            errors=errors,
        )
