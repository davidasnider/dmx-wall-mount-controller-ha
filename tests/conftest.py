"""Shared test setup: stand-ins for the Home Assistant modules we import.

The tests run without Home Assistant installed. The stubs are installed here,
once, before pytest imports any test module, so every test file sees the
same modules no matter which file is collected first.

Real module objects (not MagicMocks) are used so that a name the integration
imports but the stubs do not define fails loudly instead of silently becoming
a mock.
"""

import sys
import types
from typing import Any
from unittest.mock import MagicMock


def _install_module(name: str, **attributes: Any) -> types.ModuleType:
    """Register a stub module (and attach it to its parent package)."""
    module = types.ModuleType(name)
    module.__dict__.update(attributes)
    sys.modules[name] = module
    parent_name, _, child_name = name.rpartition(".")
    if parent_name:
        setattr(sys.modules[parent_name], child_name, module)
    return module


class AbortFlow(Exception):
    """Stand-in for homeassistant.data_entry_flow.AbortFlow."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class ConfigFlow:
    """Minimal stand-in for homeassistant.config_entries.ConfigFlow.

    Implements only the helpers the integration's flow uses, with the same
    abort semantics as Home Assistant core (raising AbortFlow).
    """

    def __init_subclass__(cls, domain: str | None = None, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)

    def __init__(self) -> None:
        self.context: dict[str, Any] = {}
        self.unique_id: str | None = None
        # Entries Home Assistant already has; tests fill this in. Each entry
        # needs ``data`` (dict) and ``unique_id`` attributes.
        self.current_entries: list[Any] = []

    async def async_set_unique_id(self, unique_id: str | None = None) -> None:
        self.unique_id = unique_id

    def _abort_if_unique_id_configured(
        self, updates: dict[str, Any] | None = None
    ) -> None:
        for entry in self.current_entries:
            if self.unique_id is not None and entry.unique_id == self.unique_id:
                if updates:
                    entry.data.update(updates)
                raise AbortFlow("already_configured")

    def _async_abort_entries_match(self, match_dict: dict[str, Any]) -> None:
        for entry in self.current_entries:
            if all(entry.data.get(key) == value for key, value in match_dict.items()):
                raise AbortFlow("already_configured")

    def _set_confirm_only(self) -> None:
        self.context["confirm_only"] = True

    def async_create_entry(self, *, title: str, data: dict[str, Any]) -> dict:
        return {"type": "create_entry", "title": title, "data": data}

    def async_show_form(self, *, step_id: str, **kwargs: Any) -> dict:
        return {"type": "form", "step_id": step_id, **kwargs}

    def add_suggested_values_to_schema(
        self, data_schema: Any, suggested_values: dict[str, Any]
    ) -> dict:
        # Returned as a dict so tests can check which values are suggested.
        return {"schema": data_schema, "suggested_values": suggested_values}

    def _get_reconfigure_entry(self) -> Any:
        return self.context["entry"]

    def async_update_reload_and_abort(
        self, entry: Any, *, data_updates: dict[str, Any]
    ) -> dict:
        entry.data.update(data_updates)
        return {"type": "abort", "reason": "reconfigure_successful"}


class OptionsFlow:
    """Minimal stand-in for homeassistant.config_entries.OptionsFlow."""

    # Home Assistant sets this on the flow before the first step runs.
    config_entry: Any = None

    def async_create_entry(self, *, data: dict[str, Any]) -> dict:
        return {"type": "create_entry", "data": data}

    def async_show_form(self, *, step_id: str, **kwargs: Any) -> dict:
        return {"type": "form", "step_id": step_id, **kwargs}


class LightEntity:
    """Minimal stand-in for homeassistant.components.light.LightEntity."""

    def async_write_ha_state(self) -> None:
        pass


class NumberEntity:
    """Minimal stand-in for homeassistant.components.number.NumberEntity."""

    def async_write_ha_state(self) -> None:
        pass


def format_mac(mac: str) -> str:
    """Stand-in for homeassistant.helpers.device_registry.format_mac."""
    mac = mac.lower().replace(":", "").replace("-", "")
    return ":".join(mac[i : i + 2] for i in range(0, 12, 2))


class RestoreEntity:
    """Minimal stand-in for homeassistant.helpers.restore_state.RestoreEntity."""

    async def async_added_to_hass(self) -> None:
        pass

    async def async_get_last_state(self) -> Any:
        return None


class HomeAssistantError(Exception):
    """Stand-in for homeassistant.exceptions.HomeAssistantError."""


_install_module("homeassistant")
_install_module(
    "homeassistant.config_entries",
    ConfigEntry=MagicMock,
    ConfigFlow=ConfigFlow,
    ConfigFlowResult=dict,
    OptionsFlow=OptionsFlow,
    CONN_CLASS_LOCAL_PUSH="local_push",
    SOURCE_INTEGRATION_DISCOVERY="integration_discovery",
)
_install_module(
    "homeassistant.const",
    CONF_HOST="host",
    CONF_MAC="mac",
    CONF_NAME="name",
    CONF_PORT="port",
    EVENT_HOMEASSISTANT_STOP="homeassistant_stop",
    Platform=types.SimpleNamespace(LIGHT="light", NUMBER="number"),
    STATE_ON="on",
)
_install_module("homeassistant.core", HomeAssistant=MagicMock, callback=lambda f: f)
_install_module("homeassistant.data_entry_flow", AbortFlow=AbortFlow)
_install_module("homeassistant.exceptions", HomeAssistantError=HomeAssistantError)
_install_module("homeassistant.components")
_install_module(
    "homeassistant.components.light",
    ATTR_BRIGHTNESS="brightness",
    ATTR_EFFECT="effect",
    ATTR_RGB_COLOR="rgb_color",
    ATTR_RGBW_COLOR="rgbw_color",
    EFFECT_OFF="off",
    ColorMode=types.SimpleNamespace(RGB="rgb"),
    LightEntity=LightEntity,
    LightEntityFeature=types.SimpleNamespace(EFFECT=4),
)
_install_module(
    "homeassistant.components.number",
    NumberEntity=NumberEntity,
    NumberMode=types.SimpleNamespace(SLIDER="slider"),
)
_install_module("homeassistant.helpers")
_install_module(
    "homeassistant.helpers.config_validation",
    empty_config_schema=lambda domain: ("empty_config_schema", domain),
    multi_select=lambda options: ("multi_select", options),
)
_install_module(
    "homeassistant.helpers.device_registry",
    CONNECTION_NETWORK_MAC="mac",
    # DeviceInfo is a TypedDict in Home Assistant.
    DeviceInfo=dict,
    format_mac=format_mac,
)
# Tests patch these per test; the defaults report an empty registry.
_install_module(
    "homeassistant.helpers.entity_registry",
    async_get=MagicMock(),
    async_entries_for_config_entry=MagicMock(return_value=[]),
)
_install_module("homeassistant.helpers.entity_platform", AddEntitiesCallback=MagicMock)
_install_module("homeassistant.helpers.restore_state", RestoreEntity=RestoreEntity)

# The config flow only builds a schema; it is never validated in these tests.
sys.modules["voluptuous"] = MagicMock()
