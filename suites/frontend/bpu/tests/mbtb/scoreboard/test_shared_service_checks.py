"""Full accepted input and both destination effects are indispensable."""
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace
import pytest
from bpuverify.mbtb.model.shared_service import PROGRAMS,RULES
from bpuverify.mbtb.coverage.shared_service import Coverage
from bpuverify.mbtb.checker.shared_service import Checks
from bpuverify.mbtb.case.definitions import BranchVector
from bpuverify.mbtb.case.cleanup_overlap_scenario import feedback
from bpuverify.mbtb.model.cleanup import mbtb_entry_slot
from bpuverify.mbtb.monitor.entry import ENTRY_FIELDS


def fixture(program):
    first=BranchVector(0x40000020+(program.tag<<11),0x40002340,5,3)
    neighbor=replace(first,pc=first.pc+64,target=first.target+0x1020)
    selected=neighbor if program.shared else replace(neighbor,position=6,target=neighbor.target+0x200)
    updated=replace(selected,target=selected.target+0x800)
    metadata=tuple(tuple(dict(rawHit=0,position=0,counter_value=0,attribute=dict(branchType=0,rasAction=0))
        for _ in range(2)) for _ in range(2))
    transaction=feedback(updated,metadata)
    branches=[dict(valid=1,target=updated.target,taken=1,position=updated.position,branch_type=3,ras_action=0,mispredict=1)]
    branches.extend(dict(valid=0,target=0,taken=0,position=0,branch_type=0,ras_action=0,mispredict=0) for _ in range(7))
    accepted=dict(ready=1,bits=dict(start_pc0=neighbor.pc,start_pc1=(neighbor.pc//8+1)*8,
        meta_entries=metadata,branches=branches))
    prepared=dict(first=first,neighbor=neighbor,updated=updated,transaction=transaction,
        retained_before=dict(owner=1 if program.shared else 0,rank=0,record_exists=program.shared,pending=False),capacity_before=2)
    normal={k:v for k,v in mbtb_entry_slot(updated).items() if k not in ('valid','dirty')}
    clear=dict(set_idx=1,tag=0,branch_type=0,ras_action=0,position=0,carry=0,lower=0)
    requests=[(0,normal),(1,clear)];services=[(1 if program.shared else 0,normal),(1,clear)]
    def frame(tick,values,direction):
        banks=[[[dict(write_valid=0,read_valid=0,read_ready=1,**{d+'_'+k:0 for d in ('write','read') for k,_ in ENTRY_FIELDS})
            for _ in range(2)] for _ in range(2)] for _ in range(2)]
        for owner,bits in values:banks[0][0][owner].update({direction+'_valid':1,**{direction+'_'+k:v for k,v in bits.items()}})
        return SimpleNamespace(event=SimpleNamespace(tick=tick),value=dict(banks=banks))
    frames=[frame(10,requests,'write')]
    if program.shared:frames.extend((frame(12,services[:1],'read'),frame(14,services[1:],'read')))
    else:frames.append(frame(12,services,'read'))
    empty=dict(valid=0,dirty=0,set_idx=0,tag=0,branch_type=0,ras_action=0,position=0,carry=0,lower=0)
    bank=[[deepcopy(empty) for _ in range(2)] for _ in range(2)];bank[1][0]=mbtb_entry_slot(neighbor)
    shadows=[SimpleNamespace(event=SimpleNamespace(tick=10),value=dict(banks=[[bank,deepcopy(bank)],[deepcopy(bank),deepcopy(bank)]]))]
    trace=SimpleNamespace(frames=frames,feedback=[SimpleNamespace(event=SimpleNamespace(tick=6),value=accepted)])
    agent=SimpleNamespace(ports=SimpleNamespace(training=SimpleNamespace(bits=SimpleNamespace(branches=range(8)))))
    evidence={};c=Coverage(program);c.reach('genuine-owned-sources')
    return Checks(agent,program,prepared,evidence),trace,shadows,c,evidence


@pytest.mark.parametrize('program',PROGRAMS,ids=lambda p:p.label)
def test_complete_request_effect_and_available_capacity(program):
    checks,trace,shadows,c,evidence=fixture(program);checks.effects(trace,shadows,c)
    assert set(c.seen)==set(RULES[:4])
    assert evidence['pre_collision_shadow'][1][1]['dirty']==0
    assert c.groups['checked'].coverage==0


@pytest.mark.parametrize('fault',('missing-feedback','wrong-feedback','not-simultaneous','lost-correction','wrong-target','duplicate-service','wrong-owner','wrong-prior','no-capacity'))
def test_no_partial_or_misaligned_work_can_earn_checked(fault):
    p=next(p for p in PROGRAMS if p.shared);checks,trace,shadows,c,_=fixture(p)
    if fault=='missing-feedback':trace.feedback=[]
    elif fault=='wrong-feedback':trace.feedback[0].value['bits']['branches'][0]['target']+=0x100
    elif fault=='not-simultaneous':
        extra=deepcopy(trace.frames[0]);extra.event.tick+=2
        trace.frames[0].value['banks'][0][0][1]['write_valid']=0
        extra.value['banks'][0][0][0]['write_valid']=0;trace.frames.insert(1,extra)
    elif fault=='lost-correction':trace.frames[1].value['banks'][0][0][1]['read_valid']=0
    elif fault=='wrong-target':trace.frames[1].value['banks'][0][0][1]['read_lower']+=1
    elif fault=='duplicate-service':trace.frames.append(deepcopy(trace.frames[1]))
    elif fault=='wrong-owner':
        trace.frames[1].value['banks'][0][0][0]=trace.frames[1].value['banks'][0][0][1]
        trace.frames[1].value['banks'][0][0][1]={'read_valid':0,'write_valid':0,'read_ready':1}
    elif fault=='wrong-prior':shadows[0].value['banks'][0][0][1][0]['tag']+=1
    else:shadows[0].value['banks'][0][0][1][1]['dirty']=1
    with pytest.raises(AssertionError):checks.effects(trace,shadows,c)
    assert c.groups['checked'].coverage==0


def test_partial_lifetime_never_earns_checked():
    c=Coverage(PROGRAMS[0]);c.reach(RULES[0])
    with pytest.raises(AssertionError):c.finish()
    assert c.groups['checked'].coverage==0
