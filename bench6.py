import timeit

cmd_type_bytes = b"\x02\x12"
val = 255

prefix = b"\x55\x99\x7E\xBD\x01\xFF"
suffix = b"\xAA\xAA"

def test_tuple():
    checksum = (cmd_type_bytes[0] + cmd_type_bytes[1] + val) & 0xFF
    return prefix + bytes((cmd_type_bytes[0], cmd_type_bytes[1], val, checksum)) + suffix

print("tuple version:", timeit.timeit(test_tuple, number=1000000))
