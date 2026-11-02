import timeit

cmd_type_list = [0x02, 0x12]
cmd_type_bytes = b"\x02\x12"
val = 255
checksum = (cmd_type_list[0] + cmd_type_list[1] + val) & 0xFF

prefix = b"\x55\x99\x7E\xBD\x01\xFF"
suffix = b"\xAA\xAA"

def test_list():
    return prefix + bytes((cmd_type_list[0], cmd_type_list[1], val, checksum)) + suffix

def test_bytes():
    return prefix + cmd_type_bytes + bytes((val, checksum)) + suffix

print("list version:", timeit.timeit(test_list, number=1000000))
print("bytes version:", timeit.timeit(test_bytes, number=1000000))
