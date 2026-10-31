"""MissTrack UT: install/alloc/training/retire/invalidate/clear and S1 speculation."""
from __future__ import annotations

import random

import pytest

from suites.memblock.dcache.miss_track.coverage import MissTrackCoverage
from suites.memblock.dcache.miss_track.env import MissTrackEnv
from suites.memblock.dcache.miss_track.model import (
    Alloc,
    Install,
    Invalidate,
    Load,
    Owner,
    block,
    index,
)


@pytest.fixture
def mt(dut_factory):
    dut = dut_factory("miss_track")
    env = MissTrackEnv(dut, MissTrackCoverage())
    env.reset()
    return env


def owners_for(*entries):
    owners = [Owner() for _ in range(16)]
    for slot, vaddr, paddr in entries:
        owners[slot] = Owner(valid=True, vaddr=vaddr, paddr=paddr)
    return owners


def install(env, va, pa, way=0b0001):
    env.cycle(install=Install(valid=True, vaddr=va, paddr=pa, way=way),
              context="install")


def empty_loads(lane=0):
    loads = [Load() for _ in range(3)]
    return loads


# MT-FP-004
def test_reset_and_unknown_candidate(mt):
    mt.cycle(context="reset idle")
    spec = mt.query(0x1234, 0x5678, expected="candidate", context="empty table")
    assert spec.candidate == 1
    # Lane 1 and 2 have their own independent query path.
    for lane in (1, 2):
        mt.query(0x2200 + lane * 0x40, 0x8800, lane=lane,
                 expected="candidate", context=f"lane {lane}")


# MT-FP-001
def test_install_produces_resident_entry(mt):
    va, pa = 0x4000, 0x9000
    install(mt, va, pa, way=0b0001)
    spec = mt.query(va, pa, expected="resident")
    for lane in (1, 2):
        mt.query(va, pa, lane=lane, expected="resident", context=f"resident lane {lane}")
    # Same key, different physical block -> UNKNOWN candidate.
    mt.query(va, pa + 0x1000, expected="candidate", context="paddr mismatch")
    # Different virtual line -> no history.
    mt.query(va ^ 0x1000, pa, expected="candidate", context="vaddr mismatch")
    # A multi-way install must be ignored.
    install(mt, 0x5000, 0xA000, way=0b0011)
    mt.query(0x5000, 0xA000, expected="candidate", context="multi-way install")


# MT-FP-002, MT-FP-008
def test_alloc_pending_and_owner_retirement(mt):
    va, pa, mshr = 0x6000, 0xB000, 3
    owners = owners_for((mshr, va, pa))
    mt.cycle(allocs=[Alloc(valid=True, vaddr=va, paddr=pa, mshr_id=mshr)] +
                    [Alloc() for _ in range(3)],
             owners=owners, context="alloc")
    spec = mt.query(va, pa, expected="pending", owners=owners)
    mt.coverage.sample_lifecycle(owner="live")
    # The owner stays valid: the pending entry survives several cycles.
    for _ in range(4):
        mt.cycle(owners=owners, context="owner alive")
    mt.query(va, pa, expected="pending", context="owner alive", owners=owners)
    # Owner disappears: the pending entry is retired on the next edge.
    mt.cycle(context="owner gone")
    mt.query(va, pa, expected="candidate", context="retired")
    mt.coverage.sample_lifecycle(owner="retired")


# MT-FP-003
def test_s2_hit_training(mt):
    va, pa = 0x7000, 0xC000
    loads = [Load() for _ in range(3)]
    loads[0] = Load(s2_valid=True, s2_hit=True, s2_vaddr=va, s2_paddr=pa,
                    s2_way=0b0010)
    mt.cycle(loads=loads, context="train")
    mt.query(va, pa, expected="resident", context="trained")
    # A miss does not train.
    va2, pa2 = 0x7400, 0xD000
    loads[0] = Load(s2_valid=True, s2_hit=False, s2_vaddr=va2, s2_paddr=pa2,
                    s2_way=0b0001)
    mt.cycle(loads=loads, context="miss train")
    mt.query(va2, pa2, expected="candidate", context="miss not trained")
    # Multi-way training does not train.
    va3, pa3 = 0x7800, 0xE000
    loads[0] = Load(s2_valid=True, s2_hit=True, s2_vaddr=va3, s2_paddr=pa3,
                    s2_way=0b0011)
    mt.cycle(loads=loads, context="multi-way train")
    mt.query(va3, pa3, expected="candidate", context="multi-way not trained")


