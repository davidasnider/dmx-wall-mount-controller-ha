"""Constants for the DiodeLED DMX Controller integration."""

import logging

LOGGER = logging.getLogger(__package__)

DOMAIN = "dmx_diodeled"

DEFAULT_PORT = 8899
DEFAULT_NAME = "DiodeLED DMX Controller"

# Command Frame Components
HEADER = 0x55
IDENTIFIER = [0x99, 0x7E, 0xBD]
CONSTANTS = [0x01, 0xFF]
FOOTER = [0xAA, 0xAA]

# Command Types (Byte 7 and 8)
CMD_TYPE_POWER = [0x02, 0x12]
CMD_TYPE_BRIGHTNESS = [0x08, 0x23]
CMD_TYPE_RED = [0x08, 0x48]
CMD_TYPE_GREEN = [0x08, 0x49]
CMD_TYPE_BLUE = [0x08, 0x4A]
CMD_TYPE_WHITE = [0x08, 0x4B]
CMD_TYPE_RAINBOW = [0x02, 0x4E]
CMD_TYPE_SPEED = [0x08, 0x22]

# Values
VAL_POWER_ON = 0xAB
VAL_POWER_OFF = 0xA9
VAL_RAINBOW_ON = 0x17

# Limits
BRIGHTNESS_MIN = 0x01
BRIGHTNESS_MAX = 0x08
SPEED_MIN = 0x01
SPEED_MAX = 0x0A

# Rate Limiting (seconds between network payloads)
THROTTLE_DELAY = 0.1  # Hardware handles burst commands, but we delay between socket calls

# Maximum number of commands to batch in a single network payload
CMD_CHUNK_SIZE = 15
