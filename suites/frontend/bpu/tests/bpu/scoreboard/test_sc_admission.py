"""Independent semantics and observation boundaries; no hardware credit."""
from copy import deepcopy
from dataclasses import replace
import pytest

from suites.frontend.bpu.bpu.checker.pipeline import environment
from suites.frontend.bpu.bpu.checker.statistical import readiness
from suites.frontend.bpu.bpu.coverage.sc_admission import Coverage,BurstCoverage,ReadOnlyCoverage
from suites.frontend.bpu.bpu.model.pipeline import Outcome,Resolution
from suites.frontend.bpu.bpu.model.sc_admission import Program as Layout,PROFILES,RULES,BurstProgram,BURST_PROFILES,BURST_RULES,READ_ONLY_PROFILES
from suites.frontend.bpu.bpu.model.selection import Kind
from suites.frontend.bpu.bpu.model.statistical_prefix import conditional_outcomes
from tests.bpu.scoreboard._statistical_joint_program import Program
from tests.bpu.scoreboard.test_semantic_pipeline import boot,published,OFF
from suites.frontend.bpu.sc.model.semantic import feedback_needs_read
from suites.frontend.bpu.bpu.model.sc_admission import ContextBurstLayout,CONTEXT_BURST_PROFILES,CONTEXT_BURST_RULES
from suites.frontend.bpu.bpu.coverage.sc_admission import ContextBurstCoverage
from tests.bpu.scoreboard._statistical_joint_program import ContextBurstProgram


