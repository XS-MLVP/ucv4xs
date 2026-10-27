"""Normal-driver retained-owner diagnostic, never collected as a formal test.

The metadata is genuinely captured before tag migration. Taken base prediction
prevents useful updates, isolating counter ownership from the known useful
misassociation defect. This is standalone evidence, not FTQ qualification.
"""
import argparse
import asyncio
from copy import deepcopy
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path

from toffee import CheckContext
from toffee import Execution
from toffee import Scoreboard
from toffee import ScoreboardMode
from toffee import XCommClockBackend
from bpuverify.tage.agent.main import TageAgent
from bpuverify.tage.transaction.types import TageBatchTraining
from bpuverify.tage.transaction.types import TageBranchFeedback
from bpuverify.tage.transaction.types import TageLookup
from bpuverify.tage.transaction.types import TageTraining
from bpuverify.common.env.dut import DutFactory
from bpuverify.tage.driver.feedback import expected_tage_feedback
from bpuverify.tage.driver.feedback import observed_tage_feedback
from bpuverify.tage.model.shadow import advance_tage_shadow
from bpuverify.tage.model.shadow import expected_tage_cross_owner_writes
from bpuverify.tage.checker.assertions import fill_useful_set
from bpuverify.tage.case.way_migration_scenario import cell
from bpuverify.tage.case.way_migration_scenario import prepare_unprotected_highest_ways
from bpuverify.tage.case.way_migration_scenario import protect
from bpuverify.tage.case.way_migration_scenario import snapshot

ROOT = Path(__file__).resolve().parents[3]
REPORTS = ('feature-points.json', 'rtl-coverage-manifest.json', 'rtl-line-coverage.json', 'verification-report.html')


async def prepare_migration(agent, pc, origin):
    target = await prepare_unprotected_highest_ways(agent, pc, origin)
    capture = agent.submit_predict(pc, target, 1)
    captured = await capture
    assert cell(captured) == (3, origin)
    assert (captured.meta['providerTakenCtr_value'], captured.meta['providerUsefulCtr_value'],
            captured.meta['altOrBasePred'], captured.meta['hasAlt']) == (5, 0, 1, 0)
    pred = await agent.predict(pc, target, 0)
    await agent.train(TageTraining(pc, target, 0, 0, pred.meta, mispredict=1))
    weakened = await agent.predict(pc, target, 0)
    assert cell(weakened) == (3, origin) and weakened.meta['providerTakenCtr_value'] == 4
    cold = await agent.predict(pc, 9, 0)
    assert not cold.meta['hasProvider']
    await agent.train(TageTraining(pc, 9, 1, 0, cold.meta, mispredict=1))
    replacement = await agent.predict(pc, 9, 0)
    assert cell(replacement) == (3, origin)
    assert not (await agent.predict(pc, target, 0)).meta['hasProvider']
    await protect(agent, pc, 9, replacement, agent.train)
    missing = await agent.predict(pc, target, 0)
    assert not missing.meta['hasProvider']
    await agent.train(TageTraining(pc, target, 1, 0, missing.meta, mispredict=1))
    migrated = await agent.predict(pc, target, 1)
    assert cell(migrated) == (3, 1-origin)
    assert (migrated.meta['providerTakenCtr_value'], migrated.meta['providerUsefulCtr_value']) == (4, 0)
    return target, deepcopy(captured.meta), deepcopy(migrated.meta), capture.completed_event.tick


def initial_shadows(pc, last_profiles):
    banks = [[[dict(valid=0, dirty=0, set_idx=0, tag=0, entry_valid=0, counter=0)
               for _ in range(4)] for _ in range(2)] for _ in range(4)]
    for position, profile in last_profiles.items():
        meta = profile['meta']
        if meta['providerTableIdx'] == 3:
            banks[pc & 3][meta['providerWayIdx']][0] = dict(valid=1, dirty=0,
                set_idx=(pc >> 2) & 127, tag=((pc >> 9) & 8191) ^ position,
                entry_valid=1, counter=meta['providerTakenCtr_value'])
    return tuple(tuple(tuple(row) for row in bank) for bank in banks)