# MT-FP-006
def test_invalidate_resident_and_not_pending(mt):
    va, pa = 0x8000, 0x1_0000
    install(mt, va, pa, way=0b0001)
    # Non-overlapping way: entry stays.
    mt.cycle(invalidate=Invalidate(valid=True, idx=index(va), way=0b0010),
             context="invalid way")
    mt.query(va, pa, expected="resident", context="invalid way")
    mt.coverage.sample_lifecycle(invalidate="miss")
    # Matching idx+way: entry is removed.
    mt.cycle(invalidate=Invalidate(valid=True, idx=index(va), way=0b0001),
             context="invalidate hit")
    mt.query(va, pa, expected="candidate", context="invalidated")
    mt.coverage.sample_lifecycle(invalidate="hit")
    # Pending entries are not affected by invalidate.
    va2, pa2 = 0x8400, 0x1_1000
    owners = owners_for((2, va2, pa2))
    mt.cycle(allocs=[Alloc(valid=True, vaddr=va2, paddr=pa2, mshr_id=2)] +
                    [Alloc() for _ in range(3)],
             owners=owners,
             invalidate=Invalidate(valid=True, idx=index(va2), way=0b1111),
             context="alloc plus invalidate")
    mt.query(va2, pa2, expected="pending", context="pending not invalidated", owners=owners)


# MT-FP-006
def test_clear_suppresses_and_empties(mt):
    va, pa = 0x9000, 0x1_2000
    install(mt, va, pa)
    mt.query(va, pa, expected="resident")
    # A query in flight while clear is asserted must be suppressed.
    loads = [Load() for _ in range(3)]
    loads[0] = Load(s0_valid=True, s0_vaddr=va)
    mt.cycle(loads=loads, context="query before clear")
    loads[0] = Load(s1_valid=True, s1_paddr=pa)
    mt.cycle(loads=loads, clear=True, context="clear with query")
    mt.query(va, pa, expected="candidate", context="after clear")
    for entry in mt.model.entries:
        assert not entry.valid


# MT-FP-005
def test_multi_hit_suppression(mt):
    # Same {idx, hash} key, different physical block.
    va1, pa1 = 0x1000, 0x2_0000
    va2, pa2 = 0x1001, 0x3_0000
    assert index(va1) == index(va2)
    install(mt, va1, pa1, way=0b0001)
    install(mt, va2, pa2, way=0b0010)
    # Both entries share the key, so the query is suppressed.
    for lane in range(3):
        mt.query(va1, pa1, lane=lane, expected="suppressed",
                 context=f"multi lane {lane}")
    # Removing one entry restores a unique resident match.
    mt.cycle(invalidate=Invalidate(valid=True, idx=index(va1), way=0b0001),
             context="invalidate first")
    mt.query(va1, pa1, expected="candidate", context="invalidated block")
    mt.query(va2, pa2, expected="resident", context="other block")


