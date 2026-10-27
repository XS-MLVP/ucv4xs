"""Seven-model composition, real learning and immutable original provenance."""
from copy import deepcopy

ABSENT_SLOT=0
CONDITIONAL_SLOT=2
from dataclasses import replace

import pytest

from bpuverify.bpu.model.pipeline import Redirect, Resolution
from bpuverify.bpu.model.selection import Kind
from tests.bpu.scoreboard._statistical_joint_program import Program


@pytest.mark.parametrize('positive', (False, True))
def test_shared_sc_experience_changes_the_prefix_without_training_the_target_tage(positive):
    p = Program(positive=positive)
    target, original, sources, fresh = p.prepare()
    result = p.bank.statistical_snapshot(fresh, resolved=True)
    tagged = dict(p.bank.tage_snapshot(fresh, resolved=True).wanted)
    slot, = [slot for slot in range(10) if tagged.get(f'{slot}.has_provider')]
    assert tagged[f'{slot}.counter'] == (4 if positive else 3)
    main = fresh.lookup.values()
    direction = tagged[f'{slot}.taken'] if tagged[f'{slot}.valid'] else main[f'{slot}.taken']
    assert bool(direction) is not positive
    assert result.prediction.used[slot] == 1 and result.prediction.directions[slot] == int(positive)
    assert result.prediction.sums[slot] == (32 if positive else -24)
    assert result.late.branch.position == (2 if positive else 4)
    assert result.late.branch.target == (p.d if positive else p.a)
    assert result.late.source == ('main' if positive else 'indirect-history')
    assert p.bank.statistical_snapshot(target, resolved=True) is original
    assert original.prediction.sums[slot] == 8 and not original.prediction.used[slot]
    assert len({source.history.sequence for source in sources}) == len(sources)


def test_all_seven_predictor_algorithms_advance_exactly_once_per_boundary(monkeypatch):
    p = Program(positive=True)
    names = ('micro', 'main', 'ahead', 'short', 'tage', 'indirect', 'sc')
    counts = dict.fromkeys(names, 0)
    for name in names:
        component = getattr(p.bank, name)
        original = component.advance
        def counted(*args, _name=name, _original=original, **kwargs):
            counts[_name] += 1
            return _original(*args, **kwargs)
        monkeypatch.setattr(component, 'advance', counted)
    for _ in range(8):
        p.step()
    assert counts == dict.fromkeys(names, 8)


