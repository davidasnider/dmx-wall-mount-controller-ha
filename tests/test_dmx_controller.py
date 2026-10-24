"""Tests for DiodLEDController error handling and log sanitization.

These pin down the null-byte guard (``asyncio.open_connection()`` raises a
``ValueError`` for hosts with embedded null bytes; the controller must re-raise
it as ``OSError`` so LightEntity handles it gracefully) and the log-injection
guard (control characters in the host must be escaped, never logged verbatim).
"""

import asyncio
import logging
from typing import Any, NoReturn

import pytest

from custom_components.dmx_diodeled.const import (
    CMD_TYPE_POWER,
    VAL_POWER_ON,
)
from custom_components.dmx_diodeled.dmx_controller import DiodLEDController


@pytest.fixture
def caplog_debug(caplog: pytest.LogCaptureFixture) -> pytest.LogCaptureFixture:
    """Capture DEBUG and above so the controller's send/error lines are visible."""
    caplog.set_level(logging.DEBUG)
    return caplog


@pytest.mark.asyncio
async def test_null_byte_ip_raises_oserror(caplog_debug: Any) -> None:
    """A host with an embedded null byte must surface as OSError, not ValueError.

    Uses the real ``asyncio.open_connection()`` so the test exercises the full
    path: resolver ValueError -> controller re-raise as OSError.
    """
    ctrl = DiodLEDController("1.2.3.4\x00\n", 6454)
    with pytest.raises(OSError, match="Invalid IP address") as exc_info:
        await ctrl.async_send_command(CMD_TYPE_POWER, VAL_POWER_ON)

    # The OSError must be caused by the resolver's ValueError.
    assert isinstance(exc_info.value.__cause__, ValueError)


@pytest.mark.asyncio
async def test_null_byte_ip_logs_are_escaped(caplog_debug: Any) -> None:
    """Control characters in the host must be escaped (repr'd) in log output."""
    ctrl = DiodLEDController("1.2.3.4\x00\n", 6454)
    with pytest.raises(OSError):
        await ctrl.async_send_command(CMD_TYPE_POWER, VAL_POWER_ON)

    messages = [record.getMessage() for record in caplog_debug.records]
    assert messages, "expected the controller to log a send attempt and error"

    # No raw control character may appear in any single log record.
    for message in messages:
        assert "\x00" not in message
        assert "\n" not in message

    # The host is logged with repr() escaping, i.e. literal backslash sequences.
    assert any("1.2.3.4\\x00\\n" in message for message in messages)


@pytest.mark.asyncio
async def test_all_non_printable_host_chars_are_escaped(
    caplog_debug: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every non-printable character named in review (ESC, VT, C1 NEL U+0085,
    Unicode line separator U+2028) must be escaped in the logs.
    ``open_connection`` is stubbed to fail fast so the test does not pay a real
    connection timeout."""

    async def _refused(*_args: Any, **_kwargs: Any) -> NoReturn:
        raise OSError("connection refused")

    monkeypatch.setattr(asyncio, "open_connection", _refused)

    # The control characters named in the review: ESC[2J (clear-screen escape),
    # VT, C1 NEL and the Unicode line separator.
    esc = "\x1b"
    vt = chr(0x0B)
    nel = chr(0x85)
    line_sep = "\u2028"
    host = f"1.2.3.4{esc}[2J{vt}{nel}{line_sep}"
    ctrl = DiodLEDController(host, 6454)
    with pytest.raises(OSError):
        await ctrl.async_send_command(CMD_TYPE_POWER, VAL_POWER_ON)

    # No raw control character may appear in the captured logs.
    for raw in (esc, vt, nel, line_sep):
        assert raw not in caplog_debug.text, f"raw {raw!r} leaked into the logs"

    # The host is logged escaped exactly as repr() renders it.
    assert repr(host)[1:-1] in caplog_debug.text


@pytest.mark.asyncio
async def test_printable_host_is_logged_verbatim(
    caplog_debug: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """repr()-based sanitization must not alter ordinary hosts."""

    async def _refused(*_args: Any, **_kwargs: Any) -> NoReturn:
        raise OSError("connection refused")

    monkeypatch.setattr(asyncio, "open_connection", _refused)

    ctrl = DiodLEDController("192.168.1.50", 6454)
    with pytest.raises(OSError):
        await ctrl.async_send_command(CMD_TYPE_POWER, VAL_POWER_ON)

    assert any(
        "to 192.168.1.50:6454" in record.getMessage() for record in caplog_debug.records
    )
