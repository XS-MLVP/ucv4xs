"""Real second-key feedback evicts old shadow entries; read back through SRAM."""
from dataclasses import asdict
from bpuverify.bpu.transaction.types import BpuBranchFeedback
from bpuverify.bpu.model.sc.metadata import mbtb_counter_for_position
from bpuverify.bpu.model.sc.metadata import mbtb_meta_for_position
from bpuverify.bpu.case.bypass.force_plan import second_key
from bpuverify.bpu.case.bypass.lower_plan import recipe
from bpuverify.bpu.case.bypass.public_readback import conditional_source_ways
from bpuverify.bpu.case.bypass.public_readback import public_readback_pair


def conditional_slots(actual, position):
    return [entry for entry in actual.meta.resolve['utage']['abtbResult']
        if entry['valid'] and entry['cfiPosition'] == position]


async def force_old_entry_to_SRAM(agent, checker, observation, checkpoints, report, wait, capture, train):
    plan, old = second_key(), recipe()
    a, b, c = (plan[name] for name in ('a', 'b', 'c'))
    position, fallback = plan['position'], plan['fallback']
    old_index, new_index = old['expected_utage_index'], plan['expected_index']
    checker.phase = 'second_key_setup'
    start_tick = checker.bypass.last_event.tick
    await wait(agent.configure_predictors(abtb=False, settle=True), 'disable early training while preparing second key', 32)
    await wait(agent.set_ready(prediction=True, meta=True), 'accept second-key MainBTB readback', 8)
    def conditional(taken, mispredict):
        return BpuBranchFeedback(position, a, 1, taken=taken, mispredict=mispredict)
    def fallback_branch(mispredict=0):
        return BpuBranchFeedback(fallback, b, 3, taken=1, mispredict=mispredict)
    for pc, target in ((b, c), (c, a)):
        actual = await capture(pc, 'second-key cold unconditional source')
        await train(actual, (BpuBranchFeedback(position, target, 3, taken=1, mispredict=1),),
            'install actual neutral second-key fallback edge')
    actual = await capture(a, 'second-key cold conditional source')
    await train(actual, (conditional(1, 1),), 'allocate second-key conditional MainBTB entry')
    actual = await capture(a, 'second-key initial MainBTB counter')
    checker.compare(2, mbtb_counter_for_position(actual, position), field='second_key_initial_counter')
    await train(actual, (conditional(0, 1),), 'prepare second-key negative conditional')
    actual = await capture(a, 'second-key negative MainBTB counter')
    checker.compare(1, mbtb_counter_for_position(actual, position), field='second_key_negative_counter')
    await train(actual, (conditional(0, 0), None, fallback_branch(1)), 'allocate second-key real fallback')
    actual = await capture(a, 'second-key two MainBTB residents')
    checker.compare((0, 3), (mbtb_counter_for_position(actual, position),
        mbtb_meta_for_position(actual, fallback)[1]['attribute']['branchType']), field='second_key_both_residents')
    async def steer(goal):
        await wait(agent.set_ready(prediction=False, meta=True), 'stop younger second-key requests', 8)
        await wait(observation.drain(), 'drain older second-key fastTrain', 32)
        await wait(agent.configure_predictors(abtb=False, settle=True), 'isolate actual second-key MainBTB transition', 32)
        await wait(agent.set_ready(prediction=True, meta=True), 'resume second-key MainBTB reads', 8)
        actual = await capture(a, 'real second-key MainBTB state')
        for step in range(8):
            counter = mbtb_counter_for_position(actual, position)
            if counter == goal:
                break
            taken = int(counter < goal)
            branch = conditional(taken, int((counter >= 2) != bool(taken)))
            await train(actual, (branch,) if taken else (branch, None, fallback_branch()),
                'real feedback steers second-key conditional')
            actual = await capture(a, 'read actual second-key MainBTB increment/decrement')
            checker.compare(min(3, counter + 1) if taken else max(0, counter - 1),
                mbtb_counter_for_position(actual, position), field='second_key_counter_transition', step=step)
        checker.compare(goal, mbtb_counter_for_position(actual, position), field='second_key_counter_goal')
        await wait(agent.configure_predictors(abtb=True, settle=True), 'resume second-key genuine fastTrain', 32)
        return await capture(a, 'start natural second-key loop')
    for phase, goal in (('second_warm_fallback', 0), ('second_positive', 3), ('second_negative', 0)):
        checker.phase = phase
        await steer(goal)
        for _ in range(2):
            await wait(observation.settle(64), 'continuous second-key natural predictions', 128)
            await wait(agent.pause_prediction_reads(), 'commit second-key shadow writes', 32)
    await wait(agent.set_ready(prediction=False, meta=True), 'stop new second-key predictions', 8)
    await wait(observation.drain(), 'observe final force-write and shadow eviction', 16)
    upper = checker.bypass.references[1]
    selected_writes = [row for row in checker.bypass.writes
        if row['tick'] > start_tick and row['table'] == 1 and row['index'] == new_index]
    checker.compare(True, len(selected_writes) >= 8, field='second_key_fills_all_eight_upper_shadow_slots')
    checker.compare(False, any(cell['valid'] and cell['index'] == old_index for cell in upper.cells),
        field='old_upper_key_really_absent_from_all_shadow_slots')
    forced = [row for row in checker.bypass.bank_writes
        if row['table'] == 1 and row['index'] == old_index and row['force']]
    checker.compare(True, bool(forced), field='real_old_key_forced_SRAM_write_not_just_ring_wrap')
    checker.compare(True, bool(checker.bypass.forced_conflicts), field='real_forced_read_conflict_valid_invalidation')
    expected = checker.bypass.srams[1].memory[old_index]
    checker.compare(True, expected is not None and expected['data_valid'] == 1,
        field='old_key_expected_SRAM_payload_derived_from_actual_normal_feedback')
    checker.phase = 'old_key_SRAM_public_readback'
    await wait(agent.set_ready(prediction=True, meta=True), 'resume old-key public readback', 8)
    read_start = checker.bypass.last_event.tick
    actual = await capture(old['a'], 'old-key public prediction after complete upper shadow eviction')
    recovery_transactions = []
    recovery_read_free_windows = []
    def source_metadata(transaction):
        return next(row['abtb']['meta1'] for row in checker.records
            if row['tick'] == transaction.prediction_tick)
    def check_public(transaction, label):
        source = source_metadata(transaction)
        wanted, observed = public_readback_pair(asdict(transaction), source, expected,
            pc=old['a'], index=old_index, position=old['conditional_position'])
        checker.compare(wanted, observed, field=label, prediction_tick=transaction.prediction_tick)
        return source
    for attempt in range(32):
        hits = conditional_slots(actual, old['conditional_position'])
        source = source_metadata(actual)
        source_ways = conditional_source_ways(source, old['conditional_position'])
        if source_ways or hits:
            break
        # A genuine S2/S3 correction queues a replacement ABTB entry, but
        # continuous same-bank reads prevent this read-priority SRAM from
        # committing it. Drain the real fastTrain write through the driver.
        # Keep all captured tasks: validity/position qualify observation,
        # while hit/provider/counter are checked at the first valid task.
        recovery_transactions.append(asdict(actual))
        if attempt == 0:
            await wait(observation.settle(8), 'allow actual old-key S3 fastTrain to reach ABTB write buffer', 16)
            begin = checker.bypass.last_event.tick
            await wait(agent.pause_prediction_reads(), 'read-free drain commits actual old-key conditional ABTB fastTrain', 32)
            recovery_read_free_windows.append(dict(begin_tick=begin,
                end_tick=checker.bypass.last_event.tick, requested_cycles=12))
        actual = await wait(agent.next_transaction(start_pc=old['a'],
            after_tick=actual.prediction_tick, limit=256),
            'next genuine old-key task after normal ABTB conditional recovery', 512)
        report.setdefault('public_captures', []).append(asdict(actual))
    checker.compare(True, bool(source_ways), field='real_ABTB_input_has_old_conditional_way')
    first_source = check_public(actual, 'all_public_UTAGE_ways_and_prediction_match_replayed_SRAM')
    first_public = asdict(actual)
    cleanup_transactions, cleanup_read_free_windows = [], []
    if len(source_ways) > 1:
        # AheadBtb.scala explicitly detects multi-hit and queues invalidation.
        # Check all duplicate results before allowing cleanup to run.
        await wait(observation.settle(8), 'allow actual multi-hit invalidation to enqueue', 16)
        begin = checker.bypass.last_event.tick
        await wait(agent.pause_prediction_reads(), 'commit genuine ABTB multi-hit invalidation', 32)
        cleanup_read_free_windows.append(dict(begin_tick=begin,
            end_tick=checker.bypass.last_event.tick, requested_cycles=12))
        for attempt in range(32):
            actual = await wait(agent.next_transaction(start_pc=old['a'],
                after_tick=actual.prediction_tick, limit=256), 'next old-key task during actual multi-hit cleanup', 512)
            report.setdefault('public_captures', []).append(asdict(actual))
            source = check_public(actual, 'each_duplicate_or_cleaned_public_way_must_remain_correct')
            cleanup_transactions.append(dict(transaction=asdict(actual), source_ABTB_meta=source))
            source_ways = conditional_source_ways(source, old['conditional_position'])
            if len(source_ways) == 1:
                break
        checker.compare(1, len(source_ways), field='actual_ABTB_multi_hit_cleanup_restores_one_conditional_way')
    readbacks = [row for row in checker.bypass.SRAM_reads
        if row['tick'] > read_start and row['table'] == 1 and row['index'] == old_index]
    checker.compare(True, bool(readbacks), field='real_old_key_read_data_from_SRAM_without_shadow_hit')
    await wait(agent.set_ready(prediction=False, meta=True), 'stop new tasks before end-of-scenario checking', 8)
    await wait(observation.drain(), 'confirm all accepted fastTrain tasks complete before closing monitors', 16)
    checker.compare((None, None), (checker.counter.pending1, checker.counter.pending2),
        field='all_accepted_ABTB_fastTrain_tasks_drained_before_finalization')
    return dict(start_tick=start_tick, second_key=plan, upper_second_key_writes=len(selected_writes),
        old_shadow_key_fully_evicted_before_readback=True, forced_old_SRAM_writes=forced,
        independent_expected_old_SRAM=expected, actual_no_shadow_SRAM_readbacks=readbacks,
        actual_public_readback=first_public, source_ABTB_meta_for_first_public=first_source,
        actual_cleaned_public_readback=asdict(actual), source_ABTB_meta_for_cleaned_public=source_metadata(actual),
        recovery_transactions=recovery_transactions, cleanup_transactions=cleanup_transactions,
        recovery_read_free_windows=recovery_read_free_windows,
        cleanup_read_free_windows=cleanup_read_free_windows,
        first_valid_conditional_checked_without_counter_filter=True, only_upper_table_persistence_claimed=True)
