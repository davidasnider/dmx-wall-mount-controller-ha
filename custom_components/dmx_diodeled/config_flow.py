from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_NAME, CONF_PORT
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_ZONES,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_ZONES,
    DOMAIN,
    ZONES,
)
from .dmx_controller import DiodLEDController

# SECURITY: Add length limit to prevent potential DoS from oversized inputs.
# vol.Strip runs before the length check, so a blank (whitespace-only) value
# is rejected during schema validation instead of passing Length(min=1) and
# being reduced to "" afterwards.
_HOST_VALIDATOR = vol.All(str, vol.Strip, vol.Length(min=1, max=253))
_PORT_VALIDATOR = vol.All(int, vol.Range(min=1, max=65535))
# SECURITY: Add length limit to prevent potential DoS from oversized inputs
_NAME_VALIDATOR = vol.All(str, vol.Strip, vol.Length(min=1, max=100))

# SECURITY: A discovery MAC is untrusted UDP input. It becomes the entry's
# unique ID and, via device_info(), the device registry's network-MAC connection —
# i.e. part of what identifies this device in Home Assistant, and the key
# discovery uses to re-find an existing entry. Only a real 48-bit MAC may become
# that identity: twelve hex digits, bare or with a consistent ":"/"-"
# separator (the forms the discovery firmware broadcasts; dotted, mixed and
# other spellings are rejected). Accepted spellings normalize to one canonical
# form, so a device always dedupes to the same unique ID. Anything else is
# treated like a manual entry (no MAC identity), so an attacker on the LAN
# cannot choose the string that identifies a device in the registry. Note:
# HA core's format_mac() does NOT raise on malformed input (it returns it
# unchanged), so this is identity hardening, not a crash fix.
_MAC_HEX_DIGITS = frozenset("0123456789abcdef")


def _mac_is_well_formed(mac: str) -> bool:
    """Return True if mac is a 48-bit MAC in an accepted spelling.

    Accepted: twelve bare hex digits, or six two-digit hex groups joined by a
    single consistent separator (":" or "-"). Mixed or misplaced separators are
    rejected so each MAC has exactly one accepted spelling.
    """
    if ":" in mac:
        groups = mac.split(":")
    elif "-" in mac:
        groups = mac.split("-")
    else:
        return len(mac) == 12 and set(mac).issubset(_MAC_HEX_DIGITS)

    return len(groups) == 6 and all(
        len(group) == 2 and set(group).issubset(_MAC_HEX_DIGITS) for group in groups
    )


def _mac_canonical_id(mac: str) -> str:
    """Return the canonical "aa:bb:cc:dd:ee:ff" unique ID for a well-formed mac.

    Every accepted spelling (bare hex, ":" or "-" separated) maps to the same
    form, so a device that broadcasts different spellings of its MAC still
    dedupes to one unique ID. Callers must pass a lowercased mac (see the flow).
    """
    digits = mac.replace(":", "").replace("-", "")
    return ":".join(digits[i : i + 2] for i in range(0, 12, 2))


async def _async_can_connect(host: str, port: int) -> bool:
    """Return True if the controller accepts a TCP connection."""
    try:
        await DiodLEDController(host, port).async_check_connection()
    except OSError:
        return False
    return True


class DiodLEDConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for DiodeLED DMX Controller."""

    # v2: discovery MACs are stored as the canonical "aa:bb:cc:dd:ee:ff"
    # unique ID. v1 entries stored the MAC verbatim (bare hex or as broadcast);
    # async_migrate_entry in __init__.py rewrites them so existing installs
    # keep deduping against rebroadcasts after the upgrade.
    VERSION = 2
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
            # The validators above strip surrounding whitespace (and reject
            # blank values) during schema validation. Normalize again here so a
            # whitespace-only host can never reach the connection check or be
            # stored, even if this step is called without schema validation.
            user_input[CONF_HOST] = user_input[CONF_HOST].strip()
            if CONF_NAME in user_input and isinstance(user_input[CONF_NAME], str):
                # A whitespace-only name would otherwise become an empty title.
                user_input[CONF_NAME] = user_input[CONF_NAME].strip() or DEFAULT_NAME
            if user_input[CONF_HOST]:
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
                        vol.Optional(CONF_NAME, default=DEFAULT_NAME): _NAME_VALIDATOR,
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
            # The validator strips surrounding whitespace (and rejects blank
            # values) during schema validation; normalize again here so a
            # whitespace-only host can never reach the connection check.
            user_input[CONF_HOST] = user_input[CONF_HOST].strip()
            host = user_input[CONF_HOST]
            port = user_input.get(CONF_PORT, DEFAULT_PORT)
            if host:
                # Do not let two entries point at the same controller. The entry's
                # own host is excluded so saving it unchanged is allowed.
                if host != entry.data[CONF_HOST]:
                    self._async_abort_entries_match({CONF_HOST: host})
                if await _async_can_connect(host, port):
                    # Update the entry only; do not use async_update_reload_and_abort
                    # here. Updating the entry fires the update listener registered in
                    # async_setup_entry, and that schedules the one reload. A second,
                    # flow-scheduled reload would overlap it on the single-connection
                    # controller.
                    return self.async_update_and_abort(
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
            # or whitespace still dedupe to the same unique_id; separator layout
            # is canonicalized by _mac_canonical_id.
            mac = mac.strip().lower()
            # SECURITY: Only well-formed MACs may become unique IDs (see
            # _mac_is_well_formed). An attacker on the LAN can put any string in
            # this field, and a unique ID becomes the device's network-MAC
            # connection in the registry; anything non-MAC-shaped falls back to
            # host-based identification instead of becoming device identity.
            if _mac_is_well_formed(mac):
                # Canonicalize so ":" and "-" spellings of the same MAC map to
                # one unique ID instead of splitting the device into duplicate
                # identities.
                await self.async_set_unique_id(_mac_canonical_id(mac))
                # Core defaults to reload_on_update=True, which would schedule a
                # second reload on top of the entry's update listener (registered in
                # async_setup_entry) — the single place a reload is scheduled. Keep
                # core's reload off so a discovery-driven host change reloads the
                # entry exactly once.
                self._abort_if_unique_id_configured(
                    updates={CONF_HOST: host}, reload_on_update=False
                )

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
