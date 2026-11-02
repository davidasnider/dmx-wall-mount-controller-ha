1. **Optimize Prefix Creation in `_build_packet`**:
   - Currently, `_build_packet` constructs a static `_PACKET_PREFIX` for `zone == 0x01`. However, for other zones, it dynamically constructs the prefix using concatenation and byte unpacking (`_PACKET_HEADER_IDENTIFIER + bytes((zone,)) + _PACKET_CONSTANTS_TAIL`).
   - We will pre-calculate all possible `_PACKET_PREFIXES` (256 values) during module initialization as a tuple.
   - We will update `_build_packet` to retrieve the prefix from `_PACKET_PREFIXES[zone]`. We'll handle `TypeError` and `IndexError` to gracefully fall back to the existing `ValueError` for out-of-range zones.
   - This optimization eliminates dynamic prefix byte construction for non-default zones and avoids bounds-checking overhead, improving the performance of payload creation.

2. **Verify Changes**:
   - Check the difference using `git diff`.
   - Run tests with `uv run pytest tests/` to confirm correctness.
   - Run format and lint checks (`uv run ruff check .` and `uv run ruff format .`).

3. **Complete Pre-Commit Steps**:
   - Run the pre-commit script to verify the work.

4. **Commit & Submit Changes**:
   - Create a PR locally simulating a Bolt optimization (`⚡ Bolt: Pre-calculate zone packet prefixes`).
