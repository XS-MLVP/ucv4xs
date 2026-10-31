"""Algorithm-only workload qualification; never native or hardware credit."""
from dataclasses import replace
import pytest

from suites.frontend.bpu.utage.model.predecessor_retention import Program,PROFILES,MODES,PHASES,RULES
from suites.frontend.bpu.utage.model.semantic import Context,indices,tag,UtageReference,Events,Base
from suites.frontend.bpu.utage.coverage.predecessor_retention import Coverage
from suites.frontend.bpu.utage.model.learning_persistence import Program as Original,PC
from suites.frontend.bpu.utage.model.usefulness_events import ProtectionState
from suites.frontend.bpu.utage.model.working_set import expected
from tests.utage.scoreboard.test_semantic_model import feedback,learn

PROGRAMS = tuple(Program(p,m,t) for p in PROFILES for m in MODES for t in (False,True))


@pytest.mark.parametrize('p',PROGRAMS,ids=lambda p:p.label)
def test_code_predecessors_and_matching_branch_have_distinct_complete_ancestors(p):
    assert len({p.predecessor(k) for k in p.histories})==p.count
    for table in (0,1):
        assert len({p.identity(k,table)[1] for k in p.histories})==p.count
        for key in p.histories:
            request=p.lookup(key,table)
            assert request.read_pc!=request.pc==PC
            assert p.identity(key,table)==(table,indices(request.read_pc,Context.from_recent(key))[table],
                tag(request.pc,Context(),table),request.position)
            assert p.identity(key,table)[2]==0
    assert not p.state()['physical_enumeration'] and not p.state()['tag_reference_truncated']


@pytest.mark.parametrize('p',PROGRAMS,ids=lambda p:p.label)
def test_independent_algorithm_retains_all_predecessors_and_direction_bounds(p):
    model=UtageReference()
    before=None
    def query(key,phase=None):
        request=p.lookup(key,0,phase=phase)
        event=Events(read_pc=request.read_pc,read_context=Context.from_recent(request.read_history),select=True,
            pc=request.pc,context=Context.from_recent(request.folded_history),advance=True,
            positions=tuple(request.position+i for i in range(4)),
            bases=(Base(True,request.position,bool(request.base_taken),1),Base(),Base(),Base()))
        model.advance(event);model.advance(event)
        return model.prediction
    for phase in PHASES:
        requests=[]
        for key in p.order(phase):
            source=query(key,phase)
            assert source.frame.providers()[0]==(None if before is None else 0)
            if before is not None:
                assert source.frame.read.entries[0].counter==before
            requests.append(replace(feedback(source,taken=p.taken),position=source.frame.positions[0]))
        for request in requests:
            if p.mode=='serial':learn(model,request)
            else:model.advance(Events(feedback=request))
        while model.offered is not None or model.learning is not None:model.advance()
        for _ in range(2):
            for key in p.histories:
                source=query(key)
                assert source.frame.providers()[0]==0
                assert source.frame.read.entries[0].counter==p.counter(phase)
        assert all(model.memory[0][p.identity(k,0)[1]].counter==p.counter(phase) for k in p.histories)
        assert all(model.useful[0].get(index,0)==value for index,value in enumerate(p.protection(phase)[:512]))
        assert not model.useful[1] and not model.memory[1]
        before=p.counter(phase)


def test_original_same_ancestor_defaults_are_unchanged():
    for profile in PROFILES:
        for mode in MODES:
            p=Original(profile,mode)
            for table in (0,1):
                for key in p.histories:
                    request=p.lookup(key,table,phase='reward')
                    assert request.index_pc is None and request.index_history is None
                    state=ProtectionState(4,table+1)
                    assert p.expected(key,table,4,phase='reward')==expected(key,0,state,table=table,position=request.position)
                    assert p.actual('reward')==1


@pytest.mark.parametrize('missing',RULES)
def test_missing_persistence_or_consumer_witness_never_grants_checked_credit(missing):
    coverage=Coverage(PROGRAMS[0])
    for rule in RULES:
        if rule!=missing:coverage.reach(rule)
    with pytest.raises(AssertionError):coverage.finish()
    assert not coverage.closed and coverage.groups['checked'].coverage==0