# MT-FP-007
def test_event_priority_and_coalescing(mt):
    va_a, pa_a = 0xA000, 0x4_0000
    va_b, pa_b = 0xA400, 0x5_0000
    # install and alloc for the same line: install wins, one record.
    loads = [Load() for _ in range(3)]
    mt.cycle(loads=loads,
             allocs=[Alloc(valid=True, vaddr=va_a, paddr=pa_a, mshr_id=1)] +
                    [Alloc() for _ in range(3)],
             owners=owners_for((1, va_a, pa_a)),
             install=Install(valid=True, vaddr=va_a, paddr=pa_a, way=0b0010),
             context="install + alloc same line")
    mt.query(va_a, pa_a, expected="resident", context="install wins")
    # Different lines compete for the single insertion port: the round-robin
    # arbiter starts at slot 1, so the allocation wins and the install is lost.
    mt.cycle(allocs=[Alloc(valid=True, vaddr=va_b, paddr=pa_b, mshr_id=2)] +
                    [Alloc() for _ in range(3)],
             owners=owners_for((2, va_b, pa_b)),
             install=Install(valid=True, vaddr=0xA800, paddr=0x6_0000,
                             way=0b0100),
             context="install + alloc different lines")
    mt.query(va_b, pa_b, expected="pending", context="alloc won")
    mt.query(0xA800, 0x6_0000, expected="candidate", context="install lost")


# MT-FP-008
def test_victim_selection_and_age_saturation(mt):
    entries = [(0x1_0000 + i * 0x40, 0x7_0000 + i * 0x1000) for i in range(16)]
    for va, pa in entries:
        install(mt, va, pa)
    assert sum(1 for e in mt.model.entries if e.valid) == 16
    mt.coverage.sample_victim("invalid_slot", occupancy="partial")
    # Age saturates at 7 after enough idle cycles.
    for _ in range(8):
        mt.cycle(context="age")
    assert max(e.age for e in mt.model.entries if e.valid) == 7
    # Installing a 17th line replaces the oldest (first) entry.
    new_va, new_pa = 0x2_0000, 0x8_0000
    install(mt, new_va, new_pa)
    mt.coverage.sample_victim("oldest")
    mt.query(entries[0][0], entries[0][1], expected="candidate",
             context="oldest evicted")
    mt.query(new_va, new_pa, expected="resident", context="new line installed")
    # An empty slot is preferred over a valid one.
    mt.cycle(invalidate=Invalidate(valid=True, idx=index(entries[5][0]), way=0b0001),
             context="free one slot")
    mt.cycle(invalidate=Invalidate(valid=True, idx=index(entries[6][0]), way=0b0001),
             context="free another slot")
    install(mt, 0x2_8000, 0x9_0000)
    mt.query(0x2_8000, 0x9_0000, expected="resident", context="invalid slot used")


# MT-FP-004, MT-FP-009
def test_retained_result_on_bubble(mt):
    va, pa = 0xB000, 0xA_0000
    install(mt, va, pa)
    mt.query(va, pa, expected="resident")
    # s0 bubble, but s1 still presents the same load: the retained result is used.
    loads = [Load() for _ in range(3)]
    loads[0] = Load(s1_valid=True, s1_paddr=pa)
    spec = mt.cycle(loads=loads, context="retained")[0]
    assert spec.valid and not spec.candidate, spec
    # Repeating the S1 payload keeps working while the retained result is stable.
    spec = mt.cycle(loads=loads, context="retained 2")[0]
    assert spec.valid and not spec.candidate


