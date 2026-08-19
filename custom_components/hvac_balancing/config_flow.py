"""Config flow for HVAC Balancing."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
)

from .const import (
    CONF_ACTUATION_ENABLED,
    CONF_REFERENCE_SENSOR,
    CONF_RUNTIME_MODE,
    CONF_THERMOSTAT,
    CONF_ZONE_1_FAN,
    CONF_ZONE_1_NAME,
    CONF_ZONE_1_TEMPERATURE,
    CONF_ZONE_2_FAN,
    CONF_ZONE_2_NAME,
    CONF_ZONE_2_TEMPERATURE,
    CONF_ZONE_3_FAN,
    CONF_ZONE_3_NAME,
    CONF_ZONE_3_TEMPERATURE,
    DOMAIN,
    NAME,
    RUNTIME_MODE_PRODUCTION,
    RUNTIME_MODE_TEST_BENCH,
)


def _production_schema() -> vol.Schema:
    """Return current three-zone production setup schema."""

    return vol.Schema(
        {
            vol.Required(CONF_THERMOSTAT): EntitySelector(
                EntitySelectorConfig(
                    domain="climate"
                )
            ),
            vol.Required(CONF_REFERENCE_SENSOR): EntitySelector(
                EntitySelectorConfig(
                    domain="sensor"
                )
            ),
            vol.Required(
                CONF_ZONE_1_NAME,
                default="Bed 1",
            ): str,
            vol.Required(CONF_ZONE_1_TEMPERATURE): EntitySelector(
                EntitySelectorConfig(
                    domain="sensor"
                )
            ),
            vol.Required(CONF_ZONE_1_FAN): EntitySelector(
                EntitySelectorConfig(
                    domain="fan"
                )
            ),
            vol.Required(
                CONF_ZONE_2_NAME,
                default="Bed 2",
            ): str,
            vol.Required(CONF_ZONE_2_TEMPERATURE): EntitySelector(
                EntitySelectorConfig(
                    domain="sensor"
                )
            ),
            vol.Required(CONF_ZONE_2_FAN): EntitySelector(
                EntitySelectorConfig(
                    domain="fan"
                )
            ),
            vol.Required(
                CONF_ZONE_3_NAME,
                default="Bed 3",
            ): str,
            vol.Required(CONF_ZONE_3_TEMPERATURE): EntitySelector(
                EntitySelectorConfig(
                    domain="sensor"
                )
            ),
            vol.Required(CONF_ZONE_3_FAN): EntitySelector(
                EntitySelectorConfig(
                    domain="fan"
                )
            ),
            vol.Required(
                CONF_ACTUATION_ENABLED,
                default=False,
            ): bool,
        }
    )


class HVACBalancingConfigFlow(
    config_entries.ConfigFlow,
    domain=DOMAIN,
):
    """Handle the HVAC Balancing config flow."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ):
        """Choose Test Bench or active production runtime."""

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
    ):
        """Create the safe Test Bench runtime."""

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
    ):
        """Create explicitly enabled active production runtime."""

        errors: dict[str, str] = {}

        if user_input is not None:
            if not user_input.get(
                CONF_ACTUATION_ENABLED,
                False,
            ):
                errors["base"] = (
                    "actuation_confirmation_required"
                )

            temperature_entity_ids = (
                user_input[CONF_ZONE_1_TEMPERATURE],
                user_input[CONF_ZONE_2_TEMPERATURE],
                user_input[CONF_ZONE_3_TEMPERATURE],
            )

            fan_entity_ids = (
                user_input[CONF_ZONE_1_FAN],
                user_input[CONF_ZONE_2_FAN],
                user_input[CONF_ZONE_3_FAN],
            )

            if (
                not errors
                and len(set(temperature_entity_ids))
                != len(temperature_entity_ids)
            ):
                errors["base"] = (
                    "duplicate_zone_temperature"
                )

            if (
                not errors
                and len(set(fan_entity_ids))
                != len(fan_entity_ids)
            ):
                errors["base"] = (
                    "duplicate_zone_fan"
                )

            if (
                not errors
                and user_input[CONF_REFERENCE_SENSOR]
                in temperature_entity_ids
            ):
                errors["base"] = (
                    "reference_matches_zone"
                )

            if not errors:
                return self.async_create_entry(
                    title=f"{NAME} Production",
                    data={
                        CONF_RUNTIME_MODE: RUNTIME_MODE_PRODUCTION,
                        **user_input,
                    },
                )

        return self.async_show_form(
            step_id="production",
            data_schema=_production_schema(),
            errors=errors,
        )
