"""Counter-path coverage is physical, cause-specific, delayed and atomic."""
from copy import deepcopy

import pytest
from toffee import ScoreboardMismatch
from suites.frontend.bpu.abtb.model.state.counter import CounterReference
from suites.frontend.bpu.abtb.model.state.counter import index
from suites.frontend.bpu.abtb.model.state.counter import victim
from suites.frontend.bpu.bpu.coverage.abtb.supplemental import CounterCoverage
from suites.frontend.bpu.bpu.coverage.abtb.supplemental import PATHS
from suites.frontend.bpu.bpu.case.abtb.provenance import MetadataPipeline
from suites.frontend.bpu.bpu.case.abtb.provenance import eligible
from suites.frontend.bpu.bpu.case.abtb.provenance import expected_fast_train


def metadata(bank=2, set_index=31, way=1, *, valid=1):
    return dict(valid=valid, bankMask=1 << bank, setIdx=set_index,
        entries=[dict(hit=int(slot == way), position=6,
            attribute=dict(branchType=1, rasAction=0), targetLowerBits=128)
            for slot in range(4)])


def counter_trace(steps, *, bank=2, set_index=31, way=1):
    """Small monitor-shaped fixture; expected path counts are hand checked below."""
    reference, pipeline = CounterReference(), MetadataPipeline()
    rises, controls = [], []
    meta = metadata(bank, set_index, way)

    def state(row):
        row['cells'] = reference.cells[:]
        for b, port in enumerate(row['replacers']):
            port.update(states=reference.plru[b][:], shadow=reference.plru[b][:],
                victim=victim(reference.plru[b][0]))
        return row

    for step in [dict(reset=1)] + [dict() for _ in range(2)] + steps:
        tick = 2 * len(controls) + 1
        reset = step.get('reset', 0)
        captured = metadata(bank, set_index, step.get('way', way))
        captured['valid'] = step.get('meta_valid', 1)
        source = pipeline.stage3
        final = dict(valid=int(bool(source) and step.get('valid', 1)), pc=64,
            target=128, taken=step.get('taken', 1), position=step.get('position', 6),
            branch_type=step.get('branch_type', 1), ras_action=0)
        fast = dict(valid=final['valid'])
        if source:
            fast.update(expected_fast_train(final, source))
        ports, writes = [], []
        for b in range(4):
            write = dict(valid=int(step.get('write', False) and b == bank),
                set_index=step.get('write_set', set_index), way=step.get('write_way', way),
                reset_counter=int(step.get('reset_counter', True)))
            writes.append(write)
            tx = reference.pending2
            matching = [] if tx is None else [int(bool(entry['hit']
                and entry['position'] == tx['position']
                and entry['attribute'] == dict(branchType=tx['branch_type'], rasAction=tx['ras_action'])))
                for entry in tx['meta']['entries']]
            read_valid = int(bool(tx and tx['taken'] and tx['meta']['bankMask'] & (1 << b) and any(matching)))
            ports.append(dict(replace_set=0, read_valid=read_valid, read_set=set_index,
                read_mask=matching, write_valid=write['valid'], write_set=write['set_index'], write_way=write['way']))
        row = state(dict(enable=step.get('enable', 1), cells=[], replacers=ports, writes=writes,
            t1_fire=int(reference.pending1 is not None), meta1=captured,
            meta2=deepcopy(pipeline.stage2['meta'] if pipeline.stage2 else meta),
            meta3=deepcopy(source['meta'] if source else meta), fast=fast, final=final,
            capture=dict(fire1=1, fire2=1, pc1=64)))
        controls.append(dict(tick=tick, reset=reset, abtb=deepcopy(row)))
        accepted = fast.copy() if fast['valid'] and eligible(1, fast['meta']['valid'], row['enable']) else None
        if accepted:
            accepted.pop('valid')
        actual_writes = [dict(bank=b, **{key: value for key, value in write.items() if key != 'valid'})
            for b, write in enumerate(writes) if write['valid']]
        reference.advance(reset=reset, accepted=accepted, writes=actual_writes)
        pipeline.advance(reset=reset, fire1=1, fire2=1, meta=captured, pc=64, tick=tick)
        rises.append(dict(tick=tick + 1, reset=reset, abtb=deepcopy(state(row))))
    return dict(passed=True, records=rises, preedge_records=controls)


def full_path_trace(*, ways=None, **coordinates):
    steps = ([dict() for _ in range(5)]
        + [dict(taken=0, position=15, branch_type=0) for _ in range(5)]
        + [dict() for _ in range(5)]
        + [dict(taken=1, position=7, branch_type=3) for _ in range(5)]
        + [dict(valid=0) for _ in range(3)])
    if ways is not None:
        # One continuous reset-derived reference epoch, not concatenated traces.
        steps = [dict(step, way=way) for way in ways for step in steps]
    return counter_trace(steps, **coordinates)


