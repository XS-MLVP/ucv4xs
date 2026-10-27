"""Reject missing ownership, incomplete target patches and premature FC credit."""
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace as NS

import pytest
from toffee import Scoreboard

from bpuverify.bpu.checker.indirect_service import IndirectServiceChecks
from bpuverify.bpu.coverage.indirect_service import IndirectServiceCoverage
from bpuverify.bpu.model.ittage_service import PC,PATHS,TARGETS,STREAM_PC,pending_plan,offered_payload,ENTRY_WIDTH
from tests.bpu.scoreboard.test_indirect_sources import pending_program,query_path,ENABLED
from tests.bpu.scoreboard.test_direction_sources import quiet


def fixture(table=2):
    model,event,anchor,tokens,requests,_=pending_program(table)
    receipts=tuple(NS(token=token,prediction_tick=100+index*10,meta_tick=104+index*10)
        for index,token in enumerate(tokens))
    accepted=tuple((200+index*2,request) for index,request in enumerate(requests))
    retired=[]
    pipeline=NS(board=Scoreboard('indirect-service-contract'),model=model,last_tick=220,
        last_resolution_controls=(206,ENABLED),source_token=lambda r:r.token,raise_failure=lambda:None,
        retire_source=retired.append,corrections_for_source=lambda r:((r.prediction_tick+2,2),)+
            (() if model.sources.snapshot(r.token,resolved=True).prediction.target==TARGETS[-1]*2 else ((r.prediction_tick+4,3),)))
    checks=IndirectServiceChecks(pipeline,IndirectServiceCoverage(table),table)
    row=dict(reset=0,maintenance=0,read=dict(valid=1,ready=1,pc=STREAM_PC),
        training=dict(valid=0,ready=1),prediction=dict(valid=1,ready=1,pc=STREAM_PC),
        incoming=dict(valid=0,bits={}),write=dict(valid=1,ready=0,bits=deepcopy(pending_plan(model.sources.indirect,table,PC%2)[0])),
        dirty=(1,1,1,1))
    return checks,receipts,accepted,row,(model,event,anchor),retired


def armed(table=2):
    checks,receipts,accepted,row,program,retired=fixture(table)
    checks.arm(receipts);checks.begin_read_window()
    for tick,_ in accepted:
        actual=deepcopy(row);actual['training']['valid']=1;checks.capture_state(NS(tick=tick),actual)
    for index,complete in enumerate(checks.plan):
        actual=deepcopy(row);actual['incoming']=dict(valid=1,bits=offered_payload(complete))
        checks.capture_state(NS(tick=210+index*2),actual)
    checks.capture_state(NS(tick=220),row);checks.accepted_burst(accepted)
    return checks,row,program,retired


def consumers(checks,program,*,committed):
    model,event,anchor=program
    if committed:quiet(model,event)
    for index,path in enumerate(PATHS):
        token=query_path(model,event,anchor,path,stream=not committed)
        receipt=NS(token=token,prediction_tick=(350 if committed else 230)+index*10,
            meta_tick=(354 if committed else 234)+index*10)
        checks.consumed(receipt,index,committed=committed)


@pytest.mark.parametrize('table',(0,2))
def test_both_history_classes_require_all_four_old_consumers_full_service_and_new_consumers_before_credit(table):
    checks,row,program,retired=armed(table);checks.pending()
    assert checks.coverage.groups['checked'].coverage==0
    consumers(checks,program,committed=False);checks.release()
    for index,complete in enumerate(checks.plan):
        checks.write_accepted(0,NS(accepted_tick=280+index*2,value=deepcopy(complete)))
    empty=deepcopy(row);empty['read']['valid']=0;empty['write'].update(valid=0,ready=1)
    checks.capture_state(NS(tick=310),empty)
    assert not retired and checks.coverage.groups['checked'].coverage==0
    consumers(checks,program,committed=True);checks.finish()
    assert checks.closed and len(retired)==12
    assert all(group.coverage==100 for group in checks.coverage.groups.values())


