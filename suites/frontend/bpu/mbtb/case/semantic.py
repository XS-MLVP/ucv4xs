"""Discriminating branch programs at representative addresses, not bank sweeps."""
from suites.frontend.bpu.models.configuration import *
from suites.frontend.bpu.mbtb.transaction.types import MbtbBatchTraining, MbtbBranchFeedback, MbtbTraining


PC = 0x40000800
TARGET = 0x40003456


def branch_state(prediction, position, kind):
    entries = [(way, entry) for way, entry in enumerate(prediction.entries)
               if entry.valid and (entry.position, entry.branch_type) == (position, kind)]
    assert len(entries) == 1
    way, entry = entries[0]
    source = prediction.meta_entries[way // (MAIN_WAYS + 1)][way % (MAIN_WAYS + 1)]
    assert source['rawHit'] and source['position'] == position
    return way, entry.target, entry.taken, source['counter_value']


def new_offers(agent, tick):
    return [(at, request) for at, request in agent.reference.accepted_feedback if at > tick]


async def unmatched_feedback(agent, coverage, *, same_position):
    await agent.reset()
    cold = await agent.predict(PC)
    await agent.train(MbtbTraining(PC, TARGET, 1, 3, 1, cold.meta_entries))
    warm = await agent.predict(PC)
    way, target, taken, counter = branch_state(warm, 3, 1)
    assert (target, taken, counter) == (TARGET, 1, 2)
    # Different tag, identical row/bank/branch position. Raw unhit payloads
    # must not be turned into training permission for the resident tag.
    foreign_pc = PC + (1 << 15)
    miss = await agent.predict(foreign_pc)
    assert not any(entry.valid for entry in miss.entries)
    assert not any(source['rawHit'] for row in miss.meta_entries for source in row)
    position = 3 if same_position else 6
    rule = 'unmatched-same-position-isolation' if same_position else 'unmatched-other-position-control'
    first_tick = agent.reference.input_tick
    try:
        await agent.train_batch(MbtbBatchTraining(foreign_pc, miss.meta_entries,
            (MbtbBranchFeedback(TARGET + 0x100, 0, position, 1, mispredict=0),)))
    finally:
        offers = new_offers(agent, first_tick)
        if len(offers) == 1:
            at, request = offers[0]
            assert request.pcs[0] == foreign_pc and request.branches[0].position == position
            assert not any(source.hit for row in request.sources for source in row)
            assert not request.branches[0].mispredict
            coverage.record('reached', rule, accepted_tick=at, source_tag_miss=True, position=position)
    observed = await agent.predict(PC)
    assert branch_state(observed, 3, 1) == (way, TARGET, 1, 2)
    coverage.record('checked', rule, checked_tick=agent.reference.input_tick + 1, resident_way=way, counter=2)


async def coalesced_reset(agent, coverage, *, stale):
    await agent.reset()
    cold = await agent.predict(PC)
    # The conditional is before the indirect. Fall-through feedback for the
    # former and taken feedback for the latter describe a consistent program.
    await agent.train(MbtbTraining(PC, TARGET, 1, 5, 3, cold.meta_entries))
    source = await agent.predict(PC)
    await agent.train(MbtbTraining(PC, TARGET + 0x200, 1, 1, 1, source.meta_entries))
    for _ in range(2):
        source = await agent.predict(PC)
        await agent.train(MbtbTraining(PC, TARGET + 0x200, 0, 1, 1, source.meta_entries))
    source = await agent.predict(PC)
    assert branch_state(source, 1, 1)[2:] == (0, 0)
    # Correct feedback touches only the taken indirect for replacement. The
    # next stale-miss nomination is the peer, while the logical shadow owner
    # remains the indirect's way. No private replacer/slot writes are used.
    await agent.train_batch(MbtbBatchTraining(PC, source.meta_entries, (
        MbtbBranchFeedback(TARGET + 0x200, 0, 1, 1),
        MbtbBranchFeedback(TARGET, 1, 5, 3),
    )))
    source = await agent.predict(PC)
    peer = branch_state(source, 1, 1)
    owner = branch_state(source, 5, 3)
    assert peer[0] != owner[0] and peer[2:] == (0, 0) and owner[3] == 2
    metadata = cold.meta_entries if stale else source.meta_entries
    rule = 'stale-metadata-retained-owner' if stale else 'current-metadata-owner-control'
    first_tick = agent.reference.input_tick
    try:
        await agent.train(MbtbTraining(PC, TARGET + 0x100, 1, 5, 3, metadata))
    finally:
        offers = new_offers(agent, first_tick)
        if len(offers) == 1:
            at, request = offers[0]
            assert request.branches[0].kind == 3 and request.branches[0].position == 5
            assert any(source.hit for row in request.sources for source in row) == (not stale)
            coverage.record('reached', rule, accepted_tick=at, owner=owner[0], peer=peer[0], peer_counter=0)
    observed = await agent.predict(PC)
    assert branch_state(observed, 1, 1) == peer
    assert branch_state(observed, 5, 3) == (owner[0], TARGET + 0x100, 1, 2)
    coverage.record('checked', rule, checked_tick=agent.reference.input_tick + 1,
                    retained_owner=owner[0], unchanged_peer=peer[0], peer_counter=0)


async def cleanup_zero_key(agent, coverage, *, combined_zero):
    from suites.frontend.bpu.mbtb.case.cleanup_overlap_scenario import check_case

    rule = 'combined-zero-key-destination-clear' if combined_zero else 'nonzero-key-clear-control'
    prepared_tick = None

    class PreparedCheckpoint:
        def sample(self, value):
            nonlocal prepared_tick
            if value['phase'] == 'prepared':
                prepared_tick = agent.reference.input_tick

    try:
        await check_case(agent, PreparedCheckpoint(), align=0, bank=0, depth=0,
                         shadow_state='dirty', key='combined-zero' if combined_zero else 'nonzero',
                         key_fields=(0, 0) if combined_zero else None)
    finally:
        # A prepared duplicate alone does not prove the clear was offered.
        # This is a public S2-consume event paired with the independently
        # owned duplicate snapshot, not an internal flush/write-port read.
        accepted = [item for item in agent.reference.accepted_cleanup if prepared_tick is not None
                    and item['tick'] > prepared_tick and item['align'] == 0 and item['bank'] == 0
                    and item['tag'] == (0 if combined_zero else 1)
                    and item['position'] == (0 if combined_zero else 5)]
        if accepted:
            assert all(item['way'] == 1 for item in accepted)
            coverage.record('reached', rule, accepted_ticks=tuple(item['tick'] for item in accepted),
                            tag=accepted[0]['tag'], position=accepted[0]['position'], cleared_way=1)
    agent.reference.raise_failure()
    coverage.record('checked', rule, tick=agent.reference.input_tick + 1,
                    survivor_way=0, cleared_way=1, neighboring_training_preserved=True)
