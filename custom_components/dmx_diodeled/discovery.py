import asyncio
import logging
import time
from collections import OrderedDict, deque

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class DMXDiscoveryProtocol(asyncio.DatagramProtocol):
    """Protocol for DMX Controller UDP Discovery."""

    # SECURITY: Hard cap on discovery task creation. The dedup cache bounds
    # *memory*, but a flood of unique MACs would still create one task (and
    # one config-entry flow) per packet; the sliding window below caps the
    # event-loop work that unauthenticated UDP can trigger.
    _MAX_TASKS_PER_WINDOW = 10
    _RATE_LIMIT_WINDOW_SECONDS = 30.0

    # SECURITY: Upper bound on the dedup cache to prevent unbounded memory
    # growth from randomized MACs. The oldest entries are evicted first so
    # recently seen devices stay deduplicated across the cap boundary.
    _SEEN_CACHE_CAP = 1000

    def __init__(self, hass: HomeAssistant, callback):
        self.hass = hass
        self.callback = callback
        self.transport = None
        # LRU dedup cache: oldest entries are evicted when the cap is reached.
        self._seen_devices: OrderedDict[tuple[str, str], None] = OrderedDict()
        # Monotonic timestamps of discovery tasks created within the window.
        self._task_times: deque[float] = deque()
        # Ensures rate-limit drops are logged once per burst, not per packet.
        self._rate_limit_logged = False

    def _allow_discovery_task(self) -> bool:
        """Return True if a discovery task is allowed within the rate limit.

        Maintains a sliding window of recent discovery-task timestamps; once
        ``_MAX_TASKS_PER_WINDOW`` tasks have been created within the last
        ``_RATE_LIMIT_WINDOW_SECONDS``, further requests are rejected until
        entries age out of the window.
        """
        now = time.monotonic()
        cutoff = now - self._RATE_LIMIT_WINDOW_SECONDS
        # Bounded: at most _MAX_TASKS_PER_WINDOW entries live in the window.
        while self._task_times and self._task_times[0] <= cutoff:
            self._task_times.popleft()
        if len(self._task_times) >= self._MAX_TASKS_PER_WINDOW:
            return False
        self._task_times.append(now)
        return True

    def connection_made(self, transport):
        """Handle connection established."""
        self.transport = transport
        _LOGGER.debug("DMX Discovery UDP listener started on port 48899")

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        """Handle received datagram."""
        # SECURITY: Drop overly large UDP packets to prevent memory exhaustion and DoS
        if len(data) > 1024:
            return

        # Performance optimization: Fast-path reject unrelated broadcast packets
        # before expensive string decoding and memory allocation.
        if b"HF-LPB100" not in data:
            return

        try:
            payload = data.decode("utf-8", errors="ignore").strip()
            # SECURITY: Sanitize the raw network payload before logging to prevent Log Injection
            sanitized_payload = payload.replace("\n", "\\n").replace("\r", "\\r")
            _LOGGER.debug("Received UDP payload: %s from %s", sanitized_payload, addr)
            parts = payload.split(",")
            if len(parts) >= 3 and "HF-LPB100" in parts[2]:
                # Use the packet source address as the authoritative host: the
                # IP embedded in the payload can be spoofed by any host on the
                # network.
                ip_address = addr[0]
                mac_address = parts[1]

                # SECURITY: Validate MAC length to prevent memory exhaustion from oversized payloads
                if len(mac_address) > 64:
                    return

                # SECURITY: Deduplicate discovery tasks to prevent event loop starvation
                # from UDP floods. Cap cache size (LRU eviction) to prevent memory leaks.
                device_key = (mac_address, ip_address)
                if device_key in self._seen_devices:
                    return

                # SECURITY: Rate limit discovery task creation so a rotating-unique-MAC
                # flood cannot keep spawning tasks/flows. The device is intentionally not
                # marked as seen here, so it stays eligible for a later broadcast once the
                # window clears.
                if not self._allow_discovery_task():
                    # Log once per burst, not for every dropped packet.
                    if not self._rate_limit_logged:
                        _LOGGER.warning(
                            "DMX discovery rate limit reached (%d tasks per %.0fs); further discoveries will be dropped until the window clears",
                            self._MAX_TASKS_PER_WINDOW,
                            self._RATE_LIMIT_WINDOW_SECONDS,
                        )
                    self._rate_limit_logged = True
                    return
                self._rate_limit_logged = False

                # SECURITY: Evict the oldest entries when the bounded cap is reached
                # instead of clearing everything, so recently seen devices remain
                # deduplicated across the cap boundary.
                while len(self._seen_devices) >= self._SEEN_CACHE_CAP:
                    self._seen_devices.popitem(last=False)
                self._seen_devices[device_key] = None

                if ip_address != parts[0]:
                    # SECURITY: Sanitize claimed IP to prevent Log Injection
                    sanitized_claimed_ip = (
                        parts[0].replace("\n", "\\n").replace("\r", "\\r")
                    )
                    _LOGGER.warning(
                        "Discovered device claimed IP %s but packet arrived from %s; using sender address",
                        sanitized_claimed_ip,
                        ip_address,
                    )
                # SECURITY: Sanitize MAC address to prevent Log Injection
                sanitized_mac = mac_address.replace("\n", "\\n").replace("\r", "\\r")
                _LOGGER.info(
                    "Discovered DMX Controller at %s (MAC: %s)",
                    ip_address,
                    sanitized_mac,
                )
                self.hass.async_create_task(self.callback(ip_address, mac_address))
        except Exception:
            _LOGGER.exception("Error parsing UDP payload from %s", addr)


async def async_start_discovery(
    hass: HomeAssistant, callback
) -> asyncio.DatagramTransport | None:
    """Start the UDP discovery listener."""
    loop = asyncio.get_running_loop()
    try:
        transport, _ = await loop.create_datagram_endpoint(
            lambda: DMXDiscoveryProtocol(hass, callback),
            local_addr=("0.0.0.0", 48899),
        )
        return transport
    except Exception:
        _LOGGER.exception("Failed to start UDP listener on port 48899")
        return None
