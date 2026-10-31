"""Fault qualification of semantic comparison and complete-lifetime credit."""
from dataclasses import replace
import pytest
from toffee import ScoreboardMismatch

from suites.frontend.bpu.bpu.model.selection import Kind
from suites.frontend.bpu.bpu.model.pipeline import Redirect
from suites.frontend.bpu.bpu.model.direction_sources import context_for as direction_context
from suites.frontend.bpu.bpu.model.indirect_sources import context_for as target_context
from suites.frontend.bpu.bpu.model.joint_lifetime import (
    Program,MODES,RULES,PC,VIA,CONDITION,INDIRECT,CONDITION_TARGET,INDIRECT_TARGET,MAIN_WRONG)
from suites.frontend.bpu.bpu.checker.joint_lifetime import JointFact,expect_fact
from suites.frontend.bpu.bpu.coverage.joint_lifetime import Coverage
from tests.bpu.scoreboard.test_joint_sources import (
    prepared,query,resolve,outcome,joint_learned,quiet,revisit)


def example(blocked):
    final=(CONDITION,CONDITION_TARGET,Kind.CONDITIONAL,'main') if blocked else (
        INDIRECT,INDIRECT_TARGET,Kind.INDIRECT,'indirect-history')
    middle=final if blocked else (INDIRECT,MAIN_WRONG,Kind.INDIRECT,'main')
    return JointFact(PC,True,MAIN_WRONG,blocked,True,True,True,INDIRECT_TARGET,3,
        middle,final,(2,) if blocked else (2,3))


@pytest.mark.parametrize('blocked',(False,True))
def test_both_human_selection_outcomes_have_distinct_complete_expected_facts(blocked):
    expect_fact(example(blocked),blocked=blocked)


FAULTS=('pc','opposed-base-direction','opposed-base-target','undefined-direction','no-direction-provider',
    'direction-not-qualified','no-target-provider','target','confidence','middle','final-position',
    'final-target','final-kind','final-source','missing-repair','extra-repair')


@pytest.mark.parametrize('blocked',(False,True))
@pytest.mark.parametrize('fault',FAULTS)
def test_joint_checker_rejects_wrong_branch_target_qualification_or_repair(blocked,fault):
    correct=example(blocked)
    changes={
        'pc':dict(pc=PC+8),
        'opposed-base-direction':dict(main_condition_taken=False),
        'opposed-base-target':dict(main_indirect_target=INDIRECT_TARGET),
        'undefined-direction':dict(qualified_direction=None),
        'no-direction-provider':dict(direction_provider=False),
        'direction-not-qualified':dict(direction_uses_provider=False),
        'no-target-provider':dict(target_provider=False),
        'target':dict(indirect_target=MAIN_WRONG),
        'confidence':dict(target_confidence=2),
        'middle':dict(middle=(0,MAIN_WRONG,Kind.NONE,'fallthrough')),
        'final-position':dict(final=(INDIRECT if blocked else CONDITION,*correct.final[1:])),
        'final-target':dict(final=(correct.final[0],INDIRECT_TARGET if blocked else CONDITION_TARGET,*correct.final[2:])),
        'final-kind':dict(final=(*correct.final[:2],Kind.DIRECT,correct.final[3])),
        'final-source':dict(final=(*correct.final[:3],'indirect-history' if blocked else 'main')),
        'missing-repair':dict(repair_stages=correct.repair_stages[:-1]),
        'extra-repair':dict(repair_stages=(*correct.repair_stages,3)),
    }
    with pytest.raises(ScoreboardMismatch) as error:
        expect_fact(replace(correct,**changes[fault]),blocked=blocked)
    assert error.value.context.request['blocked'] is blocked
    assert error.value.expected==correct


@pytest.mark.parametrize('mode',MODES)
@pytest.mark.parametrize('missing',RULES)
def test_incomplete_semantic_lifetime_cannot_receive_checked_credit(mode,missing):
    coverage=Coverage(Program(mode))
    for rule in RULES:
        if rule!=missing:coverage.reach(rule)
    with pytest.raises(AssertionError,match='incomplete'):coverage.finish()
    assert coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('mode',MODES)