def test_all_cells_and_three_causes_have_a_fixed_honest_denominator():
    coverage = CounterCoverage()
    summary = coverage.collect(full_path_trace())
    prefix = 'bank2.set31.way1.'
    assert set(summary['transition_counts']) == {
        prefix + path + '.' + transition for path, transitions in PATHS.items() for transition in transitions}
    # Both increment sweeps start at zero; each negative cause reaches low hold.
    assert summary['transition_counts'][prefix + 'same_position_taken.inc0_1'] == 2
    assert summary['transition_counts'][prefix + 'final_not_taken.dec3_2'] == 1
    assert summary['transition_counts'][prefix + 'later_taken.dec3_2'] == 1
    assert summary['transition_counts'][prefix + 'final_not_taken.dec0_0'] >= 1
    assert summary['transition_counts'][prefix + 'later_taken.dec0_0'] >= 1
    assert summary['transition_total_bins'] == 12288
    assert summary['write_reset_total_bins'] == 1024
    assert summary['reset_priority_total_bins'] == 12288
    assert 0 < coverage.transitions.coverage < 1
    assert coverage.resets.samples == coverage.priority.samples == 0


@pytest.mark.parametrize('bank,set_index,way', ((0, 0, 0), (1, 63, 3), (2, 31, 1), (3, 56, 2)))
def test_bin_identity_uses_the_observed_physical_way(bank, set_index, way):
    coverage = CounterCoverage()
    summary = coverage.collect(full_path_trace(bank=bank, set_index=set_index, way=way))
    assert all(label.startswith(f'bank{bank}.set{set_index}.way{way}.')
        for label in summary['transition_counts'])


@pytest.mark.parametrize('fault', (
    'cell', 'neighbor', 'short_cells', 'plru', 'shadow', 'victim', 'metadata',
    'fast_pc', 'fast_taken', 'fast_meta', 'fast_valid', 't1_gate',
    't2_gate', 't2_set', 't2_mask', 'write_gate', 'write_identity',
    'phase_gap', 'missing_rise', 'missing_control', 'initial_reset', 'execution_reset',
))
def test_observation_faults_raise_context_and_never_commit_early_bins(fault):
    trace = full_path_trace()
    stable = trace['preedge_records'][-5]
    rise = trace['records'][-1]
    abtb = stable['abtb']
    if fault == 'cell':
        rise['abtb']['cells'][index(2, 31, 1)] ^= 1
    elif fault == 'neighbor':
        rise['abtb']['cells'][1023] ^= 1
    elif fault == 'short_cells':
        rise['abtb']['cells'].pop()
    elif fault in ('plru', 'shadow'):
        rise['abtb']['replacers'][3]['states' if fault == 'plru' else 'shadow'][63] ^= 1
    elif fault == 'victim':
        rise['abtb']['replacers'][3]['victim'] ^= 1
    elif fault == 'metadata':
        abtb['meta3']['entries'][1]['position'] ^= 1
    elif fault in ('fast_pc', 'fast_taken', 'fast_meta', 'fast_valid'):
        if fault == 'fast_meta':
            abtb['fast']['meta']['bankMask'] ^= 1
        else:
            field = fault.removeprefix('fast_')
            abtb['fast'][field] ^= 1
    elif fault == 't1_gate':
        abtb['t1_fire'] ^= 1
    elif fault.startswith('t2_'):
        # Choose a same-position T2 touch, not a deliberately inactive port.
        abtb = trace['preedge_records'][8]['abtb']
        port = abtb['replacers'][2]
        assert port['read_valid'] == 1
        if fault == 't2_gate':
            port['read_valid'] = 0
        elif fault == 't2_set':
            port['read_set'] ^= 1
        else:
            port['read_mask'][1] ^= 1
    elif fault == 'write_gate':
        abtb['replacers'][2]['write_valid'] = 1
    elif fault == 'write_identity':
        trace = counter_trace([dict(), dict(write=True), dict(valid=0), dict(valid=0)])
        trace['preedge_records'][4]['abtb']['replacers'][2]['write_way'] ^= 1
    elif fault == 'phase_gap':
        stable['tick'] += 2
    elif fault == 'missing_rise':
        trace['records'].pop(-2)
    elif fault == 'missing_control':
        trace['preedge_records'].pop(-2)
    elif fault == 'initial_reset':
        trace['preedge_records'][0]['reset'] = 0
    else:
        rise['reset'] = 1
    coverage = CounterCoverage()
    with pytest.raises(ScoreboardMismatch) as error:
        coverage.collect(trace)
    assert 'bpu.integrated_abtb_counter_coverage_reset_replay' in str(error.value)
    assert all(group.samples == 0 for group in coverage.groups)


@pytest.mark.parametrize('path,step', (
    ('same_position_taken', {}),
    ('final_not_taken', dict(taken=0, position=15, branch_type=0)),
    ('later_taken', dict(taken=1, position=7, branch_type=3)),
))
def test_same_cell_reset_has_priority_and_does_not_credit_suppressed_transition(path, step):
    trace = counter_trace([step, dict(valid=0, write=True), dict(valid=0), dict(valid=0)])
    summary = CounterCoverage().collect(trace)
    prefix = 'bank2.set31.way1'
    assert summary['write_reset_counts'] == {prefix: 1}
    assert summary['reset_priority_counts'] == {prefix + '.' + path + '.before0': 1}
    assert summary['transition_counts'] == {}


