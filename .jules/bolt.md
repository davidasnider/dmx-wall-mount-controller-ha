## 2026-08-16 - ⚡ Bolt: Optimize packet creation
Replaced multiple extend and append calls on a bytearray with a single bytes initialization using unpacking, and replaced modulo % 256 with bitwise AND & 0xFF for checksum calculation to reduce Python function call overhead and speed up packet creation.
## 2026-08-31 - ⚡ Bolt: Optimize packet payload concatenation
**Learning:** In CPython, using `b"".join()` with a generator or list comprehension is significantly faster and more memory-efficient than repeatedly calling `bytearray.extend()` in a loop when batching byte payloads. Also, pre-calculating constant byte prefixes and suffixes at the module level and using simple byte concatenation (`+`) is much faster than dynamically unpacking lists into a new `bytes()` object on every function call.
**Action:** Default to `b"".join()` for batching bytes and pre-calculate constant byte prefixes/suffixes rather than dynamically constructing them.
