"""Real feedback plus an uninterrupted loop exercises lower-table ring slots."""
from collections import Counter
from dataclasses import asdict
import json
from suites.frontend.bpu.runtime.trace import dump_trace
from suites.frontend.bpu.bpu.transaction.types import BpuBatchTraining
from suites.frontend.bpu.bpu.transaction.types import BpuBranchFeedback
from suites.frontend.bpu.bpu.transaction.types import BpuRedirect
from suites.frontend.bpu.bpu.case.sc.role_scenarios import revisit
from suites.frontend.bpu.bpu.case.sc.role_scenarios import source_pc
from suites.frontend.bpu.bpu.model.sc.metadata import mbtb_counter_for_position
from suites.frontend.bpu.bpu.model.sc.metadata import mbtb_meta_for_position
from suites.frontend.bpu.abtb.model.state.counter import TRANSITIONS
from suites.frontend.bpu.bpu.checker.bypass.natural import CombinedChecks
from suites.frontend.bpu.bpu.env.bypass.natural import CombinedObservation
from suites.frontend.bpu.bpu.case.bypass.lower_plan import recipe
from suites.frontend.bpu.bpu.case.abtb.timeouts import bounded


async def run_lower_ring(agent, output):
    plan = recipe()
    a, b, c = (plan[name] for name in ('a', 'b', 'c'))
    position, fallback = plan['conditional_position'], plan['fallback_position']
    checker = CombinedChecks(dict(pc_bank=0, scope='representable lower provider'))
    observation = CombinedObservation(agent, checker)
    report = dict(plan=plan, formal_credit=False, native_credit=False,
        hardware_internal_state_written=False, metadata_fabricated=False,
        parent_UTAGE_policy_or_SRAM_persistence_modeled=False)
    async def wait(operation, label, cycles=8192):
        return await bounded(agent, checker, operation, label, cycles)
    async def capture(pc, label):
        actual = await wait(revisit(agent, checker, pc, checkpoints[pc]), label, 512)
        report.setdefault('public_captures', []).append(asdict(actual))
        return actual
    async def train(actual, branches, label):
        transaction = BpuBatchTraining(actual.prediction.start_pc, actual.meta.resolve, branches)
        checker.plan_feedback(transaction)
        await wait(agent.train_batch_with_prediction_pause(transaction), label, 256)
        report.setdefault('feedback', []).append(asdict(transaction))
    def branch(taken, mispredict):
        return BpuBranchFeedback(position, a, 1, taken=taken, mispredict=mispredict)
    def fallback_branch(mispredict=0):
        return BpuBranchFeedback(fallback, b, 3, taken=1, mispredict=mispredict)
    async def steer(goal):
        await wait(agent.set_ready(prediction=False, meta=True), 'stop younger predictions before steering', 8)
        await wait(observation.drain(), 'drain actual older fastTrain', 32)
        await wait(agent.configure_predictors(abtb=False, settle=True), 'hold early predictor training while steering', 32)
        await wait(agent.set_ready(prediction=True, meta=True), 'resume MainBTB readback', 8)
        actual = await capture(a, 'actual MainBTB conditional state')
        for step in range(8):
            old = mbtb_counter_for_position(actual, position)
            if old == goal:
                break
            taken = int(old < goal)
            first = branch(taken, int((old >= 2) != bool(taken)))
            branches = (first,) if taken else (first, None, fallback_branch())
            await train(actual, branches, 'real feedback steers actual MainBTB counter')
            actual = await capture(a, 'real MainBTB transition readback')
            checker.compare(min(3, old + 1) if taken else max(0, old - 1),
                mbtb_counter_for_position(actual, position), field='MainBTB_feedback_counter_transition', step=step)
        checker.compare(goal, mbtb_counter_for_position(actual, position), field='real_MainBTB_direction_goal')
        await wait(agent.configure_predictors(abtb=True, settle=True), 'enable real early predictor training', 32)
        return await capture(a, 'one recovery starts uninterrupted natural loop')
    async def bootstrap_lower_without_stale_miss_promotion():
        # Stop accepting younger prediction transfers after the first real
        # S3 token carrying a valid conditional ABTB entry. This does not
        # assume a particular leaf-buffer allocation latency.
        for _ in range(256):
            await wait(observation.settle(1), 'wait for genuine conditional S3 bootstrap task', 4)
            fast = checker.control_records[-1]['abtb']['fast']
            if (fast['valid'] and fast['pc'] == a and fast['meta']['valid']
                    and any(entry['hit'] and entry['position'] == position
                        and entry['attribute']['branchType'] == 1 for entry in fast['meta']['entries'])):
                break
        else:
            raise AssertionError('no actual conditional S3 bootstrap task')
        await wait(agent.set_ready(prediction=False, meta=True), 'backpressure younger bootstrap tasks', 8)
        await wait(observation.drain(), 'commit the first actual lower allocation and drain older tasks', 32)
        allocations = [row for row in checker.bypass.writes if row['source'] == 'allocation']
        checker.compare([0], [row['table'] for row in allocations],
            field='bootstrap_commits_lower_only_not_stale_upper_allocation')
        # Flush a possibly held, pre-allocation S1 miss using a genuine
        # earlier checkpoint, still with ready low. No metadata is invented.
        recovery = BpuRedirect(a, checkpoints[a].meta.redirect,
            cfi_pc=a - 1, taken=0, branch_type=1)
        await wait(agent.redirect(recovery), 'genuine recovery discards the held stale miss', 32)
        await wait(observation.drain(), 'retire real recovery while backpressured', 16)
        await wait(agent.set_ready(prediction=True, meta=True), 'resume fresh lower-provider predictions', 8)
        report['bootstrap_recovery'] = asdict(recovery)
    try:
        await observation.__aenter__()
        pcs = (a, b, c)
        leads = [source_pc(pc) - 8 for pc in pcs]
        await wait(agent.reset(leads[0]), 'monitor before genuine reset')
        raw_sources = [await wait(agent.next_transaction(start_pc=lead, limit=1024),
            'actual cold source checkpoint', 4096) for lead in leads]
        await wait(agent.configure_predictors(ubtb=False, abtb=False, mbtb=True, tage=False,
            sc=False, ittage=False, ras=False, settle=True), 'isolate real MainBTB direction', 32)
        sources = [await wait(revisit(agent, checker, source_pc(pc), source),
            'actual half-block checkpoint', 256) for pc, source in zip(pcs, raw_sources, strict=True)]
        checkpoints = dict(zip(pcs, sources, strict=True))
        report['source_checkpoints'] = [asdict(item) for item in sources]
        for pc, target in ((b, c), (c, a)):
            actual = await capture(pc, 'cold unconditional edge metadata')
            await train(actual, (BpuBranchFeedback(plan['positions'][pc], target, 3, taken=1, mispredict=1),),
                'genuine feedback installs neutral path edge')
        actual = await capture(a, 'cold position0 conditional metadata')
        await train(actual, (branch(1, 1),), 'allocate real conditional self-loop')
        actual = await capture(a, 'actual initial conditional counter')
        checker.compare(2, mbtb_counter_for_position(actual, position), field='actual_initial_MainBTB_counter')
        await train(actual, (branch(0, 1),), 'make earlier branch negative before fallback allocation')
        actual = await capture(a, 'actual negative conditional state')
        checker.compare(1, mbtb_counter_for_position(actual, position), field='actual_negative_MainBTB_counter')
        await train(actual, (branch(0, 0), None, fallback_branch(1)), 'real late mispredict allocates fallback')
        actual = await capture(a, 'readback both real MainBTB residents')
        checker.compare((0, 3), (mbtb_counter_for_position(actual, position),
            mbtb_meta_for_position(actual, fallback)[1]['attribute']['branchType']), field='both_actual_MainBTB_residents')
        checker.phase = 'warm_fallback'
        await steer(0)
        for _ in range(2):
            await wait(observation.settle(64), 'warm actual three-block fallback', 128)
            await wait(agent.pause_prediction_reads(), 'commit real fallback entries', 32)
        seen = {row['transaction']['pc'] for row in checker.accepts if row['phase'] == 'warm_fallback'
            and row['transaction']['taken'] and row['transaction']['branch_type'] == 3}
        checker.compare({a, b, c}, {a, b, c} & seen, field='all_three_genuine_fallback_sources')
        for phase, goal in (('positive_first', 3), ('negative_to_zero', 0), ('positive_from_zero', 3)):
            checker.phase = phase
            await steer(goal)
            if phase == 'negative_to_zero':
                await bootstrap_lower_without_stale_miss_promotion()
            for _ in range(2):
                await wait(observation.settle(64), 'uninterrupted natural stream without redirects', 128)
                await wait(agent.pause_prediction_reads(), 'drain real writes without recovery', 32)
        await wait(agent.set_ready(prediction=False, meta=True), 'stop younger predictions', 8)
        await wait(observation.drain(), 'confirm committed shadow/counter effects', 16)
        checker.raise_failure()
        bypass = checker.bypass.finish()
        lower = [row for row in checker.bypass.writes if row['table'] == 0]
        checker.compare(True, sum(row['source'] == 'resident' for row in lower) >= 8,
            field='real_lower_provider_resident_updates_not_only_allocation')
        checker.compare(True, any(row['enq_wrap'] for row in lower), field='actual_lower_shadow_ring_wrap')
        checker.compare({0}, {row['index'] for row in lower}, field='lower_useful_index_independently_expected')
        checker.compare(set(range(8)), {row['slot'] for row in lower}, field='all_eight_lower_shadow_slots')
        checker.compare(0, len(checker.feedback_plans), field='all_genuine_feedback_observed')
        report.update(passed=True, bypass_summary=bypass, ABTB_summary=checker.summary(),
            lower_source_counts=dict(Counter(row['source'] for row in lower)))
    except BaseException as error:
        report['failure'] = repr(error)
        raise
    finally:
        await observation.aclose()
        report.update(bypass_records=checker.bypass.records, bypass_writes=checker.bypass.writes,
            records=checker.records, preedge_records=checker.control_records,
            coherent_transactions=checker.coherent_transactions, feedback_accepts=checker.feedback_accepts,
            accepts=checker.accepts, confirmed_transitions=checker.confirmed, gates=checker.gates)
        dump_trace((output / 'integrated-lower-shadow-ring.json'), report)
    return report
