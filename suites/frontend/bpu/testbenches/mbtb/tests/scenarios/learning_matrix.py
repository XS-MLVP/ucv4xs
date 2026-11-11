"""Real lookup provenance and legal normal-allocation histories, no forced RTL."""
from copy import deepcopy

from suites.frontend.bpu.testbenches.mbtb.checker.learning_matrix import branch_facts
from suites.frontend.bpu.testbenches.mbtb.checker.learning_matrix import check_destination
from suites.frontend.bpu.testbenches.mbtb.checker.learning_matrix import check_payload
from suites.frontend.bpu.testbenches.mbtb.coverage.learning_matrix import LearningMatrixCoverage
from suites.frontend.bpu.testbenches.mbtb.transactions.types import MbtbBatchTraining
from suites.frontend.bpu.testbenches.mbtb.transactions.types import MbtbBranchFeedback
from suites.frontend.bpu.testbenches.mbtb.transactions.metadata import metadata_origin
from suites.frontend.bpu.testbenches.shared.env.artifacts import output_directory
from suites.frontend.bpu.testbenches.shared.env.paths import REPO_ROOT


async def learn(agent, source, pc, position, kind, target, *, taken=1):
    await agent.train_batch(MbtbBatchTraining(pc, source.meta_entries, (
        MbtbBranchFeedback(target, taken, position, kind, mispredict=1),)))


async def check_payload_matrix(agent, case):
    coverage = LearningMatrixCoverage(case, 'payload')
    try:
        await agent.reset()
        peer_position = 8
        peer_target = case.pc + 0x700
        source = await agent.predict(case.pc)
        await learn(agent, source, case.pc, peer_position, 3, peer_target)
        if case.initial_kind is not None:
            source = await agent.predict(case.pc)
            await learn(agent, source, case.pc, case.position, case.initial_kind, case.target)
        source = await agent.predict(case.pc)
        frozen = deepcopy(source.meta_entries)
        # Source instruction type may be wrong; IFU/resolve corrects it. This
        # is a module feedback contract, not a self-modifying-code/FTQ proof.
        await learn(agent, source, case.pc, case.position, case.resolved_kind,
                    case.successor, taken=0)
        origin = metadata_origin(source.meta_entries)
        assert origin is not None
        coverage.record('reached', source_pc=case.pc, position=case.position,
                        origin_uid=origin.uid, epoch=origin.epoch)
        actual = await agent.predict(case.pc)
        check_payload(case, actual, (peer_position, 3, 0, peer_target, 1, 2))
        assert source.meta_entries == frozen
        await agent.finish()
        coverage.record('checked', facts=branch_facts(actual))
    finally:
        coverage.write(output_directory(REPO_ROOT, 'mbtb'))


async def fill_window(agent, pc):
    # Distinct indirect instructions, each queried at its own start: no
    # impossible execution through an earlier taken instruction is required.
    for position in range(1, 7):
        source = await agent.predict(pc + position)
        await learn(agent, source, pc + position, position, 3, pc + 0x800 + 8 * position)


async def check_residency_matrix(agent, case):
    coverage = LearningMatrixCoverage(case, 'residency')
    try:
        await agent.reset()
        await fill_window(agent, case.pc)
        original = await agent.predict(case.pc + 2)
        assert original.meta_entries[case.alignment][4]['rawHit']
        assert original.meta_entries[case.alignment][4]['position'] == 2
        frozen = deepcopy(original.meta_entries)
        for pc in case.pressure:
            await fill_window(agent, pc)
        before = await agent.predict(case.pc + 2)
        visible = [entry for slot, entry in enumerate(before.entries)
                   if slot % 5 == 4 and entry.valid and entry.position == 2]
        assert bool(visible) == (case.mode == 'resident'), 'normal pressure did not establish the declared residency class'
        # The SAME immutable original, not this diagnostic fresh lookup, owns
        # the delayed feedback even though current victim residency changed.
        await learn(agent, original, case.pc + 2, 2, 3, case.target)
        coverage.record('reached', normal_pressure_windows=len(case.pressure), original=frozen)
        after = await agent.predict(case.pc + 2)
        check_destination(case, after)
        assert original.meta_entries == frozen
        await agent.finish()
        coverage.record('checked', facts=branch_facts(after))
    finally:
        coverage.write(output_directory(REPO_ROOT, 'mbtb'))
