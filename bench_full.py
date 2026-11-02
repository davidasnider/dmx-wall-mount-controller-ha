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

def old_build(zone):
    if val < 0:
        v = 0
    elif val > 254:
        v = 254
    else:
        v = val

    checksum = (cmd_type[0] + cmd_type[1] + v) & 0xFF

    prefix = (
        _PACKET_PREFIX
        if zone == 0x01
        else _PACKET_HEADER_IDENTIFIER + bytes((zone,)) + _PACKET_CONSTANTS_TAIL
    )

    return (
        prefix + bytes((cmd_type[0], cmd_type[1], v, checksum)) + _PACKET_SUFFIX
    )

def new_build(zone):
    if val < 0:
        v = 0
    elif val > 254:
        v = 254
    else:
        v = val

    checksum = (cmd_type[0] + cmd_type[1] + v) & 0xFF

    prefix = _PACKET_PREFIXES[zone]

    return (
        prefix + bytes((cmd_type[0], cmd_type[1], v, checksum)) + _PACKET_SUFFIX
    )

print("old (zone 1):", timeit.timeit("old_build(1)", globals=globals(), number=1000000))
print("old (zone 2):", timeit.timeit("old_build(2)", globals=globals(), number=1000000))
print("new (zone 1):", timeit.timeit("new_build(1)", globals=globals(), number=1000000))
print("new (zone 2):", timeit.timeit("new_build(2)", globals=globals(), number=1000000))
