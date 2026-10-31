"""Derive version cohorts from the existing independent learning algorithm."""
from copy import deepcopy
from dataclasses import replace
import pytest

from suites.frontend.bpu.utage.model.semantic import Events
from suites.frontend.bpu.utage.case.definitions import SHADOW_CAPACITY
from tests.utage.scoreboard.test_semantic_model import lookup,feedback,learn,POSITIONS
from tests.utage.scoreboard.test_read_lifetime_model import prepared,bases,values
from suites.frontend.bpu.utage.model.query_cohort import Program,PROFILES,ANCESTRIES,PC,NEIGHBOR


def derive(program):
    model,teacher=prepared(program.legacy)
    event=Events(read_pc=PC,read_context=program.read_context,select=True,
        pc=program.match_pc,context=program.match_context,positions=POSITIONS,bases=bases(0),advance=True)
    # One continuous selected stream, not independent before/after model runs.
    inputs=(event,replace(event,feedback=feedback(teacher,taken=bool(program.actual))),event,event,event)
    originals=[];responses=[];effect=None
    for tick,current in enumerate(inputs):
        previous=model.read
        model.advance(current)
        if tick:
            assert model.frame.read.entries is previous.entries
            responses.append((tick-1,model.prediction))
        originals.append(model.read)
        if model.effects:
            assert effect is None
            effect=tick
    # Complete the final selected read without inventing a second query stream.
    model.advance(event)
    assert model.frame.read.entries is originals[-1].entries
    responses.append((len(inputs)-1,model.prediction))
    assert effect is not None
    return model,originals,responses,effect


@pytest.mark.parametrize('profile',PROFILES)
@pytest.mark.parametrize('ancestry',ANCESTRIES)
def test_semantic_algorithm_derives_all_query_ages_and_later_fresh_source_turnover(profile,ancestry):
    p=Program(profile,ancestry)
    model,originals,responses,effect=derive(p)
    snapshots=deepcopy(responses)
    ages=set()
    for tick,response in responses:
        relation='before' if tick<effect else 'same-boundary' if tick==effect else 'after'
        ages.add(relation)
        assert values(response)==p.query_expected(relation)
        assert response.frame.read.entries is originals[tick].entries
    assert ages=={'before','same-boundary','after'}
    first=model.updates[p.target_table].recent[-1].sequence
    for ordinal in range(SHADOW_CAPACITY):
        source=lookup(model,p.teacher_pc,p.history,bases=bases(p.teacher_base))
        assert values(source)==p.teacher_expected(ordinal)
        learn(model,feedback(source,taken=bool(p.actual)))
    assert not any(version.sequence==first for version in model.updates[p.target_table].recent)
    assert values(lookup(model,p.match_pc,p.match_history,read_pc=PC,read_history=p.history,bases=bases(0)))==p.final_query()
    assert values(lookup(model,p.teacher_pc,p.history,bases=bases(p.teacher_base)))==p.teacher_expected(SHADOW_CAPACITY)
    if ancestry=='distinct-ancestors':
        assert values(lookup(model,p.match_pc,p.match_history,bases=bases(0)))==(0,None,None,None)
    assert values(lookup(model,NEIGHBOR,bases=bases(1)))==(1,0,3,0)
    assert tuple(table.get(index,0) for table in model.useful for index in range(512))==p.protection('turnover')
    assert responses==snapshots