def check_native(checks, shadows, feedback, expected_writes, initial, *, bank, origin, depth, mode, context):
    expected = deepcopy(initial)
    by_tick = {beat.event.tick+8:(index, frame) for index, (beat, frame)
               in enumerate(zip(feedback, expected_writes, strict=True))}
    witnesses = []
    for observation, following in zip(shadows, shadows[1:]):
        checks.check(expected=2, actual=following.event.tick-observation.event.tick, context=context)
        actual = tuple(row['shadow'] for row in observation.value['banks'])
        checks.check(expected=expected, actual=actual, context=context)
        ready = tuple(tuple(port['ready'] for port in row['reads']) for row in observation.value['banks'])
        checks.check(expected=tuple(tuple(int(any(slot['dirty'] for slot in owner)) for owner in row)
                                   for row in expected),
                     actual=tuple(tuple(port['valid'] for port in row['reads'])
                                  for row in observation.value['banks']), context=context)
        step = by_tick.get(observation.event.tick)
        if step is None:
            transition = advance_tage_shadow(expected, ready)
        else:
            index, frame = step
            active = [(bank, port, value) for bank, ports in enumerate(frame) for port, value in enumerate(ports)
                      if value is not None]
            assert len(active) == 1
            target_bank, port, value = active[0]
            transition = advance_tage_shadow(expected, ready, bank=target_bank, port=port, write=value)
            if index > depth:
                old = expected[bank][1-origin][depth]
                counter = (5, 6, 7)[index-depth-1]
                checks.check(expected={'owner':1-origin, 'depth':depth, 'old_counter':counter,
                    'dirty':int(mode == 'pending'), 'ready':(int(mode == 'clean'),)*2},
                    actual={'owner':transition['owner'], 'depth':transition['depth'], 'old_counter':old['counter'],
                            'dirty':old['dirty'], 'ready':ready[bank]}, context=context)
                witnesses.append(dict(tick=observation.event.tick, requested_port=port, owner=transition['owner'],
                    depth=transition['depth'], old_counter=old['counter'], requested_counter=value['counter'],
                    new_counter=transition['banks'][bank][1-origin][depth]['counter']))
        expected = transition['banks']
        checks.check(expected=expected, actual=tuple(row['shadow'] for row in following.value['banks']), context=context)
    checks.check(expected=3, actual=len(witnesses), context=context)
    return witnesses


async def read_profiles(agent, profiles, *, reverse=False):
    coordinates = [(pc, position) for pc, entries in profiles.items() for position in entries]
    if reverse:
        coordinates.reverse()
    comparisons = Scoreboard('tage.retained_owner_profiles')
    def checker(wanted):
        frozen = deepcopy(wanted)
        # The outer asynchronous Scoreboard owns identity/timing and failure
        # statistics. Pure compare keeps field differences without wrapping an
        # inner context-free ScoreboardMismatch that would hide that context.
        return lambda prediction: comparisons.compare(frozen, snapshot(prediction))
    transfers = [agent.submit_predict(pc, position, 1, expected=checker(profiles[pc][position]))
                 for pc, position in coordinates]
    await agent.drain_predictions()
    ticks = [transfer.accepted_event.tick for transfer in transfers]
    assert ticks == list(range(ticks[0], ticks[0]+2*len(ticks), 2))
    assert [transfer.completed_event.tick for transfer in transfers] == [tick+4 for tick in ticks]
    return {f'{pc:#x}:{pos}': deepcopy(snapshot(await transfer))
            for (pc, pos), transfer in zip(coordinates, transfers, strict=True)}


