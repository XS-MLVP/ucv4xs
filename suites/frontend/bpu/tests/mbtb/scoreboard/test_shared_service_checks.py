"""Full accepted input and both destination effects are indispensable."""
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace
import pytest
from suites.frontend.bpu.mbtb.model.shared_service import PROGRAMS,RULES,shared_service_addresses
from suites.frontend.bpu.mbtb.coverage.shared_service import Coverage
from suites.frontend.bpu.mbtb.checker.shared_service import Checks
from suites.frontend.bpu.mbtb.case.definitions import BranchVector
from suites.frontend.bpu.mbtb.case.cleanup_overlap_scenario import feedback
from suites.frontend.bpu.mbtb.model.cleanup import mbtb_entry_slot
from suites.frontend.bpu.mbtb.monitor.entry import ENTRY_FIELDS
from suites.frontend.bpu.models.configuration import ALIGN_HALFWORDS,MAIN_WAYS,MAIN_BANKS,MAIN_RETAINED
from suites.frontend.bpu.mbtb.model.semantic import coordinate


def fixture(program):
    pc,neighbor_pc,target=shared_service_addresses(program.tag);owners=program.owners
    first=BranchVector(pc,target,5,3)
    neighbor=replace(first,pc=neighbor_pc,target=first.target+0x1020)
    selected=neighbor if program.shared else replace(neighbor,position=6,target=neighbor.target+0x200)
    updated=replace(selected,target=selected.target+0x800)
    metadata=tuple(tuple(dict(rawHit=0,position=0,counter_value=0,attribute=dict(branchType=0,rasAction=0))
        for _ in range(MAIN_WAYS)) for _ in range(2))
    transaction=feedback(updated,metadata)
    branches=[dict(valid=1,target=updated.target,taken=1,position=updated.position,branch_type=3,ras_action=0,mispredict=1)]
    branches.extend(dict(valid=0,target=0,taken=0,position=0,branch_type=0,ras_action=0,mispredict=0) for _ in range(7))
    accepted=dict(ready=1,bits=dict(start_pc0=neighbor.pc,start_pc1=(neighbor.pc//ALIGN_HALFWORDS+1)*ALIGN_HALFWORDS,
        meta_entries=metadata,branches=branches))
    prepared=dict(first=first,neighbor=neighbor,updated=updated,transaction=transaction,
        retained_before=dict(owner=owners.correction if program.shared else None,
            rank=0 if program.shared else None,record_exists=program.shared,pending=False),capacity_before=MAIN_RETAINED)
    normal={k:v for k,v in mbtb_entry_slot(updated).items() if k not in ('valid','dirty')}
    clear=dict(set_idx=coordinate(first.pc)[2],tag=0,branch_type=0,ras_action=0,position=0,carry=0,lower=0)
    requests=[(owners.nomination,normal),(owners.clear,clear)]
    services=[(owners.correction,normal),(owners.clear,clear)]
    def frame(tick,values,direction):
        banks=[[[dict(write_valid=0,read_valid=0,read_ready=1,**{d+'_'+k:0 for d in ('write','read') for k,_ in ENTRY_FIELDS})
            for _ in range(MAIN_WAYS)] for _ in range(MAIN_BANKS)] for _ in range(2)]
        for owner,bits in values:banks[0][0][owner].update({direction+'_valid':1,**{direction+'_'+k:v for k,v in bits.items()}})
        return SimpleNamespace(event=SimpleNamespace(tick=tick),value=dict(banks=banks))
    frames=[frame(10,requests,'write')]
    if program.shared:frames.extend((frame(12,services[:1],'read'),frame(14,services[1:],'read')))
    else:frames.append(frame(12,services,'read'))
    empty=dict(valid=0,dirty=0,set_idx=0,tag=0,branch_type=0,ras_action=0,position=0,carry=0,lower=0)
    bank=[[deepcopy(empty) for _ in range(MAIN_RETAINED)] for _ in range(MAIN_WAYS)]
    bank[owners.original][0]=mbtb_entry_slot(neighbor)
    shadows=[SimpleNamespace(event=SimpleNamespace(tick=10),value=dict(
        banks=[[deepcopy(bank) for _ in range(MAIN_BANKS)] for _ in range(2)]))]
    trace=SimpleNamespace(frames=frames,feedback=[SimpleNamespace(event=SimpleNamespace(tick=6),value=accepted)])
    agent=SimpleNamespace(ports=SimpleNamespace(training=SimpleNamespace(bits=SimpleNamespace(branches=range(8)))))
    evidence={};c=Coverage(program);c.reach('genuine-owned-sources')
    return Checks(agent,program,prepared,evidence),trace,shadows,c,evidence


@pytest.mark.parametrize('program',PROGRAMS,ids=lambda p:p.label)
def test_complete_request_effect_and_available_capacity(program):
    checks,trace,shadows,c,evidence=fixture(program);checks.effects(trace,shadows,c)
    assert set(c.seen)==set(RULES[:4])
    assert len(evidence['pre_collision_shadow'])==MAIN_WAYS
    assert all(slot['dirty']==0 for slot in evidence['pre_collision_shadow'][program.owners.correction])
    assert c.groups['checked'].coverage==0


@pytest.mark.parametrize('fault',('missing-feedback','wrong-feedback','not-simultaneous','lost-correction','wrong-target','duplicate-service','wrong-owner','wrong-prior','no-capacity'))
def test_no_partial_or_misaligned_work_can_earn_checked(fault):
    p=next(p for p in PROGRAMS if p.shared);checks,trace,shadows,c,_=fixture(p)
    owners=p.owners
    if fault=='missing-feedback':trace.feedback=[]
    elif fault=='wrong-feedback':trace.feedback[0].value['bits']['branches'][0]['target']+=0x100
    elif fault=='not-simultaneous':
        extra=deepcopy(trace.frames[0]);extra.event.tick+=2
        trace.frames[0].value['banks'][0][0][owners.clear]['write_valid']=0
        extra.value['banks'][0][0][owners.nomination]['write_valid']=0;trace.frames.insert(1,extra)
    elif fault=='lost-correction':trace.frames[1].value['banks'][0][0][owners.correction]['read_valid']=0
    elif fault=='wrong-target':trace.frames[1].value['banks'][0][0][owners.correction]['read_lower']+=1
    elif fault=='duplicate-service':trace.frames.append(deepcopy(trace.frames[1]))
    elif fault=='wrong-owner':
        trace.frames[1].value['banks'][0][0][0]=trace.frames[1].value['banks'][0][0][owners.correction]
        trace.frames[1].value['banks'][0][0][owners.correction]={'read_valid':0,'write_valid':0,'read_ready':1}
    elif fault=='wrong-prior':shadows[0].value['banks'][0][0][owners.correction][0]['tag']+=1
    else:shadows[0].value['banks'][0][0][owners.correction][1]['dirty']=1
    with pytest.raises(AssertionError):checks.effects(trace,shadows,c)
    assert c.groups['checked'].coverage==0


@pytest.mark.parametrize('fault',('two-ways','two-banks','two-retained-slots','old-capacity','old-prior-owner','last-rank-dirty'))
def test_legacy_geometry_and_hidden_capacity_do_not_pass_even_with_matching_payload(fault):
    p=next(p for p in PROGRAMS if p.shared);checks,trace,shadows,c,_=fixture(p)
    if fault=='two-ways':
        trace.frames[0].value['banks'][0][1]=trace.frames[0].value['banks'][0][1][:2]
    elif fault=='two-banks':trace.frames[0].value['banks'][1]=trace.frames[0].value['banks'][1][:2]
    elif fault=='two-retained-slots':shadows[0].value['banks'][1][3][0]=shadows[0].value['banks'][1][3][0][:2]
    elif fault=='old-capacity':checks.prepared['capacity_before']=2
    elif fault=='old-prior-owner':checks.prepared['retained_before']['owner']=1
    else:shadows[0].value['banks'][0][0][p.owners.correction][-1]['dirty']=1
    with pytest.raises((AssertionError,ValueError)):checks.effects(trace,shadows,c)
    assert c.groups['checked'].coverage==0


@pytest.mark.parametrize('program',PROGRAMS,ids=lambda p:p.label)
@pytest.mark.parametrize('direction',('write','read'))
@pytest.mark.parametrize('field',tuple(key for key,_ in ENTRY_FIELDS))
def test_every_full_request_and_service_field_is_discriminating(program,direction,field):
    checks,trace,shadows,c,_=fixture(program)
    frame=trace.frames[0 if direction=='write' else 1]
    owner=program.owners.nomination if direction=='write' else program.owners.correction
    frame.value['banks'][0][0][owner][direction+'_'+field]^=1
    with pytest.raises(AssertionError):checks.effects(trace,shadows,c)
    assert c.groups['checked'].coverage==0


def test_partial_lifetime_never_earns_checked():
    c=Coverage(PROGRAMS[0]);c.reach(RULES[0])
    with pytest.raises(AssertionError):c.finish()
    assert c.groups['checked'].coverage==0
