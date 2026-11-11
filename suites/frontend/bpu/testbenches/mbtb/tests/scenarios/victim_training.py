"""Normal allocations expose the difference between residency and prediction."""
from copy import deepcopy

from suites.frontend.bpu.testbenches.mbtb.transactions.types import MbtbBatchTraining
from suites.frontend.bpu.testbenches.mbtb.transactions.types import MbtbBranchFeedback

PC = 0x40000800


async def train(agent, source, pc, position, *, kind=3, taken=1, target=None, prefix=()):
    tx = MbtbBatchTraining(pc, source.meta_entries, tuple(prefix) + (
        MbtbBranchFeedback(target if target is not None else PC + 0x800 + position * 8,
                           taken, position, kind, mispredict=1),))
    await agent.train_batch(tx)


async def check_victim_training(agent, *, exposed, alignment=0):
    assert alignment in (0, 1)
    offset = 16 * alignment
    await agent.reset()
    # Six distinct instructions share an alignment. Query each at its own
    # starting PC, so preparation never executes through an earlier taken jump.
    for position in range(1, 7):
        source = await agent.predict(PC + offset + position)
        await train(agent, source, PC + offset + position, position, kind=1 if position == 1 else 3)
    # The earlier conditional is genuinely learned NT before a block-start
    # producer can resolve the later indirect. No internal state is forced.
    for _ in range(2):
        source = await agent.predict(PC + offset + 1)
        assert source.meta_entries[alignment][4]['rawHit'] and source.meta_entries[alignment][4]['position'] == 1
        await train(agent, source, PC + offset + 1, 1, kind=1, taken=0, target=PC + offset + 2)
    pc = PC + offset + 2 if exposed else PC
    source = await agent.predict(pc)
    frozen = deepcopy(source.meta_entries)
    assert source.meta_entries[alignment][4]['rawHit']
    assert source.meta_entries[alignment][4]['position'] == (2 if exposed else offset + 1)
    old = await agent.predict(PC + offset + 2)
    victim_slot = alignment * 5 + 4
    assert old.entries[victim_slot].valid and old.entries[victim_slot].position == 2
    target = PC + 0x1234
    await train(agent, source, pc, 2 if exposed else offset + 2, target=target, prefix=() if exposed else (
        MbtbBranchFeedback(PC + offset + 2, 0, offset + 1, 1),))
    result = await agent.predict(PC + offset + 2)
    locations = [way for way, entry in enumerate(result.entries)
        if entry.valid and entry.position == 2 and entry.target == target]
    assert len(locations) == 1
    assert (locations[0] == victim_slot) == exposed
    assert source.meta_entries == frozen
    await agent.finish()


async def check_payload_preservation(agent, *, mode):
    await agent.reset()
    target = PC + 0x1234
    if mode != 'cold-nt':
        source = await agent.predict(PC)
        await train(agent, source, PC, 5, kind=1 if mode == 'conditional-nt' else 3, target=target)
    source = await agent.predict(PC)
    frozen = deepcopy(source.meta_entries)
    kind = 0 if mode == 'false-hit' else 1
    await train(agent, source, PC, 5, kind=kind, taken=0, target=PC + 6)
    result = await agent.predict(PC)
    active = [entry for entry in result.entries if entry.valid]
    if mode == 'conditional-nt':
        assert len(active) == 1 and active[0].target == target and not active[0].taken
        assert result.meta_entries[0][3]['counter_value'] == 1
    else:
        assert not active
    assert source.meta_entries == frozen
    await agent.finish()