async def check_case(agent, *, bank, origin, depth, mode):
    pc = 0x40000000+bank
    target, captured, current, capture_tick = await prepare_migration(agent, pc, origin)
    profiles = {pc:{pos:deepcopy(snapshot(await agent.predict(pc, pos, 1))) for pos in range(10)}}
    dummy_rows = []
    for number in range(3):
        dummy_pc = pc+0x20*(number+1)
        residents = await fill_useful_set(agent, pc=dummy_pc)
        position = next(pos for pos, pred in residents.items() if cell(pred) == (3, 1-origin))
        pred = await agent.predict(dummy_pc, position, 1)
        assert pred.meta['providerTakenCtr_value'] == 5
        await agent.train(TageTraining(dummy_pc, position, 1, 1, pred.meta, mispredict=0))
        pred = await agent.predict(dummy_pc, position, 1)
        assert pred.meta['providerTakenCtr_value'] == 6 and cell(pred) == (3, 1-origin)
        profiles[dummy_pc] = {pos:deepcopy(snapshot(await agent.predict(dummy_pc, pos, 1))) for pos in range(8)}
        dummy_rows.append((dummy_pc, position, deepcopy(pred.meta)))
    assert snapshot(await agent.predict(pc, target, 1)) == profiles[pc][target]
    prefix = tuple(TageBatchTraining(address, (TageBranchFeedback(position, 1, 1, meta),))
                   for address, position, meta in dummy_rows[:depth])
    transactions = prefix+(TageBatchTraining(pc, (TageBranchFeedback(target, 1, 1, current),)),)+(
        TageBatchTraining(pc, (TageBranchFeedback(target, 1, 1, captured),)),)*3
    expected_input = tuple(expected_tage_feedback(tx, branch_count=8) for tx in transactions)
    expected_writes = expected_tage_cross_owner_writes(pc, target, origin,
        tuple((address, position) for address, position, _ in dummy_rows[:depth]))
    expected_profiles = deepcopy(profiles)
    expected_profiles[pc][target]['meta'].update(providerTakenCtr_value=7, useProvider=1)
    for address, position, _ in dummy_rows[:depth]:
        expected_profiles[address][position]['meta']['providerTakenCtr_value'] = 7
    initial = initial_shadows(dummy_rows[-1][0], profiles[dummy_rows[-1][0]])
    sentinel_pc = 0x40000180+bank
    sentinel = deepcopy(snapshot(await agent.predict(sentinel_pc, 14, 1)))
    assert not sentinel['meta']['hasProvider']
    async with agent.observe_training() as feedback, agent.observe_writes() as writes, agent.observe_shadows() as shadows:
        comparisons = Scoreboard('tage.read_pressure')
        checker = lambda pred: comparisons.compare(sentinel, snapshot(pred))
        pressured = transactions if mode == 'pending' else transactions[:depth+1]
        transfers = await agent.train_batches_with_read_pressure(pressured, TageLookup(sentinel_pc, 14, 1), expected=checker)
        if mode == 'clean':
            for transaction in transactions[depth+1:]:
                await agent.train_batch(transaction)
    checks = Scoreboard('tage.retained_owner')
    context = CheckContext(scoreboard='tage.retained_owner', mode=ScoreboardMode.DIRECT, sequence_id=1,
        request=dict(bank=bank, origin=origin, depth=depth, mode=mode, transactions=transactions),
        accepted_event=feedback[0].event if feedback else None, observed_event=writes[-1].event if writes else None)
    checks.check(expected=expected_input,
        actual=tuple(observed_tage_feedback(frame.value) for frame in feedback), context=context)
    checks.check(expected=expected_writes, actual=tuple(frame.value['banks'] for frame in writes), context=context)
    checks.check(expected=(8,)*len(transactions),
        actual=tuple(write.event.tick-beat.event.tick for write, beat in zip(writes, feedback, strict=True)), context=context)
    intervals = [b.event.tick-a.event.tick for a, b in zip(feedback, feedback[1:])]
    checks.check(expected=True, actual=all(tick == 2 for tick in intervals[:depth])
        and all(tick == 2 if mode == 'pending' else tick > 8 for tick in intervals[depth:]), context=context)
    witnesses = check_native(checks, shadows, feedback, expected_writes, initial,
                            bank=bank, origin=origin, depth=depth, mode=mode, context=context)
    forward = await read_profiles(agent, expected_profiles)
    reverse = await read_profiles(agent, expected_profiles, reverse=True)
    assert captured == transactions[-1].branches[0].meta and profiles[pc][target]['meta']['providerTakenCtr_value'] == 4
    return dict(bank=bank, origin=origin, depth=depth, mode=mode, target=target, capture_tick=capture_tick,
        captured_meta=captured, current_meta=current, initial_shadows=initial, expected_input=expected_input,
        expected_writes=expected_writes, expected_profiles=expected_profiles, prepared_profiles=profiles,
        witnesses=witnesses, forward=forward, reverse=reverse,
        prediction_cadence=[(tx.accepted_event.tick, tx.completed_event.tick) for tx in transfers],
        accepted=[dict(tick=frame.event.tick, value=frame.value) for frame in feedback],
        writes=[dict(tick=frame.event.tick, value=frame.value) for frame in writes],
        checks=asdict(checks.status), native_cycles_checked=len(shadows)-1)


