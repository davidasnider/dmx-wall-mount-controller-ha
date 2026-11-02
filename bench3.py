import timeit

cmd_type_list = [0x02, 0x12]
cmd_type_tuple = (0x02, 0x12)
val = 255

prefix = b"\x55\x99\x7E\xBD\x01\xFF"
suffix = b"\xAA\xAA"

def test_list():
    checksum = (cmd_type_list[0] + cmd_type_list[1] + val) & 0xFF
    return prefix + bytes((cmd_type_list[0], cmd_type_list[1], val, checksum)) + suffix

def test_tuple():
    checksum = (cmd_type_tuple[0] + cmd_type_tuple[1] + val) & 0xFF
    return prefix + bytes((cmd_type_tuple[0], cmd_type_tuple[1], val, checksum)) + suffix

print("list version:", timeit.timeit(test_list, number=1000000))
print("tuple version:", timeit.timeit(test_tuple, number=1000000))
