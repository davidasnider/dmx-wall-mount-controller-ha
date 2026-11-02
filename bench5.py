import timeit

cmd_type_bytes = b"\x02\x12"
val = 255
checksum = (0x02 + 0x12 + val) & 0xFF

prefix = b"\x55\x99\x7E\xBD\x01\xFF"
suffix = b"\xAA\xAA"

def test_concat():
    return prefix + cmd_type_bytes + bytes((val, checksum)) + suffix

print("concat version:", timeit.timeit(test_concat, number=1000000))
