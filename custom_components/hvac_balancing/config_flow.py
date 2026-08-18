"""Config flow for HVAC Balancing."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries

from .const import DOMAIN, NAME


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
        """Create the initial HVAC Balancing config entry.

        Phase 1 intentionally has no thermostat or balancing-zone
        configuration fields. Those are introduced in Phase 3.
        """

        if self._async_current_entries():
            return self.async_abort(
                reason="single_instance_allowed"
            )

        if user_input is not None:
            return self.async_create_entry(
                title=NAME,
                data={},
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({}),
        )
