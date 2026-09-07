## 2026-08-16 - ⚡ Bolt: Optimize packet creation
Replaced multiple extend and append calls on a bytearray with a single bytes initialization using unpacking, and replaced modulo % 256 with bitwise AND & 0xFF for checksum calculation to reduce Python function call overhead and speed up packet creation.
## 2026-08-31 - ⚡ Bolt: Optimize packet payload concatenation
**Learning:** In CPython, using `b"".join()` with a generator or list comprehension is significantly faster and more memory-efficient than repeatedly calling `bytearray.extend()` in a loop when batching byte payloads. Also, pre-calculating constant byte prefixes and suffixes at the module level and using simple byte concatenation (`+`) is much faster than dynamically unpacking lists into a new `bytes()` object on every function call.
**Action:** Default to `b"".join()` for batching bytes and pre-calculate constant byte prefixes/suffixes rather than dynamically constructing them.
## 2024-05-19 - Python function call overhead in hot paths
**Learning:** Python's built-in `min()` and `max()` functions have surprising overhead compared to simple `if/elif` bounds checking when executed inside tight loops or hot paths (like building byte payloads for DMX network packets).
**Action:** When micro-optimizing extremely frequent byte manipulation logic, use `if/elif` rather than `min()`/`max()` and avoid list unpacking `*list` inside `bytes()` where direct indexing `list[0], list[1]` works just as well.
