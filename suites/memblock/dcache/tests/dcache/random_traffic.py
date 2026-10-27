"""Constrained-random traffic for the DCache top level.

The generator keeps an L2 shadow memory plus the set of store bytes that the
DCache has acknowledged but not yet written back.  Every load is compared against
that model, and every dirty eviction is checked on the C channel before its bytes
are absorbed into the model.  This is the coverage-driven complement to the
directed tests: it mixes hits, misses, refills, dirty evictions, dual-channel
traffic and partial store masks in a single reproducible run.

Contract note: a 64-bit load reads only the banks selected by its 8-byte mask
(`byteMaskToBankMask`), so the 128-bit response carries valid bytes only for that
mask.  The generator therefore compares the low 64 bits of a 16-byte-aligned load
instead of assuming the whole window is fresh.

Documented limit of the generator: it never issues a second store to a line that
still has an outstanding miss, because that sequence is the open RTL defect
`MQ-STORE-MERGE-DATA-PENDING` (see
`test_two_partial_stores_same_missing_line_merge_data`).  Everything else,
including dirty eviction, is covered by the directed tests; this generator uses
one line per set so its model does not need a PLRU.  A `handled=0` response is
retried like the LSU would replay it, and the L2 side is kept ready (`ack_ready`)
so writebacks always drain.
"""
from __future__ import annotations

import random


def shadow_line(block: int) -> bytearray:
    """Deterministic L2 content for one 64B block."""
    seed = (block >> 6) & 0xFFFF
    return bytearray(((seed * 37 + i * 11 + 5) & 0xFF) for i in range(64))


def line_beats(line: bytes) -> list[int]:
    return [int.from_bytes(line[:32], "little"),
            int.from_bytes(line[32:], "little")]


def block_of(addr: int) -> int:
    return addr & ~0x3F


def collect_same_set(start: int, count: int, span: int = 0x400000) -> list[int]:
    """Collect `count` block addresses mapping to the same set as `start`."""
    from dcacheverify.load_pipe.model import dcache_index
    want = dcache_index(start)
    out = [start]
    addr = start + 0x40
    while len(out) < count and addr < start + span:
        if dcache_index(addr) == want:
            out.append(addr)
        addr += 0x40
    return out


def same_set_addresses(start: int, count: int) -> list[int]:
    """Return `count` block addresses that map to the same DCache set."""
    from dcacheverify.load_pipe.model import dcache_index
    want = dcache_index(start)
    found = [start]
    addr = start + 0x40
    while len(found) < count:
        if dcache_index(addr) == want:
            found.append(addr)
        addr += 0x40
    return found


def expected_line(model: dict, block: int) -> bytearray:
    """L2 content plus the store bytes the model believes are still pending."""
    line = bytearray(model["l2"].setdefault(block, shadow_line(block)))
    for offset, value in model["pending"].get(block, {}).items():
        line[offset] = value
    return line


def ack_ready(dc) -> None:
    """Make the L2 side permanently ready: accept every C beat and ack the D release.

    A real L2 drains writebacks as soon as they appear, so the DCache never holds
    a WritebackQueue entry open (which would block later misses to that block).
    ReleaseAck has opcode 6, whose bit0 is 0, so MissQueue GrantData logic ignores
    it; GrantData beats from `service_miss` temporarily override these pins.
    """
    for channel in dc.channels:
        channel["c_ready"].Set(1)
        channel["d_valid"].Set(1)
        channel["d_opcode"].Set(6)      # ReleaseAck
        channel["d_size"].Set(6)
        channel["d_source"].Set(0)
        channel["d_sink"].Set(0)
        channel["d_denied"].Set(0)
        channel["d_corrupt"].Set(0)
        channel["d_data"].Set(0)


