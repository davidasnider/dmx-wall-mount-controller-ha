import sys
import os
import unittest.mock
import pytest
import importlib.util
from typing import Any

# Mock Home Assistant modules so tests can run without full core platform
sys.modules["homeassistant"] = unittest.mock.MagicMock()
sys.modules["homeassistant.config_entries"] = unittest.mock.MagicMock()
sys.modules["homeassistant.const"] = unittest.mock.MagicMock()
sys.modules["homeassistant.core"] = unittest.mock.MagicMock()
sys.modules["homeassistant.components"] = unittest.mock.MagicMock()
sys.modules["homeassistant.components.light"] = unittest.mock.MagicMock()
sys.modules["homeassistant.helpers"] = unittest.mock.MagicMock()
sys.modules["homeassistant.helpers.entity_platform"] = unittest.mock.MagicMock()

# Load the root test_idle_timeout.py module explicitly
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
spec = importlib.util.spec_from_file_location(
    "root_test_idle_timeout", os.path.join(root_dir, "test_idle_timeout.py")
)
assert spec is not None and spec.loader is not None
root_test_idle_timeout = importlib.util.module_from_spec(spec)
spec.loader.exec_module(root_test_idle_timeout)

run_idle_test = root_test_idle_timeout.run_idle_test


def _create_mock_writer() -> unittest.mock.AsyncMock:
    """Create a mock asyncio.StreamWriter where write and close are sync methods."""
    writer = unittest.mock.AsyncMock()
    writer.write = unittest.mock.Mock()
    writer.close = unittest.mock.Mock()
    writer.drain = unittest.mock.AsyncMock()
    writer.wait_closed = unittest.mock.AsyncMock()
    return writer


@pytest.mark.asyncio
async def test_run_idle_test_success() -> None:
    """Test run_idle_test when connection and follow-up command succeed."""
    mock_reader = unittest.mock.MagicMock()
    mock_reader.at_eof.return_value = False

    mock_writer = _create_mock_writer()

    async def mock_open_connection(
        host: str, port: int
    ) -> tuple[Any, unittest.mock.AsyncMock]:
        return mock_reader, mock_writer

    with unittest.mock.patch(
        "asyncio.open_connection", side_effect=mock_open_connection
    ):
        result = await run_idle_test("127.0.0.1", 8899, wait_seconds=0.01)
        assert result is True
        assert mock_writer.write.call_count == 2
        mock_writer.close.assert_called_once()


@pytest.mark.asyncio
async def test_run_idle_test_connection_reset() -> None:
    """Test run_idle_test when follow-up command encounters ConnectionResetError."""
    mock_reader = unittest.mock.MagicMock()

    mock_writer = _create_mock_writer()
    # First drain succeeds, second drain raises ConnectionResetError
    mock_writer.drain = unittest.mock.AsyncMock(
        side_effect=[None, ConnectionResetError("Connection reset by peer")]
    )

    async def mock_open_connection(
        host: str, port: int
    ) -> tuple[Any, unittest.mock.AsyncMock]:
        return mock_reader, mock_writer

    with unittest.mock.patch(
        "asyncio.open_connection", side_effect=mock_open_connection
    ):
        result = await run_idle_test("127.0.0.1", 8899, wait_seconds=0.01)
        assert result is False
        mock_writer.close.assert_called_once()


@pytest.mark.asyncio
async def test_run_idle_test_eof_detected() -> None:
    """Test run_idle_test when reader reports EOF after idle period."""
    mock_reader = unittest.mock.MagicMock()
    mock_reader.at_eof.return_value = True

    mock_writer = _create_mock_writer()

    async def mock_open_connection(
        host: str, port: int
    ) -> tuple[Any, unittest.mock.AsyncMock]:
        return mock_reader, mock_writer

    with unittest.mock.patch(
        "asyncio.open_connection", side_effect=mock_open_connection
    ):
        result = await run_idle_test("127.0.0.1", 8899, wait_seconds=0.01)
        assert result is False
        mock_writer.close.assert_called_once()
