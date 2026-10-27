"""Hand-derived residents and deliberately wrong actual evidence; no DUT."""
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace as NS

import pytest
from toffee import ScoreboardMismatch, TransferState
from bpuverify.mbtb.checker.full_capacity_learning import FullCapacityChecks
from bpuverify.mbtb.coverage.full_capacity_learning import FullCapacityCoverage
from bpuverify.mbtb.env.full_capacity_learning import planned_payload, observed_payload
from bpuverify.mbtb.model.full_capacity_learning import FullCapacityProgram, MODES, ORDERS, PC, NEIGHBOR, RULES
from bpuverify.mbtb.model.replacement import mbtb_replacement_geometry
from bpuverify.mbtb.model.semantic import Source, Feedback, Branch
from bpuverify.mbtb.transaction.types import MbtbPrediction, MbtbEntry, MbtbLookup, MbtbBatchTraining, MbtbBranchFeedback


def prediction(program, stage, owner):
    entries = [MbtbEntry(0, 0, 0, 0, 0, 0) for _ in range(10)]
    meta = [[dict(rawHit=0, position=0, counter_value=0,
                  attribute=dict(branchType=0, rasAction=0)) for _ in range(5)] for _ in range(2)]
    for way, position, target, taken, kind, action, counter in program.profile(stage, owner):
        entries[way] = MbtbEntry(1, taken, target, position, kind, action)
        meta[way//5][way%5] = dict(rawHit=1, position=position, counter_value=counter,
                            attribute=dict(branchType=kind, rasAction=action))
    for slot, hit in enumerate(program.raw_hits(stage, owner)):
        meta[slot//5][slot%5]["rawHit"] = hit
    return MbtbPrediction(tuple(entries), meta)


def transfer(program, owner, tick=10):
    return NS(state=TransferState.COMPLETED, accepted_event=NS(tick=tick), completed_event=NS(tick=tick + 4),
              request=MbtbLookup(program.branches[owner].pc))


def checker(mode='adjacent', order='forward', *, position_relation='same-position'):
    return FullCapacityChecks(mode, order, FullCapacityCoverage(mode, order, position_relation=position_relation),
                              position_relation=position_relation)


@pytest.mark.parametrize('order', ORDERS)
def test_each_new_allocation_has_its_own_initial_direction_and_preserves_the_later_owner(order):
    p = FullCapacityProgram(order)
    initial = {r.owner: r for r in p.stages['prepared']}
    assert (initial['old-a'].counter, initial['old-b'].counter) == (0, 3)
    assert p.victims['prepared'] == dict(target=3, neighbor=2)
    assert {r.owner for r in p.stages['pair'] if r.way < 4} == {'new-a', 'new-b', 'old-c', 'old-d', 'neighbor-a', 'neighbor-b', 'neighbor-c', 'neighbor-d'}
    assert [(next(r for r in p.stages['pair'] if r.owner == o).way) for o in p.sequence] == [3, 2]
    assert {r.counter for r in p.stages['pair'] if r.owner.startswith('new')} == {2}
    assert {r.owner for r in p.stages['neighbor-probe'] if r.way < 4} == {'new-a', 'new-b', 'old-c', 'old-d', 'neighbor-a', 'neighbor-c', 'neighbor-d', 'neighbor-probe'}
    assert {r.owner for r in p.stages['target-probe'] if r.way < 4} == {'new-a', 'new-b', 'old-d', 'target-probe', 'neighbor-a', 'neighbor-c', 'neighbor-d', 'neighbor-probe'}
    assert next(r for r in p.stages['neighbor-probe'] if r.owner == 'neighbor-a').counter == 3
    assert p.victims['pair'] == {'target': 1, 'neighbor': 2}
    assert p.victims['neighbor-touch'] == {'target': 1, 'neighbor': 1}


def test_page_adjacent_windows_have_independent_age_without_a_coordinate_matrix():
    p = FullCapacityProgram('forward')
    a, b = (mbtb_replacement_geometry(pc & ~31, (pc & 31)+1) for pc in (PC, NEIGHBOR))
    assert PC // 0x800 + 1 == NEIGHBOR // 0x800
    assert a.replacement_index != b.replacement_index
    assert len({mbtb_replacement_geometry(p.branches[o].pc & ~31, (p.branches[o].pc & 31)+1) for o in ('old-a', 'old-b', 'new-a', 'new-b')}) == 1
    assert len(p.branches) == 12 and p.victims['prepared'] == {'target': 3, 'neighbor': 2}


def completed_program(c):
    p = c.program
    for owner in ('old-a', 'old-b', 'old-c', 'old-d', 'neighbor-a', 'neighbor-b', 'neighbor-c', 'neighbor-d'):
        c.response('prepared', owner, transfer(p, owner), prediction(p, 'prepared', owner))
    c.reach('full-distinct-old-residents')
    ts = tuple(transfer(p, o, 20 + 2 * i) for i, o in enumerate(p.sequence))
    c.sources(ts, tuple(prediction(p, 'prepared', o) for o in p.sequence))
    c.admissions(((40, 'a'), (42 if c.mode == 'adjacent' else 46, 'b')), ('a', 'b'))
    for stage, owners in (('pair', (*p.sequence, 'old-a', 'old-b', 'neighbor-a', 'neighbor-b')),
                           ('neighbor-probe', (*p.sequence, 'neighbor-a', 'neighbor-b', 'neighbor-probe')),
                           ('neighbor-touch', (*p.sequence, 'neighbor-a', 'neighbor-b', 'neighbor-probe')),
                           ('target-probe', (*p.sequence, 'target-probe', 'neighbor-a', 'neighbor-b', 'neighbor-probe'))):
        for owner in (*owners, "old-c", "old-d", "neighbor-c", "neighbor-d"):
            c.response(stage, owner, transfer(p, owner, 100), prediction(p, stage, owner), after=46)
    for rule in RULES[3:-1]:
        c.reach(rule)
    return c


@pytest.mark.parametrize('mode', MODES)
@pytest.mark.parametrize('order', ORDERS)
def test_complete_actual_program_earns_checked_only_after_all_consumers_and_immutable_sources(mode, order):
    c = completed_program(checker(mode, order))
    assert c.coverage.groups['checked'].coverage == 0
    c.finish()
    assert c.coverage.groups['checked'].coverage == 12.5


@pytest.mark.parametrize('fault', ('counter', 'target', 'position', 'kind', 'action', 'taken', 'way', 'lost-entry'))
def test_two_new_hits_are_insufficient_when_a_complete_branch_field_is_wrong(fault):
    c = checker(); p = c.program; owner = p.sequence[0]
    result = prediction(p, 'pair', owner); entries = list(result.entries)
    way = next(i for i, e in enumerate(entries) if e.valid)
    if fault == 'counter': result.meta_entries[way//5][way%5]['counter_value'] = 1
    elif fault == 'way': entries[(way//5)*5+(way%5+1)%4], entries[way] = entries[way], entries[(way//5)*5+(way%5+1)%4]
    elif fault == 'lost-entry': entries[way] = replace(entries[way], valid=0)
    else:
        attribute = dict(kind='branch_type', action='ras_action').get(fault, fault)
        entries[way] = replace(entries[way], **{attribute: getattr(entries[way], attribute) ^ 1})
    result = replace(result, entries=tuple(entries))
    before = deepcopy(p.state())
    with pytest.raises(ScoreboardMismatch) as error:
        c.response('pair', owner, transfer(p, owner), result)
    assert error.value.expected != error.value.actual and error.value.context.request['program'] == before
    assert p.state() == before and c.coverage.groups['checked'].coverage == 0


@pytest.mark.parametrize('stage,owner', (('pair', 'old-a'), ('target-probe', 'new-a'), ('neighbor-probe', 'neighbor-b')))
def test_evicted_identity_cannot_keep_a_visible_or_filtered_raw_hit(stage, owner):
    c = checker(); p = c.program; result = prediction(p, stage, owner)
    result.meta_entries[0][0]['rawHit'] = 1
    with pytest.raises(ScoreboardMismatch): c.response(stage, owner, transfer(p, owner), result)


@pytest.mark.parametrize('fault', ('wrong-request', 'no-overlap', 'unfinished', 'missing-result', 'non-cold'))
def test_source_capture_requires_two_distinct_owned_completed_overlapping_cold_queries(fault):
    c = checker(); p = c.program
    ts = [transfer(p, o, 20 + 2 * i) for i, o in enumerate(p.sequence)]
    results = tuple(prediction(p, 'prepared', o) for o in p.sequence)
    if fault == 'wrong-request': ts[1].request = ts[0].request
    elif fault == 'no-overlap': ts[1].accepted_event.tick = ts[0].completed_event.tick
    elif fault == 'unfinished': ts[1].state = TransferState.PENDING
    elif fault == 'missing-result': results = results[:1]
    else: results[1].meta_entries[0][0]['rawHit'] = 1
    with pytest.raises(ScoreboardMismatch): c.sources(tuple(ts), results)
    assert 'original-overlapping-cold-sources' not in c.completed and c.coverage.groups['checked'].coverage == 0


@pytest.mark.parametrize('mode,fault', (('adjacent', 'bubble'), ('adjacent', 'serialised'), ('serial', 'adjacent'),
                                       ('adjacent', 'missing'), ('adjacent', 'payload'), ('adjacent', 'reverse')))
def test_wrong_actual_admission_cannot_qualify_the_planned_program(mode, fault):
    c = checker(mode); receipts = ((100, 'a'), (102, 'b'))
    if fault in ('bubble', 'serialised'): receipts = ((100, 'a'), (106, 'b'))
    elif fault == 'missing': receipts = receipts[:1]
    elif fault == 'payload': receipts = ((100, 'a'), (102, 'wrong-metadata'))
    elif fault == 'reverse': receipts = ((100, 'b'), (102, 'a'))
    with pytest.raises(ScoreboardMismatch): c.admissions(receipts, ('a', 'b'))
    assert 'actual-feedback-cadence' not in c.completed and c.coverage.groups['checked'].coverage == 0


@pytest.mark.parametrize('fault', ('old-consumer', 'missing-obligation', 'modified-snapshot'))
def test_incomplete_or_mutated_program_cannot_receive_checked_credit(fault):
    c = checker(); p = c.program; owner = 'new-a'; result = prediction(p, 'pair', owner)
    c.response('pair', owner, transfer(p, owner, 100), result)
    with pytest.raises(ScoreboardMismatch):
        if fault == 'old-consumer': c.response('pair', owner, transfer(p, owner, 100), result, after=100)
        elif fault == 'modified-snapshot':
            result.meta_entries[0][1]['counter_value'] ^= 1
            c.finish()
        else: c.finish()
    assert c.coverage.groups['checked'].coverage == 0


def test_public_feedback_comparison_preserves_both_windows_all_source_fields_and_all_branch_fields():
    p = FullCapacityProgram('forward'); result = prediction(p, 'pair', 'new-a')
    tx = MbtbBatchTraining(p.branches['new-a'].pc, result.meta_entries, (MbtbBranchFeedback(0x40009000, 1, 1, 1, 0, 1),))
    sources = tuple(tuple(Source(bool(s['rawHit']), s['position'], s['attribute']['branchType'],
        s['attribute']['rasAction'], s['counter_value']) for s in row) for row in result.meta_entries)
    pcs = (tx.pc, (tx.pc // 16 + 1) * 16)
    fb = Feedback(pcs, sources, (Branch(0x40009000, True, 1, 1, 0, True),))
    assert planned_payload(tx) == observed_payload(fb)
    wrong = replace(fb, sources=((replace(sources[0][0], counter=1), *sources[0][1:]), sources[1]))
    assert planned_payload(tx) != observed_payload(wrong)


@pytest.mark.parametrize('mode,order', (('banks', 'forward'), ('adjacent', 'all-tags')))
def test_physical_enumeration_is_not_a_semantic_program_parameter(mode, order):
    with pytest.raises(ValueError): checker(mode, order)


@pytest.mark.parametrize('order', ORDERS)
def test_new_positions_change_only_the_declared_position_relation_not_capacity_or_direction_rules(order):
    old = FullCapacityProgram(order)
    new = FullCapacityProgram(order, position_relation='new-position')
    assert old.victims == new.victims and old.sequence == new.sequence
    assert {new.branches[o].position for o in ('new-a', 'new-b')} == {2, 4}
    assert {new.branches[o].position for o in ('old-a', 'old-b')} == {1, 5}
    assert not ({new.branches[o].position for o in ('new-a', 'new-b')} &
                {new.branches[o].position for o in ('old-a', 'old-b')})
    for owner in old.branches:
        a, b = old.branches[owner], new.branches[owner]
        assert replace(b, position=a.position) == a
    assert new.stages['prepared'] == old.stages['prepared']


@pytest.mark.parametrize('mode', MODES)
@pytest.mark.parametrize('order', ORDERS)
def test_new_position_program_requires_all_the_same_complete_consumers_before_checked(mode, order):
    c = completed_program(checker(mode, order, position_relation='new-position'))
    assert c.coverage.groups['checked'].coverage == 0
    c.finish()
    assert c.coverage.groups['checked'].coverage == 12.5


@pytest.mark.parametrize('stage,owner', (('prepared', 'old-a'), ('pair', 'old-b'), ('pair', 'neighbor-a'),
    ('target-probe', 'new-b'), ('neighbor-probe', 'neighbor-a'), ('neighbor-probe', 'neighbor-probe')))
def test_missing_completed_consumer_is_rejected_even_if_the_caller_marked_its_rule_complete(stage, owner):
    c = completed_program(checker(position_relation='new-position'))
    del c.consumers[stage, owner]
    with pytest.raises(ScoreboardMismatch, match='mismatch'):
        c.finish()
    assert c.coverage.groups['checked'].coverage == 0


@pytest.mark.parametrize('order', ORDERS)
@pytest.mark.parametrize('stage', ('target-probe', 'neighbor-probe'))
def test_lost_recency_or_foreign_neighbor_touch_cannot_preserve_the_wrong_old_resident(order, stage):
    c = checker(order=order, position_relation='new-position'); p = c.program
    owner = 'old-c' if stage == 'target-probe' else 'neighbor-b'
    previous = 'neighbor-touch' if stage == 'target-probe' else 'pair'
    wrong = prediction(p, previous, owner)
    with pytest.raises(ScoreboardMismatch):
        c.response(stage, owner, transfer(p, owner, 100), wrong, after=50)
    assert c.coverage.groups['checked'].coverage == 0


def test_v2_schema_retains_all_36_original_obligations_and_keeps_failed_relation_separate():
    from bpuverify.mbtb.coverage.full_capacity_learning import obligation
    c = FullCapacityCoverage('adjacent', 'forward', position_relation='new-position')
    for rule in RULES:
        c.record('reached', rule)
    report = c.groups['reached'].report()
    counts = report['points'][0]['counts']
    originals = {f'{m}.{o}.{r}' for m in MODES for o in ORDERS for r in RULES}
    assert len(counts) == 72 and originals <= counts.keys()
    assert all(counts[key] == 0 for key in originals)
    assert all(counts[obligation('adjacent', 'forward', r, 'new-position')] == 1 for r in RULES)
    assert c.groups['checked'].coverage == 0


@pytest.mark.parametrize('relation', ('unclassified', 'new-position'))
def test_unknown_or_mismatched_position_coverage_cannot_label_a_program_as_success(relation):
    with pytest.raises(ValueError):
        FullCapacityChecks('adjacent', 'forward', FullCapacityCoverage('adjacent', 'forward'),
                           position_relation=relation)
