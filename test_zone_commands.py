"""Feature 7 Test: Zone Command Identification (Testing Byte 5).

This script tests whether the DMX controller accepts sequential integers in Byte 5
to route instructions to independent physical zones (e.g. Zone 1 = 0x01, Zone 2 = 0x02, Zone 3 = 0x03).

Test sequence:
  For each zone in [1, 2, 3]:
    1. Send Power ON command frame with Byte 5 = zone byte.
    2. Pause for observation.
    3. Send Power OFF command frame with Byte 5 = zone byte.
    4. Pause for observation.

Uses macOS `say` command for voice announcements so you can watch the physical zones from across the room.

Usage:
    uv run python test_zone_commands.py --ip <CONTROLLER_IP>
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
from custom_components.dmx_diodeled.const import (  # noqa: E402
    CMD_TYPE_POWER,
    VAL_POWER_ON,
    VAL_POWER_OFF,
)

logger = logging.getLogger("zone_test")


def speak(text: str) -> None:
    """Announce text using macOS text-to-speech if available."""
    if shutil.which("say"):
        subprocess.Popen(["say", text])
    else:
        logger.info("TTS [say] NOT AVAILABLE: %s", text)


async def run_test(ip: str, port: int, pause: float, zones: list[int]) -> None:
    """Run the zone command test by sending Power ON/OFF commands to each zone."""
    logger.info("=" * 60)
    logger.info("STARTING ZONE COMMAND TEST (Testing Byte 5)")
    logger.info("=" * 60)
    speak("Starting zone command test.")
    await asyncio.sleep(2.0)

    for zone in zones:
        controller = DiodLEDController(ip, port, zone=zone)

        # Power ON
        msg_on = f"Testing Zone {zone}. Powering ON."
        speak(msg_on)
        logger.info("  Sending Zone %d Power ON command...", zone)
        packet_on = controller._build_packet(CMD_TYPE_POWER, VAL_POWER_ON)
        logger.info("  Frame: %s (Byte 5 = 0x%02X)", packet_on.hex(), zone)
        await controller.async_set_power(True)
        await asyncio.sleep(pause)

        # Power OFF
        msg_off = f"Testing Zone {zone}. Powering OFF."
        speak(msg_off)
        logger.info("  Sending Zone %d Power OFF command...", zone)
        packet_off = controller._build_packet(CMD_TYPE_POWER, VAL_POWER_OFF)
        logger.info("  Frame: %s (Byte 5 = 0x%02X)", packet_off.hex(), zone)
        await controller.async_set_power(False)
        await asyncio.sleep(pause)

    speak("Zone command test complete.")
    logger.info("=" * 60)
    logger.info("ZONE COMMAND TEST COMPLETE")
    logger.info("=" * 60)


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Test zone routing commands (Byte 5 mutation) on TCP port 8899"
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
        "--pause",
        type=float,
        default=3.0,
        help="Seconds to pause between commands (default: 3.0)",
    )
    parser.add_argument(
        "--zones",
        default="1,2,3",
        help="Comma-separated list of zone numbers to test (default: '1,2,3')",
    )

    args = parser.parse_args()

    if not args.ip:
        speak("Error. No controller IP specified.")
        logger.error("No controller IP specified. Use --ip <IP> or set DMX_IP env var.")
        sys.exit(1)

    try:
        zone_list = [int(z.strip()) for z in args.zones.split(",") if z.strip()]
    except ValueError:
        logger.error(
            "Invalid zones format. Expected comma-separated integers like '1,2,3'"
        )
        sys.exit(1)

    try:
        await run_test(args.ip, args.port, args.pause, zone_list)
    except Exception as e:
        speak("Connection failed.")
        logger.error("Connection failed: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s.%(msecs)03d %(levelname)s (%(threadName)s) [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    asyncio.run(main())
