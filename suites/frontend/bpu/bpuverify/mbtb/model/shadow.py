"""Bounded captured-cold feedback routing, not a complete FTQ/shadow model.

LRU chooses each request way, while an existing entry shadow retains its owner.
Only one retained key, two rewrites and initially counter-2 residents are covered.
"""
from bpuverify.mbtb.model.entry import expected_mbtb_entry_activity
from bpuverify.mbtb.model.replacement import MbtbTwoWayLru


SHADOW_PHASES = ("clean_first", "pending_second")


def expected_mbtb_shadow_request_ways(owner, phase):
    MbtbTwoWayLru._require_way(owner)
    if phase not in SHADOW_PHASES:
        raise ValueError("MainBTB shadow phase must be clean_first or pending_second")
    lru = MbtbTwoWayLru()
    # A genuine correct-taken hit changes replacement state without entry writes.
    lru.touch(owner if phase == "clean_first" else 1 - owner)
    return lru.allocate(), lru.allocate()


def require_mbtb_shadow_cold_metadata(metadata):
    """Reject fabricated hit feedback and unsupported geometry before driving."""
    if (not isinstance(metadata, (tuple, list)) or len(metadata) != 2
            or any(not isinstance(row, (tuple, list)) or len(row) != 2 for row in metadata)
            or any(not isinstance(entry, dict) or entry.get("rawHit") != 0
                   for row in metadata for entry in row)):
        raise ValueError("shadow replay requires genuine all-miss two-bank/two-way cold metadata")


def expected_mbtb_shadow_activity(pc, position, owner, targets, mode, phase, *, reads=24):
    request_ways = expected_mbtb_shadow_request_ways(owner, phase)
    if not isinstance(pc, int) or pc < 0 or pc & 15:
        raise ValueError("shadow scenario requires an aligned fetch start")
    if len(targets) != 2 or any(not isinstance(target, int) for target in targets):
        raise ValueError("shadow scenario requires two integer target rewrites")
    # Payload/carry/timing follow the existing two-rewrite contract. Deeply
    # independent writeback dictionaries retain owner even as request ways change.
    expected = expected_mbtb_entry_activity(pc, position, owner, targets, mode, reads=reads)
    for payload, way in zip(expected["requests"], request_ways, strict=True):
        payload["way"] = way
    ready = int(mode == "flow")
    # read_valid belongs to the active request port, not global buffer occupancy.
    expected["request_read_state"] = ((0, ready), (int(request_ways[1] == owner), ready))
    return expected
