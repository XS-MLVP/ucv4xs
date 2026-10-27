"""Fault injection qualifies the oracle; no observed state repairs its golden."""
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace

import pytest
from toffee import ScoreboardMismatch

from bpuverify.bpu.checker.pipeline import PipelineChecker, compared_values, environment
from bpuverify.bpu.coverage.pipeline import PipelineCoverage, RULES
from bpuverify.bpu.model.pipeline import Events
from tests.bpu.scoreboard.test_semantic_pipeline import OFF, PC, boot, published


def fixture_row(checker, events):
    """Render a reference cycle solely for negative checker tests.

    This fixture is not evidence of RTL correctness; independent positive
    algorithms/control tests and the native DUT runs provide that evidence.
    """
    cycle = checker.model.evaluate(events)
    observed = dict(valids=(),fires=(),flushes=(),repair2=0,repair3=0,initialized=0,
        pcs=(0,0,0),choices=({}, {}, {}),enabled=(),lookup_folds=(),
        micro_confidence=tuple(entry.confidence for entry in checker.model.sources.micro.entries),
        indirect_read=dict(pc=0,folds=()),indirect_random=(0,)*15,
        prediction=dict(valid=0,pc=0,target=0,taken=0,position=0,repair2=0,repair3=0),
        metadata=dict(valid=0,pc=0,history={},main=tuple(tuple(dict(hit=0,position=0,kind=0,action=0,counter=0)
            for _ in range(5)) for _ in range(2)),tage=tuple(dict.fromkeys((
                'hasProvider','hasAlt','useProvider','providerTableIdx','providerWayIdx',
                'providerTakenCtr_value','providerUsefulCtr_value','altOrBasePred','altConf'),0) for _ in range(10))))
    if getattr(checker.model.sources,'has_own_ittage',False):
        observed['metadata']['ittage']=dict(valid=0,provider=dict(valid=0,bits=0),altProvider=dict(valid=0,bits=0),
            allocate=dict(valid=0,bits=0),altDiffers=0,providerCnt_value=0,providerUsefulCnt_value=0,
            providerTarget_addr=0,altProviderCnt_value=0,altProviderTarget_addr=0)
    expected, _, _ = compared_values(checker.model,cycle,observed,events)
    if 'ittage_metadata' in expected:observed['metadata']['ittage'].update(deepcopy(expected['ittage_metadata']))
    if 'indirect_read' in expected:observed['indirect_read']=deepcopy(expected['indirect_read'])
    if 'indirect_random' in expected:observed['indirect_random']=tuple((expected['indirect_random']>>bit)&1 for bit in range(15))
    for name in ('valids','fires','flushes','repair2','repair3','initialized','enabled','lookup_folds'):
        if name in expected:
            observed[name] = expected[name]
    observed['pcs'] = tuple(expected.get(f'pc{stage}',0) for stage in (1,2,3))
    observed['choices'] = tuple(expected.get(f'choice{stage}',{}) for stage in (1,2,3))
    observed['prediction'].update(expected.get('prediction',{}),valid=expected['prediction_valid'])
    observed['metadata'].update(expected.get('metadata',{}),valid=expected['metadata_valid'])
    for key,value in expected.get('main_metadata',{}).items():
        alignment,way,field = key.split('.')
        observed['metadata']['main'][int(alignment)][int(way)][field] = value
    for key,value in expected.get('tage_metadata',{}).items():
        slot,field = key.split('.')
        observed['metadata']['tage'][int(slot)][field] = value
    inputs = dict(reset=events.reset,reset_vector=events.reset_vector,commit_valid=False,
        prediction_ready=events.prediction_ready,metadata_ready=events.metadata_ready,
        enabled=events.enabled,initialization=(events.initialization_complete,)*6,
        redirect=dict(valid=False),training=dict(valid=False,ready=True))
    if events.consumed_reset is not None:inputs['consumed_reset']=events.consumed_reset
    if events.redirect is not None:
        request = events.redirect
        inputs['redirect'] = dict(valid=True,pc=request.cfi_pc,target=request.target,taken=request.taken,
            history=request.source.metadata())
    return dict(inputs=inputs,observed=deepcopy(observed))


def ready_checker(coverage=None):
    checker = PipelineChecker(coverage)
    checker.model, events = boot(checker.model.sources)
    published(checker.model, events)
    checker.initialized = True
    checker.last_tick = 100
    checker.phase = 'stall'
    return checker, replace(events,prediction_ready=False,metadata_ready=False)


@pytest.mark.parametrize('fault', ('valid','fire','flush','pc','choice','repair','control','fold','meta-pc','meta-history','tick'))
def test_wrong_actual_is_latched_without_advancing_any_owned_state(fault):
    coverage = PipelineCoverage('stream')
    checker, events = ready_checker(coverage)
    row = fixture_row(checker,events)
    actual = row['observed']
    if fault == 'valid': actual['valids'] = (0,0,0)
    elif fault == 'fire': actual['fires'] = (1,1,1,1)
    elif fault == 'flush': actual['flushes'] = (1,1,1)
    elif fault == 'pc': actual['pcs'] = (PC,0,0)
    elif fault == 'choice': actual['choices'][0]['target'] ^= 16
    elif fault == 'repair': actual['repair2'] = 1
    elif fault == 'control': actual['enabled'] = (1,)*7
    elif fault == 'fold': actual['lookup_folds'] = (1,)*9
    elif fault == 'meta-pc': actual['metadata']['pc'] ^= 16
    elif fault == 'meta-history': actual['metadata']['history']['phrLowBits'] ^= 1
    before = deepcopy(checker.model.state()), deepcopy(checker.model.sources.micro.state()), dict(checker.model.history.owned)
    tick = 104 if fault == 'tick' else 102
    checker.capture(row,SimpleNamespace(tick=tick))
    expected_error = AssertionError if fault == 'tick' else ScoreboardMismatch
    with pytest.raises(expected_error) as first:
        checker.raise_failure()
    assert (checker.model.state(),checker.model.sources.micro.state(),dict(checker.model.history.owned)) == before
    assert coverage.groups['checked'].coverage == 0
    if fault != 'tick':
        assert coverage.groups['reached'].coverage > 0
        assert '102' in str(first.value) and 'actual' in str(first.value)
    checker.capture(fixture_row(checker,events),SimpleNamespace(tick=102))
    with pytest.raises(expected_error) as second:
        checker.finish()
    assert first.value is second.value
    assert not checker.counts and not checker.records


