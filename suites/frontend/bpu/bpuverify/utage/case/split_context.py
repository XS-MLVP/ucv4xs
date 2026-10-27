"""Genuine high-address provider updates with independent index/tag context."""

from bpuverify.common.coverage.exports import write_functional_coverage
from dataclasses import asdict
import json

from toffee import Bin, CoverGroupDef, CoverPointDef, CoverageDatabase, CrossDef

from bpuverify.common.env.artifacts import output_path
from bpuverify.common.env.artifacts import write_output
from bpuverify.utage.case.useful_address_scenario import UsefulContext
from bpuverify.utage.coverage.supplemental import UPDATE_ROLES, utage_useful_update_coverage_model
from bpuverify.utage.env.lookup import check_lookup_burst
from bpuverify.utage.model.split_context import contexts, neighbor_context


async def check_split_context_useful(agent, output):
    profiles = contexts()
    positive, negative = profiles['positive'], profiles['negative']
    neighbor = neighbor_context()
    index = positive.indices[0]
    contracts = ('distinct_index_tag_inputs', 'genuine_high_address_provider',
                 'increase', 'increase_hold', 'base_agreement_holds',
                 'decrease', 'decrease_hold', 'independent_upper_miss_readback',
                 'adjacent_lookup_context_association', 'independent_neighbor_preserved')
    coverage = CoverGroupDef('utage_split_context_useful', (
        CoverPointDef('mode', {mode: Bin.values(mode) for mode in ('serial', 'adjacent')}),
        CoverPointDef('contract', {name: Bin.values(name) for name in contracts}),
    ), crosses=(CrossDef('all_contracts', ('mode', 'contract')),)
    ).instantiate('kunminghu_v3.utage.split_context_useful')
    # Share the ORIGINAL full physical schema. Only genuinely checked roles
    # gain credit; do not reduce its 8192-bin denominator for this one row.
    address_coverage = utage_useful_update_coverage_model()
    summaries = []
    for mode in ('serial', 'adjacent'):
        async with UsefulContext(agent, mode=mode, name='split-context-high-index',
                                 index=index, output=output, update_coverage=address_coverage) as run:
            async def predict(profile, base, expected):
                return await run.predict(profile.pc, profile.tag_history, base, expected=expected,
                    position=6, index_pc=profile.index_pc, index_history=profile.index_history)
            run.check(True, positive.index_pc != positive.pc, point='independent index/tag PC')
            run.check(True, positive.index_history != positive.tag_history, point='independent index/tag PHR')
            cold = await predict(positive, 0, (0, None, None, None))
            await run.feedback(positive.pc, cold, 1, phase='allocate-high-lower')
            lower = await predict(positive, 0, (1, 0, 4, 1))
            run.check(1, run.checker.reference.values[index], point='genuine high-row useful allocation')
            await run.feedback(positive.pc, lower, 1, count=3, phase='high-useful-increase-and-saturate')
            run.check(3, run.checker.reference.values[index], point='high useful saturates at three')
            cold_neighbor = await predict(neighbor, 1, (0, None, None, None))
            await run.feedback(neighbor.pc, cold_neighbor, 0, phase='allocate-independent-negative-neighbor')
            burst = await check_lookup_burst(run, (
                (positive, 1, (1, 0, 7, 1)), (neighbor, 0, (1, 0, 3, 0)),
                (negative, 1, (1, 0, 7, 1)), (neighbor, 0, (1, 0, 3, 0)),
            ))
            agreeing = await predict(positive, 1, (1, 0, 7, 1))
            await run.feedback(positive.pc, agreeing, 1, phase='high-base-agrees-useful-holds')
            run.check(3, run.checker.reference.values[index], point='base agreement leaves high useful unchanged')
            await run.feedback(positive.pc, lower, 0, count=4, phase='high-useful-decrease-and-saturate')
            run.check(0, run.checker.reference.values[index], point='high useful saturates at zero')
            # The other phase has the same lower index/tag but a distinct,
            # untouched upper index. Require lower as the actual provider;
            # do not inspect or overwrite internal state to hide the new upper.
            returned = await predict(negative, 0, (1, 0, 3, 0))
            unchanged_neighbor = await predict(neighbor, 0, (1, 0, 3, 0))
            run.check(1, run.checker.reference.values[neighbor.indices[0]], point='neighbor useful remains allocated')
            for role in UPDATE_ROLES:
                run.check(True, (0, index, role) in run.checker.route_bins,
                          point='required complete high-address useful effect: ' + role)
            summary = run.checker.summary()
            summaries.append(dict(mode=mode, input={name: asdict(value) for name, value in profiles.items()},
                accepted_feedback=summary['accepted'], cell_comparisons=summary['cell_comparisons'],
                routes=summary['route_bins'], final_lower=asdict(returned),
                neighbor=asdict(neighbor), final_neighbor=asdict(unchanged_neighbor), lookup_burst=burst,
                feedback_metadata_fabricated=False, internal_state_written=False,
                full_FTQ_legality_proven=False))
        for contract in contracts:
            coverage.sample(dict(mode=mode, contract=contract))
    coverage.assert_coverage(100.0)
    path = output_path(output / 'functional-coverage-split-context-useful.json')
    path.parent.mkdir(parents=True, exist_ok=True)
    write_functional_coverage(CoverageDatabase([coverage, address_coverage]), path)
    write_output(output / 'split-context-useful-summary.json', json.dumps(dict(
        feature='BPU-UTAGE-023', modes=summaries, passed=True,
        scope='one high physical row; not all 512 addresses or integrated FTQ legality'), indent=2) + '\n')
