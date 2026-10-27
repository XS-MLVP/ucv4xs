"""Prove every declared phase with the unchanged independent predictor model."""
from copy import deepcopy
import pytest
from bpuverify.utage.model.semantic import Events,UtageReference
from tests.utage.scoreboard.test_semantic_model import lookup,feedback,learn
from tests.utage.scoreboard.test_read_lifetime_model import bases,values
from bpuverify.utage.model.selective_protection import Program,PC,READ_PCS,MODES



@pytest.mark.parametrize('first',(0,1))
@pytest.mark.parametrize('mode',MODES)
def test_fresh_sources_derive_selective_penalty_lower_direction_crossing_and_recovery(first,mode):
    p=Program(first,mode);model=UtageReference();originals=[];count=0
    for group in p.groups:
        requests=[]
        for step in group:
            source=lookup(model,PC,step.history,read_pc=READ_PCS[step.owner],read_history=0,bases=bases(step.base))
            assert values(source)==step.expected
            originals.append((source,deepcopy(source)))
            request=feedback(source,taken=bool(step.actual))
            if mode=='serial':learn(model,request)
            else:requests.append(request)
        if mode=='adjacent':
            for request in requests:model.advance(Events(feedback=request))
            model.advance();model.advance()
        count+=len(group)
        assert tuple(table.get(index,0) for table in model.useful for index in range(512))==p.protection_after(count)
    assert count==28 and model.low_tick==model.high_tick==6
    assert not model.aged
    for owner in (0,1):
        assert values(lookup(model,PC,64,read_pc=READ_PCS[owner],read_history=0,bases=bases(owner)))==(1,0,0 if owner==0 else 7,owner)
        assert values(lookup(model,PC,0,read_pc=READ_PCS[owner],read_history=0,bases=bases(owner)))==(1,1,3 if owner==0 else 4,owner)
    assert all(original==saved for original,saved in originals)