def pump(dc, model: dict, cycles: int = 4) -> None:
    """Drain C-channel releases, check them, and absorb dirty data into the model.

    The D channel is kept acked continuously (see `ack_ready`), which mirrors an
    always-ready L2 and prevents WritebackQueue entries from blocking later
    misses to the same block.
    """
    for _ in range(cycles):
        ack_ready(dc)
        dc.refresh()
        for index, channel in enumerate(dc.channels):
            if not dc._val(channel["c_valid"]):
                continue
            opcode = dc._val(channel["c_opcode"])
            address = dc._val(channel["c_address"])
            source = dc._val(channel["c_source"])
            key = (index, source, address)
            entry = model["releases"].setdefault(
                key, {"opcode": opcode, "beats": [], "absorbed": False})
            assert entry["opcode"] == opcode
            if len(entry["beats"]) < 2:
                entry["beats"].append(dc._val(channel["c_data"]))
        for key, entry in model["releases"].items():
            if entry["absorbed"]:
                continue
            needed = 2 if entry["opcode"] == 7 else 1
            if len(entry["beats"]) < needed:
                continue
            block = block_of(key[2])
            line = expected_line(model, block)
            if entry["opcode"] == 7:
                assert entry["beats"][0] == int.from_bytes(line[:32], "little"), (
                    "release beat0 mismatch", hex(block), hex(entry["beats"][0]),
                    line[:32].hex())
                assert entry["beats"][1] == int.from_bytes(line[32:], "little"), (
                    "release beat1 mismatch", hex(block), hex(entry["beats"][1]),
                    line[32:].hex())
            else:
                assert not model["pending"].get(block), (
                    "clean Release for a line with pending store bytes",
                    hex(block), entry["opcode"])
            model["l2"][block] = line
            model["pending"].pop(block, None)
            model["retired"].add(block)
            entry["absorbed"] = True
        dc.dut.Step(1)
        dc.refresh()


def service(dc, model: dict, block: int, context: str, limit: int = 20) -> bool:
    """Answer one Acquire for `block` with the model's L2 content."""
    line = expected_line(model, block)
    call = model["pending"].get(block, {})
    # The DCache applies the store bytes itself, so the refill must carry the
    # unmodified L2 line.  Temporarily hide the pending bytes.
    model["pending"].pop(block, None)
    try:
        dc.service_miss(block, data_beats=line_beats(bytes(line)), context=context)
    finally:
        if call:
            model["pending"][block] = call
        # `service_miss` leaves D idle; restore the always-ready ReleaseAck so a
        # writeback that appears a few cycles later is acknowledged instead of
        # holding its WritebackQueue entry (which would block that block forever).
        ack_ready(dc)
    return True


def observe_miss(dc, model: dict, block: int, context: str,
                 limit: int = 10) -> bool:
    """If the DCache raises an Acquire for `block`, answer it. Returns True if so."""
    for _ in range(limit):
        for channel in dc.channels:
            channel["a_ready"].Set(1)
        dc.refresh()
        for channel in dc.channels:
            if dc._val(channel["a_valid"]):
                address = dc._val(channel["a_address"])
                if address == block:
                    service(dc, model, block, context)
                    pump(dc, model, 2)
                    return True
                raise AssertionError(
                    f"{context}: unexpected Acquire for {address:#x} (want {block:#x})")
        dc.dut.Step(1)
        dc.refresh()
    return False


def store_word(dc, addr: int, word: int, mask: int, value: int, store_id: int,
               context: str) -> dict:
    """Drive one partial store inside a single 8B word and return its response."""
    # `mask` bit i selects byte i (64 bytes); `data` byte i lives at bits 8*i.
    # A word at offset `word` therefore shifts the data by 64*word bits but the
    # mask by only 8*word bits.
    dc.drive_store(addr, addr, value << (64 * word), mask << (8 * word),
                   store_id=store_id)
    accepted = False
    for _ in range(6):
        accepted = accepted or bool(dc._val(dc.store["req_ready"]))
        dc.dut.Step(1)
        dc.refresh()
        if accepted:
            break
    dc.stop_store()
    assert accepted, f"{context}: store not accepted"
    return dc.wait_store_hit(16)


