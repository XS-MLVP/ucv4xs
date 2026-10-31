"""Synthetic source/commit/consumer fault contracts; never DUT coverage credit."""
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace
import pytest
from toffee import Scoreboard, ScoreboardMismatch, CoverageDatabase
from suites.frontend.bpu.bpu.checker.ittage_region import RegionChecker
from suites.frontend.bpu.bpu.coverage.ittage import DirectoryCoverage, DIRECTORY_RULES
from suites.frontend.bpu.bpu.model.ittage import IttageContextModel, Entry
from suites.frontend.bpu.bpu.model.ittage_region import directory_program, allocation_rule
from tests.bpu.scoreboard.test_ittage_region import Trace, transaction, PC


def origin(tx, tick):
    return SimpleNamespace(prediction_tick=tick-10, meta_tick=tick-8,
        meta=SimpleNamespace(resolve=deepcopy(tx.resolve_meta)))


def consumer(trace, resident):
    trace.step()
    model = deepcopy(resident['model'])
    if resident['pointer'] is not None:
        target = trace.model.decode(resident['pointer'], resident['offset'] << 1) >> 1
        model.entries = {table: replace(entry, target=target) for table, entry in model.entries.items()}
    tick = trace.tick-1
    source = SimpleNamespace(prediction_tick=tick-4, meta_tick=tick,
        prediction=SimpleNamespace(start_pc=resident['input']['pc']),
        meta=SimpleNamespace(resolve=dict(ittage=model.metadata())))
    phr = SimpleNamespace(records=[dict(tick=tick, parent=dict(s3_pc=resident['input']['pc'],
        s3_target=model.target(), s3_taken=1), boundary=dict(s3=dict(valid=1,
        prediction=dict(position=resident['input']['position']))))])
    trace.events.append(['consumer', (deepcopy(resident), source, phr)])


def qualified_trace():
    trace, residents = Trace(), []
    for row in directory_program():
        tx = replace(transaction(row['target']), pc=row['pc'])
        trace.events.append(['plan-source', (tx, origin(tx, trace.tick))])
        trace.step(feedback=tx)
        foreign = row['pc'] >> 19 != row['target'] >> 19
        pointer = deepcopy(trace.model).allocate(row['target'] << 1).pointer if foreign else None
        trace.step(write=row['target'] >> 19 if foreign else None)
        model = IttageContextModel(); model.entries[1] = Entry(row['target'])
        residents.append(dict(input=row, model=model, pointer=pointer, offset=row['target'] & ((1<<19)-1)))
        for resident in reversed(residents):
            consumer(trace, resident)
    return trace


def replay(trace):
    coverage = DirectoryCoverage(); checker = RegionChecker(coverage); board = Scoreboard('pure.residents')
    for phase, value in trace.events:
        if phase == 'plan-source': checker.plan_feedback(*value)
        elif phase == 'consumer': checker.check_consumer(*value, board)
        else: checker.observe(phase, value)
    return checker, coverage, checker.summary()


def test_actual_sources_commit_all_five_allocation_contexts_and_three_consumption_rules():
    checker, coverage, summary = replay(qualified_trace())
    coverage.require()
    assert len(summary['accepted_feedback']) == 21 and len(summary['writes']) == 20
    reached = coverage.groups['allocation','reached'].report()
    assert reached['points'][0]['counts'] == dict(zip(DIRECTORY_RULES['allocation'],(1,16,1,1,2)))
    checked = coverage.groups['allocation','checked'].report()
    assert checked['points'][0]['counts'] == reached['points'][0]['counts']
    partial = next(row for row in summary['writes'] if row['source']['rule'] == 'reuse-before-full')
    assert (partial['pointer'],partial['reused'],partial['evicted_region']) == (3,True,None)
    assert sum(r is not None for r in partial['source']['before_regions']) == 8
    for family in DIRECTORY_RULES:
        assert coverage.groups[family,'reached'].samples == coverage.groups[family,'checked'].samples
    assert coverage.groups['consumption','checked'].samples == sum(range(1,22))
    CoverageDatabase.from_dict(CoverageDatabase(list(coverage.groups.values())).report())


@pytest.mark.parametrize('fault',('write-pointer','write-region','region','neighbor','valid','read-region',
    'update-pointer','phase','gap','missing-effect'))
def test_accepted_write_fault_retains_reached_without_commit_credit(fault):
    trace = Trace(); tx = transaction(0x40100090)
    source = origin(tx,trace.tick)
    trace.step(feedback=tx); trace.step(write=tx.branches[0].target >> 19)
    coverage = DirectoryCoverage(); checker = RegionChecker(coverage)
    checker.observe(*trace.events[0]);checker.observe(*trace.events[1]);checker.plan_feedback(tx,source)
    events = deepcopy(trace.events[2:])
    if fault == 'write-pointer': events[-2][1].value['ports']['write_pointer'] ^= 1
    elif fault == 'write-region': events[-2][1].value['ports']['write_region'] ^= 1
    elif fault == 'region': events[-1][1].value['state'][0]['region'] ^= 1
    elif fault == 'neighbor': events[-1][1].value['state'][15]['region'] = 1
    elif fault == 'valid': events[-1][1].value['state'][0]['valid'] = 0
    elif fault == 'read-region': events[-1][1].value['ports']['responses'][0]['region'] ^= 1
    elif fault == 'update-pointer': events[-1][1].value['ports']['updates'][0]['pointer'] ^= 1
    elif fault == 'phase': events[-1][0] = 'preedge'
    elif fault == 'gap': events[-1][1].event.tick += 2
    else: events.pop()
    for phase,value in events: checker.capture(phase,value)
    with pytest.raises(ScoreboardMismatch): checker.summary()
    assert coverage.groups['allocation','reached'].samples == 1
    assert coverage.groups['allocation','checked'].samples == 0
    report=checker.diagnostics()
    assert report['checks']['failed']==1 and 'mismatch' in report['checks']['first_failure']


