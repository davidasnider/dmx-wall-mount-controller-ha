import asyncio
import argparse
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

# Put custom_components in path to load module independently of Home Assistant
sys.path.insert(0, os.path.abspath(os.path.join(os.getcwd(), ".")))

from custom_components.dmx_diodeled.dmx_controller import DiodLEDController  # noqa: E402


async def main():
    parser = argparse.ArgumentParser(description="DiodeLED DMX CLI Tester")
    parser.add_argument(
        "--ip", default="10.1.1.87", help="Controller IP Address (default: 10.1.1.87)"
    )
    parser.add_argument(
        "--port", type=int, default=8899, help="Controller TCP Port (default: 8899)"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Power
    cmd_power = subparsers.add_parser("power", help="Turn device ON or OFF")
    cmd_power.add_argument("state", choices=["on", "off"], help="State to set")

    # RGBW
    cmd_rgbw = subparsers.add_parser("rgbw", help="Set RGBW colors (0-255)")
    cmd_rgbw.add_argument("r", type=int, help="Red channel")
    cmd_rgbw.add_argument("g", type=int, help="Green channel")
    cmd_rgbw.add_argument("b", type=int, help="Blue channel")
    cmd_rgbw.add_argument("w", type=int, help="White channel")

    # Brightness
    cmd_bright = subparsers.add_parser(
        "brightness", help="Set Master Brightness (0-255)"
    )
    cmd_bright.add_argument(
        "val",
        type=int,
        help="Brightness value in HA range (0-255). Will be mapped to 2-8.",
    )

    # Effect
    cmd_effect = subparsers.add_parser("effect", help="Trigger built-in routines")
    cmd_effect.add_argument("name", choices=["rainbow"], help="Effect name")

    # Speed
    cmd_speed = subparsers.add_parser("speed", help="Set pattern playback speed (1-10)")
    cmd_speed.add_argument("val", type=int, help="Speed step (1=Slowest, 10=Fastest)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # In our CLI script, we will use a logger instead of prints for consistency
    cli_logger = logging.getLogger("dmx_cli_tester")

    controller = DiodLEDController(args.ip, args.port)
    cli_logger.info("Connecting to DMX controller at %s:%s...", args.ip, args.port)

    try:
        if args.command == "power":
            is_on = args.state == "on"
            await controller.async_set_power(is_on)
            cli_logger.info("Sent Power %s frame.", "ON" if is_on else "OFF")

        elif args.command == "rgbw":
            await controller.async_set_rgbw(args.r, args.g, args.b, args.w)
            cli_logger.info(
                "Sent RGBW updates for (%s, %s, %s, %s).",
                args.r,
                args.g,
                args.b,
                args.w,
            )

        elif args.command == "brightness":
            await controller.async_set_brightness(args.val)
            cli_logger.info("Sent brightness level mapping for %s.", args.val)

        elif args.command == "effect":
            if args.name == "rainbow":
                await controller.async_set_rainbow(True)
                cli_logger.info("Activated Rainbow Effect.")

        elif args.command == "speed":
            await controller.async_set_speed(args.val)
            cli_logger.info("Sent speed interval update for step %s.", args.val)

    except Exception as e:
        cli_logger.error("Connection Failed: %s", e)


if __name__ == "__main__":
    # Configure logging to match Home Assistant standard
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s.%(msecs)03d %(levelname)s (%(threadName)s) [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    asyncio.run(main())
