"""Feature 1 Test: Full-Range Master Brightness Scaling (0x00 to 0xFF).

This script tests whether the DMX controller's master brightness command
(CMD_TYPE_BRIGHTNESS = [0x08, 0x23]) works when RGBW channels are active.

Test sequence:
  1. Power ON
  2. Set RGBW to full white (255, 255, 255, 255)
  3. Sweep brightness from 0x02 upward with pauses

Uses macOS `say` command for voice announcements so you can watch the
lights from across the room.

Usage:
    uv run python test_brightness_range.py --ip <CONTROLLER_IP>
"""

import asyncio
import argparse
import subprocess
import sys
import os
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

sys.path.insert(0, os.path.abspath(os.path.join(os.getcwd(), ".")))

from custom_components.dmx_diodeled.dmx_controller import DiodLEDController  # noqa: E402
from custom_components.dmx_diodeled.const import (  # noqa: E402
    CMD_TYPE_BRIGHTNESS,
)

logger = logging.getLogger("brightness_test")

# Test values: 0x00 through 0x30 (0-48) to map zone brightness layout
TEST_VALUES = [
    (0x00, "Brightness 0."),
    (0x01, "Brightness 1."),
    (0x02, "Brightness 2. App step 1 of 7."),
    (0x03, "Brightness 3. App step 2 of 7."),
    (0x04, "Brightness 4. App step 3 of 7."),
    (0x05, "Brightness 5. App step 4 of 7."),
    (0x06, "Brightness 6. App step 5 of 7."),
    (0x07, "Brightness 7. App step 6 of 7."),
    (0x08, "Brightness 8. App step 7 of 7. App maximum."),
    (0x09, "Brightness 9."),
    (0x0A, "Brightness 10."),
    (0x0B, "Brightness 11."),
    (0x0C, "Brightness 12."),
    (0x0D, "Brightness 13."),
    (0x0E, "Brightness 14."),
    (0x0F, "Brightness 15."),
    (0x10, "Brightness 16."),
    (0x11, "Brightness 17."),
    (0x12, "Brightness 18."),
    (0x13, "Brightness 19."),
    (0x14, "Brightness 20."),
    (0x15, "Brightness 21."),
    (0x16, "Brightness 22."),
    (0x17, "Brightness 23."),
    (0x18, "Brightness 24."),
    (0x19, "Brightness 25."),
    (0x1A, "Brightness 26."),
    (0x1B, "Brightness 27."),
    (0x1C, "Brightness 28."),
    (0x1D, "Brightness 29."),
    (0x1E, "Brightness 30."),
    (0x1F, "Brightness 31."),
    (0x20, "Brightness 32."),
    (0x21, "Brightness 33."),
    (0x22, "Brightness 34."),
    (0x23, "Brightness 35."),
    (0x24, "Brightness 36."),
    (0x25, "Brightness 37."),
    (0x26, "Brightness 38."),
    (0x27, "Brightness 39."),
    (0x28, "Brightness 40."),
    (0x29, "Brightness 41."),
    (0x2A, "Brightness 42."),
    (0x2B, "Brightness 43."),
    (0x2C, "Brightness 44."),
    (0x2D, "Brightness 45."),
    (0x2E, "Brightness 46."),
    (0x2F, "Brightness 47."),
    (0x30, "Brightness 48."),
]


def speak(text: str):
    """Announce text using macOS text-to-speech."""
    subprocess.Popen(["say", text])


async def run_test(ip: str, port: int, pause: float):
    """Run the brightness range test with RGBW active."""
    controller = DiodLEDController(ip, port)

    # --- Silent reset to known state (no announcements, no pauses) ---
    logger.info("Resetting to known state...")
    await controller.async_set_power(False)
    await controller.async_set_power(True)
    await controller.async_set_rgbw(255, 255, 255, 255)
    await controller.async_send_command(CMD_TYPE_BRIGHTNESS, 0x02)
    logger.info("Reset complete: OFF → ON → White → Brightness 0x02")

    # --- Announced brightness sweep ---
    speak("Ready. Starting brightness sweep from the lowest setting.")
    logger.info("=" * 60)
    logger.info("BRIGHTNESS SWEEP (with white active)")
    logger.info("=" * 60)
    await asyncio.sleep(3.0)

    for val, description in TEST_VALUES:
        speak(description)
        logger.info(
            "  Sending brightness 0x%02X (%3d) — %s",
            val,
            val,
            description,
        )
        packet = controller._build_packet(CMD_TYPE_BRIGHTNESS, val)
        logger.debug("  Raw packet: %s", packet.hex())

        await controller.async_send_command(CMD_TYPE_BRIGHTNESS, val)
        await asyncio.sleep(pause)

    speak("Test complete.")
    logger.info("=" * 60)
    logger.info("TEST COMPLETE")
    logger.info("=" * 60)


async def main():
    parser = argparse.ArgumentParser(
        description="Test brightness command 08 23 with active RGBW output"
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
        default=5.0,
        help="Seconds to pause between test values (default: 5.0)",
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
