"""Derive the two-context result before attempting a real DUT stimulus."""
from dataclasses import replace
import pytest

from suites.frontend.bpu.utage.model.semantic import Context,Events,indices,tag
from tests.utage.scoreboard.test_semantic_model import lookup,feedback,POSITIONS
from tests.utage.scoreboard.test_read_lifetime_model import prepared,bases,values
from suites.frontend.bpu.utage.model.ancestor_lifetime import Program,PROFILES,RELATIONS,PC,MATCH_PC,MATCH_HISTORY


def query(p):
    return Events(read_pc=PC,read_context=Context.from_recent(p.history),select=True,pc=MATCH_PC,
        context=Context.from_recent(MATCH_HISTORY),positions=POSITIONS,bases=bases(0),advance=True)


def derive(p):
    model,teacher=prepared(p)
    assert values(lookup(model,MATCH_PC,MATCH_HISTORY,bases=bases(0)))==(0,None,None,None)
    old=lookup(model,MATCH_PC,MATCH_HISTORY,read_pc=PC,read_history=p.history,bases=bases(0))
    assert values(old)==p.old
    model.advance(Events(feedback=feedback(teacher,taken=bool(p.actual))))
    model.advance()
    event=query(p)
    if p.relation=='read-with-write':
        model.advance(event);original=model.read;effects=model.effects
    else:
        model.advance();effects=model.effects
        model.advance(event);original=model.read
    model.advance(event)
    assert model.frame.read.entries is original.entries
    return model,original,effects,event


@pytest.mark.parametrize('profile',PROFILES)
@pytest.mark.parametrize('relation',RELATIONS)
def test_two_ancestor_lifetime_has_independently_distinguishable_old_and_new_results(profile,relation):
    p=Program(profile,relation)
    model,original,_,_=derive(p)
    assert values(model.prediction)==p.expected
    assert model.frame.pc==MATCH_PC and model.frame.context==Context.from_recent(MATCH_HISTORY)
    assert model.frame.read.indices==indices(PC,Context.from_recent(p.history))
    assert values(lookup(model,MATCH_PC,MATCH_HISTORY,read_pc=PC,read_history=p.history,bases=bases(0)))==p.new
    assert values(lookup(model,MATCH_PC,MATCH_HISTORY,bases=bases(0)))==(0,None,None,None)
    assert tuple(table.get(index,0) for table in model.useful for index in range(512))==p.protection(after=True)


def test_algebraic_choice_is_not_a_same_context_or_an_undefined_high_tag_alias():
    later=Context.from_recent(MATCH_HISTORY)
    assert indices(MATCH_PC,later)==(346,442)
    assert tuple(tag(MATCH_PC,later,t) for t in range(2))==(0,0)
    assert tuple(tag(PC,Context(),t) for t in range(2))==(0,0)
    assert tag(MATCH_PC,Context(),0)!=0 and tag(PC,later,0)!=0
    assert MATCH_PC!=PC and later!=Context()