def test_complete_joint_lifetime_only_credits_its_own_scenario_once(mode):
    coverage=Coverage(Program(mode))
    for rule in RULES:coverage.reach(rule)
    coverage.finish()
    assert coverage.groups['checked'].coverage==50
    with pytest.raises(AssertionError):coverage.finish()
    with pytest.raises(ValueError):coverage.reach(RULES[0])


@pytest.mark.parametrize('mode',(None,'single-source',True))
def test_unknown_or_weaker_scenario_is_rejected(mode):
    with pytest.raises(ValueError):Program(mode)


def test_program_has_legal_execution_prefixes_not_a_physical_owner_matrix():
    assert Program(MODES[0]).establishment()==Program(MODES[1]).establishment()
    for step in Program(MODES[0]).establishment():
        positions=tuple(branch.position for branch in step.branches)
        assert positions==tuple(sorted(set(positions)))
        first=next((branch.position for branch in step.branches if branch.taken),None)
        assert first is None or all(branch.position<=first for branch in step.branches)
        assert sum(branch.wrong for branch in step.branches)<=1
    assert not Program(MODES[0]).state()['physical_enumeration']


def test_weak_opposed_direction_is_not_mistaken_for_a_qualified_late_correction():
    model,event,anchor=prepared()
    source=query(model,event,anchor)
    resolve(model,event,source,outcome(INDIRECT,INDIRECT_TARGET,Kind.INDIRECT,wrong=True))
    source=query(model,event,anchor)
    resolve(model,event,source,outcome(CONDITION,CONDITION_TARGET,Kind.CONDITIONAL,wrong=True))
    source=query(model,event,anchor)
    resolve(model,event,source,outcome(CONDITION,CONDITION_TARGET,Kind.CONDITIONAL,taken=False,wrong=True),
        outcome(INDIRECT,INDIRECT_TARGET,Kind.INDIRECT))
    source=query(model,event,anchor)
    metadata=dict(model.sources.snapshot(source,resolved=True).wanted)
    conditional=next(slot for slot in range(4) if source.lookup.values().get(f'{slot}.position')==CONDITION)
    assert metadata[f'{conditional}.fast_valid']==1 and metadata[f'{conditional}.fast_taken']==0
    assert metadata[f'{conditional}.valid']==0 and f'{conditional}.taken' not in metadata


def test_retiring_one_owner_releases_both_snapshots_but_preserves_another():
    model,event,anchor,old=joint_learned()
    new=query(model,event,anchor)
    original=(model.sources.snapshot(new),model.sources.target_snapshot(new))
    model.retire_source(old.sequence)
    for snapshot in (model.sources.snapshot,model.sources.target_snapshot):
        with pytest.raises(ValueError,match='absent, retired'):snapshot(old)
    assert model.sources.snapshot(new) is original[0] and model.sources.target_snapshot(new) is original[1]


def test_reset_ends_both_source_lifetimes_and_both_learned_predictors():
    model,event,anchor,source=joint_learned()
    quiet(model,event)
    model.advance(replace(event,reset=True))
    sources=model.sources
    assert not sources.reads and not sources.resolved and not sources.targets.reads and not sources.targets.resolved
    assert not sources.tage.memory and not any(memory for banks in sources.indirect.memories for memory in banks)
    for snapshot in (sources.snapshot,sources.target_snapshot):
        with pytest.raises(ValueError,match='absent, retired'):snapshot(source)


def test_same_pc_different_original_history_owns_both_independent_new_reads():
    model,event,anchor,old=joint_learned()
    intermediate=revisit(model,event,anchor,VIA)
    idle=quiet(model,event)
    model.advance(replace(idle,redirect=Redirect(intermediate.history,VIA+4,PC,True)))
    for _ in range(8):
        cycle=model.advance(event)
        if cycle.metadata is not None and cycle.metadata.pc==PC:
            new=cycle.metadata
            break
    else:raise AssertionError('same-PC second-history source not published')
    assert new.history.metadata()!=old.history.metadata()
    sources=model.sources
    tagged,target=sources.snapshot(new),sources.target_snapshot(new)
    assert tagged.owner is target.owner is new.history
    assert tagged.read.context==direction_context(new.history) and target.read.context==target_context(new.history)
    assert tagged.read is not sources.snapshot(old).read and target.read is not sources.target_snapshot(old).read