# MT-FP-001..009
def test_random_traffic(mt):
    rng = random.Random(0x4D54_2026)
    owners = [Owner() for _ in range(16)]
    previous_s0 = [False, False, False]
    for cycle in range(120):
        allocs = []
        for _ in range(4):
            if rng.random() < 0.25:
                mshr = rng.randrange(16)
                va = rng.getrandbits(50)
                pa = rng.getrandbits(48)
                allocs.append(Alloc(valid=True, vaddr=va, paddr=pa, mshr_id=mshr))
                owners[mshr] = Owner(valid=True, vaddr=va, paddr=pa)
            else:
                allocs.append(Alloc())
        if rng.random() < 0.3:
            owners[rng.randrange(16)] = Owner()
        install = Install()
        if rng.random() < 0.3:
            install = Install(valid=True, vaddr=rng.getrandbits(50),
                              paddr=rng.getrandbits(48),
                              way=1 << rng.randrange(4))
        invalidate = Invalidate()
        if rng.random() < 0.2:
            invalidate = Invalidate(valid=True, idx=rng.randrange(256),
                                    way=rng.getrandbits(4))
        clear = rng.random() < 0.03
        loads = []
        for lane in range(3):
            s0_valid = rng.random() < 0.5
            # A real load pipeline only presents S1 after a valid S0. This also
            # avoids depending on the non-reset retained registers at time 0.
            s1_valid = previous_s0[lane] and rng.random() < 0.8
            previous_s0[lane] = s0_valid
            loads.append(Load(
                s0_valid=s0_valid, s0_vaddr=rng.getrandbits(50),
                s1_valid=s1_valid, s1_paddr=rng.getrandbits(48),
                s2_valid=rng.random() < 0.3, s2_vaddr=rng.getrandbits(50),
                s2_paddr=rng.getrandbits(48),
                s2_way=1 << rng.randrange(4), s2_hit=rng.random() < 0.5,
            ))
        mt.cycle(loads=loads, allocs=allocs, owners=owners, install=install,
                 invalidate=invalidate, clear=clear,
                 context=f"random {cycle}")


# MT-FP-007, MT-FP-008
def test_events_refresh_all_existing_entries(mt):
    """Every table entry must take the event-update path, not just insertion."""
    entries = [(0x10_0000 + i * 0x40, 0x20_0000 + i * 0x1000) for i in range(16)]
    for va, pa in entries:
        mt.cycle(install=Install(valid=True, vaddr=va, paddr=pa, way=0b0001),
                 context="fill")
    assert sum(1 for e in mt.model.entries if e.valid) == 16
    owners = [Owner() for _ in range(16)]
    for i, (va, pa) in enumerate(entries):
        owners[i] = Owner(valid=True, vaddr=va, paddr=pa)
        # Re-allocating an existing line updates that record in place.
        mt.cycle(allocs=[Alloc(valid=True, vaddr=va, paddr=pa, mshr_id=i)] +
                        [Alloc() for _ in range(3)],
                 owners=owners, context=f"refresh {i}")
    assert sum(1 for e in mt.model.entries if e.valid) == 16
    # Install and s2-training also refresh an existing record.
    va, pa = entries[0]
    mt.cycle(install=Install(valid=True, vaddr=va, paddr=pa, way=0b0001),
             owners=owners, context="install refresh")
    loads = [Load() for _ in range(3)]
    loads[0] = Load(s2_valid=True, s2_hit=True, s2_vaddr=va, s2_paddr=pa,
                    s2_way=0b0010)
    mt.cycle(loads=loads, owners=owners, context="training refresh")
    mt.query(va, pa, expected="resident", owners=owners, context="refreshed")


# MT-FP-001, MT-FP-004
def test_datapath_bit_sweep(mt):
    """Full-width tag/address bits must toggle in both directions."""
    import random
    rng = random.Random(0xB17_2026)

    def fill(paddr_of, context):
        # Clear resets the table so the next 16 installs fill every slot.
        mt.cycle(clear=True, context=f"{context} clear")
        for index in range(16):
            va = rng.getrandbits(50)
            pa = paddr_of(index)
            mt.cycle(install=Install(valid=True, vaddr=va, paddr=pa,
                                     way=1 << (index & 3)),
                     context=f"{context} {index}")
    fill(lambda index: ((1 << 48) - 1) - index, "ones")
    fill(lambda index: index, "zeros")
    fill(lambda index: (rng.getrandbits(42) << 6) | index, "random")
    # Random S1 payloads on all three lanes exercise the retained snapshots;
    # alternating owner buses toggle every owner address bit both ways.
    for cycle in range(48):
        owners = [Owner(valid=True, vaddr=rng.getrandbits(50),
                        paddr=rng.getrandbits(48)) for _ in range(16)]
        mt.query(rng.getrandbits(50), rng.getrandbits(48), lane=cycle % 3,
                 owners=owners, expected=None, context="random query")
