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


_PACKET_PREFIX = bytes([HEADER, *IDENTIFIER, *CONSTANTS])
_PACKET_SUFFIX = bytes(FOOTER)


class DiodLEDController:
    """Handle communication with the DiodeLED DMX Controller."""

    def __init__(self, ip: str, port: int) -> None:
        """Initialize the controller."""
        self.ip = ip
        self.port = port
        self._last_send_time = 0
        self._lock = asyncio.Lock()

    def _build_packet(self, cmd_type: list[int], val: int, zone: int = 0x01) -> bytes:
        """Construct the 12-byte hex packet."""
        # Cap the channel value byte (Byte 9 / `val`) at 254 because `0xFF`
        # is forbidden for that field on this hardware, even though `0xFF`
        # may still appear in other fixed packet bytes.
        # SECURITY: Prevent negative value crash (DoS risk) by clamping to 0-254
        # Performance optimization: if/elif is significantly faster than min()/max() calls
        if val < 0:
            val = 0
        elif val > 254:
            val = 254

        # Byte 7, 8, 9 are the command components
        # Checksum = (Byte 7 + Byte 8 + Byte 9) mod 256
        # Performance optimization: using & 0xFF is slightly faster than % 256
        checksum = (cmd_type[0] + cmd_type[1] + val) & 0xFF

        # Performance optimization: pre-calculated prefix for default Zone 1 (0x01),
        # dynamically constructed prefix for broadcast (0x00, 0x04) or other zones (0x02, 0x03).
        prefix = (
            _PACKET_PREFIX
            if zone == 0x01
            else bytes([HEADER, *IDENTIFIER, zone, CONSTANTS[1]])
        )

        return (
            prefix + bytes([cmd_type[0], cmd_type[1], val, checksum]) + _PACKET_SUFFIX
        )

    async def async_send_commands(
        self,
        commands: list[tuple[list[int], int] | tuple[list[int], int, int]],
    ) -> None:
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

                # Performance optimization: b"".join is significantly faster than
                # repeatedly calling bytearray.extend in a loop.
                # Additionally, using a list comprehension is ~30% faster than a generator
                # expression here because CPython can pre-calculate the total size.
                payload_list = []
                for item in chunk:
                    if len(item) == 3:
                        cmd_type, val, zone = item  # type: ignore[misc]
                        payload_list.append(self._build_packet(cmd_type, val, zone))
                    else:
                        cmd_type, val = item  # type: ignore[misc]
                        payload_list.append(self._build_packet(cmd_type, val))

                payload = b"".join(payload_list)

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

    async def async_send_command(
        self, cmd_type: list[int], val: int, zone: int = 0x01
    ) -> None:
        """Send a single command to the controller with rate limiting."""
        await self.async_send_commands([(cmd_type, val, zone)])

    def get_power_command(
        self, on: bool, zone: int = 0x01
    ) -> tuple[list[int], int, int]:
        """Get the power command tuple."""
        val = VAL_POWER_ON if on else VAL_POWER_OFF
        return (CMD_TYPE_POWER, val, zone)

    def get_brightness_command(
        self, ha_brightness: int, zone: int = 0x01
    ) -> tuple[list[int], int, int]:
        """Get the brightness command tuple."""
        val = BRIGHTNESS_MIN + round(
            (ha_brightness / 255.0) * (BRIGHTNESS_MAX - BRIGHTNESS_MIN)
        )
        return (CMD_TYPE_BRIGHTNESS, val, zone)

    def get_rgbw_commands(
        self, r: int, g: int, b: int, w: int, zone: int = 0x01
    ) -> list[tuple[list[int], int, int]]:
        """Get a list of RGBW command tuples."""
        return [
            (CMD_TYPE_RED, r, zone),
            (CMD_TYPE_GREEN, g, zone),
            (CMD_TYPE_BLUE, b, zone),
            (CMD_TYPE_WHITE, w, zone),
        ]

    def get_rainbow_command(
        self, on: bool, zone: int = 0x01
    ) -> tuple[list[int], int, int] | None:
        """Get the rainbow effect command tuple."""
        if on:
            return (CMD_TYPE_RAINBOW, VAL_RAINBOW_ON, zone)
        return None

    def get_speed_command(
        self, speed: int, zone: int = 0x01
    ) -> tuple[list[int], int, int]:
        """Get the speed command tuple."""
        val = max(SPEED_MIN, min(SPEED_MAX, speed))
        return (CMD_TYPE_SPEED, val, zone)

    async def async_set_power(self, on: bool, zone: int = 0x01) -> None:
        """Turn the light on or off."""
        await self.async_send_commands([self.get_power_command(on, zone=zone)])

    async def async_set_brightness(self, ha_brightness: int, zone: int = 0x01) -> None:
        """Set master brightness (map 0-255 to 0x01-0x08)."""
        await self.async_send_commands(
            [self.get_brightness_command(ha_brightness, zone=zone)]
        )

    async def async_set_rgbw(
        self, r: int, g: int, b: int, w: int, zone: int = 0x01
    ) -> None:
        """Set RGBW values."""
        await self.async_send_commands(self.get_rgbw_commands(r, g, b, w, zone=zone))

    async def async_set_rainbow(self, on: bool, zone: int = 0x01) -> None:
        """Activate rainbow mode."""
        cmd = self.get_rainbow_command(on, zone=zone)
        if cmd:
            await self.async_send_commands([cmd])
        else:
            # Turn off power as a safe default when disabling rainbow effect
            await self.async_set_power(False, zone=zone)

    async def async_set_speed(self, speed: int, zone: int = 0x01) -> None:
        """Set pattern speed (1-10)."""
        await self.async_send_commands([self.get_speed_command(speed, zone=zone)])
