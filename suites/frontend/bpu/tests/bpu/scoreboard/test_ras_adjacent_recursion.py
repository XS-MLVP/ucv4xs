"""Expanded calls and independent compressed state judge every surviving frame."""
from collections import Counter
import pytest
from toffee import Scoreboard,ScoreboardMismatch
from bpuverify.ras.model.model import CommittedStack,advance
from bpuverify.ras.model.semantic import RasReference,Events,Retirement
from bpuverify.bpu.model.ras.adjacent_recursion import Program,DEPTHS,RELATIONS,RULES,ROOT_RETURN
from bpuverify.bpu.coverage.ras_adjacent_recursion import Coverage
from bpuverify.bpu.checker.ras.layered_recursion import compare_returns


@pytest.mark.parametrize('depth',DEPTHS)
@pytest.mark.parametrize('relation',RELATIONS)
def test_expanded_program_preserves_both_adjacent_recursive_counts_at_capacity(depth,relation):
    p=Program(depth,relation);stack=p.committed();expanded=list(p.call_addresses())
    assert not stack.evicted and len(stack.groups)==len(CommittedStack().cells)-(depth=='one-group-free')
    assert Counter(expanded)[p.layer_pcs[-2]+16]==p.counts[-2]
    assert Counter(expanded)[p.layer_pcs[-1]+16]==p.counts[-1]
    assert Counter(expanded)[ROOT_RETURN]==1
    assert stack.groups[-2].counter==p.counts[-2]-1 and stack.groups[-1].counter==p.counts[-1]-1
    for returned,target in enumerate(p.return_targets,1):
        assert target==expanded.pop()==stack.projection()['top']
        stack=advance(stack,1)
        assert stack==p.committed(returned=returned)
        assert stack.projection()['top']==(expanded[-1] if expanded else 0)
    assert len(stack.groups)==1 and stack.head==0 and not stack.evicted
    with pytest.raises(ValueError,match='bottom/empty'):advance(stack,1)


@pytest.mark.parametrize('depth',DEPTHS)
@pytest.mark.parametrize('relation',RELATIONS)
def test_existing_expanded_RAS_reference_checks_declared_calls_and_natural_returns(depth,relation):
    p=Program(depth,relation);model=RasReference()
    for address in p.call_addresses():
        before=model.program
        model.advance(Events(2,2*address));model.advance()
        model.advance(Events(retirement=Retirement(*before.commit_key(),2)));model.advance()
    for target in p.return_targets:
        assert model.projection['top']==target
        before=model.program
        model.advance(Events(1));model.advance()
        model.advance(Events(retirement=Retirement(*before.commit_key(),1)));model.advance()
    assert len(model.program.frames)==1 and model.program.head.address==0
    assert model.retirements==2*len(p.call_addresses())


@pytest.mark.parametrize('depth',DEPTHS)
@pytest.mark.parametrize('relation',RELATIONS)
@pytest.mark.parametrize('missing',RULES)
def test_any_missing_call_correction_return_or_retirement_prevents_checked_credit(depth,relation,missing):
    c=Coverage(Program(depth,relation))
    for rule in RULES:
        if rule!=missing:c.reached(rule)
    with pytest.raises(AssertionError,match='incomplete'):c.finish()
    assert c.groups['checked'].coverage==0


@pytest.mark.parametrize('depth',DEPTHS)
@pytest.mark.parametrize('relation',RELATIONS)
def test_complete_semantic_program_only_credits_its_own_twelve_obligations_once(depth,relation):
    c=Coverage(Program(depth,relation))
    for rule in RULES:c.reached(rule)
    c.finish();assert c.groups['checked'].coverage==25
    with pytest.raises(AssertionError):c.finish()
    with pytest.raises(ValueError):c.reached(RULES[0])


@pytest.mark.parametrize('depth',DEPTHS)
@pytest.mark.parametrize('relation',RELATIONS)
@pytest.mark.parametrize('damage',('borrow-inner-count','wrong-outer-target','wrong-return-PC','missing-return','duplicate-return'))
def test_whole_return_chain_rejects_counter_alias_wrong_owner_and_incomplete_unwind(depth,relation,damage):
    p=Program(depth,relation);pcs=list(p.return_pcs);targets=list(p.return_targets)
    inner=p.counts[-1]
    if damage=='borrow-inner-count':targets[inner]=targets[0]
    elif damage=='wrong-outer-target':targets[-2]=targets[0]
    elif damage=='wrong-return-PC':pcs[-1]=pcs[0]
    elif damage=='missing-return':pcs.pop();targets.pop()
    else:pcs.append(pcs[-1]);targets.append(targets[-1])
    board=Scoreboard('adjacent-recursive-return-control')
    def check(expected,actual,**context):board.check(expected=expected,actual=actual)
    with pytest.raises(ScoreboardMismatch):compare_returns(check,p,pcs,targets)


@pytest.mark.parametrize('args',(('slot6','outer-heavy'),('exact-retained-capacity','slot7'),
    (True,'outer-heavy'),('one-group-free',False)))
def test_unknown_or_physical_coordinate_profile_is_rejected_before_native_work(args):
    with pytest.raises(ValueError):Program(*args)


@pytest.mark.parametrize('layers',(-1,15,True))
def test_invalid_logical_prefix_does_not_silently_truncate(layers):
    with pytest.raises(ValueError):Program('exact-retained-capacity','outer-heavy').call_addresses(layers)
