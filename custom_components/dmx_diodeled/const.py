"""Constants for the DiodeLED DMX Controller integration."""

import logging

LOGGER = logging.getLogger(__package__)

DOMAIN: str = "dmx_diodeled"

DEFAULT_PORT: int = 8899
DEFAULT_NAME: str = "DiodeLED DMX Controller"

# Command Frame Components
HEADER: int = 0x55
IDENTIFIER: list[int] = [0x99, 0x7E, 0xBD]
CONSTANTS: list[int] = [0x01, 0xFF]
FOOTER: list[int] = [0xAA, 0xAA]

# Command Types (Byte 7 and 8)
CMD_TYPE_POWER: list[int] = [0x02, 0x12]
CMD_TYPE_BRIGHTNESS: list[int] = [0x08, 0x23]
CMD_TYPE_RED: list[int] = [0x08, 0x48]
CMD_TYPE_GREEN: list[int] = [0x08, 0x49]
CMD_TYPE_BLUE: list[int] = [0x08, 0x4A]
CMD_TYPE_WHITE: list[int] = [0x08, 0x4B]
CMD_TYPE_RAINBOW: list[int] = [0x02, 0x4E]
CMD_TYPE_SPEED: list[int] = [0x08, 0x22]

# Values
VAL_POWER_ON: int = 0xAB
VAL_POWER_OFF: int = 0xA9
VAL_RAINBOW_ON: int = 0x17

# Limits
BRIGHTNESS_MIN: int = 0x01
BRIGHTNESS_MAX: int = 0x08
SPEED_MIN: int = 0x01
SPEED_MAX: int = 0x0A

# Rate Limiting (seconds between network payloads)
THROTTLE_DELAY: float = (
    0.1  # Hardware handles burst commands, but we delay between socket calls
)

# Maximum number of commands to batch in a single network payload
# Set to 1 because hardware requires one TCP connection per 12-byte command
CMD_CHUNK_SIZE: int = 1
