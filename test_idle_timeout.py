"""Feature 3 Test: Persistent Socket Connection & Idle Timeout.

This script tests whether maintaining a persistent TCP socket connection to port 8899
over an extended idle period (e.g. 305 seconds) causes the High-Flying Wi-Fi module
to unceremoniously drop the connection due to its 300-second TCP timeout setting,
or if subsequent commands over the same socket succeed or fail.

Usage:
    uv run python test_idle_timeout.py --ip <CONTROLLER_IP> [--wait 305]
"""

import asyncio
import argparse
import subprocess
import sys
import os
import shutil
import unittest.mock
import logging

# Mock Home Assistant modules so they don't break the import
sys.modules["homeassistant"] = unittest.mock.MagicMock()
sys.modules["homeassistant.config_entries"] = unittest.mock.MagicMock()
sys.modules["homeassistant.const"] = unittest.mock.MagicMock()
sys.modules["homeassistant.core"] = unittest.mock.MagicMock()
sys.modules["homeassistant.components"] = unittest.mock.MagicMock()
sys.modules["homeassistant.components.light"] = unittest.mock.MagicMock()
sys.modules["homeassistant.helpers"] = unittest.mock.MagicMock()
sys.modules["homeassistant.helpers.entity_platform"] = unittest.mock.MagicMock()

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from custom_components.dmx_diodeled.dmx_controller import DiodLEDController  # noqa: E402

logger = logging.getLogger("idle_timeout_test")


def speak(text: str) -> None:
    """Announce text using macOS text-to-speech if available."""
    if shutil.which("say"):
        subprocess.Popen(["say", text])
    else:
        logger.info("TTS [say] NOT AVAILABLE: %s", text)


async def run_idle_test(ip: str, port: int, wait_seconds: float) -> bool:
    """Open persistent connection, send initial command, wait idle, then send follow-up command."""
    controller = DiodLEDController(ip, port)
    power_on_cmd = controller.get_power_command(True)
    packet = controller._build_packet(power_on_cmd[0], power_on_cmd[1])

    logger.info("Connecting to %s:%s for persistent TCP connection test...", ip, port)
    speak("Opening persistent connection to D MX controller.")

    reader = None
    writer = None
    connected = False
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(ip, port), timeout=5.0
        )
        connected = True
        logger.info("Persistent connection established.")

        # Step 1: Send initial power command over socket
        logger.info("Sending initial command payload: %s", packet.hex())
        writer.write(packet)
        await asyncio.wait_for(writer.drain(), timeout=2.0)
        logger.info("Initial command sent successfully.")
        speak("Initial command sent. Starting idle timeout wait.")

        # Step 2: Idle wait without sending any data
        logger.info("Waiting for %s seconds without sending commands...", wait_seconds)
        await asyncio.sleep(wait_seconds)

        # Step 3: Attempt to fire follow-up command over same socket
        speak("Idle period ended. Attempting to send follow-up command.")
        logger.info("Attempting follow-up command on persistent connection...")
        writer.write(packet)
        await asyncio.wait_for(writer.drain(), timeout=2.0)

        # Give the peer a short window to react, then probe the reader: an EOF
        # read (b"") or an exception raised from the read means the idle period
        # dropped the connection. A plain timeout just means no reply yet, which
        # is normal since this hardware never answers commands on the socket.
        try:
            data = await asyncio.wait_for(reader.read(1), timeout=2.0)
        except asyncio.TimeoutError:
            data = None  # no reply yet; socket is still open
        if data == b"":
            raise ConnectionResetError("Socket reached EOF after idle timeout.")

        logger.info("SUCCESS: Follow-up command succeeded on persistent socket!")
        speak("Success. Persistent socket connection stayed alive.")
        return True

    except (
        asyncio.TimeoutError,
        ConnectionResetError,
        BrokenPipeError,
        OSError,
    ) as err:
        if connected:
            logger.error(
                "FAILED: Persistent connection was dropped or timed out after idle period. Error: %s",
                err,
            )
        else:
            logger.error(
                "FAILED: Initial connection to %s:%s failed before the idle test began. Error: %s",
                ip,
                port,
                err,
            )
        speak("Persistent connection failed or was dropped by module.")
        return False
    finally:
        if writer is not None:
            writer.close()
            try:
                await asyncio.wait_for(writer.wait_closed(), timeout=2.0)
            except (asyncio.TimeoutError, ConnectionResetError, OSError):
                pass


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Test persistent socket connection & idle timeout (305s wait)"
    )
    parser.add_argument(
        "--ip",
        default=os.getenv("DMX_IP"),
        help="Controller IP Address (default: DMX_IP env var)",
    )
    parser.add_argument(
        "--port", type=int, default=8899, help="Controller TCP Port (default: 8899)"
    )
    parser.add_argument(
        "--wait",
        type=float,
        default=305.0,
        help="Idle wait duration in seconds before firing command (default: 305.0)",
    )

    args = parser.parse_args()

    if not args.ip:
        speak("Error. No controller IP specified.")
        logger.error("No controller IP specified. Use --ip <IP> or set DMX_IP env var.")
        sys.exit(1)

    success = await run_idle_test(args.ip, args.port, args.wait)
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s.%(msecs)03d %(levelname)s (%(threadName)s) [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    asyncio.run(main())
