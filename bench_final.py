import timeit

_PACKET_HEADER_IDENTIFIER = b"\x55\x99\x7E\xBD"
_PACKET_CONSTANTS_TAIL = b"\xFF"
_PACKET_PREFIX = _PACKET_HEADER_IDENTIFIER + b"\x01" + _PACKET_CONSTANTS_TAIL
_PACKET_SUFFIX = b"\xAA\xAA"
_PACKET_PREFIXES = tuple(
    _PACKET_HEADER_IDENTIFIER + bytes((z,)) + _PACKET_CONSTANTS_TAIL
    for z in range(256)
)

cmd_type = [0x08, 0x23]
val = 128
zone = 2

def current(cmd_type, val, zone):
    if val < 0:
        val = 0
    elif val > 254:
        val = 254

    checksum = (cmd_type[0] + cmd_type[1] + val) & 0xFF

    if not 0 <= zone <= 0xFF:
        raise ValueError(f"zone must be a byte (0-255), got {zone!r}")

    prefix = (
        _PACKET_PREFIX
        if zone == 0x01
        else _PACKET_HEADER_IDENTIFIER + bytes((zone,)) + _PACKET_CONSTANTS_TAIL
    )

    return (
        prefix + bytes((cmd_type[0], cmd_type[1], val, checksum)) + _PACKET_SUFFIX
    )

def optimized(cmd_type, val, zone):
    if val < 0:
        val = 0
    elif val > 254:
        val = 254

    checksum = (cmd_type[0] + cmd_type[1] + val) & 0xFF

    try:
        prefix = _PACKET_PREFIXES[zone]
    except IndexError:
        raise ValueError(f"zone must be a byte (0-255), got {zone!r}") from None

    return (
        prefix + bytes((cmd_type[0], cmd_type[1], val, checksum)) + _PACKET_SUFFIX
    )

print("current zone 1:", timeit.timeit("current(cmd_type, val, 1)", globals=globals(), number=1000000))
print("optimized zone 1:", timeit.timeit("optimized(cmd_type, val, 1)", globals=globals(), number=1000000))
print("current zone 2:", timeit.timeit("current(cmd_type, val, 2)", globals=globals(), number=1000000))
print("optimized zone 2:", timeit.timeit("optimized(cmd_type, val, 2)", globals=globals(), number=1000000))
