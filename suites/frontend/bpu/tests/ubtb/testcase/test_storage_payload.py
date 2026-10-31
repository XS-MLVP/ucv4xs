"""MicroBTB entry storage is full width and survives clear/rewrite; idle holds PLRU.

Semantic points:
- Reset clears every stored entry field, so a lookup immediately after reset has
  no taken source until a fresh feedback writes a complete identity.
- Every entry field (tag, target offset, position, branch type, RAS action,
  usefulness) stores its full configured width. A write must not truncate or
  alias a neighbour, and a later reset must return all of them to zero.
- With the predictor enabled but neither a consuming prediction nor a training
  write present, the replacement state holds; an idle window cannot silently
  reorder the victim sequence.
"""

from __future__ import annotations

import pytest

from suites.frontend.bpu.ubtb.case.definitions import NUM_ENTRIES
from suites.frontend.bpu.ubtb.transaction.types import BranchTraining
from suites.frontend.bpu.ubtb.transaction.types import UbtbPrediction

TAG_MASK = (1 << 22) - 1
TARGET_MASK = (1 << 23) - 1
REGION = 0x9000_0000


def pattern_vectors(complement: bool) -> tuple[BranchTraining, ...]:
    """32 distinct identities whose tag/target/position/type/RAS bits alternate."""
    vectors = []
    for index in range(NUM_ENTRIES):
        tag = (index * 0x155555) & TAG_MASK
        if complement:
            tag ^= TAG_MASK
        pc = REGION + (tag << 1)
        target_offset = (index * 0x0AAAAA) & (TARGET_MASK - 1)
        if complement:
            target_offset ^= TARGET_MASK - 1
        target = REGION + (target_offset & ~1)
        vectors.append(BranchTraining(
            pc=pc, target=target, taken=1,
            position=(index % 32) ^ (31 if complement else 0),
            branch_type=(index % 4) ^ (3 if complement else 0),
            ras_action=((index // 4) % 4) ^ (3 if complement else 0),
        ))
    return tuple(vectors)


def expected(transaction: BranchTraining) -> UbtbPrediction:
    return UbtbPrediction(1, 1, transaction.target, transaction.position,
                          transaction.branch_type, transaction.ras_action)


async def train_wave(agent, vectors) -> None:
    for transaction in vectors:
        await agent.train(transaction)


async def check_wave(agent, vectors) -> None:
    for transaction in vectors:
        actual = await agent.predict(transaction.pc)
        assert actual == expected(transaction), f'{transaction.pc:#x} payload lost'


async def exercise_start_pc_edges(agent) -> None:
    """Register the lowest and highest legal start PCs before the next reset."""
    for pc in (0, (1 << 50) - 2):
        await agent.predict(pc)


@pytest.mark.feature('BPU-UBTB-001')
async def test_reset_clears_every_entry_field_and_requires_fresh_training(ubtb_agent):
    await ubtb_agent.reset()
    first = pattern_vectors(complement=False)[0]
    await ubtb_agent.train(first)
    assert await ubtb_agent.predict(first.pc) == expected(first)

    await ubtb_agent.reset()
    missed = await ubtb_agent.predict(first.pc)
    assert missed.valid == 0

    replacement = BranchTraining(
        pc=first.pc, target=first.target + 0x400, taken=1,
        position=(first.position + 7) % 32,
        branch_type=(first.branch_type + 1) % 4,
        ras_action=(first.ras_action + 2) % 4,
    )
    await ubtb_agent.train(replacement)
    assert await ubtb_agent.predict(first.pc) == expected(replacement)


@pytest.mark.feature('BPU-UBTB-006')
async def test_all_entry_payload_bits_survive_write_clear_rewrite(ubtb_agent):
    await ubtb_agent.reset()
    first = pattern_vectors(complement=False)
    second = pattern_vectors(complement=True)

    await train_wave(ubtb_agent, first)
    await check_wave(ubtb_agent, first)
    await exercise_start_pc_edges(ubtb_agent)

    await ubtb_agent.reset()
    await train_wave(ubtb_agent, second)
    await check_wave(ubtb_agent, second)
    await exercise_start_pc_edges(ubtb_agent)

    await ubtb_agent.reset()
    for transaction in second[:4]:
        assert (await ubtb_agent.predict(transaction.pc)).valid == 0


@pytest.mark.feature('BPU-UBTB-006')
async def test_idle_enabled_cycle_holds_replacement_state(ubtb_agent):
    await ubtb_agent.reset()
    # A miss leaves s1_hit at zero, so idle cycles have neither a prediction
    # touch nor a training touch and must evaluate the hold arm.
    assert (await ubtb_agent.predict(pattern_vectors(False)[0].pc)).valid == 0
    await ubtb_agent.wait_cycles(4)

    vectors = pattern_vectors(complement=False)
    for transaction in vectors:
        await ubtb_agent.train(transaction)
    await check_wave(ubtb_agent, vectors)

    # One further identity replaces exactly one victim; every other resident
    # must still answer with its own complete payload.
    extra = BranchTraining(pc=REGION + 0x700_000, target=REGION + 0x740_000,
                           taken=1, position=9, branch_type=2, ras_action=1)
    await ubtb_agent.train(extra)
    hits = 0
    for transaction in vectors:
        prediction = await ubtb_agent.predict(transaction.pc)
        if prediction.valid:
            hits += 1
            assert prediction == expected(transaction)
    assert hits == NUM_ENTRIES - 1
    assert await ubtb_agent.predict(extra.pc) == expected(extra)
