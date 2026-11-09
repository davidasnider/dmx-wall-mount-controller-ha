"""Schema-level validation tests for the config flow forms.

tests/conftest.py replaces ``voluptuous`` with a MagicMock before any test
module imports it, so the schemas built by the flow steps are never validated
in the step tests (they call the steps directly). In Home Assistant, though,
the form's ``data_schema`` runs *before* any step: a blank (whitespace-only)
host or name must fail there with ``vol.Invalid`` so an empty host never
reaches a connection attempt or gets stored.

These tests re-import ``config_flow`` against the real voluptuous (a dev
dependency) and validate submissions against the exact schema the steps build.
The conftest mock is restored afterwards so no other test is affected.
"""

import importlib
import sys
import types
from typing import Any

import pytest

_FLOW_MODULE = "custom_components.dmx_diodeled.config_flow"


@pytest.fixture
def real_schema_module() -> Any:
    """Yield ``(real_voluptuous, config_flow re-imported with it)``."""
    saved_mock = sys.modules.pop("voluptuous")
    # The flow module is only in sys.modules if an earlier test file imported
    # it; pop() must not raise when this file runs on its own.
    saved_flow = sys.modules.pop(_FLOW_MODULE, None)
    try:
        real_voluptuous = importlib.import_module("voluptuous")
        flow_module = importlib.import_module(_FLOW_MODULE)
        yield real_voluptuous, flow_module
    finally:
        # Restore the conftest mock and the original module object. The
        # import also re-bound config_flow on the parent package, so reset
        # that attribute too (or clear both when there was nothing to save).
        sys.modules["voluptuous"] = saved_mock
        if saved_flow is not None:
            sys.modules[_FLOW_MODULE] = saved_flow
            sys.modules["custom_components.dmx_diodeled"].config_flow = saved_flow
        else:
            sys.modules.pop(_FLOW_MODULE, None)


def _form_schema(result: dict[str, Any]) -> Any:
    """The real ``vol.Schema`` inside the stubbed add_suggested_values_to_schema."""
    return result["data_schema"]["schema"]


@pytest.mark.asyncio
async def test_user_form_rejects_whitespace_only_host(real_schema_module: Any) -> None:
    """A blank host must fail the user form's data_schema before any step runs."""
    voluptuous, flow_module = real_schema_module

    result = await flow_module.DiodLEDConfigFlow().async_step_user()
    schema = _form_schema(result)

    with pytest.raises(voluptuous.Invalid):
        schema({"host": "   ", "port": 8899})


@pytest.mark.asyncio
async def test_user_form_rejects_whitespace_only_name(real_schema_module: Any) -> None:
    """A blank name must fail the user form's data_schema (no empty title)."""
    voluptuous, flow_module = real_schema_module

    result = await flow_module.DiodLEDConfigFlow().async_step_user()
    schema = _form_schema(result)

    with pytest.raises(voluptuous.Invalid):
        schema({"host": "192.168.1.50", "port": 8899, "name": "   "})


@pytest.mark.asyncio
async def test_user_form_trims_whitespace(real_schema_module: Any) -> None:
    """Padded values pass validation and come out trimmed (the stored form)."""
    voluptuous, flow_module = real_schema_module

    result = await flow_module.DiodLEDConfigFlow().async_step_user()
    schema = _form_schema(result)

    assert schema(
        {"host": "  192.168.1.50  ", "port": 8899, "name": "  Kitchen  "}
    ) == {"host": "192.168.1.50", "port": 8899, "name": "Kitchen"}


@pytest.mark.asyncio
async def test_reconfigure_form_rejects_whitespace_only_host(
    real_schema_module: Any,
) -> None:
    """A blank host must fail the reconfigure form's data_schema too."""
    voluptuous, flow_module = real_schema_module

    flow = flow_module.DiodLEDConfigFlow()
    flow.context["entry"] = types.SimpleNamespace(
        data={"host": "192.168.1.50", "port": 8899}
    )

    result = await flow.async_step_reconfigure()
    schema = _form_schema(result)

    with pytest.raises(voluptuous.Invalid):
        schema({"host": "   ", "port": 8899})
