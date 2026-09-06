import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_NAME, CONF_MAC
from typing import Any

from .const import DOMAIN, DEFAULT_PORT, DEFAULT_NAME


class DiodLEDConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for DiodeLED DMX Controller."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            # We could add a connection test here
            # But the PRD says it's purely write-only, so a simple check is enough
            return self.async_create_entry(
                title=user_input.get(CONF_NAME, DEFAULT_NAME), data=user_input
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    # SECURITY: Add length limit to prevent potential DoS from oversized inputs
                    vol.Required(CONF_HOST): vol.All(str, vol.Length(min=1, max=253)),
                    vol.Optional(CONF_PORT, default=DEFAULT_PORT): vol.All(
                        int, vol.Range(min=1, max=65535)
                    ),
                    # SECURITY: Add length limit to prevent potential DoS from oversized inputs
                    vol.Optional(CONF_NAME, default=DEFAULT_NAME): vol.All(
                        str, vol.Length(min=1, max=100)
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_integration_discovery(
        self, discovery_info: dict[str, Any]
    ) -> config_entries.ConfigFlowResult:
        """Handle integration discovery."""
        host = discovery_info[CONF_HOST]
        mac = discovery_info.get(CONF_MAC)

        if mac:
            # Normalize (strip/lowercase) so broadcasts with different casing
            # or whitespace still dedupe to the same unique_id.
            mac = mac.strip().lower()
            await self.async_set_unique_id(mac)
            self._abort_if_unique_id_configured(updates={CONF_HOST: host})

        self.context["title_placeholders"] = {"host": host}

        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Confirm discovery."""
        if user_input is not None:
            return self.async_create_entry(
                title=f"DiodeLED DMX ({self.context['title_placeholders']['host']})",
                data={
                    CONF_HOST: self.context["title_placeholders"]["host"],
                    CONF_PORT: DEFAULT_PORT,
                    CONF_NAME: DEFAULT_NAME,
                },
            )

        self._set_confirm_only()
        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders={
                "host": self.context["title_placeholders"]["host"]
            },
        )
