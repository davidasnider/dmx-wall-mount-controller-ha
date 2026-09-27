"""Feature 8 Test: "All Zones" Broadcast Command.

This script tests sending packets with Byte 5 set to different zone values
(0x00, 0x01, 0x02, 0x03, 0x04) to see if 0x00 or 0x04 acts as a broadcast byte
that triggers a global state change on all decoders simultaneously.

Test sequence for each zone candidate:
  1. Power ON command with specified zone byte in Byte 5
  2. Set RGBW to full white with specified zone byte in Byte 5
  3. Set Brightness (0x05) with specified zone byte in Byte 5
  4. Power OFF command with specified zone byte in Byte 5

Uses macOS `say` command for voice announcements so you can watch the
lights across decoders/universes.

Usage:
    uv run python test_broadcast_command.py --ip <CONTROLLER_IP> [--pause 3.0]
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

logger = logging.getLogger("broadcast_test")

ZONE_TEST_CASES = [
    (0x00, "Zone Byte 0x00: Broadcast candidate 1."),
    (0x01, "Zone Byte 0x01: Zone 1."),
    (0x02, "Zone Byte 0x02: Zone 2."),
    (0x03, "Zone Byte 0x03: Zone 3."),
    (0x04, "Zone Byte 0x04: Broadcast candidate 2."),
]


def speak(text: str) -> None:
    """Announce text using macOS text-to-speech if available."""
    if shutil.which("say"):
        subprocess.Popen(["say", text])
    else:
        logger.info("TTS [say] NOT AVAILABLE: %s", text)


async def run_test(ip: str, port: int, pause: float) -> None:
    """Run the broadcast command test sequence across zone candidates."""
    controller = DiodLEDController(ip, port)

    logger.info("=" * 60)
    logger.info("FEATURE 8: ALL ZONES BROADCAST COMMAND TEST")
    logger.info("=" * 60)
    speak("Starting broadcast command test sequence across zone bytes.")
    await asyncio.sleep(2.0)

    for zone_byte, description in ZONE_TEST_CASES:
        speak(f"Testing {description}")
        logger.info("-" * 50)
        logger.info("Testing Zone Byte 0x%02X (%s)", zone_byte, description)
        logger.info("-" * 50)

        # Step 1: Power ON for zone candidate
        logger.info("  Sending Power ON with zone byte 0x%02X", zone_byte)
        await controller.async_set_power(True, zone=zone_byte)
        await asyncio.sleep(pause)

        # Step 2: Set RGBW color for zone candidate
        logger.info(
            "  Sending RGBW (254, 254, 254, 0) with zone byte 0x%02X", zone_byte
        )
        await controller.async_set_rgbw(254, 254, 254, 0, zone=zone_byte)
        await asyncio.sleep(pause)

        # Step 3: Set Brightness for zone candidate
        logger.info(
            "  Sending Brightness HA 128 (0x05) with zone byte 0x%02X", zone_byte
        )
        await controller.async_set_brightness(128, zone=zone_byte)
        await asyncio.sleep(pause)

        # Step 4: Power OFF for zone candidate
        logger.info("  Sending Power OFF with zone byte 0x%02X", zone_byte)
        await controller.async_set_power(False, zone=zone_byte)
        await asyncio.sleep(pause)

    speak("Broadcast test sequence complete.")
    logger.info("=" * 60)
    logger.info("BROADCAST TEST COMPLETE")
    logger.info("=" * 60)


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Test broadcast byte candidates (0x00, 0x04) in Byte 5 of DMX packets"
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
        help="Seconds to pause between test steps (default: 3.0)",
    )

    args = parser.parse_args()

    if not args.ip:
        speak("Error. No controller IP specified.")
        logger.error("No controller IP specified. Use --ip <IP> or set DMX_IP env var.")
        sys.exit(1)

    try:
        await run_test(args.ip, args.port, args.pause)
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
