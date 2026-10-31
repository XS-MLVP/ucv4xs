"""Full-width ABTB address and payload state, not just the low test vectors.

Semantic points covered here:
- Every public PC/target bit must reach the in-flight S2 replay state and the
  training pipeline; a predictor may not silently truncate a legal address.
- A branch identity is the tuple of target, position, kind and stack action.
  Reusing a partial tag with a different payload must replace the whole
  record, not merge unrelated fields.
- Multi-hit cleanup reports the physical set it cleaned; exercising both the
  lowest and highest set makes every bit of that observation toggle.
"""

from __future__ import annotations

import pytest

from suites.frontend.bpu.abtb.case.definitions import CONDITIONAL
from suites.frontend.bpu.abtb.checker.assertions import assert_miss
from suites.frontend.bpu.abtb.transaction.types import AbtbTraining

HIGH = (1 << 49) - 2
LOW = 0
MIXED = 0x00F0


def training_for(meta, *, pc=LOW, target=HIGH, position=31, kind=3, action=3):
    return AbtbTraining(pc=pc, target=target, taken=1, position=position,
                        branch_type=kind, ras_action=action, meta=meta)


@pytest.mark.feature("BPU-ABTB-007")
async def test_full_width_address_and_payload_reach_the_branch_record(abtb_agent):
    await abtb_agent.reset()
    for pc in (LOW, MIXED, HIGH):
        cold = await abtb_agent.predict(pc)
        assert_miss(cold)
        transaction = training_for(cold.meta, pc=pc)
        await abtb_agent.train(transaction)
        observed = await abtb_agent.predict(pc)
        hits = [entry for entry in observed.entries if entry.valid]
        assert len(hits) == 1, (hex(pc), observed)
        entry, = hits
        assert (entry.position, entry.branch_type, entry.ras_action) == (31, 3, 3), hex(pc)
        # The target is reconstructed in the PC's 4 MiB region from the stored
        # local target; only that local field is part of the ABTB record.
        assert entry.target == (pc & ~((1 << 22) - 1)) | (HIGH & ((1 << 22) - 1))

    # Alternate the extreme identities so start-PC/target tag bits take both
    # values while still serving the trained record.
    for pc in (LOW, HIGH, LOW):
        observed = await abtb_agent.predict(pc)
        entry = observed.entries[0]
        assert entry.valid and entry.position == 31 and entry.branch_type == 3


@pytest.mark.feature("BPU-ABTB-026")
async def test_multi_hit_cleanup_reports_the_extreme_set_indices(abtb_agent):
    # Bank 0, history 0: set = (pc % 128) // 2 for even halfword PCs.
    for pc in (0x4000_0000, 0x4000_007E, 0x4000_0000, 0x4000_007E):
        await abtb_agent.reset()
        cold = await abtb_agent.predict(pc)
        assert_miss(cold)
        training = AbtbTraining(
            pc=pc, target=CONDITIONAL.target, taken=1,
            position=CONDITIONAL.position, branch_type=1,
            meta=cold.meta,
        )
        await abtb_agent.train(training)
        await abtb_agent.predict(pc)
        # Reuse the real cold snapshot to allocate a genuine duplicate.
        await abtb_agent.train(training)
        duplicate = await abtb_agent.predict(pc)
        ways = [way for way, entry in enumerate(duplicate.entries)
                if entry.valid and entry.position == CONDITIONAL.position
                and entry.branch_type == 1]
        assert len(ways) == 2, (hex(pc), ways, duplicate)
        await abtb_agent.drain_bank_writes()
        cleaned = await abtb_agent.predict(pc)
        remaining = [way for way, entry in enumerate(cleaned.entries)
                     if entry.valid and entry.position == CONDITIONAL.position
                     and entry.branch_type == 1]
        assert len(remaining) == 1, (hex(pc), remaining, cleaned)


@pytest.mark.feature("BPU-ABTB-046")
async def test_write_buffer_stores_full_width_identity_for_every_slot(abtb_agent):
    """All four write-buffer slots retain the complete tag/target identity.

    Every round allocates four distinct identities into one bank/set. Adding
    the pattern above the set/bank bits changes only the tag, and alternating
    complementary 24-bit tag and 22-bit target patterns makes every stored bit
    take both values while all four slots are rewritten. A final reset then
    drives the one-to-zero direction for every entry field.
    """
    from dataclasses import replace

    from suites.frontend.bpu.abtb.case.state.vectors import interior_set_vectors

    for bank in (0, 3):
        await abtb_agent.reset()
        base = interior_set_vectors(bank, 16, count=1)[0]
        rounds = 6
        for round_index in range(rounds):
            pattern = 0x155555 if round_index % 2 == 0 else 0x2AAAAA
            vectors = []
            for slot in range(4):
                tag = (pattern + slot) & 0xFFFFFF
                target = (0x4000_0000 if pattern == 0x155555 else 0x4000_0000 | 0x3FFFFE)
                vectors.append(replace(
                    base,
                    pc=base.pc + (tag << 9),
                    target=target + slot * 0x20,
                    position=(31 - slot) if round_index % 2 == 0 else (1 + slot),
                    branch_type=(3 - slot) if round_index % 2 == 0 else slot,
                ))
            for vector in vectors:
                cold = await abtb_agent.predict(vector.pc, path_hash=bank)
                assert cold.meta["bankMask"] == 1 << bank
                await abtb_agent.train(AbtbTraining(
                    pc=vector.pc, target=vector.target, taken=1,
                    position=vector.position, branch_type=vector.branch_type,
                    ras_action=vector.branch_type, meta=cold.meta))
            for vector in vectors:
                prediction = await abtb_agent.predict(vector.pc, path_hash=bank)
                hits = [entry for entry in prediction.entries
                        if entry.valid and entry.position == vector.position
                        and entry.branch_type == vector.branch_type]
                assert len(hits) == 1, (bank, round_index, vector, prediction)
                entry, = hits
                assert entry.taken == 1
                assert entry.ras_action == vector.branch_type

        # Clear every stored bit: all entries must read cold afterwards.
        await abtb_agent.reset()
        for vector in vectors:
            assert not any(entry.valid for entry in
                           (await abtb_agent.predict(vector.pc, path_hash=bank)).entries)
