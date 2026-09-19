## 2026-08-22 - Missing Input Validation DoS Risk
**Vulnerability:** The `val` parameter in `_build_packet` was only checked for a maximum value (`min(val, 254)`) but not for negative values.
**Learning:** Python's `bytes()` constructor raises a `ValueError` if any byte is not in `range(0, 256)`. Unvalidated negative values can cause the integration to crash, resulting in a Denial of Service.
**Prevention:** Always validate both the upper and lower bounds of integers before converting them into raw bytes (`val = max(0, min(val, 254))`).
## 2024-05-20 - Log Injection Vulnerability
**Vulnerability:** Unsanitized raw UDP payloads were passed directly to `_LOGGER.debug()`.
**Learning:** Raw network payloads might contain unescaped newline characters `\n` or `\r`. If an attacker sends a crafted payload with these characters, they can write arbitrary lines to the application log, potentially obscuring malicious activity or faking log entries (Log Injection).
**Prevention:** Always sanitize strings originating from external network boundaries before logging them, particularly by escaping line break characters (e.g., `payload.replace("\n", "\\n").replace("\r", "\\r")`).
