import timeit

cmd_type_bytes = b"\x02\x12"
val = 255

prefix = b"\x55\x99\x7E\xBD\x01\xFF"
suffix = b"\xAA\xAA"

def test_tuple():
    checksum = (0x02 + 0x12 + val) & 0xFF
    return prefix + bytes((0x02, 0x12, val, checksum)) + suffix

def test_bytes():
    checksum = (cmd_type_bytes[0] + cmd_type_bytes[1] + val) & 0xFF
    return prefix + cmd_type_bytes + bytes((val, checksum)) + suffix

print("tuple version (hardcoded):", timeit.timeit(test_tuple, number=1000000))
print("bytes version:", timeit.timeit(test_bytes, number=1000000))
