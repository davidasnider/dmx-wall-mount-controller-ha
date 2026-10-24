## 2026-08-22 - Missing Input Validation DoS Risk
**Vulnerability:** The `val` parameter in `_build_packet` was only checked for a maximum value (`min(val, 254)`) but not for negative values.
**Learning:** Python's `bytes()` constructor raises a `ValueError` if any byte is not in `range(0, 256)`. Unvalidated negative values can cause the integration to crash, resulting in a Denial of Service.
**Prevention:** Always validate both the upper and lower bounds of integers before converting them into raw bytes (`val = max(0, min(val, 254))`).
## 2024-05-20 - Log Injection Vulnerability
**Vulnerability:** Unsanitized raw UDP payloads were passed directly to `_LOGGER.debug()`.
**Learning:** Raw network payloads might contain unescaped newline characters `\n` or `\r`. If an attacker sends a crafted payload with these characters, they can write arbitrary lines to the application log, potentially obscuring malicious activity or faking log entries (Log Injection).
**Prevention:** Always sanitize strings originating from external network boundaries before logging them, particularly by escaping line break characters (e.g., `payload.replace("\n", "\\n").replace("\r", "\\r")`).

## 2026-04-05 - Discovery UDP Flood & Memory Exhaustion Mitigation
**Vulnerability:** The integration's UDP discovery protocol continuously listened for incoming datagrams and created an asyncio task for every packet matching the `"HF-LPB100"` signature. A malicious actor on the local network could flood port 48899 with spoofed packets containing varied MAC addresses or extremely long strings. Because Home Assistant core creates an entity creation flow per unique task, this would lead to event loop starvation (DoS) and memory exhaustion.
**Learning:** Even simple local UDP discovery protocols must implement caching/deduplication and strictly bound payload properties (like MAC address length) to prevent resource exhaustion from unauthenticated network inputs.
**Prevention:** Implement a deduplication cache (e.g., `_seen_devices` set) with a strict length cap, and enforce length limits on parsed fields like MAC addresses before processing.

## 2026-10-10 - Unbounded UDP Datagram DoS
**Vulnerability:** The `datagram_received` method accepted and processed UDP packets of any size, leading to potential memory exhaustion before parsing limits could take effect.
**Learning:** Even if individual fields (like MAC addresses) are length-capped later in the pipeline, the raw data must be bounded at the very edge of the network listener to prevent attackers from causing Out-Of-Memory (OOM) errors with massive payloads.
**Prevention:** Enforce a strict, hard maximum length check (`if len(data) > MAX_EXPECTED: return`) as the absolute first operation in any network callback.

## 2026-04-05 - Log Injection in DMX Controller Errors
**Vulnerability:** User-provided or dynamically gathered inputs (like IP address) were being logged directly in `dmx_controller.py` without sanitization. An attacker could craft a payload with newline characters (`\n`, `\r`) to inject fake log entries, obscuring actual logs or confusing administrators.
**Learning:** Even internal class properties that seem safe (like an IP address configured via HA config flow) can carry unsanitized input if the source of that input (e.g. UDP discovery packets) isn't fully sanitized when passed down to the controller layer. The config flow validation for `CONF_HOST` uses `vol.All(str, vol.Length(min=1, max=253))` but doesn't prevent newlines or other control characters.
**Prevention:** Always sanitize inputs such as IP addresses or hostnames by replacing `\n` and `\r` before logging them, or sanitize them at the edge (in the config flow) to ensure the system works with clean data throughout.