def test_missing_region_write_is_not_completed_by_idle_observations():
    trace = Trace(); tx = transaction(0x40100090); source = origin(tx,trace.tick)
    trace.step(feedback=tx); trace.step()
    coverage=DirectoryCoverage();checker=RegionChecker(coverage)
    for phase,value in trace.events[:2]:checker.observe(phase,value)
    checker.plan_feedback(tx,source)
    for phase,value in trace.events[2:]:checker.observe(phase,value)
    with pytest.raises(ScoreboardMismatch,match='drained'):checker.summary()
    assert coverage.groups['allocation','reached'].samples==1 and coverage.groups['allocation','checked'].samples==0


def test_PC_region_bypass_checked_waits_for_its_complete_public_consumer():
    trace = qualified_trace()
    index = next(i for i,(phase,value) in enumerate(trace.events) if phase=='consumer')
    coverage=DirectoryCoverage();checker=RegionChecker(coverage);board=Scoreboard('pure.bypass')
    for phase,value in trace.events[:index]:
        if phase=='plan-source':checker.plan_feedback(*value)
        else:checker.observe(phase,value)
    assert coverage.groups['allocation','reached'].samples==1 and coverage.groups['allocation','checked'].samples==0
    checker.check_consumer(*trace.events[index][1],board)
    checker.summary()
    assert coverage.groups['allocation','checked'].samples==1


def test_PC_region_bypass_without_public_consumer_is_incomplete_not_a_passing_idle():
    trace=qualified_trace()
    index=next(i for i,(phase,value) in enumerate(trace.events) if phase=='consumer')
    checker=RegionChecker(DirectoryCoverage())
    for phase,value in trace.events[:index]:
        if phase=='plan-source':checker.plan_feedback(*value)
        else:checker.observe(phase,value)
    with pytest.raises(ScoreboardMismatch,match='bypass'):checker.summary()
    assert checker.coverage.groups['allocation','checked'].samples==0
    assert 'bypass' in checker.diagnostics()['checks']['first_failure']


@pytest.mark.parametrize('fault',('source-PC','provider-counter','provider-target','target','taken','position',
    'invalid-final','missing-final','duplicate-final'))
def test_public_consumer_failure_never_earns_checked_credit(fault):
    trace=qualified_trace()
    # Select an actually replaced-pointer source; the PC-region source remains unaffected.
    target_index=next(i for i in range(len(trace.events)-1,-1,-1) if trace.events[i][0]=='consumer'
        and trace.events[i][1][0]['pointer'] is not None
        and trace.events[i][1][1].meta.resolve['ittage']['providerTarget_addr']!=trace.events[i][1][0]['input']['target'])
    resident,source,phr=deepcopy(trace.events[target_index][1])
    rows=phr.records
    if fault=='source-PC':source.prediction.start_pc ^= 8
    elif fault=='provider-counter':source.meta.resolve['ittage']['providerCnt_value'] ^= 1
    elif fault=='provider-target':source.meta.resolve['ittage']['providerTarget_addr'] ^= 1
    elif fault=='target':rows[0]['parent']['s3_target'] ^= 1
    elif fault=='taken':rows[0]['parent']['s3_taken']=0
    elif fault=='position':rows[0]['boundary']['s3']['prediction']['position'] ^= 1
    elif fault=='invalid-final':rows[0]['boundary']['s3']['valid']=0
    elif fault=='missing-final':rows.clear()
    else:rows.append(deepcopy(rows[0]))
    coverage=DirectoryCoverage();checker=RegionChecker(coverage);board=Scoreboard('pure.consumer')
    for phase,value in trace.events[:target_index]:
        if phase=='plan-source':checker.plan_feedback(*value)
        elif phase=='consumer':checker.check_consumer(*value,board)
        else:checker.observe(phase,value)
    before=coverage.groups['consumption','checked'].samples
    with pytest.raises(ScoreboardMismatch):checker.check_consumer(resident,source,phr,board)
    assert coverage.groups['consumption','checked'].samples==before
    assert coverage.groups['consumption','reached'].samples==before+1


@pytest.mark.parametrize('fault',('missing-source','modified-metadata'))
def test_missing_or_modified_prediction_source_is_not_inferred(fault):
    checker=RegionChecker(DirectoryCoverage());tx=transaction(0x40100090);source=origin(tx,43)
    if fault=='missing-source':
        with pytest.raises(ValueError,match='source identities'):checker.plan_feedback(tx)
    else:
        source.meta.resolve['ittage']['providerCnt_value'] ^= 1
        with pytest.raises(ScoreboardMismatch,match='unmodified'):checker.plan_feedback(tx,source)


@pytest.mark.parametrize('family,status',[(family,status) for family in DIRECTORY_RULES for status in ('reached','checked')])
def test_event_schemas_have_no_phase_sequence_or_physical_cross(family,status):
    group=DirectoryCoverage().groups[family,status]
    assert tuple(point.name for point in group.definition.points)==('rule',)
    assert not group.definition.crosses and group.samples==0


@pytest.mark.parametrize('occupied,region,expected',((0,0x800,'pc-region-bypass'),(0,0x810,'free-entry'),
    (8,0x813,'reuse-before-full'),(16,0x813,'reuse-at-full'),(16,0x830,'PLRU-replacement')))
def test_allocation_rules_come_from_logical_preconditions_not_actual_DUT_pointers(occupied,region,expected):
    regions=tuple(0x810+i if i<occupied else None for i in range(16))
    assert allocation_rule(regions,PC,(region<<19)|0x90)==expected