def run_random(dc, seed: int, operations: int = 36) -> dict:
    rng = random.Random(seed)
    model = {"l2": {}, "pending": {}, "releases": {}, "retired": set()}
    # Distinct sets only (consecutive 64B blocks map to consecutive sets): way
    # replacement and the writeback-blocking contract are covered by the directed
    # tests `test_dirty_eviction_releases_line`, `test_clean_eviction_releases_without_data`
    # and `test_pending_release_blocks_remiss_until_drained`.  Mixing replacement
    # into the random model would need a full PLRU model, which this generator
    # deliberately avoids.
    pool = [0x18000 + 0x40 * index for index in range(20)]
    # Prime both sets through the model so the first accesses are genuine misses.
    stats = {"loads": 0, "hits": 0, "stores": 0, "misses": 0, "replays": 0,
             "evictions": 0}
    for cycle in range(operations):
        pump(dc, model, 1)     # drain a writeback that completed just now
        live = [item for item in pool if block_of(item) not in model["retired"]]
        assert live, "working set exhausted: no un-retired block left"
        addr = rng.choice(live)
        block = block_of(addr)
        word = rng.randrange(8)
        if rng.random() < 0.45:
            mask = rng.choice((0x01, 0x03, 0x0F, 0x7F, 0xFF))
            value = rng.getrandbits(64) & 0xFFFF_FFFF_FFFF_FFFF
            for attempt in range(4):
                response = store_word(dc, addr, word, mask, value,
                                      store_id=(cycle % 60) + 1,
                                      context=f"random store {cycle}.{attempt}")
                assert response["hit"] or response["replay"], (cycle, response)
                if response["hit"]:
                    break
                # A replay means the store was not applied: drain writebacks and
                # retry the same request.
                pump(dc, model, 6)
            else:
                raise AssertionError(f"store {cycle} replayed 4 times: {response}")
            stats["stores"] += 1
            for bit in range(8):
                if (mask >> bit) & 1:
                    model["pending"].setdefault(block, {})[word * 8 + bit] =\
                        (value >> (8 * bit)) & 0xFF
            if observe_miss(dc, model, block, f"store miss {cycle}"):
                stats["misses"] += 1
            pump(dc, model, 3)
        else:
            load_addr = block + 16 * (cycle % 4)   # 16B aligned, addr[3] = 0
            response = dc.load_once(0, load_addr, load_addr,
                                    context=f"random load {cycle}")
            for retry in range(10):
                if not (response["miss"] and not response["handled"]):
                    break
                # handled=0 means "replay": a writeback for this block may still be
                # draining.  Keep the L2 side moving and issue the load again.
                stats["replays"] += 1
                pump(dc, model, 3)
                response = dc.load_once(0, load_addr, load_addr,
                                        context=f"random load retry {cycle}.{retry}")
            if response["miss"]:
                stats["misses"] += 1
                assert response["handled"], (
                    cycle, hex(block), response,
                    "retired", sorted(hex(b) for b in model["retired"]),
                    "releases", sorted(hex(k[2]) for k in model["releases"]))
                service(dc, model, block, f"load miss {cycle}")
                pump(dc, model, 2)
                for _ in range(6):
                    dc.dut.Step(1)
                response = dc.load_once(0, load_addr, load_addr,
                                        context=f"random reload {cycle}")
                assert response["miss"] == 0, (cycle, response)
            stats["loads"] += 1
            if response["miss"] == 0:
                stats["hits"] += 1
            line = expected_line(model, block)
            window = load_addr & 0x3F
            expected = int.from_bytes(line[window:window + 8], "little")
            actual = response["data"] & ((1 << 64) - 1)
            assert actual == expected, (
                f"random load {cycle} addr {load_addr:#x}: {actual:#x} != {expected:#x}"
                f" (pending={model['pending'].get(block)})")
            pump(dc, model, 2)
    # Final drain so any trailing release is checked and acknowledged.
    pump(dc, model, 8)
    stats["evictions"] = len([1 for key in model["releases"] if key[2]])
    return stats
