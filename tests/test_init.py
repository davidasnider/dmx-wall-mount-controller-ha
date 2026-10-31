import types
import unittest.mock
from typing import Any

import pytest

import custom_components.dmx_diodeled as integration
from custom_components.dmx_diodeled.const import DOMAIN
from custom_components.dmx_diodeled.dmx_controller import DiodLEDController


@pytest.fixture
def hass() -> Any:
    hass = unittest.mock.MagicMock()
    hass.data = {}
    hass.config_entries.flow.async_init = unittest.mock.AsyncMock()
    hass.config_entries.async_forward_entry_setups = unittest.mock.AsyncMock()
    hass.config_entries.async_unload_platforms = unittest.mock.AsyncMock(
        return_value=True
    )
    return hass


def test_config_schema_accepts_empty_yaml_key() -> None:
    """A "dmx_diodeled:" YAML key must be accepted, so discovery can start
    before the first controller is added."""
    assert integration.CONFIG_SCHEMA == ("empty_config_schema", DOMAIN)


@pytest.mark.asyncio
async def test_setup_starts_discovery_listener(hass: Any) -> None:
    transport = unittest.mock.MagicMock()
    with unittest.mock.patch.object(
        integration,
        "async_start_discovery",
        unittest.mock.AsyncMock(return_value=transport),
    ) as start:
        assert await integration.async_setup(hass, {}) is True

    start.assert_awaited_once()
    assert hass.data[DOMAIN]["discovery"]["transport"] is transport

    # The listener is closed when Home Assistant stops.
    event, stop_listener = hass.bus.async_listen_once.call_args[0]
    assert event == "homeassistant_stop"
    stop_listener(None)
    transport.close.assert_called_once()


@pytest.mark.asyncio
async def test_setup_closes_previous_listener(hass: Any) -> None:
    previous = unittest.mock.MagicMock()
    hass.data[DOMAIN] = {"discovery": {"transport": previous}}

    with unittest.mock.patch.object(
        integration,
        "async_start_discovery",
        unittest.mock.AsyncMock(return_value=unittest.mock.MagicMock()),
    ):
        await integration.async_setup(hass, {})

    previous.close.assert_called_once()


@pytest.mark.asyncio
async def test_setup_without_listener_still_succeeds(hass: Any) -> None:
    """If the UDP port cannot be bound, setup continues without discovery."""
    with unittest.mock.patch.object(
        integration, "async_start_discovery", unittest.mock.AsyncMock(return_value=None)
    ):
        assert await integration.async_setup(hass, {}) is True

    assert "transport" not in hass.data[DOMAIN]["discovery"]
    hass.bus.async_listen_once.assert_not_called()


@pytest.mark.asyncio
async def test_discovered_device_starts_config_flow(hass: Any) -> None:
    with unittest.mock.patch.object(
        integration, "async_start_discovery", unittest.mock.AsyncMock(return_value=None)
    ) as start:
        await integration.async_setup(hass, {})

    on_discovered = start.call_args[0][1]
    await on_discovered("192.168.1.50", "AABBCCDDEEFF")

    hass.config_entries.flow.async_init.assert_awaited_once_with(
        DOMAIN,
        context={"source": "integration_discovery"},
        data={"host": "192.168.1.50", "mac": "AABBCCDDEEFF"},
    )


def _config_entry(options: dict[str, Any] | None = None) -> Any:
    return types.SimpleNamespace(
        entry_id="entry1",
        data={"host": "192.168.1.50"},
        options=options or {},
        add_update_listener=unittest.mock.Mock(return_value="remove_listener"),
        async_on_unload=unittest.mock.Mock(),
    )


@pytest.mark.asyncio
async def test_setup_and_unload_entry(hass: Any) -> None:
    entry = _config_entry()

    assert await integration.async_setup_entry(hass, entry) is True

    controller = hass.data[DOMAIN]["entry1"]
    assert isinstance(controller, DiodLEDController)
    assert (controller.ip, controller.port) == ("192.168.1.50", 8899)
    hass.config_entries.async_forward_entry_setups.assert_awaited_once_with(
        entry, integration.PLATFORMS
    )

    assert await integration.async_unload_entry(hass, entry) is True
    assert "entry1" not in hass.data[DOMAIN]


def test_platforms_include_light_and_number() -> None:
    assert integration.PLATFORMS == ["light", "number"]


@pytest.mark.asyncio
async def test_setup_entry_reloads_on_options_change(hass: Any) -> None:
    entry = _config_entry()
    hass.config_entries.async_reload = unittest.mock.AsyncMock()

    await integration.async_setup_entry(hass, entry)

    entry.async_on_unload.assert_called_once_with("remove_listener")
    listener = entry.add_update_listener.call_args[0][0]
    await listener(hass, entry)
    hass.config_entries.async_reload.assert_awaited_once_with("entry1")


@pytest.mark.asyncio
async def test_setup_entry_removes_entities_of_disabled_zones(hass: Any) -> None:
    """Zones switched off in the options must not linger as unavailable entities."""
    entry = _config_entry({"zones": [1]})
    registry = unittest.mock.MagicMock()
    registered = [
        types.SimpleNamespace(entity_id="light.kept", unique_id="diodeled_dmx_entry1"),
        types.SimpleNamespace(
            entity_id="number.kept", unique_id="diodeled_dmx_entry1_speed"
        ),
        types.SimpleNamespace(
            entity_id="light.zone_2", unique_id="diodeled_dmx_entry1_zone_2"
        ),
        types.SimpleNamespace(
            entity_id="number.zone_2", unique_id="diodeled_dmx_entry1_zone_2_speed"
        ),
    ]
    with (
        unittest.mock.patch.object(integration.er, "async_get", return_value=registry),
        unittest.mock.patch.object(
            integration.er, "async_entries_for_config_entry", return_value=registered
        ),
    ):
        await integration.async_setup_entry(hass, entry)

    removed = [call.args[0] for call in registry.async_remove.call_args_list]
    assert removed == ["light.zone_2", "number.zone_2"]
