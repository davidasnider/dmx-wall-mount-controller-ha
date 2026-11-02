import timeit

_PACKET_HEADER_IDENTIFIER = b"\x55\x99\x7E\xBD"
_PACKET_CONSTANTS_TAIL = b"\xFF"
_PACKET_PREFIXES = tuple(
    _PACKET_HEADER_IDENTIFIER + bytes((z,)) + _PACKET_CONSTANTS_TAIL
    for z in range(256)
)
_PACKET_PREFIX = _PACKET_PREFIXES[1]
_PACKET_SUFFIX = b"\xAA\xAA"

def new2(zone):
    try:
        return _PACKET_PREFIXES[zone]
    except IndexError:
        raise ValueError() from None
    except TypeError:
        if type(zone) is not int:
            raise ValueError() from None
        raise

print("new2 zone 1:", timeit.timeit("new2(1)", globals=globals(), number=1000000))
print("new2 zone 2:", timeit.timeit("new2(2)", globals=globals(), number=1000000))
