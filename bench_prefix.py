import timeit

_PACKET_HEADER_IDENTIFIER = b"\x55\x99\x7E\xBD"
_PACKET_CONSTANTS_TAIL = b"\xFF"
_PACKET_PREFIX = _PACKET_HEADER_IDENTIFIER + b"\x01" + _PACKET_CONSTANTS_TAIL

_PACKET_PREFIXES = tuple(
    _PACKET_HEADER_IDENTIFIER + bytes((z,)) + _PACKET_CONSTANTS_TAIL
    for z in range(256)
)

def test_if_else(zone):
    prefix = (
        _PACKET_PREFIX
        if zone == 0x01
        else _PACKET_HEADER_IDENTIFIER + bytes((zone,)) + _PACKET_CONSTANTS_TAIL
    )
    return prefix

def test_array(zone):
    return _PACKET_PREFIXES[zone]

print("if/else (zone 1):", timeit.timeit("test_if_else(1)", globals=globals(), number=1000000))
print("if/else (zone 2):", timeit.timeit("test_if_else(2)", globals=globals(), number=1000000))
print("array (zone 1):", timeit.timeit("test_array(1)", globals=globals(), number=1000000))
print("array (zone 2):", timeit.timeit("test_array(2)", globals=globals(), number=1000000))
