import asyncio
import time
from .const import (
    LOGGER,
    HEADER,
    IDENTIFIER,
    CONSTANTS,
    FOOTER,
    CMD_TYPE_POWER,
    CMD_TYPE_BRIGHTNESS,
    CMD_TYPE_RED,
    CMD_TYPE_GREEN,
    CMD_TYPE_BLUE,
    CMD_TYPE_WHITE,
    CMD_TYPE_RAINBOW,
    CMD_TYPE_SPEED,
    VAL_POWER_ON,
    VAL_POWER_OFF,
    VAL_RAINBOW_ON,
    THROTTLE_DELAY,
    BRIGHTNESS_MIN,
    BRIGHTNESS_MAX,
    SPEED_MIN,
    SPEED_MAX,
)


class DiodLEDController:
    """Handle communication with the DiodeLED DMX Controller."""

    def __init__(self, ip, port):
        """Initialize the controller."""
        self.ip = ip
        self.port = port
        self._last_send_time = 0
        self._lock = asyncio.Lock()

    def _build_packet(self, cmd_type: list[int], val: int) -> bytes:
        """Construct the 12-byte hex packet."""
        # Byte 7, 8, 9 are the command components
        # Checksum = (Byte 7 + Byte 8 + Byte 9) mod 256
        checksum = (cmd_type[0] + cmd_type[1] + val) % 256

        packet = bytearray([HEADER])
        packet.extend(IDENTIFIER)
        packet.extend(CONSTANTS)
        packet.extend(cmd_type)
        packet.append(val)
        packet.append(checksum)
        packet.extend(FOOTER)

        return bytes(packet)

    async def async_send_command(self, cmd_type: list[int], val: int):
        """Send a command to the controller with rate limiting."""
        async with self._lock:
            # Throttling
            now = time.time()
            elapsed = now - self._last_send_time
            if elapsed < THROTTLE_DELAY:
                await asyncio.sleep(THROTTLE_DELAY - elapsed)

            packet = self._build_packet(cmd_type, val)
            LOGGER.debug(
                "Sending command frame to %s:%s - %s", self.ip, self.port, packet.hex()
            )

            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(self.ip, self.port), timeout=2.0
                )
                writer.write(packet)
                await writer.drain()
                writer.close()
                await writer.wait_closed()
                self._last_send_time = time.time()
            except (asyncio.TimeoutError, ConnectionRefusedError, OSError) as err:
                LOGGER.error(
                    "Failed to communicate with DMX controller at %s:%s. Error: %s",
                    self.ip,
                    self.port,
                    err,
                )
                raise

    async def async_set_power(self, on: bool):
        """Turn the light on or off."""
        val = VAL_POWER_ON if on else VAL_POWER_OFF
        await self.async_send_command(CMD_TYPE_POWER, val)

    async def async_set_brightness(self, ha_brightness: int):
        """Set master brightness (map 0-255 to 0x02-0x08)."""
        # Map 0-255 to 2-8
        # Formula: min + (val/255) * (max-min)
        val = BRIGHTNESS_MIN + round(
            (ha_brightness / 255.0) * (BRIGHTNESS_MAX - BRIGHTNESS_MIN)
        )
        await self.async_send_command(CMD_TYPE_BRIGHTNESS, val)

    async def async_set_rgbw(self, r: int, g: int, b: int, w: int):
        """Set RGBW values."""
        # The protocol seems to send independent frames for each channel
        # We send them sequentially. Rate limiting will handle the spacing.
        tasks = [
            self.async_send_command(CMD_TYPE_RED, r),
            self.async_send_command(CMD_TYPE_GREEN, g),
            self.async_send_command(CMD_TYPE_BLUE, b),
            self.async_send_command(CMD_TYPE_WHITE, w),
        ]
        # We don't use gather because we want to enforce the lock in async_send_command
        # and ensure they are sent sequentially with the throttle.
        for task in tasks:
            await task

    async def async_set_rainbow(self, on: bool):
        """Activate rainbow mode."""
        if on:
            await self.async_send_command(CMD_TYPE_RAINBOW, VAL_RAINBOW_ON)
        else:
            # How to turn off rainbow? Probably by sending a color or power off.
            # PRD doesn't mention rainbow off specifically.
            pass

    async def async_set_speed(self, speed: int):
        """Set pattern speed (1-10)."""
        val = max(SPEED_MIN, min(SPEED_MAX, speed))
        await self.async_send_command(CMD_TYPE_SPEED, val)
