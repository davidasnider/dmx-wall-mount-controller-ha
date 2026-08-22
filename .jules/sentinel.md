## 2026-08-22 - Missing Input Validation DoS Risk
**Vulnerability:** The `val` parameter in `_build_packet` was only checked for a maximum value (`min(val, 254)`) but not for negative values.
**Learning:** Python's `bytes()` constructor raises a `ValueError` if any byte is not in `range(0, 256)`. Unvalidated negative values can cause the integration to crash, resulting in a Denial of Service.
**Prevention:** Always validate both the upper and lower bounds of integers before converting them into raw bytes (`val = max(0, min(val, 254))`).