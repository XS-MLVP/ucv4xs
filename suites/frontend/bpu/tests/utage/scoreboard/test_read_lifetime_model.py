"""Pure source-first derivation of the same-boundary read-before-write rule."""
from copy import deepcopy
import pytest

from suites.frontend.bpu.utage.model.semantic import Base,Context,Events,UtageReference,indices,tag
from tests.utage.scoreboard.test_semantic_model import lookup,feedback,learn,POSITIONS
from suites.frontend.bpu.utage.model.read_lifetime import Program,PROFILES,RELATIONS,PC,POSITION,NEIGHBOR


def bases(taken):return (Base(True,POSITION,bool(taken),1),Base(),Base(),Base())


def prepared(program):
    model=UtageReference()
    cold=lookup(model,PC,bases=bases(0))
    learn(model,feedback(cold,taken=True))
    if program.profile=='different-identity-replacement':
        source=lookup(model,PC,bases=bases(0))
        learn(model,feedback(source,taken=False))
    cold_neighbor=lookup(model,NEIGHBOR,bases=bases(1))
    learn(model,feedback(cold_neighbor,taken=False))
    teacher=lookup(model,program.teacher_pc,program.history,bases=bases(0))
    return model,teacher


def values(prediction):
    row=prediction.values()
    return (row['0.hit'],row.get('0.provider'),row.get('0.counter'),row.get('0.taken'))


@pytest.mark.parametrize('profile',PROFILES)
@pytest.mark.parametrize('relation',RELATIONS)
def test_independent_model_derives_original_and_fresh_consumers_without_state_seeding(profile,relation):
    p=Program(profile,relation)
    model,teacher=prepared(p)
    before=lookup(model,PC,p.history,bases=bases(0))
    assert values(before)==p.old
    assert tuple(table.get(index,0) for table in model.useful for index in range(512))==p.protection(after=False)
    before_frame=deepcopy(before.frame)
    request=feedback(teacher,taken=bool(p.actual))
    query=Events(read_pc=PC,read_context=Context.from_recent(p.history),select=True,pc=PC,
        context=Context.from_recent(p.history),positions=POSITIONS,bases=bases(0),advance=True)
    model.advance(Events(feedback=request))
    model.advance()
    if relation=='read-with-write':
        model.advance(query)
        original_read=model.read
        assert model.effects and original_read.entries[0].counter==p.old_counter
        assert tuple(model.effects) and model.updates[0].newest(original_read.indices[0]).entry is not original_read.entries[0]
        model.advance(query)
        assert model.frame.read.entries is original_read.entries
    else:
        model.advance()
        lookup(model,PC,p.history,bases=bases(0))
    assert values(model.prediction)==p.expected
    assert values(lookup(model,PC,p.history,bases=bases(0)))==p.new
    if profile=='different-identity-replacement':
        assert values(lookup(model,p.teacher_pc,p.history,bases=bases(0)))==(1,0,4,1)
    assert values(lookup(model,NEIGHBOR,bases=bases(1)))==(1,0,3,0)
    assert before.frame==before_frame
    actual=tuple(table.get(index,0) for table in model.useful for index in range(512))
    assert actual==p.protection(after=True)


def test_replacement_is_a_real_distinct_tag_same_short_identity_location_not_a_bank_sweep():
    p=Program(PROFILES[1],RELATIONS[0])
    context=Context.from_recent(p.history)
    assert indices(PC,context)==indices(p.teacher_pc,context)
    assert tag(PC,context,0)!=tag(p.teacher_pc,context,0)
    assert tag(PC,context,0)<256 and tag(p.teacher_pc,context,0)<256
    assert p.old[-1]!=1 and p.actual==1


@pytest.mark.parametrize('profile,relation',((None,RELATIONS[0]),('copy-turnover',RELATIONS[0]),
    (True,RELATIONS[0]),(PROFILES[0],None),(PROFILES[0],'same-PC-is-enough')))
def test_weaker_or_unknown_lifetime_is_rejected(profile,relation):
    with pytest.raises(ValueError):Program(profile,relation)
