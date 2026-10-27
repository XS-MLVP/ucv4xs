"""Source-semantic feasibility before implementing the real mixed-owner case."""
from copy import deepcopy
from dataclasses import replace
import pytest

from bpuverify.utage.model.semantic import Context,Events,UtageReference,indices,tag
from tests.utage.scoreboard.test_semantic_model import lookup,feedback,learn,POSITIONS
from tests.utage.scoreboard.test_read_lifetime_model import bases,values

PC=0x40000000
READ_PCS=(PC,PC+0x100)


@pytest.mark.parametrize('teacher',(0,1))
def test_full_index_alias_pair_keeps_opposed_versions_across_real_learning_ages_and_fresh_turnover(teacher):
    model=UtageReference()
    originals=[]
    for owner,read_pc in enumerate(READ_PCS):
        cold=lookup(model,PC,read_pc=read_pc,bases=bases(owner))
        assert values(cold)==(0,None,None,None)
        learn(model,feedback(cold,taken=not owner))
    assert tuple(indices(pc,Context())[0] for pc in READ_PCS)==(0,256)
    assert tag(PC,Context(),0)==0
    assert (0&255)==(256&255)
    source=lookup(model,PC,read_pc=READ_PCS[teacher],bases=bases(teacher))
    request=feedback(source,taken=not teacher)
    before=deepcopy(source)
    owners=(1-teacher,teacher)*3+(1-teacher,)
    reads=[];responses=[];effect=None
    for ordinal,owner in enumerate(owners):
        event=Events(read_pc=READ_PCS[owner],read_context=Context(),select=True,pc=PC,
            context=Context(),positions=POSITIONS,bases=bases(owner),advance=True)
        if ordinal==1:event=replace(event,feedback=request)
        model.advance(event)
        if ordinal:responses.append(model.prediction)
        reads.append(model.read)
        if model.effects:
            assert effect is None
            effect=ordinal
    model.advance(event);responses.append(model.prediction)
    assert effect is not None
    ages=set()
    for ordinal,(owner,response) in enumerate(zip(owners,responses,strict=True)):
        age='before' if ordinal<effect else 'same-boundary' if ordinal==effect else 'after'
        if owner==teacher:ages.add(age)
        counter=(4 if owner==0 else 3)+(1 if owner==0 else -1)*int(owner==teacher and age=='after')
        assert values(response)==(1,0,counter,1-owner)
        assert response.frame.read.entries is reads[ordinal].entries
        assert response.frame.read.indices==indices(READ_PCS[owner],Context())
        originals.append((response,deepcopy(response)))
    assert ages=={'before','same-boundary','after'}
    initial=model.updates[0].recent[-1].sequence
    for ordinal in range(8):
        owner=ordinal%2
        fresh=lookup(model,PC,read_pc=READ_PCS[owner],bases=bases(owner))
        assert values(fresh)[-1]==1-owner
        learn(model,feedback(fresh,taken=not owner))
    assert not any(version.sequence==initial for version in model.updates[0].recent)
    for owner,read_pc in enumerate(READ_PCS):
        assert values(lookup(model,PC,read_pc=read_pc,bases=bases(owner)))==(1,0,7 if owner==0 else 0,1-owner)
        assert model.useful[0][indices(read_pc,Context())[0]]==3
    assert source==before
    assert all(original==saved for original,saved in originals)
    assert model.useful[1]=={}
    assert set(model.useful[0])=={0,256}