@pytest.mark.parametrize('fault', ('missing-kind', 'foreign-owner'))
def test_backend_history_needs_declared_branch_semantics_and_exact_original(fault):
    p = Program(positive=True)
    idle = p.quiet()
    source = p.anchor.history if fault == 'missing-kind' else replace(p.anchor.history)
    request = Redirect(source, (p.a // 16) * 16 + 4, p.b, True,
        None if fault == 'missing-kind' else Kind.INDIRECT)
    with pytest.raises(ValueError, match='semantic branch kind|owned|original|checkpoint'):
        p.step(replace(idle, redirect=request))


@pytest.mark.parametrize('domain', ('statistical-read', 'statistical-result', 'query-history'))
@pytest.mark.parametrize('ending', ('foreign', 'retire', 'reset'))
def test_every_added_domain_has_the_same_explicit_original_lifetime(domain, ending):
    p = Program(positive=False)
    token = p.query(p.b)
    getter = (p.bank.queries.snapshot if domain == 'query-history' else
        lambda value: p.bank.statistical_snapshot(value, resolved=domain == 'statistical-result'))
    getter(token)
    if ending == 'foreign':
        token = replace(token, history=replace(token.history))
    elif ending == 'retire':
        p.model.retire_source(token.sequence)
    else:
        p.model.advance(replace(p.event, reset=True))
    with pytest.raises(ValueError, match='absent|retired|checkpoint|original'):
        getter(token)


def test_invalid_younger_feedback_is_rejected_before_any_component_learns():
    p = Program(positive=True)
    target, _, _, fresh = p.prepare()
    idle = p.quiet()
    from bpuverify.bpu.model.pipeline import Outcome
    request = Resolution(fresh.history, fresh.pc, (Outcome(2, p.d, Kind.CONDITIONAL, True),
        Outcome(4, p.a, Kind.INDIRECT, True)), origin=fresh)
    names = ('micro', 'main', 'ahead', 'short', 'tage', 'indirect', 'sc')
    before = tuple(deepcopy(getattr(p.bank, name).state()) for name in names)
    with pytest.raises(ValueError, match='unexecuted younger'):
        p.step(replace(idle, feedback=request))
    assert before == tuple(getattr(p.bank, name).state() for name in names)


@pytest.mark.parametrize('positive', (False, True))
def test_learning_projection_is_pure_and_predicts_the_one_actual_SC_advance(positive):
    from bpuverify.sc.model.semantic import Context, Events
    from bpuverify.bpu.model.pipeline import Outcome
    p = Program(positive=positive)
    _, _, _, token = p.prepare()
    branches = (Outcome(2,p.d,Kind.CONDITIONAL,not positive),)
    request = Resolution(token.history,token.pc,branches,origin=token)
    transaction = p.bank.sc_feedback(request,True)
    p.bank.sc.advance(Events(feedback=transaction,feedback_context=Context.from_history(transaction.history)))
    before = deepcopy(p.bank.sc.state()), deepcopy(p.bank.sc.memory)
    patches, thresholds = p.bank.sc.preview_learning()
    assert len(patches) == 4 and thresholds != p.bank.sc.thresholds.values
    assert before == (p.bank.sc.state(), p.bank.sc.memory)
    p.bank.sc.advance(Events())
    assert p.bank.sc.pending == patches and p.bank.sc.thresholds.values == thresholds


def metadata_actual(value):
    from bpuverify.bpu.bundle.statistical import DEBUG_VECTORS
    prediction = value.prediction
    return dict(prediction.metadata(), debug=dict(
        **{name: tuple(row[table] for row in prediction.components) for table,name in enumerate(DEBUG_VECTORS)},
        predPathIdx=prediction.read.indices[:2],predGlobalIdx=prediction.read.indices[2:4],
        predBWIdx=prediction.read.indices[4:6],predImliIdx=prediction.read.indices[6],predBiasIdx=prediction.read.indices[7]))


@pytest.mark.parametrize('field', ('scPred','scPathTakenVec','scImliTakenVec','tageCtr','scBiasLowerBits'))
def test_unused_absent_candidate_payload_is_not_invented_but_authority_remains_checked(field):
    from bpuverify.bpu.checker.statistical import metadata_values
    p = Program(positive=False)
    _, _, _, token = p.prepare()
    source = p.bank.statistical_snapshot(token,resolved=True)
    actual = metadata_actual(source)
    target = actual['debug'] if field.startswith('sc') and field.endswith('TakenVec') else actual
    target[field] = tuple(1-v if slot==ABSENT_SLOT else v for slot,v in enumerate(target[field]))
    expected, observed = metadata_values(p.bank,token,actual)
    assert expected == observed
    actual['useScPred'] = tuple(1 if slot==ABSENT_SLOT else v for slot,v in enumerate(actual['useScPred']))
    assert metadata_values(p.bank,token,actual)[0] != metadata_values(p.bank,token,actual)[1]


@pytest.mark.parametrize('field', ('scPred','scPathTakenVec','scImliTakenVec','tageCtr','scBiasLowerBits'))
def test_every_real_candidate_field_still_rejects_corruption(field):
    from bpuverify.bpu.checker.statistical import metadata_values
    p = Program(positive=False)
    _, _, _, token = p.prepare()
    actual = metadata_actual(p.bank.statistical_snapshot(token,resolved=True))
    target = actual['debug'] if field.startswith('sc') and field.endswith('TakenVec') else actual
    target[field] = tuple(1-v if slot==CONDITIONAL_SLOT else v for slot,v in enumerate(target[field]))
    expected, observed = metadata_values(p.bank,token,actual)
    assert expected != observed


@pytest.mark.parametrize('field,payload',(('tageCtr',0),('tageCtr',3),('tageCtr',5),('tageCtr',7),('tagePred',1)))
def test_independently_invalid_provider_payload_is_unspecified_but_validity_is_not(field,payload):
    from dataclasses import replace
    from types import SimpleNamespace
    from bpuverify.sc.model.semantic import decide
    from bpuverify.bpu.checker.statistical import metadata_values
    p=Program(positive=False)
    _,_,_,token=p.prepare()
    source=p.bank.statistical_snapshot(token,resolved=True)
    branches=tuple(replace(branch,provider_valid=0,tage_counter=0) if slot==CONDITIONAL_SLOT else branch
        for slot,branch in enumerate(source.prediction.branches))
    value=replace(source,prediction=decide(source.original.read,branches,p.bank.sc.thresholds.values))
    bank=SimpleNamespace(statistical_snapshot=lambda *args,**kwargs:value)
    actual=metadata_actual(value)
    actual[field]=tuple(payload if slot==CONDITIONAL_SLOT else bit for slot,bit in enumerate(actual[field]))
    assert metadata_values(bank,token,actual)[0]==metadata_values(bank,token,actual)[1]
    actual['tagePredValid']=tuple(1 if slot==CONDITIONAL_SLOT else bit for slot,bit in enumerate(actual['tagePredValid']))
    assert metadata_values(bank,token,actual)[0]!=metadata_values(bank,token,actual)[1]


@pytest.mark.parametrize('field',('useScPred','scBiasLowerBits','sumAboveThres','scPred'))
def test_invalid_provider_does_not_relax_authority_bias_confidence_or_sc_direction(field):
    from dataclasses import replace
    from types import SimpleNamespace
    from bpuverify.sc.model.semantic import decide
    from bpuverify.bpu.checker.statistical import metadata_values
    p=Program(positive=False)
    _,_,_,token=p.prepare()
    source=p.bank.statistical_snapshot(token,resolved=True)
    branches=tuple(replace(branch,provider_valid=0,tage_counter=0) if slot==CONDITIONAL_SLOT else branch
        for slot,branch in enumerate(source.prediction.branches))
    value=replace(source,prediction=decide(source.original.read,branches,p.bank.sc.thresholds.values))
    bank=SimpleNamespace(statistical_snapshot=lambda *args,**kwargs:value)
    actual=metadata_actual(value)
    actual[field]=tuple(1-bit if slot==CONDITIONAL_SLOT else bit for slot,bit in enumerate(actual[field]))
    assert metadata_values(bank,token,actual)[0]!=metadata_values(bank,token,actual)[1]


from bpuverify.bpu.coverage.statistical_prefix import Coverage
from bpuverify.bpu.model.statistical_prefix import PROFILES, RULES


@pytest.mark.parametrize('profile,missing', tuple((p,r) for p in PROFILES for r in RULES))
def test_missing_any_native_prefix_obligation_cannot_award_checked_credit(profile,missing):
    coverage = Coverage(profile)
    for rule in RULES:
        if rule != missing:
            coverage.record(rule,10)
    with pytest.raises(AssertionError,match='all actual SC prefix'):
        coverage.finish()
    assert not coverage.closed and coverage.groups['checked'].coverage == 0


@pytest.mark.parametrize('profile',PROFILES)
def test_completed_profile_cannot_claim_other_entry_or_direction_obligations(profile):
    coverage = Coverage(profile)
    for rule in RULES:
        coverage.record(rule,10)
    coverage.finish()
    report = coverage.groups['checked'].report()['points'][0]['counts']
    assert {name for name,count in report.items() if count} == {profile+'.'+rule for rule in RULES}


@pytest.mark.parametrize('conflicting',(False,True))
def test_SC_read_conflict_rejects_before_all_learning_and_disjoint_reads_coexist(conflicting):
    from bpuverify.bpu.model.pipeline import Outcome
    p = Program(positive=True,pc=0x40000002 if conflicting else 0x40000001)
    _,_,_,token = p.prepare()
    p.quiet()
    request = Resolution(token.history,token.pc,
        (Outcome(2,p.d,Kind.CONDITIONAL,False,mispredict=True),),origin=token)
    events = replace(p.event,prediction_ready=True,feedback=request)
    cycle = p.model.evaluate(events)
    assert cycle.fires[0] and (cycle.next_pc%2==token.pc%2) is conflicting
    names = ('micro','main','ahead','short','tage','indirect','sc')
    before = tuple(deepcopy(getattr(p.bank,name).state()) for name in names)
    if conflicting:
        with pytest.raises(AssertionError,match='conflicting prediction and feedback'):
            p.step(events)
        assert before == tuple(getattr(p.bank,name).state() for name in names)
    else:
        p.step(events)
        assert p.bank.sc.learning is not None
        assert p.bank.sc.read.pc%2 != token.pc%2


from bpuverify.bpu.model.statistical_prefix import CONTEXT_PROFILES,ContextLayout
from tests.bpu.scoreboard._statistical_joint_program import ContextProgram


@pytest.mark.parametrize('profile',CONTEXT_PROFILES)
def test_executed_nonzero_prefix_owns_five_family_learning_and_both_used_feedback_classes(profile):
    from bpuverify.sc.model.semantic import feedback_needs_read
    p=ContextProgram(profile)
    control,originals,fresh=p.setup()
    layout=p.layout
    old=p.bank.statistical_snapshot(control,resolved=True)
    source=p.bank.statistical_snapshot(fresh,resolved=True)
    slot,=[i for i,b in enumerate(source.branches) if b is not None and b.position==layout.position]
    assert old.original.history.common_valid and old.original.history.global_history==1
    assert old.original.history.backward==int(layout.backward)
    assert not old.prediction.used[slot]
    assert len({token.sequence for token in originals})==4
    assert all(p.bank.statistical_snapshot(token).read.indices==old.original.read.indices for token in originals)
    tagged=dict(p.bank.tage_snapshot(fresh,resolved=True).wanted)
    assert tagged[f'{slot}.counter']==layout.provider_counter
    assert source.prediction.used[slot] and source.prediction.directions[slot]
    assert source.prediction.sums[slot]==72
    assert all(a!=b for a,b in zip(old.original.read.weights,source.original.read.weights,strict=True))
    before=deepcopy(p.bank.sc.memory),p.bank.sc.thresholds.values
    p.controls(tage=False)
    request=p.conditional(fresh,True)
    assert feedback_needs_read(p.bank.sc_feedback(request,True)) is (not layout.agrees)
    assert before==(p.bank.sc.memory,p.bank.sc.thresholds.values)
    p.controls(tage=True)
    correct_consumer=p.query(layout.b)
    p.controls(tage=False)
    request=p.conditional(correct_consumer,False)
    assert feedback_needs_read(p.bank.sc_feedback(request,True))
    p.controls(tage=True)
    after=p.query(layout.b)
    after_source=p.bank.statistical_snapshot(after,resolved=True)
    assert after_source.prediction.sums[slot]==56
    assert all(a!=b for a,b in zip(source.original.read.weights,after_source.original.read.weights,strict=True))
    assert p.bank.statistical_snapshot(control,resolved=True) is old


@pytest.mark.parametrize('profile',CONTEXT_PROFILES)
def test_context_layout_uses_the_existing_genuine_prefix_and_zero_hash_path_edges(profile):
    from bpuverify.bpu.model.phr.model import path_hash
    p=ContextLayout(profile)
    assert bool(p.prefix_target<p.prefix+2)==p.backward
    assert path_hash(p.prefix+2,p.prefix_target)==path_hash(p.jump,p.b)==path_hash(p.b+p.position,p.d)==0


def test_context_lifetime_requires_every_scenario_obligation_and_never_awards_other_profiles():
    from bpuverify.bpu.coverage.statistical_prefix import ContextCoverage
    from bpuverify.bpu.model.statistical_prefix import CONTEXT_RULES
    for profile in CONTEXT_PROFILES:
        for missing in CONTEXT_RULES:
            coverage=ContextCoverage(profile)
            for rule in CONTEXT_RULES:
                if rule!=missing:coverage.record(rule,10)
            with pytest.raises(AssertionError):coverage.finish()
            assert coverage.groups['checked'].coverage==0
        coverage=ContextCoverage(profile)
        for rule in CONTEXT_RULES:coverage.record(rule,10)
        coverage.finish()
        counts=coverage.groups['checked'].report()['points'][0]['counts']
        assert {name for name,count in counts.items() if count}=={profile+'.'+rule for rule in CONTEXT_RULES}


from bpuverify.bpu.model.statistical_prefix import ConcurrentContextLayout,CONCURRENT_CONTEXT_PROFILES,CONCURRENT_CONTEXT_RULES


@pytest.mark.parametrize('profile',CONCURRENT_CONTEXT_PROFILES)
def test_concurrent_program_refreshes_a_neutral_anchor_without_intercepting_the_real_prefix(profile):
    from bpuverify.bpu.model.phr.model import path_hash
    layout=ConcurrentContextLayout(profile)
    assert path_hash(layout.a+layout.recovery_offset,layout.a)==0
    assert not layout.prefix_target<=layout.loop<=layout.jump
    assert (layout.loop%2==layout.b%2) is layout.same_resource


@pytest.mark.parametrize('profile',CONCURRENT_CONTEXT_PROFILES)
@pytest.mark.parametrize('feedback_class',('cold','used-correct','used-wrong'))
def test_old_nonzero_context_keeps_its_learning_identity_during_new_zero_history_predictions(profile,feedback_class):
    from bpuverify.bpu.model.pipeline import Outcome
    from bpuverify.sc.model.semantic import Context,coordinates,feedback_needs_read
    layout=ConcurrentContextLayout(profile)
    p=ContextProgram(profile,layout_type=ConcurrentContextLayout)
    _,originals,used=p.setup()
    source=originals[0] if feedback_class=='cold' else used
    snapshot=p.bank.statistical_snapshot(source,resolved=True)
    p.controls(tage=False)
    # Enable the ordinary MicroBTB source and learn a real self-loop.
    enabled=(True,*p.event.enabled[1:])
    p.event=replace(p.event,enabled=enabled)
    while p.model.control_pipe[-1]!=enabled:p.step(replace(p.event,prediction_ready=False))
    token=p.query(layout.loop)
    p.feedback(token,Outcome(4,layout.loop,Kind.DIRECT,True,mispredict=True))
    p.anchor=p.query(p.a)
    idle=p.quiet()
    p.step(replace(idle,redirect=Redirect(p.anchor.history,p.a+layout.recovery_offset,layout.loop,True,Kind.INDIRECT)))
    for _ in range(128):
        cycle=p.step()
        if (all(t is not None and t.pc==layout.loop for t in cycle.tokens) and all(cycle.fires)
                and not any(cycle.flushes) and not cycle.middle_repair and not cycle.final_repair):break
    else:raise AssertionError('no genuinely learned continuous prediction stream')
    assert p.bank.queries.value.mapping()==dict(valid=1,ghr=0,bw=0)
    taken=feedback_class!='used-wrong'
    request=Resolution(source.history,source.pc,(layout.outcome(source,snapshot.late,taken),),origin=source)
    feedback=p.bank.sc_feedback(request,True)
    needs_read=feedback_needs_read(feedback)
    assert needs_read is (feedback_class!='used-correct' or not layout.agrees)
    before=deepcopy(p.bank.sc.memory),p.bank.sc.thresholds.values
    if layout.blocks(needs_read):
        names=('micro','main','ahead','short','tage','indirect','sc')
        all_before=tuple(deepcopy(getattr(p.bank,name).state()) for name in names)
        with pytest.raises(AssertionError,match='conflicting prediction and feedback'):
            p.step(replace(p.event,feedback=request))
        assert all_before==tuple(getattr(p.bank,name).state() for name in names)
        for _ in range(2):
            cycle=p.step()
            assert cycle.fires[0] and cycle.next_pc==layout.loop
            assert before==(p.bank.sc.memory,p.bank.sc.thresholds.values)
        accepted=p.step(replace(p.event,prediction_ready=False,feedback=request))
    else:
        accepted=p.step(replace(p.event,feedback=request))
    assert bool(accepted.fires[0]) is (not layout.blocks(needs_read))
    if needs_read:
        transaction,read=p.bank.sc.learning
        assert transaction==feedback
        assert read.context==Context.from_history(snapshot.original.history)
        assert read.context.common_valid and read.context.global_history==1
        assert read.context.backward==int(layout.backward)
        assert read.indices==coordinates(source.pc,read.context)[1]
        patches,_=p.bank.sc.preview_learning()
        assert bool(patches) is (feedback_class!='used-correct')
        if patches:assert tuple(row[0] for row in patches)==tuple(range(8))
    else:
        assert p.bank.sc.learning is None
    p.quiet()
    if feedback_class=='used-correct':assert before==(p.bank.sc.memory,p.bank.sc.thresholds.values)
    p.anchor=p.query(p.a)
    enabled=(False,*p.event.enabled[1:])
    p.event=replace(p.event,enabled=enabled)
    while p.model.control_pipe[-1]!=enabled:p.step(replace(p.event,prediction_ready=False))
    p.controls(tage=True)
    fresh=p.query(layout.b)
    fresh_read=p.bank.statistical_snapshot(fresh,resolved=True).original.read
    assert fresh_read.indices==snapshot.original.read.indices
    assert p.bank.statistical_snapshot(source,resolved=True) is snapshot


def test_concurrent_context_checked_credit_requires_the_complete_behavior_not_only_a_conflict():
    from bpuverify.bpu.coverage.statistical_prefix import ConcurrentContextCoverage
    for profile in CONCURRENT_CONTEXT_PROFILES:
        for missing in CONCURRENT_CONTEXT_RULES:
            coverage=ConcurrentContextCoverage(profile)
            for rule in CONCURRENT_CONTEXT_RULES:
                if rule!=missing:coverage.record(rule,20)
            with pytest.raises(AssertionError):coverage.finish()
            assert not coverage.closed and coverage.groups['checked'].coverage==0
        coverage=ConcurrentContextCoverage(profile)
        for rule in CONCURRENT_CONTEXT_RULES:coverage.record(rule,20)
        coverage.finish()
        counts=coverage.groups['checked'].report()['points'][0]['counts']
        assert {name for name,count in counts.items() if count}=={profile+'.'+rule for rule in CONCURRENT_CONTEXT_RULES}


@pytest.mark.parametrize('fault',('payload','borrow-current-history','deny-unqualified','early-learning','duplicate-acceptance','accept-conflict'))
def test_concurrent_context_monitor_rejects_ownership_and_admission_faults(monkeypatch,fault):
    from types import SimpleNamespace
    from bpuverify.bpu.checker.statistical_prefix import ContextChecks,ConcurrentContextChecks
    from bpuverify.bpu.coverage.statistical_prefix import ConcurrentContextCoverage
    profile='forward.agree.same-resource'
    checks=ConcurrentContextChecks(profile,ConcurrentContextCoverage(profile))
    def compare(expected,actual,point):assert expected==actual,point
    checks.check=compare
    monkeypatch.setattr(ContextChecks,'checked',lambda *args:None)
    checks.pipeline=SimpleNamespace(model=SimpleNamespace(sources=SimpleNamespace(
        sc=SimpleNamespace(memory=({},)*5,thresholds=SimpleNamespace(values=(6,)*4)))))
    checks.probe=dict(before=(({},)*5,(6,)*4))
    checks.arbitration=dict(needs_read=True,blocked=0,overlap=0,payload=None,accepted=None)
    checks.cycle=SimpleNamespace(tokens=(None,)*3,fires=(True,True,True),next_pc=checks.program.loop)
    checks.training=dict(valid=True,ready=True,complete_old_source=123)
    checks.observed=dict(statistical=dict(ready=True,lookup=dict(valid=True,ghr=0,bw=0)))
    checks.events=SimpleNamespace(feedback=None)
    checks.checked(10)
    if fault=='payload':checks.training['complete_old_source']=456
    elif fault=='borrow-current-history':checks.observed['statistical']['lookup']['ghr']=1
    elif fault=='deny-unqualified':
        checks.arbitration['needs_read']=False
        checks.observed['statistical']['ready']=False
        checks.training['ready']=False
    elif fault=='early-learning':
        checks.observed['statistical']['ready']=False
        checks.training['ready']=False
        checks.bank.sc.memory=({0:(1,)},{},{},{},{})
    elif fault=='duplicate-acceptance':
        checks.arbitration['accepted']=9
        checks.events.feedback=object()
    elif fault=='accept-conflict':checks.events.feedback=object()
    with pytest.raises(AssertionError):checks.checked(12)


def numeric_actual(read,*,consumed=False):
    # Seven history tables combine into four signed family sums before bias.
    groups=((0,1),(2,3),(4,5),(6,),(7,))
    values=(tuple(tuple(sum(2*read.weights[i][column]+1 for i in group) % (256 if len(group)==2 else 128)
                  for column in range(len(read.weights[group[0]]))) for group in groups) if consumed else
            tuple(tuple(v%64 for v in weights) for weights in read.weights))
    return dict(indices=read.indices,history_valid=int(read.context.common_valid),
        banks=(1<<(read.pc%2),)*8,words=values)


@pytest.fixture(scope='module')
def numeric_context():
    p=ContextProgram('backward.disagree')
    _,originals,fresh=p.setup()
    return p,originals,fresh


@pytest.mark.parametrize('consumed',(False,True))
def test_complete_numeric_experience_matches_the_independently_owned_read(numeric_context,consumed):
    from bpuverify.bpu.checker.statistical import numeric_values
    p,_,token=numeric_context
    read=p.bank.statistical_snapshot(token).read
    expected,actual=numeric_values(p.bank,token,numeric_actual(read,consumed=consumed),consumed=consumed)
    assert expected==actual
    names=('path','global','backward','loop','bias') if consumed else ('path.0','path.1','global.2','global.3','backward.4','backward.5','loop.6','bias.7')
    assert set(names)<=expected.keys()
    assert sum(len(expected[name]) for name in names)==(64 if consumed else 88)


@pytest.mark.parametrize('consumed',(False,True))
def test_same_sign_and_same_public_decision_do_not_hide_wrong_weight_magnitude(numeric_context,consumed):
    from toffee import Scoreboard
    from bpuverify.bpu.checker.statistical import numeric_values
    from bpuverify.sc.model.semantic import decide
    p,_,token=numeric_context
    source=p.bank.statistical_snapshot(token,resolved=True)
    old=source.prediction
    column=next(i for i,value in enumerate(old.read.weights[0]) if value>0)
    changed=[list(row) for row in old.read.weights];changed[0][column]+=1
    corrupt=replace(old.read,weights=tuple(tuple(row) for row in changed))
    newer=decide(corrupt,old.branches,p.bank.sc.thresholds.values)
    assert newer.metadata()==old.metadata()  # Existing sign/use/confidence checks cannot distinguish it.
    actual=numeric_actual(corrupt,consumed=consumed)
    expected,observed=numeric_values(p.bank,token,actual,consumed=consumed)
    with pytest.raises(AssertionError,match='path'):
        Scoreboard('SC-complete-experience').check(expected=expected,actual=observed)


@pytest.mark.parametrize('consumed',(False,True))
def test_unequal_family_experience_cannot_be_swapped_even_if_the_total_is_unchanged(consumed):
    from types import SimpleNamespace as NS
    from bpuverify.bpu.checker.statistical import numeric_values
    from bpuverify.sc.model.semantic import Read,Context
    # Comparator-only pure fixture. It is never installed in a DUT oracle.
    weights=tuple(tuple(value+i for i in range(8)) for value in (1,5,9,-8,-4,0,4))+(tuple(range(-16,16)),)
    read=Read(0x40010000,Context(),tuple(range(1,9)),weights)
    bank=NS(statistical_snapshot=lambda token:NS(read=read));token=NS(pc=read.pc)
    actual=numeric_actual(read,consumed=consumed)
    swapped=list(actual['words']);other=1 if consumed else 2;swapped[0],swapped[other]=swapped[other],swapped[0]
    assert sum(map(sum,swapped))==sum(map(sum,actual['words']))
    actual['words']=tuple(swapped)
    expected,observed=numeric_values(bank,token,actual,consumed=consumed)
    assert expected!=observed


def test_invalid_history_ignores_old_raw_ports_but_requires_actual_zeroed_consumption(numeric_context):
    from types import SimpleNamespace as NS
    from bpuverify.bpu.checker.statistical import numeric_values
    from bpuverify.sc.model.semantic import Read,Context
    p,_,token=numeric_context
    original=p.bank.statistical_snapshot(token).read
    weights=list(original.weights);weights[2:6]=((0,)*8,)*4
    read=replace(original,context=replace(original.context,common_valid=False),weights=tuple(weights))
    bank=NS(statistical_snapshot=lambda token:NS(read=read))
    actual=numeric_actual(read)
    stale=list(actual['words']);stale[2]=(63,)*8;stale[4]=(31,)*8
    actual['words']=tuple(stale)
    expected,observed=numeric_values(bank,token,actual)
    assert expected==observed and 'global' not in expected and 'backward' not in expected
    actual=numeric_actual(read,consumed=True)
    expected,observed=numeric_values(bank,token,actual,consumed=True)
    assert expected==observed and expected['global']==expected['backward']==(2,)*8
    stale=list(actual['words']);stale[1]=(9,)*8
    actual['words']=tuple(stale)
    assert numeric_values(bank,token,actual,consumed=True)[0]!=numeric_values(bank,token,actual,consumed=True)[1]


def invalid_history_evidence_fixture(*,valid=False,nonzero=True):
    """Comparator-only fixture; never installed into a DUT reference."""
    from types import SimpleNamespace as NS
    from bpuverify.sc.model.semantic import Read,Context
    from bpuverify.bpu.checker.statistical import InvalidHistoryEvidence
    read=Read(0x40010000,Context(common_valid=valid),tuple(range(1,9)),
        ((0,)*8,)*7+((0,)*32,))
    token=NS(sequence=11,pc=read.pc,history=NS(sequence=7))
    def snapshot(original):
        if original is not token:raise ValueError('foreign original cannot supply a masking witness')
        return NS(read=read)
    sources=NS(statistical_snapshot=snapshot,read_enabled={7:True})
    enabled=(False,False,True,False,True,False,False)
    previous=NS(enabled=enabled,fires=(True,False,False,False),flushes=(False,)*3)
    pipeline=NS(model=NS(sources=sources,stages=(token,None,None)),sc_previous_cycle=None,sc_numeric_checked={7:{'read':2}})
    cycle=NS(tokens=(token,None,None),fires=(True,False,False,False))
    raw=numeric_actual(read)
    words=list(raw['words']);words[2]=(63,0,2,0,0,0,0,0) if nonzero else (0,)*8
    words[4]=(0,31,0,0,0,0,0,0) if nonzero else (0,)*8;raw['words']=tuple(words)
    actual=dict(prediction_requests=(True,True,valid,valid,valid,valid,True,True),
        prediction_read=raw,prediction_evidence=numeric_actual(read,consumed=True))
    def check(expected,observed,point):assert expected==observed,point
    witness=InvalidHistoryEvidence()
    witness.begin_window(-2)
    witness.observe(pipeline,cycle,actual,0,check)
    pipeline.sc_previous_cycle=previous
    cycle.fires=(False,False,False,False)
    return witness,pipeline,cycle,token,actual,check


@pytest.mark.parametrize('valid,nonzero',((False,True),(False,False),(True,True),(True,False)))
def test_invalid_history_credit_requires_nonzero_raw_and_same_query_neutral_consumption(valid,nonzero):
    witness,pipeline,cycle,token,actual,check=invalid_history_evidence_fixture(valid=valid,nonzero=nonzero)
    witness.observe(pipeline,cycle,actual,2,check)
    assert not witness.witnesses  # A raw-port observation alone proves nothing.
    pipeline.sc_previous_cycle.fires=(False,True,False,False)
    pipeline.sc_numeric_checked[7]['consume']=4
    cycle.tokens=(None,token,None)
    witness.observe(pipeline,cycle,actual,4,check)
    assert set(witness.witnesses)==({'global','backward'} if nonzero and not valid else set())
    for family,value in witness.witnesses.items():
        assert value['owner']==token.sequence and value['read_tick']==2 and value['consumed_tick']==4
        assert any(value['raw_weights']) and value['consumed_percsum']==(2,)*8
    assert pipeline.model.sources.statistical_snapshot(token).read.weights[2:6]==((0,)*8,)*4


@pytest.mark.parametrize('fault',('missing-read','missing-consume','wrong-read-boundary',
    'same-boundary','foreign-original','leaked-global','leaked-backward',
    'missing-issued-request','unexpected-history-request'))
def test_invalid_history_witness_rejects_missing_or_borrowed_proof_and_nonzero_consumption(fault):
    from types import SimpleNamespace as NS
    witness,pipeline,cycle,token,actual,check=invalid_history_evidence_fixture()
    if fault=='missing-read':
        pipeline.sc_numeric_checked[7].clear()
        with pytest.raises(AssertionError):witness.observe(pipeline,cycle,actual,2,check)
        return
    if fault in ('missing-issued-request','unexpected-history-request'):
        if fault=='missing-issued-request':witness.requests.clear()
        else:
            owner,tick,valids=witness.requests[7]
            witness.requests[7]=(owner,tick,(True,)*8)
        with pytest.raises(AssertionError):witness.observe(pipeline,cycle,actual,2,check)
        assert not witness.witnesses
        return
    witness.observe(pipeline,cycle,actual,2,check)
    pipeline.sc_previous_cycle.fires=(False,True,False,False)
    pipeline.sc_numeric_checked[7]['consume']=4
    cycle.tokens=(None,token,None)
    tick=4
    if fault=='missing-consume':del pipeline.sc_numeric_checked[7]['consume']
    elif fault=='wrong-read-boundary':pipeline.sc_numeric_checked[7]['read']=0
    elif fault=='same-boundary':
        tick=2;pipeline.sc_numeric_checked[7]['consume']=2
    elif fault=='foreign-original':cycle.tokens=(None,NS(**vars(token)),None)
    else:
        words=list(actual['prediction_evidence']['words'])
        words[1 if fault=='leaked-global' else 2]=(3,2,2,2,2,2,2,2)
        actual['prediction_evidence']['words']=tuple(words)
    with pytest.raises((AssertionError,ValueError)):
        witness.observe(pipeline,cycle,actual,tick,check)
    assert not witness.witnesses


def test_unarmed_or_pre_warm_response_cannot_grant_invalid_history_credit():
    from bpuverify.bpu.checker.statistical import InvalidHistoryEvidence
    _,pipeline,cycle,token,actual,check=invalid_history_evidence_fixture()
    witness=InvalidHistoryEvidence()
    witness.observe(pipeline,cycle,actual,2,check)
    assert not witness.requests and not witness.pending and not witness.witnesses
    witness.begin_window(4)
    witness.observe(pipeline,cycle,actual,2,check)
    assert not witness.requests and not witness.pending and not witness.witnesses


@pytest.mark.parametrize('main,sc,issue,valid,wanted',(
    (True,True,True,False,(True,True,False,False,False,False,True,True)),
    (True,True,True,True,(True,)*8),
    (False,True,True,True,(False,)*8),
    (True,False,True,True,(False,)*8),
    (True,True,False,True,(False,)*8)))
def test_actual_prediction_read_gates_depend_on_owned_history_and_qualified_issue(main,sc,issue,valid,wanted):
    from types import SimpleNamespace as NS
    from bpuverify.bpu.checker.statistical import live_values
    state=dict(valid=valid,ghr=0,bw=0)
    sources=NS(preview_history=lambda *args:NS(lookup=NS(valid=valid,mapping=lambda:state),iteration=NS(after=0)),
        queries=NS(value=NS(mapping=lambda:state),iterations=NS(cursor=0)),
        sc=NS(preview_learning=lambda:((),(6,)*4)))
    cycle=NS(enabled=(False,False,main,False,sc,False,False),fires=(issue,False,False,False))
    actual=dict(state=state,lookup=state,loop_state=0,loop_lookup=0,thresholds=(6,)*4,
        prediction_requests=wanted,updates=())
    expected,observed=live_values(sources,None,cycle,actual)
    assert expected==observed and expected['prediction_requests']==wanted
    actual['prediction_requests']=tuple(not value for value in wanted)
    assert live_values(sources,None,cycle,actual)[0]!=live_values(sources,None,cycle,actual)[1]


@pytest.mark.parametrize('profile',(*CONTEXT_PROFILES,*CONCURRENT_CONTEXT_PROFILES))
def test_cancelled_nonzero_query_then_invalid_consumer_preserves_all_learned_experience(profile):
    from bpuverify.bpu.model.statistical_prefix import ConcurrentContextLayout
    p=ContextProgram(profile,layout_type=None if profile in CONTEXT_PROFILES else ConcurrentContextLayout)
    _,_,source=p.setup()
    p.controls(tage=False)
    p.conditional(source,False)
    p.controls(tage=True)
    source=p.query(p.b)
    before=deepcopy(p.bank.sc.memory),p.bank.sc.thresholds.values
    original=p.bank.statistical_snapshot(source)
    warm,invalid=p.probe_invalid_history(source)
    now=p.bank.statistical_snapshot(invalid).read
    assert warm.sequence<invalid.sequence and not now.context.common_valid
    assert now.weights[2:6]==((0,)*8,)*4
    assert before==(p.bank.sc.memory,p.bank.sc.thresholds.values)
    assert p.bank.statistical_snapshot(source) is original


@pytest.mark.parametrize('width,raw,wanted',((6,0,0),(6,31,31),(6,32,-32),(6,63,-1),
    (7,0,0),(7,63,63),(7,64,-64),(7,127,-1)))
def test_numeric_readback_uses_the_declared_signed_width(width,raw,wanted):
    from bpuverify.bpu.checker.statistical import signed_value
    assert signed_value(raw,width)==wanted
    with pytest.raises(ValueError):signed_value(1<<width,width)


@pytest.mark.parametrize('read_fire,consume_fire,flushed,enabled,wanted',(
    (True,True,False,True,{'read','consume'}),(False,False,False,True,set()),
    (False,True,False,True,{'consume'}),(True,True,True,True,{'read'}),
    (True,True,False,False,set())))
def test_numeric_responses_follow_independent_issue_and_consumption_not_held_port_data(
        numeric_context,read_fire,consume_fire,flushed,enabled,wanted):
    from types import SimpleNamespace as NS
    from bpuverify.bpu.checker.statistical import numeric_origins
    p,originals,token=numeric_context
    previous=NS(enabled=(False,False,True,False,enabled,False,False),
        fires=(read_fire,consume_fire,False,False),flushes=(flushed,False,False))
    cycle=NS(tokens=(token,originals[0],None))
    assert numeric_origins(p.bank,cycle,None)=={}
    assert set(numeric_origins(p.bank,cycle,previous))==wanted


@pytest.mark.parametrize('consumed',(False,True))
def test_numeric_readback_rejects_foreign_original_not_just_an_equal_PC(numeric_context,consumed):
    from bpuverify.bpu.checker.statistical import numeric_values
    p,_,token=numeric_context
    foreign=replace(token,history=replace(token.history))
    with pytest.raises(ValueError,match='owner|original|absent'):
        numeric_values(p.bank,foreign,{},consumed=consumed)


def test_reset_cannot_reuse_pre_reset_numeric_source_credit():
    from types import SimpleNamespace as NS
    from bpuverify.bpu.checker.pipeline import PipelineChecker
    from bpuverify.bpu.model.statistical_joint_sources import StatisticalJointSources
    checker=PipelineChecker(sources=StatisticalJointSources())
    checker.sc_previous_cycle=object();checker.sc_numeric_checked[1]={'read':2,'consume':4}
    checker.capture(dict(inputs=dict(reset=True,training=dict(valid=0,ready=0),redirect=dict(valid=0),
        reset_vector=0x40000000,prediction_ready=0,metadata_ready=0,initialization=(0,)*7,
        enabled=(False,)*7,consumed_reset=True)),NS(tick=2))
    checker.raise_failure()
    assert checker.sc_previous_cycle is None and checker.sc_numeric_checked=={}


@pytest.mark.parametrize('kind',('prefix','nonzero-context'))
@pytest.mark.parametrize('fault',('missing-read','missing-consumption','reversed-boundaries','missing-composition','wrong-composition-boundary'))
def test_missing_numeric_evidence_raises_before_any_checked_credit(kind,fault):
    from types import SimpleNamespace as NS
    from toffee import Scoreboard
    from bpuverify.bpu.checker.statistical_prefix import Checks,ContextChecks
    from bpuverify.bpu.coverage.statistical_prefix import Coverage,ContextCoverage
    from bpuverify.bpu.model.statistical_prefix import RULES,CONTEXT_RULES
    if kind=='prefix':
        profile='conditional-entry.condition-taken'
        coverage=Coverage(profile);checks=Checks(profile,coverage);rules=RULES
    else:
        profile='forward.agree'
        coverage=ContextCoverage(profile);checks=ContextChecks(profile,coverage);rules=CONTEXT_RULES
        checks.receipts=[dict(label=label) for label in (
            'teaching-0','teaching-1','teaching-2','teaching-3','used-correct','used-wrong')]
        checks.context_offers=[None]*5;checks.context_reads=[None]*5
        checks.originals=tuple(object() for _ in range(4))
    flags={'read':2,'consume':4,'composition':4}
    if fault=='missing-read':del flags['read']
    elif fault=='missing-consumption':del flags['consume']
    elif fault=='reversed-boundaries':flags={'read':4,'consume':2,'composition':2}
    elif fault=='missing-composition':del flags['composition']
    else:flags['composition']=6
    fresh=object()
    token=lambda source:NS(sequence=id(source),history=NS(sequence=id(source)))
    checks.save=token
    checks.pipeline=NS(raise_failure=lambda:None,last_tick=6,board=Scoreboard('numeric-credit-guard'),
        counts={},sc_numeric_checked={id(fresh):flags})
    # Every old requirement is already present: only the new evidence fails.
    for rule in rules:coverage.record(rule,1)
    with pytest.raises(AssertionError,match='numeric read|precedes|composition'):
        checks.finish(fresh) if kind=='prefix' else checks.finish_context((fresh,))
    assert not coverage.closed and coverage.groups['checked'].coverage==0
