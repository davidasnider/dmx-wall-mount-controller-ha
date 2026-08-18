## 2026-08-16 - ⚡ Bolt: Optimize packet creation
Replaced multiple extend and append calls on a bytearray with a single bytes initialization using unpacking, and replaced modulo % 256 with bitwise AND & 0xFF for checksum calculation to reduce Python function call overhead and speed up packet creation.