@pytest.mark.parametrize('fault',('count','same-checkpoint','same-history','source-order','provider','target','confidence','pointer'))
def test_original_qualification_rejects_aliases_and_wrong_independent_source_semantics(fault):
    checks,sources,_,_,_,_=fixture()
    if fault=='count':sources=sources[:3]
    elif fault=='same-checkpoint':sources[1].token=replace(sources[1].token,history=sources[0].token.history)
    elif fault=='source-order':sources[1].prediction_tick=sources[0].meta_tick
    else:
        original=checks.pipeline.model.sources.snapshot
        def corrupt(token,*,resolved=False):
            saved=original(token,resolved=resolved)
            if token is not sources[1].token:return saved
            if fault=='same-history':return replace(saved,read=replace(saved.read,context=original(sources[0].token,resolved=True).read.context))
            if fault=='pointer':
                entries=list(saved.read.entries);entry=entries[checks.table]
                entries[checks.table]=replace(entry,target=replace(entry.target,pointer=7))
                return replace(saved,read=replace(saved.read,entries=tuple(entries)))
            field={'provider':'provider','target':'provider_target','confidence':'confidence'}[fault]
            return replace(saved,prediction=replace(saved.prediction,**{field:0}))
        checks.pipeline.model.sources.snapshot=corrupt
    before=deepcopy(checks.pipeline.model.sources.indirect.state())
    with pytest.raises(AssertionError) as first:checks.arm(sources)
    with pytest.raises(AssertionError) as second:checks.finish()
    assert first.value is second.value and checks.pipeline.model.sources.indirect.state()==before
    assert checks.coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('fault',('reset','maintenance','read-valid','read-ready','read-bank','write-ready','prediction-valid','prediction-ready','prediction-bank'))
def test_real_read_window_and_parallel_acceptance_are_requirements_not_stimulus_labels(fault):
    checks,sources,_,row,_,_=fixture();checks.arm(sources);checks.begin_read_window()
    actual=deepcopy(row);actual['training']['valid']=1
    if fault in ('reset','maintenance'):actual[fault]=1
    else:
        section,field=fault.split('-')
        actual['write' if section=='write' else section]['pc' if field=='bank' else field] = (STREAM_PC+1 if field=='bank' else 1 if section=='write' else 0)
    before=deepcopy(checks.pipeline.model.sources.indirect.state())
    checks.capture_state(NS(tick=200),actual)
    with pytest.raises(AssertionError):checks.raise_failure()
    assert checks.pipeline.model.sources.indirect.state()==before
    assert checks.coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('field',('row','tag','confidence','useful','offset','pointer','pc_region','mask'))
def test_every_defined_offered_target_field_is_compared_before_retention(field):
    checks,sources,_,row,_,_=fixture();checks.arm(sources);checks.begin_read_window()
    actual=deepcopy(row);bits=offered_payload(checks.plan[0]);bits[field]^=1
    actual['incoming']=dict(valid=1,bits=bits);checks.capture_state(NS(tick=210),actual)
    with pytest.raises(AssertionError):checks.raise_failure()
    assert not checks.proposals and checks.coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('field',('valid','row','tag','confidence','useful','offset','pointer','pc_region','mask'))
def test_complete_sram_service_payload_cannot_be_reduced_to_a_row_or_counter_check(field):
    checks,row,program,_=armed();checks.pending();consumers(checks,program,committed=False);checks.release()
    wrong=deepcopy(checks.plan[0]);wrong[field]^=1
    with pytest.raises(AssertionError):checks.write_accepted(0,NS(accepted_tick=280,value=wrong))
    assert not checks.written and checks.coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('fault',('dirty','front','order','early-service','missing-old','missing-commit','missing-new'))
def test_partial_progress_never_completes_the_target_service_contract(fault):
    checks,row,program,_=armed()
    with pytest.raises(AssertionError):
        if fault=='dirty':
            checks.last[1]['dirty']=(1,1,1,0);checks.pending()
        elif fault=='front':
            checks.last[1]['write']['bits']['pointer']^=1;checks.pending()
        elif fault=='order':
            checks.proposals[1],checks.proposals[2]=checks.proposals[2],checks.proposals[1];checks.pending()
        elif fault=='early-service':checks.write_accepted(0,NS(accepted_tick=218,value=checks.plan[0]))
        elif fault=='missing-old':checks.pending();checks.release()
        elif fault=='missing-commit':
            checks.pending();consumers(checks,program,committed=False);checks.release();consumers(checks,program,committed=True)
        else:checks.pending();checks.finish()
    assert checks.coverage.groups['checked'].coverage==0


def test_physical_mask_includes_padding_but_dontcare_padding_is_not_a_functional_target_field():
    checks,_,_,_,_,_=fixture()
    complete=pending_plan(checks.pipeline.model.sources.indirect,2,PC%2)[0]
    assert ENTRY_WIDTH==36 and complete['mask']==(1<<36)-1
    assert 'padding' not in complete and 'valid' in complete and 'valid' not in offered_payload(complete)
