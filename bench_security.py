import timeit

_PACKET_HEADER_IDENTIFIER = b"\x55\x99\x7E\xBD"
_PACKET_CONSTANTS_TAIL = b"\xFF"
_PACKET_PREFIXES = tuple(
    _PACKET_HEADER_IDENTIFIER + bytes((z,)) + _PACKET_CONSTANTS_TAIL
    for z in range(256)
)
_PACKET_PREFIX = _PACKET_PREFIXES[1]
_PACKET_SUFFIX = b"\xAA\xAA"
cmd_type = [0x08, 0x23]
val = 128

def old(zone):
    if not 0 <= zone <= 0xFF:
        raise ValueError()
    prefix = (
        _PACKET_PREFIX
        if zone == 0x01
        else _PACKET_HEADER_IDENTIFIER + bytes((zone,)) + _PACKET_CONSTANTS_TAIL
    )
    return prefix

def new(zone):
    if type(zone) is not int or not 0 <= zone <= 0xFF:
        raise ValueError()
    return _PACKET_PREFIXES[zone]

print("old zone 1:", timeit.timeit("old(1)", globals=globals(), number=1000000))
print("old zone 2:", timeit.timeit("old(2)", globals=globals(), number=1000000))
print("new zone 1:", timeit.timeit("new(1)", globals=globals(), number=1000000))
print("new zone 2:", timeit.timeit("new(2)", globals=globals(), number=1000000))
