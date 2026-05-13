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
    CMD_CHUNK_SIZE,
)


class DiodLEDController:
    """Handle communication with the DiodeLED DMX Controller."""

    def __init__(self, ip: str, port: int) -> None:
        """Initialize the controller."""
        self.ip = ip
        self.port = port
        self._last_send_time = 0
        self._lock = asyncio.Lock()

    def _build_packet(self, cmd_type: list[int], val: int) -> bytes:
        """Construct the 12-byte hex packet."""
        # Cap the channel value byte (Byte 9 / `val`) at 254 because `0xFF`
        # is forbidden for that field on this hardware, even though `0xFF`
        # may still appear in other fixed packet bytes.
        val = min(val, 254)

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

    async def async_send_commands(self, commands: list[tuple[list[int], int]]) -> None:
        """Send a batch of commands to the controller, max CMD_CHUNK_SIZE per network call."""
        chunk_size = CMD_CHUNK_SIZE

        async with self._lock:
            for i in range(0, len(commands), chunk_size):
                chunk = commands[i : i + chunk_size]

                # Throttling
                now = time.time()
                elapsed = now - self._last_send_time
                if elapsed < THROTTLE_DELAY:
                    await asyncio.sleep(THROTTLE_DELAY - elapsed)

                payload = bytearray()
                for cmd_type, val in chunk:
                    payload.extend(self._build_packet(cmd_type, val))

                LOGGER.debug(
                    "Sending batched command payload to %s:%s - %s",
                    self.ip,
                    self.port,
                    payload.hex(),
                )

                writer = None
                try:
                    _, writer = await asyncio.wait_for(
                        asyncio.open_connection(self.ip, self.port), timeout=2.0
                    )
                    writer.write(payload)
                    await asyncio.wait_for(writer.drain(), timeout=2.0)
                    writer.close()
                    await asyncio.wait_for(writer.wait_closed(), timeout=2.0)
                    self._last_send_time = time.time()
                except (asyncio.TimeoutError, ConnectionRefusedError, OSError) as err:
                    if writer is not None:
                        writer.close()
                        try:
                            await asyncio.wait_for(writer.wait_closed(), timeout=2.0)
                        except (asyncio.TimeoutError, ConnectionRefusedError, OSError):
                            pass
                    LOGGER.error(
                        "Failed to communicate with DMX controller at %s:%s. Error: %s",
                        self.ip,
                        self.port,
                        err,
                    )
                    raise

    async def async_send_command(self, cmd_type: list[int], val: int) -> None:
        """Send a single command to the controller with rate limiting."""
        await self.async_send_commands([(cmd_type, val)])

    def get_power_command(self, on: bool) -> tuple[list[int], int]:
        """Get the power command tuple."""
        val = VAL_POWER_ON if on else VAL_POWER_OFF
        return (CMD_TYPE_POWER, val)

    def get_brightness_command(self, ha_brightness: int) -> tuple[list[int], int]:
        """Get the brightness command tuple."""
        val = BRIGHTNESS_MIN + round(
            (ha_brightness / 255.0) * (BRIGHTNESS_MAX - BRIGHTNESS_MIN)
        )
        return (CMD_TYPE_BRIGHTNESS, val)

    def get_rgbw_commands(
        self, r: int, g: int, b: int, w: int
    ) -> list[tuple[list[int], int]]:
        """Get a list of RGBW command tuples."""
        return [
            (CMD_TYPE_RED, r),
            (CMD_TYPE_GREEN, g),
            (CMD_TYPE_BLUE, b),
            (CMD_TYPE_WHITE, w),
        ]

    def get_rainbow_command(self, on: bool) -> tuple[list[int], int] | None:
        """Get the rainbow effect command tuple."""
        if on:
            return (CMD_TYPE_RAINBOW, VAL_RAINBOW_ON)
        return None

    def get_speed_command(self, speed: int) -> tuple[list[int], int]:
        """Get the speed command tuple."""
        val = max(SPEED_MIN, min(SPEED_MAX, speed))
        return (CMD_TYPE_SPEED, val)

    async def async_set_power(self, on: bool) -> None:
        """Turn the light on or off."""
        await self.async_send_commands([self.get_power_command(on)])

    async def async_set_brightness(self, ha_brightness: int) -> None:
        """Set master brightness (map 0-255 to 0x01-0x08)."""
        await self.async_send_commands([self.get_brightness_command(ha_brightness)])

    async def async_set_rgbw(self, r: int, g: int, b: int, w: int) -> None:
        """Set RGBW values."""
        await self.async_send_commands(self.get_rgbw_commands(r, g, b, w))

    async def async_set_rainbow(self, on: bool) -> None:
        """Activate rainbow mode."""
        cmd = self.get_rainbow_command(on)
        if cmd:
            await self.async_send_commands([cmd])
        else:
            # How to turn off rainbow? Probably by sending a color or power off.
            # PRD doesn't mention rainbow off specifically.
            pass

    async def async_set_speed(self, speed: int) -> None:
        """Set pattern speed (1-10)."""
        await self.async_send_commands([self.get_speed_command(speed)])


# test trigger
