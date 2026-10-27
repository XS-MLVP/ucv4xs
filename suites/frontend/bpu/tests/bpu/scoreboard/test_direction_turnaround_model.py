"""Normal owned-event programs; no DUT state, signals or coverage credit."""
from copy import deepcopy
from dataclasses import replace

import pytest

from bpuverify.bpu.model.pipeline import Redirect
from bpuverify.bpu.model.tage.asymmetric_retirement import OUTCOMES, PRELUDE_PLAN
from bpuverify.bpu.model.tage.direction_turnaround import PROGRAMS,preparation,CAPTURES
from bpuverify.bpu.model.tage.mixed_visibility import PARTIAL_PLAN
from bpuverify.bpu.model.tage.neighbor_migration import PC, HISTORY_PATHS
from bpuverify.bpu.model.tage.service import STREAM_PC, learning_inflight, pending_plan
from tests.bpu.scoreboard.test_asymmetric_retirement_model import ThreeOriginalSources,concrete_plan
from tests.bpu.scoreboard.test_neighbor_migration import fixture
from tests.bpu.scoreboard.test_direction_forwarding import resolution
from tests.bpu.scoreboard.test_direction_service import via, streaming_query
from tests.bpu.scoreboard.test_direction_sources import quiet
from tests.bpu.scoreboard.test_dual_migration import source
from tests.bpu.scoreboard.test_mixed_visibility_model import consumers, mature


class TurnaroundSetup(ThreeOriginalSources):
    capture_roles=CAPTURES
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.intents=tuple(preparation());self.extra={}
    def retain_prepared(self,role,receipt):self.extra[role]=receipt.token


def prepared_program(initial_pc=None,checks_type=TurnaroundSetup,coverage_type=None):
    options={} if coverage_type is None else dict(coverage_type=coverage_type)
    checks,(model,event,anchor),retired=fixture(initial_pc=initial_pc,checks_type=checks_type,**options)
    warm=via(model,event,anchor,HISTORY_PATHS['original'])
    model.advance(replace(quiet(model,event),feedback=resolution(warm,OUTCOMES[1])))
    quiet(model,event)
    target=via(model,event,anchor,HISTORY_PATHS['original'])
    neighbor=via(model,event,anchor,HISTORY_PATHS['neighbor'])
    inputs=(checks.sources[0].token,neighbor,target,checks.sources[1].token,checks.sources[2].token)
    return checks,model,event,anchor,inputs,retired


def partial_program(program, initial_pc=None):
    checks, model, event, anchor, inputs,_ = prepared_program(initial_pc)
    model.advance(replace(quiet(model, event), redirect=Redirect(anchor.history, anchor.pc+4, STREAM_PC, True)))
    for _ in range(8): model.advance(event)
    before = model.sources.tage.commits
    for token, outcome in zip(inputs[:3], OUTCOMES[:3], strict=True):
        model.advance(replace(event, feedback=resolution(token, outcome)))
    mature(model, event)
    assert pending_plan(model.sources.tage, 7, PC%4) == concrete_plan(checks, model, inputs, PRELUDE_PLAN)
    consumers(checks, model, event, anchor, program, 'initial')
    model.advance(replace(event, prediction_ready=False))
    for _ in range(8): model.advance(event)
    assert model.sources.tage.commits == before+2
    mixed = consumers(checks, model, event, anchor, program, 'mixed')
    saved = dict(checks.extra,**{'old-target': inputs[3], 'mixed-target': mixed['original']})
    return checks, model, event, anchor, inputs, saved, before


@pytest.mark.parametrize('initial_pc', (None, PC+0x40), ids=('normal-boot', 'different-owned-boot'))
@pytest.mark.parametrize('program', PROGRAMS, ids=lambda p: p.name)
def test_reversed_outcomes_use_each_current_version_and_preserve_all_unrelated_histories(program, initial_pc):
    checks, model, event, anchor, inputs, saved, before = partial_program(program, initial_pc)
    late = tuple(saved[name] for name in program.late_sources)
    assert len({id(t.history) for t in (*inputs[:3], *late)}) == 3+len(late)
    frozen = tuple(deepcopy(model.sources.defined_metadata(t)) for t in late)
    offered = []
    previous = concrete_plan(checks, model, inputs, PARTIAL_PLAN)
    commits = model.sources.tage.commits
    for tick in range(16):
        request = resolution(late[tick], program.late_outcomes[tick]) if tick<len(late) else None
        if request is not None:
            assert not model.sources.feedback_for(request).reread
            predicted = model.sources.snapshot(request.origin, resolved=True).late.branch
            actual = next((b.position for b in request.branches if b is not None and b.taken), None)
            old = predicted.position if predicted.taken else None
            last=max(b.position for b in request.branches if b is not None)
            wrong = None if old==actual or actual is None and old is not None and old>last else min(p for p in (old, actual) if p is not None)
            assert tuple(b.position for b in request.branches if b is not None and b.mispredict)==(() if wrong is None else (wrong,))
        model.advance(replace(event, feedback=request))
        new = pending_plan(model.sources.tage, 7, PC%4)
        if new != previous:
            assert new == concrete_plan(checks, model, inputs, program.pending_after[len(offered)-1])
            previous = new
        proposals = model.sources.tage.offers.get((7, PC%4), ())
        if proposals:
            payload = [None, None]
            for write in proposals:
                payload[write.way] = dict(row=write.row, valid=int(write.entry.valid),
                    tag=write.entry.tag, counter=write.entry.counter)
            expected = tuple(None if p is None else dict(concrete_plan(checks, model, inputs, ((p,), ()))[0][0])
                for p in program.late_proposals[len(offered)])
            assert tuple(payload)==expected
            offered.append(tuple(payload))
        if tick>=len(late) and not learning_inflight(model.sources.tage): break
    else: raise AssertionError('independent reversal learning did not mature')
    assert len(offered)==len(late)
    assert model.sources.tage.commits==commits==before+2
    assert pending_plan(model.sources.tage, 7, PC%4)==concrete_plan(checks, model, inputs, program.final_plan)
    consumers(checks, model, event, anchor, program, 'blocked')
    quiet(model, event)
    assert model.sources.tage.commits-before==2+sum(map(len, program.final_plan))
    for name,path in HISTORY_PATHS.items():
        assert checks.profile(source(model, via(model,event,anchor,path), 62000))==program.profile('serviced', name)
    assert tuple(model.sources.defined_metadata(t) for t in late)==frozen


@pytest.mark.parametrize('program', PROGRAMS, ids=lambda p: p.name)
def test_reviewed_reversal_programs_have_complete_source_outcome_and_service_contracts(program):
    assert len(set(program.late_sources))==len(program.late_sources)
    assert len(program.late_sources)==len(program.late_outcomes)==len(program.late_proposals)==len(program.pending_after)
    assert all(any(p is not None for p in pair) for pair in program.late_proposals)
    for outcome in program.late_outcomes:
        assert not any(bad for _,_,bad in outcome)
        assert not any(taken for _,taken,_ in outcome[:-1])


@pytest.mark.parametrize('phase,name', (('entire-history-serviced','original'), ('mixed','physical-rank-2')))
def test_unreviewed_physical_or_visibility_labels_do_not_add_functional_bins(phase,name):
    with pytest.raises(ValueError,match='undeclared'):
        PROGRAMS[0].profile(phase,name)