@pytest.mark.parametrize('change', (dict(write_set=32), dict(write_way=2), dict(reset_counter=False)))
def test_other_cell_or_nonreset_write_is_not_a_reset_collision(change):
    trace = counter_trace([dict(), dict(valid=0, write=True, **change), dict(valid=0), dict(valid=0)])
    summary = CounterCoverage().collect(trace)
    assert summary['reset_priority_counts'] == {}
    assert summary['transition_counts'] == {'bank2.set31.way1.same_position_taken.inc0_1': 1}


def test_final_input_without_a_checked_next_state_gets_no_credit():
    trace = counter_trace([dict(), dict(valid=0)])
    trace['records'].pop()
    coverage = CounterCoverage()
    summary = coverage.collect(trace)
    assert summary['transition_counts'] == {}
    assert summary['unobserved_final_input_events_not_credited'] == 1
    assert coverage.transitions.samples == 0


@pytest.mark.parametrize('change', (dict(passed=False), dict(failure='late failure'), dict(records=[]), dict(preedge_records=[])))
def test_incomplete_or_failed_scenarios_cannot_publish_coverage(change):
    trace = full_path_trace()
    trace.update(change)
    with pytest.raises(ValueError):
        CounterCoverage().collect(trace)


def test_cached_claims_do_not_change_coverage():
    trace = full_path_trace()
    expected = CounterCoverage().collect(trace)
    trace.update(confirmed_transitions=[dict(transition='invented')],
        alias_windows=[dict(all_four_ways_covered=True)], expected=dict(all_bins_hit=True))
    assert CounterCoverage().collect(trace) == expected


@pytest.mark.parametrize('gate', ('enable', 'meta_valid'))
def test_disabled_or_invalid_metadata_never_creates_update_credit(gate):
    steps = [dict(enable=0)] * 8 if gate == 'enable' else (
        [dict(meta_valid=0, valid=0)] * 4 + [dict(meta_valid=0)] * 8)
    coverage = CounterCoverage()
    summary = coverage.collect(counter_trace(steps))
    assert summary['accepted_fast_train'] == 0
    assert summary['transition_counts'] == {}
    assert coverage.transitions.samples == 0


def test_middle_reset_restarts_the_reference_without_inventing_transition_hits():
    steps = [dict() for _ in range(6)] + [dict(reset=1)] + [dict() for _ in range(8)]
    summary = CounterCoverage().collect(counter_trace(steps))
    assert summary['reset_input_frames'] == 2
    assert summary['transition_counts']['bank2.set31.way1.same_position_taken.inc0_1'] == 2
    assert summary['write_reset_counts'] == {}


def test_final_not_taken_cannot_touch_the_t2_replacer():
    trace = counter_trace([dict(taken=0, position=15, branch_type=0)] * 8)
    frame = trace['preedge_records'][-1]
    assert frame['abtb']['replacers'][2]['read_valid'] == 0
    frame['abtb']['replacers'][2]['read_valid'] = 1
    with pytest.raises(ScoreboardMismatch):
        CounterCoverage().collect(trace)


def test_failure_does_not_change_already_collected_valid_credit():
    coverage = CounterCoverage()
    coverage.collect(full_path_trace())
    before = [(group.samples, group.coverage) for group in coverage.groups]
    trace = full_path_trace(bank=3, way=2)
    trace['records'][-1]['abtb']['cells'][1023] ^= 1
    with pytest.raises(ScoreboardMismatch):
        coverage.collect(trace)
    assert [(group.samples, group.coverage) for group in coverage.groups] == before


def test_coverage_serialization_preserves_full_denominators(tmp_path):
    import json
    coverage = CounterCoverage()
    coverage.collect(full_path_trace())
    coverage.save(tmp_path, case='model-contract')
    report = json.loads((tmp_path / 'functional-coverage-integrated-abtb-model-contract.json').read_text())
    assert len(report['groups']) == 4
    assert all(len(group['schema']['points'][0]['bins']) == 1024 for group in report['groups'][:3])
    assert [len(group['crosses'][0]['counts']) if group['crosses'] else
        len(group['points'][0]['counts']) for group in report['groups']] == [12288, 1024, 12288, 48]
    with pytest.raises(ValueError):
        coverage.save(tmp_path, case='../unsafe')


def test_semantic_paths_keep_all_four_ways_and_do_not_close_physical_matrix():
    coverage = CounterCoverage()
    coverage.collect(full_path_trace(ways=range(4), bank=0, set_index=0))
    coverage.semantic.assert_coverage(100)
    assert coverage.transitions.cross_coverage('physical_path_matrix') == pytest.approx(100 / 256)


def test_one_way_trace_does_not_claim_four_way_semantic_closure():
    coverage = CounterCoverage()
    coverage.collect(full_path_trace())
    assert coverage.semantic.cross_coverage('way_path_matrix') == 25
