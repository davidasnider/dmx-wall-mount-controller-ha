import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_NAME, CONF_MAC
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from typing import Any

from .const import (
    CONF_ZONES,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_ZONES,
    DOMAIN,
    ZONES,
)
from .dmx_controller import DiodLEDController

# SECURITY: Add length limit to prevent potential DoS from oversized inputs
_HOST_VALIDATOR = vol.All(str, vol.Length(min=1, max=253))
_PORT_VALIDATOR = vol.All(int, vol.Range(min=1, max=65535))


async def _async_can_connect(host: str, port: int) -> bool:
    """Return True if the controller accepts a TCP connection."""
    try:
        await DiodLEDController(host, port).async_check_connection()
    except OSError:
        return False
    return True


class DiodLEDConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for DiodeLED DMX Controller."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> "DiodLEDOptionsFlow":
        """Return the options flow (zone selection)."""
        return DiodLEDOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            # Manual entries have no MAC address (and so no unique_id), so
            # dedupe them by host instead.
            self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})
            # The controller is write-only and never answers, so accepting a
            # TCP connection is the only check available.
            if await _async_can_connect(
                user_input[CONF_HOST], user_input.get(CONF_PORT, DEFAULT_PORT)
            ):
                return self.async_create_entry(
                    title=user_input.get(CONF_NAME, DEFAULT_NAME), data=user_input
                )
            errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required(CONF_HOST): _HOST_VALIDATOR,
                        vol.Optional(CONF_PORT, default=DEFAULT_PORT): _PORT_VALIDATOR,
                        # SECURITY: Add length limit to prevent potential DoS from oversized inputs
                        vol.Optional(CONF_NAME, default=DEFAULT_NAME): vol.All(
                            str, vol.Length(min=1, max=100)
                        ),
                    }
                ),
                # Keep what the user typed when the form is shown again with an error.
                user_input or {},
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Change the host or port of an existing controller."""
        entry = self._get_reconfigure_entry()
        errors = {}
        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input.get(CONF_PORT, DEFAULT_PORT)
            # Do not let two entries point at the same controller. The entry's
            # own host is excluded so saving it unchanged is allowed.
            if host != entry.data[CONF_HOST]:
                self._async_abort_entries_match({CONF_HOST: host})
            if await _async_can_connect(host, port):
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_HOST: host, CONF_PORT: port}
                )
            errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required(CONF_HOST): _HOST_VALIDATOR,
                        vol.Required(CONF_PORT): _PORT_VALIDATOR,
                    }
                ),
                user_input
                or {
                    CONF_HOST: entry.data[CONF_HOST],
                    CONF_PORT: entry.data.get(CONF_PORT, DEFAULT_PORT),
                },
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

        # A manually added entry for this host has no unique_id, so the MAC
        # check above cannot match it; do not offer the controller again.
        self._async_abort_entries_match({CONF_HOST: host})

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


class DiodLEDOptionsFlow(config_entries.OptionsFlow):
    """Choose which of the controller's zones get entities."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Manage the zone selection."""
        errors = {}
        if user_input is not None:
            zones = sorted(int(zone) for zone in user_input[CONF_ZONES])
            if zones:
                return self.async_create_entry(data={CONF_ZONES: zones})
            errors["base"] = "no_zones"

        current = self.config_entry.options.get(CONF_ZONES, DEFAULT_ZONES)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    # multi_select works with string keys; stored as ints above.
                    vol.Required(
                        CONF_ZONES, default=[str(zone) for zone in current]
                    ): cv.multi_select({str(zone): f"Zone {zone}" for zone in ZONES}),
                }
            ),
            errors=errors,
        )