async def run(arguments):
    stage = arguments.stage.resolve()
    if stage == ROOT or ROOT in stage.parents:
        raise ValueError('diagnostic stage must be outside the formal verification repository')
    stage.mkdir(parents=True, exist_ok=True)
    protected = {name:sha256((ROOT/'results'/name).read_bytes()).hexdigest() for name in REPORTS}
    raw = stage/'probe-retained-owner-coverage.dat'
    report = dict(format='bpu-tage-retained-owner-readonly', version=1, formal_credit=False,
        integrated_ftq_qualification_proven=False, strict_xfail_registered=False, raw_file=str(raw), cases=[])
    factory = DutFactory()
    try:
        dut = factory.create('tage', coverage_name=str(raw))
        async with Execution(XCommClockBackend(dut.GetXClock()), max_batch_ticks=256) as execution:
            agent = await TageAgent(dut).start(execution)
            try:
                for bank in arguments.banks:
                    for origin in arguments.origins:
                        for depth in arguments.depths:
                            for mode in arguments.modes:
                                result = await check_case(agent, bank=bank, origin=origin, depth=depth, mode=mode)
                                report['cases'].append(result)
                                print(f'PASS bank={bank} origin={origin} depth={depth} mode={mode}', flush=True)
            finally:
                await agent.aclose()
    except BaseException as error:
        report['error'] = repr(error)
        raise
    finally:
        factory.close()
        assert protected == {name:sha256((ROOT/'results'/name).read_bytes()).hexdigest() for name in REPORTS}
        report.update(formal_reports_preserved_byte_for_byte=True, protected_sha256=protected,
            source_sha256={str(path.relative_to(ROOT)):sha256(path.read_bytes()).hexdigest() for path in (
                Path(__file__).resolve(), ROOT/'bpuverify/tage/agent/main.py', ROOT/'bpuverify/tage/model/shadow.py',
                ROOT/'bpuverify/tage/monitor/shadow.py', ROOT/'rtl/tage/WriteBuffer.sv')})
        (stage/'retained-owner-result.json').write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', type=Path, required=True)
    parser.add_argument('--banks', type=int, nargs='+', choices=range(4), default=list(range(4)))
    parser.add_argument('--origins', type=int, nargs='+', choices=range(2), default=list(range(2)))
    parser.add_argument('--depths', type=int, nargs='+', choices=range(4), default=list(range(4)))
    parser.add_argument('--modes', nargs='+', choices=('pending', 'clean'), default=['pending', 'clean'])
    asyncio.run(run(parser.parse_args()))