@pytest.mark.parametrize('profile',CONTEXT_BURST_PROFILES)
def test_distinct_nonzero_old_contexts_keep_qualification_across_adjacent_feedbacks(profile):
    from suites.frontend.bpu.sc.model.semantic import Context,decide
    from suites.frontend.bpu.bpu.model.pipeline import Redirect
    p=ContextBurstProgram(profile)
    originals,controls=p.setup()
    layout=p.layout
    expected_contexts=tuple(layout.capture_contexts[i] for i in layout.arrival_order)
    saved=tuple(p.bank.statistical_snapshot(t,resolved=True) for t in originals)
    for token,context,old in zip(originals,expected_contexts,saved,strict=True):
        history=p.bank.queries.snapshot(token).read
        assert (history.valid,history.ghr,history.bw)==(True,*layout.history(context))
        assert old.original.history.common_valid
    p.controls(tage=False,micro=True)
    p.anchor=p.query(p.a)
    idle=p.quiet()
    p.step(replace(idle,redirect=Redirect(p.anchor.history,p.a,layout.loop,True,Kind.INDIRECT)))
    for _ in range(128):
        cycle=p.step()
        if all(t is not None and t.pc==layout.loop for t in cycle.tokens) and all(cycle.fires) and not any(cycle.flushes):break
    else:raise AssertionError('no actual independent prediction stream in the reference program')
    reads,offers=[],[]
    for index,(token,old,truth) in enumerate(zip(originals,saved,layout.truths,strict=True)):
        request=Resolution(token.history,token.pc,(layout.outcome(token,old.late,truth),),origin=token)
        transaction=p.bank.sc_feedback(request,True)
        need=feedback_needs_read(transaction)
        assert need==(not truth or not layout.agrees)
        slot,_,_=p.provider(token)
        if truth:
            current=decide(p.bank.sc.snapshot(token.pc,Context.from_history(old.original.history)),
                           old.prediction.branches,p.bank.sc.thresholds.values)
            assert old.prediction.above[slot] and not current.above[slot]
        if layout.blocked and index==0:
            before=deepcopy(p.bank.sc.state())
            with pytest.raises(AssertionError,match='conflicting'):
                p.step(replace(p.event,feedback=request))
            assert p.bank.sc.state()==before
        cycle=p.step(replace(p.event,prediction_ready=not layout.blocked,feedback=request))
        assert bool(cycle.fires[0]) is (not layout.blocked)
        if need:
            actual,read=p.bank.sc.learning
            assert actual==transaction and read.context==Context.from_history(old.original.history)
            reads.append(token.sequence)
            patches,_=p.bank.sc.preview_learning()
            if truth:assert not patches
            else:
                # Independent signed patch arithmetic from the newly owned
                # committed read, not the old prediction's weight snapshot.
                column=(layout.position%8)^(layout.position//8)
                expected=[]
                for table,weights in enumerate(read.weights):
                    selected=column if table!=7 else 4*column+int(layout.agrees)
                    patch=tuple(max(-32,weight-1) if i==selected else None for i,weight in enumerate(weights))
                    expected.append((table,token.pc%2,read.indices[table],patch))
                assert patches==tuple(expected)
                offers.append(token.sequence)
    p.quiet()
    assert len(reads)==(8 if layout.agrees else 10) and len(offers)==8
    p.return_from_stream()
    fresh=tuple(p.query_context(context) for context in layout.contexts)
    for token,context in zip(fresh,layout.contexts,strict=True):
        old=saved[expected_contexts.index(context)]
        now=p.bank.statistical_snapshot(token,resolved=True)
        before=p.bank.statistical_snapshot(controls[layout.contexts.index(context)],resolved=True)
        assert now.original.read.indices==old.original.read.indices
        assert now.original.read.indices==before.original.read.indices
        assert all(a!=b for a,b in zip(now.original.read.weights,before.original.read.weights,strict=True))
        assert all(a!=b for a,b in zip(now.original.read.weights,old.original.read.weights,strict=True))
    assert all(p.bank.statistical_snapshot(t,resolved=True) is old for t,old in zip(originals,saved,strict=True))


@pytest.mark.parametrize('missing',CONTEXT_BURST_RULES)
def test_distinct_context_burst_requires_every_lifetime_obligation(missing):
    for profile in CONTEXT_BURST_PROFILES:
        coverage=ContextBurstCoverage(profile)
        for rule in CONTEXT_BURST_RULES:
            if rule!=missing:coverage.record(rule,20)
        with pytest.raises(AssertionError):coverage.finish()
        assert coverage.groups['checked'].coverage==0 and not coverage.closed


@pytest.mark.parametrize('bad_direction',(0,1,None,'not-taken'))
def test_recovery_driver_requires_a_semantic_direction_before_accessing_the_dut(bad_direction):
    import asyncio
    from suites.frontend.bpu.bpu.driver.recovery import RecoveryDriver
    with pytest.raises(ValueError,match='semantic bool'):
        asyncio.run(RecoveryDriver(None,None).send(None,taken=bad_direction))


@pytest.mark.parametrize('profile',(*PROFILES,*READ_ONLY_PROFILES))
def test_original_eligibility_and_resource_relation_predict_the_actual_learning(profile):
    layout = Layout(profile)
    p = Program(positive=layout.positive,early=True)
    if layout.read_only:
        p.prepare_branch(p.b,target_branch=True)
        p.prepare_branch(p.x,target_branch=False)
        p.controls(sc=True)
        teaching = tuple(p.query(p.x) for _ in range(5 if p.positive else 6))
        for original in teaching:
            p.conditional(original,p.positive)
        p.controls(sc=False)
        p.conditional(p.query(p.b),not p.positive)
        p.controls(sc=True)
        source = p.query(p.b)
    else:
        _,_,_,source = p.prepare()
    p.quiet()
    enabled = list(p.event.enabled)
    enabled[0] = True
    p.event = replace(p.event,enabled=tuple(enabled))
    while p.model.control_pipe[-1]!=p.event.enabled:
        p.step(replace(p.event,prediction_ready=False))
    p.quiet()
    p.feedback(p.query(layout.loop),Outcome(4,layout.loop,Kind.DIRECT,True,mispredict=True))
    p.query(layout.loop)
    for _ in range(4):
        p.step()
    original = p.bank.statistical_snapshot(source,resolved=True)
    request = Resolution(source.history,source.pc,
        conditional_outcomes(source,original.late,layout,layout.actual_taken),origin=source)
    cycle = p.model.evaluate(p.event)
    assert readiness(p.bank,cycle,request)==(not layout.blocked)
    before = deepcopy(p.bank.sc.memory),p.bank.sc.thresholds.values
    if layout.blocked:
        with pytest.raises(AssertionError,match='conflicting'):
            p.step(replace(p.event,feedback=request))
        assert before==(p.bank.sc.memory,p.bank.sc.thresholds.values)
    p.step(replace(p.event,prediction_ready=not layout.blocked,feedback=request))
    p.quiet()
    fresh = p.query(p.b)
    new = p.bank.statistical_snapshot(fresh,resolved=True)
    assert new.prediction.read.indices==original.prediction.read.indices
    assert (new.prediction.read.weights!=original.prediction.read.weights)==layout.needs_write
    assert (p.bank.sc.thresholds.values!=before[1])==layout.needs_write
    if layout.read_only:
        transaction = p.bank.sc_feedback(request,True)
        slot, = [i for i,used in enumerate(original.prediction.used) if used]
        assert transaction.meta['tagePred'][slot]!=transaction.meta['scPred'][slot]
        assert transaction.meta['scPred'][slot]==int(layout.actual_taken)
        assert before==(p.bank.sc.memory,p.bank.sc.thresholds.values)


@pytest.mark.parametrize('accepted,live_ready',((False,True),(True,False),(True,True),(False,False)))
def test_preedge_handshake_not_later_ready_level_owns_the_feedback(accepted,live_ready):
    model,event = boot()
    source = published(model,event)
    row = dict(reset=False,commit_valid=False,reset_vector=source.pc,prediction_ready=False,
        metadata_ready=True,initialization=(True,)*6,enabled=OFF,redirect=dict(valid=False),
        training_accepted=accepted,training=dict(valid=True,ready=live_ready,pc=source.pc,
            history=source.history.metadata(),branches=(dict(valid=True,position=4,target=source.pc,
                kind=int(Kind.DIRECT),taken=True,action=0,mispredict=False),)))
    result = environment(row,model,origin=source)
    assert (result.feedback is not None)==accepted
    if accepted:
        assert result.feedback.origin is source


@pytest.mark.parametrize('missing',RULES)
def test_missing_actual_admission_obligation_cannot_grant_checked_credit(missing):
    coverage = Coverage(PROFILES[0])
    for rule in RULES:
        if rule!=missing:
            coverage.record(rule,10)
    with pytest.raises(AssertionError):
        coverage.finish()
    assert not coverage.closed and coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('profile',BURST_PROFILES)
def test_three_originals_keep_individual_qualifications_and_cycle_learning(profile):
    layout = BurstProgram(profile)
    p = Program(positive=layout.positive,early=True)
    *_,first = p.prepare()
    sources = first,p.query(p.x),p.query(p.b)
    old = tuple(p.bank.statistical_snapshot(source,resolved=True) for source in sources)
    assert tuple(source.pc for source in sources)==layout.source_pcs
    assert len({source.sequence for source in sources})==3
    assert tuple(int(any(value.prediction.used)) for value in old)==(1,0,1)
    requests = tuple(Resolution(source.history,source.pc,
        conditional_outcomes(source,value.late,layout,truth),origin=source)
        for source,value,truth in zip(sources,old,layout.truths,strict=True))
    assert all(feedback_needs_read(p.bank.sc_feedback(request,True)) for request in requests)
    assert requests[0].branches!=requests[1].branches
    enabled = list(p.event.enabled)
    enabled[0] = True
    p.event = replace(p.event,enabled=tuple(enabled))
    while p.model.control_pipe[-1]!=p.event.enabled:
        p.step(replace(p.event,prediction_ready=False))
    p.quiet()
    p.feedback(p.query(layout.loop),Outcome(4,layout.loop,Kind.DIRECT,True,mispredict=True))
    p.query(layout.loop)
    for _ in range(4):
        p.step()
    assert readiness(p.bank,p.model.evaluate(p.event),requests[0])==(not layout.blocked)
    before = deepcopy(p.bank.sc.memory),p.bank.sc.thresholds.values
    if layout.blocked:
        with pytest.raises(AssertionError,match='conflicting'):
            p.step(replace(p.event,feedback=requests[0]))
        assert before==(p.bank.sc.memory,p.bank.sc.thresholds.values)
    beats = []
    for request in requests:
        p.step(replace(p.event,prediction_ready=not layout.blocked,feedback=request))
        patches,_ = p.bank.sc.preview_learning()
        assert patches
        beats.append(patches)
    assert len(beats)==3
    p.quiet()
    for source,value in zip((p.query(p.b),p.query(p.x)),old[:2],strict=True):
        fresh = p.bank.statistical_snapshot(source,resolved=True)
        assert fresh.prediction.read.indices==value.prediction.read.indices
        assert fresh.prediction.read.weights!=value.prediction.read.weights
    assert old==tuple(p.bank.statistical_snapshot(source,resolved=True) for source in sources)


@pytest.mark.parametrize('missing',BURST_RULES)
def test_missing_burst_obligation_cannot_grant_successful_hardware_credit(missing):
    coverage = BurstCoverage(BURST_PROFILES[0])
    for rule in BURST_RULES:
        if rule!=missing:
            coverage.record(rule,10)
    with pytest.raises(AssertionError):
        coverage.finish()
    assert coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('missing',RULES)
def test_read_without_write_still_requires_every_actual_admission_and_consumer(missing):
    coverage = ReadOnlyCoverage(READ_ONLY_PROFILES[0])
    for rule in RULES:
        if rule!=missing:
            coverage.record(rule,10)
    with pytest.raises(AssertionError):
        coverage.finish()
    assert coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('fault',('extra-global-read','missing-path-read','wrong-bank'))
def test_actual_read_identity_cannot_be_inferred_from_acceptance_alone(fault):
    from types import SimpleNamespace as NS
    from suites.frontend.bpu.bpu.checker.sc_admission import Checks
    from suites.frontend.bpu.sc.model.semantic import Context,coordinates
    layout = Layout(PROFILES[0])
    p = Program(positive=True,early=True)
    *_,source = p.prepare()
    value = p.bank.statistical_snapshot(source,resolved=True)
    request = Resolution(source.history,source.pc,conditional_outcomes(source,value.late,layout,False),origin=source)
    feedback = p.bank.sc_feedback(request,True)
    bank,indices = coordinates(feedback.pc,Context.from_history(feedback.history))
    ports = [dict(valid=int(i in (0,1,6,7)),bank=1<<bank,index=index) for i,index in enumerate(indices)]
    if fault=='extra-global-read':ports[2]['valid']=1
    elif fault=='missing-path-read':ports[0]['valid']=0
    else:ports[0]['bank']=2
    checks = object.__new__(Checks)
    checks.pipeline = NS(model=NS(sources=p.bank))
    checks.events,checks.observed,checks.read_receipts = NS(feedback=request),dict(statistical=dict(accepted_reads=ports)),[]
    def compare(expected,actual,point):
        if expected!=actual:raise AssertionError(point)
    checks.check = compare
    with pytest.raises(AssertionError,match='actual'):
        checks.compare_reads(10)
    assert not checks.read_receipts