def test_unsupported_commit_is_not_silently_treated_as_an_empty_cycle():
    checker, events = ready_checker()
    row = fixture_row(checker,events)
    row['inputs']['commit_valid'] = True
    before = deepcopy(checker.model.state())
    checker.capture(row,SimpleNamespace(tick=102))
    with pytest.raises(NotImplementedError,match='composed RAS'):
        checker.finish()
    assert checker.model.state() == before
    # Reset dominates otherwise unsupported external inputs.
    row['inputs']['reset'] = True
    assert environment(row['inputs'],checker.model).reset


@pytest.mark.parametrize('corrupt_output',(False,True))
def test_recent_resolution_is_only_published_after_an_exact_successful_cycle_comparison(corrupt_output):
    checker,events = ready_checker()
    source = next(iter(checker.model.published.values()))
    row = fixture_row(checker,events)
    row['inputs']['training'] = dict(valid=True,ready=True,pc=source.pc,history=source.history.metadata(),
        branches=[dict(valid=1,position=4,target=PC+0x200,kind=2,action=0,taken=1,mispredict=1)])
    if corrupt_output:
        row['observed']['choices'][0]['target'] ^= 16
    checker.capture(row,SimpleNamespace(tick=102))
    if corrupt_output:
        with pytest.raises(AssertionError):checker.raise_failure()
        assert checker.last_resolution is None and checker.counts['feedback']==0
        assert not checker.resolutions
    else:
        checker.raise_failure()
        tick,resolution = checker.last_resolution
        assert (tick,resolution.pc,resolution.branches[0].target)==(102,source.pc,PC+0x200)
        assert tuple(checker.resolutions)==(checker.last_resolution,)
        reset = fixture_row(checker,replace(events,reset=True))
        checker.capture(reset,SimpleNamespace(tick=104))
        assert checker.last_resolution is None
        assert not checker.resolutions


def test_bad_non_target_confidence_at_a_known_quiet_point_latches_without_actual_seeding():
    checker,events = ready_checker()
    for _ in range(3):checker.model.advance(events)
    row = fixture_row(checker,events)
    values = list(row['observed']['micro_confidence'])
    values[27] = 1
    row['observed']['micro_confidence'] = tuple(values)
    checker.capture(row,SimpleNamespace(tick=102))
    with pytest.raises(AssertionError,match='confidence') as first:checker.raise_failure()
    state = deepcopy(checker.model.state())
    assert all(entry.confidence==0 for entry in checker.model.sources.micro.entries)
    assert checker.micro_checked is None
    checker.capture(fixture_row(checker,events),SimpleNamespace(tick=104))
    with pytest.raises(AssertionError) as second:checker.raise_failure()
    assert first.value is second.value and checker.model.state()==state


@pytest.mark.parametrize('fault', ('no-reset','no-service','no-retirement'))
def test_vacuous_checker_cannot_finish_successfully(fault):
    checker = PipelineChecker()
    if fault != 'no-reset': checker.initialized = True
    if fault == 'no-retirement': checker.model.initialized = True
    with pytest.raises(AssertionError,match='requires reset'):
        checker.finish()


@pytest.mark.parametrize('family', RULES)
def test_coverage_is_empty_until_actual_events_and_successful_comparisons(family):
    coverage = PipelineCoverage(family)
    assert all(group.coverage == 0 for group in coverage.groups.values())
    with pytest.raises(AssertionError): coverage.finish()
    rule = RULES[family][0]
    coverage.reached(10,[rule],[])
    assert coverage.groups['reached'].coverage > 0
    assert coverage.groups['checked'].coverage == 0


@pytest.mark.parametrize('family,rule', (('stream','redirect-replaces-held'),('repair','younger-squashed')))
def test_deferred_event_credit_requires_exact_following_cycle(family,rule):
    coverage = PipelineCoverage(family)
    coverage.reached(10,[],[rule])
    coverage.checked(10,[],[rule])
    assert coverage.groups['checked'].coverage == 0
    with pytest.raises(AssertionError,match='no following-cycle'): coverage.finish()
    with pytest.raises(AssertionError,match='exact following cycle'): coverage.checked(14,[],[])
    assert coverage.groups['checked'].coverage == 0
    coverage.checked(12,[],[])
    assert coverage.groups['checked'].coverage > 0 and not coverage.pending


def test_scenario_phase_does_not_supply_coverage_without_actual_events():
    checker, events = ready_checker()
    row = fixture_row(checker,events)
    row['observed']['prediction']['valid'] = row['observed']['metadata']['valid'] = False
    cycle = checker.model.evaluate(events)
    for family in RULES:
        coverage = PipelineCoverage(family)
        for phase in ('setup','stall','redirect','reopen','repair'):
            # Do not confuse a planned request or model state with a public event.
            row['observed']['valids'] = (False,False,False)
            assert coverage.candidates(row,events,cycle,checker.model,phase,None) == ([],[])
