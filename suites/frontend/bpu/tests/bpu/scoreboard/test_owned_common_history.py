"""Independent conditional sequences and original-prefix recovery semantics."""
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace as NS
import pytest
from toffee import Scoreboard

from bpuverify.bpu.model.common_history import Value,Block,CommonDirectionReference
from bpuverify.bpu.model.selection import Branch,Kind
from bpuverify.bpu.model.pipeline import Outcome
from bpuverify.bpu.checker.common_history import CommonHistoryChecks
from bpuverify.bpu.coverage.common_history import CommonHistoryCoverage
from bpuverify.bpu.transaction.types import BpuRedirect
from bpuverify.bpu.env.common_history import PC,FALL
from tests.bpu.scoreboard.test_main_service import prepared,resolve
from tests.bpu.scoreboard.test_direction_sources import revisit


def choice(position=1,*,taken=True,kind=Kind.CONDITIONAL,target=PC):return Branch(position,target,kind,taken)


@pytest.mark.parametrize('positions',((1,5),(5,1),(1,1,5,5)))
def test_not_taken_recovery_appends_only_executed_prefix_not_later_predicted_conditionals(positions):
    block=Block(PC,positions);source=Value(True,65535,255)
    assert block.conditionals==(1,5)
    assert source.append(block.outcomes(choice(taken=False),recovering=True),valid=False)==Value(False,65534,254)
    # Completing the ENTIRE block as fallthrough is a different semantic event.
    assert source.append(block.outcomes(choice(taken=False)),valid=True)==Value(True,65532,252)


@pytest.mark.parametrize('position',(1,3,5,7))
@pytest.mark.parametrize('taken',(False,True))
def test_prefix_length_follows_instruction_order_and_always_includes_corrected_conditional(position,taken):
    block=Block(PC,(1,3,5,7));before=Value(True,0xA5,0x9)
    bits=tuple((False,False) for p in block.conditionals if p<position)+((taken,taken),)
    expected=before.append(bits,valid=False)
    assert before.append(block.outcomes(choice(position,taken=taken),recovering=True),valid=False)==expected


@pytest.mark.parametrize('kind',(Kind.DIRECT,Kind.INDIRECT))
def test_nonconditional_cfi_does_not_append_a_conditional_history_bit(kind):
    block=Block(PC,(1,5,9));before=Value(True,0x35,0x3)
    assert before.append(block.outcomes(choice(7,kind=kind)),valid=True)==before.append(((False,False),)*2,valid=True)


def test_backward_bit_uses_pinned_partial_target_comparison_not_full_region_order():
    block=Block(PC,(1,))
    branch=choice(target=PC+(1<<20))
    assert block.outcomes(branch)==((True,True),)
    assert Block(PC,()).outcomes(choice(kind=Kind.DIRECT))==()


def test_eight_real_taken_conditionals_saturate_history_then_future_conditional_extends_only_after_recovery():
    model=CommonDirectionReference();block=Block(PC,(1,5));owner=object()
    for _ in range(16):model.advance(completed=(block,choice()))
    assert model.value==Value(True,65535,255)
    original=model.checkpoint(owner,block)
    model.advance(redirect=(original,choice(taken=False)))
    assert model.value==Value(True,65535,255) and model.recoveries==0
    model.advance(completed=(block,choice(5)))
    assert model.value==Value(False,65534,254) and model.recoveries==1
    model.advance(completed=(Block(PC+3,(5,)),choice(5,target=FALL)))
    assert model.value==Value(True,65533,252)
    assert original.value==Value(True,65535,255)


@pytest.mark.parametrize('fault',('foreign','copied','retired','reset'))
def test_equal_encodings_cannot_replace_an_exact_owned_recovery_source(fault):
    model=CommonDirectionReference();source=model.checkpoint(object(),Block(PC,(1,5)))
    if fault=='foreign':source=CommonDirectionReference().checkpoint(source.owner,source.block)
    elif fault=='copied':source=replace(source)
    elif fault=='retired':model.retire(source)
    else:model.reset()
    before=model.value,model.pending
    with pytest.raises(ValueError):model.advance(redirect=(source,choice(taken=False)))
    assert (model.value,model.pending)==before


def test_pending_recovery_keeps_its_owner_until_applied_and_reset_expires_it():
    model=CommonDirectionReference();source=model.checkpoint(object(),Block(PC,(1,5)))
    model.advance(redirect=(source,choice(taken=False)))
    with pytest.raises(ValueError,match='pending'):model.retire(source)
    model.advance();model.retire(source)
    source=model.checkpoint(object(),Block(PC,(1,)));model.advance(redirect=(source,choice()))
    model.advance(reset=True);assert model.value==Value() and model.pending is None and not model.owned


def test_lookup_history_api_rejects_signal_or_mapping_seeds():
    model=CommonDirectionReference()
    with pytest.raises(TypeError):model.checkpoint(object(),Block(PC),value=Value().mapping())


@pytest.mark.parametrize('args',((1,0,0),(True,-1,0),(True,65536,0),(True,0,256),(True,0,-1)))
def test_history_rejects_invalid_semantic_values_instead_of_truncating_inputs(args):
    with pytest.raises(ValueError):Value(*args)


@pytest.mark.parametrize('bits',(((False,True),),((1,False),),((True,1),)))
def test_history_rejects_nonsemantic_or_impossible_conditional_outcomes(bits):
    with pytest.raises(ValueError):Value().append(bits,valid=True)


def fixture(*,later_conditional=True,public_only=False):
    # All actuals below are SYNTHETIC fault-qualification snapshots. No DUT is
    # constructed and no native/functional evidence is exported from them.
    main,event,anchor=prepared();source=revisit(main,event,anchor,PC)
    resolve(main,event,source,Outcome(5,FALL,Kind.CONDITIONAL if later_conditional else Kind.DIRECT,True,mispredict=True))
    source=revisit(main,event,anchor,PC);resolve(main,event,source,Outcome(1,PC,Kind.CONDITIONAL,True,mispredict=True))
    token=revisit(main,event,anchor,PC)
    pipeline=NS(board=Scoreboard('common-history-contract'),last_tick=100,source_token=lambda r:r.token,
        raise_failure=lambda:None,last_cycle=NS(metadata=None,decisions=(None,)*3,fires=(False,)*4,
            middle_repair=False,final_repair=False),last_events=NS(redirect=None),model=NS(stages=(None,)*3))
    coverage=CommonHistoryCoverage(later_conditional=later_conditional,public_only=public_only)
    checks=CommonHistoryChecks(pipeline,observe_state=not public_only,coverage=coverage);checks.initialized=True
    block=Block.from_token(token)
    for _ in range(16):checks.model.advance(completed=(block,choice()))
    checkpoint=checks.model.checkpoint(token.history,block);checks.sources[token.history.sequence]=checkpoint
    def receipt(t,value,*,pred=96,at=100):
        values={} if t.lookup is None else t.lookup.values();hits=[];positions=[];attrs=[];seen=set()
        for i in range(10):
            position=values.get(f'{i}.position',0);kind=values.get(f'{i}.kind',0)
            hit=bool(values.get(f'{i}.valid') and kind==1 and position not in seen)
            if hit:seen.add(position)
            hits.append(int(hit));positions.append(position);attrs.append(dict(branchType=kind))
        return NS(token=t,prediction_tick=pred,meta_tick=at,meta=NS(redirect=dict(commonHRMeta=dict(
            ghr=value.ghr,bw=value.bw,hitMask=tuple(hits),position=tuple(positions),attribute=tuple(attrs))),
            resolve=dict(commonHR=value.mapping())))
    actual=receipt(token,checkpoint.value);checks.original_source(actual,later_conditional=later_conditional)
    request=BpuRedirect(PC+3,actual.meta.redirect,cfi_pc=PC+1,taken=0,branch_type=1)
    checks.plan(actual,request)
    m=actual.meta.redirect['commonHRMeta']
    redirect=dict(valid=1,pc=PC+1,target=PC+3,taken=0,kind=1,
        meta=dict(ghr=m['ghr'],bw=m['bw'],hits=m['hitMask'],positions=m['position'],kinds=tuple(a['branchType'] for a in m['attribute'])))
    return checks,actual,redirect,receipt,later_conditional


def sample(checks,tick,*,redirect=None,state=None):
    checks.pipeline.last_tick=tick
    row=dict(reset=0,redirect=dict(valid=0) if redirect is None else deepcopy(redirect))
    if checks.observe_state:row['state']=(checks.model.value if state is None else state).mapping()
    checks.capture_state(NS(tick=tick),row);checks.raise_failure()


def restore_fixture(checks,redirect):
    sample(checks,100,redirect=redirect);sample(checks,102);sample(checks,104);checks.recovered(100)


@pytest.mark.parametrize('later',(False,True))
@pytest.mark.parametrize('public_only',(False,True))
def test_complete_prefix_contract_keeps_checked_empty_until_selected_endpoint_and_original_immutability(later,public_only):
    checks,actual,redirect,receipt,_=fixture(later_conditional=later,public_only=public_only)
    restore_fixture(checks,redirect);assert checks.coverage.groups['checked'].coverage==0
    if public_only:
        checks.model.advance(completed=(Block(PC+3,(5,) if later else ()),choice(5,kind=Kind.CONDITIONAL if later else Kind.DIRECT,target=FALL)))
        t=replace(actual.token,pc=FALL,history=replace(actual.token.history,sequence=actual.token.history.sequence+1000),lookup=None)
        cp=checks.model.checkpoint(t.history,Block.from_token(t));checks.sources[t.history.sequence]=cp
        consumer=receipt(t,cp.value,pred=110,at=114);checks.consumed(consumer,later_conditional=later)
    checks.finish(public_only=public_only)
    assert all(g.coverage==100 for g in checks.coverage.groups.values())


@pytest.mark.parametrize('fault',('ghr','bw','target','kind','hits','duplicate','hit-kind'))
def test_corrupted_actual_redirect_never_seeds_or_advances_the_reference(fault):
    checks,_,r,_,_=fixture()
    if fault in ('ghr','bw'):r['meta'][fault]^=1
    elif fault=='hits':r['meta']['hits']=(0,)*10
    elif fault=='duplicate':r['meta']['positions']=(1,1)+(0,)*8
    elif fault=='hit-kind':r['meta']['kinds']=(2,1)+(0,)*8
    else:r[fault]^=1
    before=checks.model.value,checks.model.pending,len(checks.plans)
    with pytest.raises(AssertionError) as first:sample(checks,100,redirect=r)
    with pytest.raises(AssertionError) as second:checks.raise_failure()
    assert first.value is second.value and (checks.model.value,checks.model.pending,len(checks.plans))==before
    assert checks.coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('fault',('extra-zero','wrong-backward','wrong-valid'))
def test_wrong_recovered_state_is_rejected_without_golden_repair(fault):
    checks,_,r,_,_=fixture();sample(checks,100,redirect=r);sample(checks,102)
    state=Value(False,65532,252) if fault=='extra-zero' else Value(False,65534,0) if fault=='wrong-backward' else Value(True,65534,254)
    before=checks.model.value
    with pytest.raises(AssertionError):sample(checks,104,state=state)
    assert checks.model.value==before==Value(False,65534,254)


@pytest.mark.parametrize('fault',('zero-valid','wrong-ghr','wrong-bw','foreign-owner','missing-known-source','changed-original'))
def test_public_only_oracle_rejects_defined_bad_payloads_and_never_reads_internal_state(fault):
    checks,actual,r,receipt,_=fixture(public_only=True);restore_fixture(checks,r)
    checks.model.advance(completed=(Block(PC+3,(5,)),choice(5,target=FALL)))
    t=replace(actual.token,pc=FALL,history=replace(actual.token.history,sequence=actual.token.history.sequence+1000),lookup=None)
    cp=checks.model.checkpoint(t.history,Block.from_token(t));checks.sources[t.history.sequence]=cp
    consumer=receipt(t,cp.value,pred=110,at=114)
    if fault=='zero-valid':consumer.meta.resolve['commonHR']['valid']=0
    elif fault=='wrong-ghr':consumer.meta.redirect['commonHRMeta']['ghr']=249
    elif fault=='wrong-bw':consumer.meta.redirect['commonHRMeta']['bw']=8
    elif fault=='foreign-owner':consumer.token=replace(t,history=replace(t.history))
    elif fault=='missing-known-source':del checks.sources[t.history.sequence]
    else:actual.meta.redirect['commonHRMeta']['ghr']^=1
    before=checks.model.value
    with pytest.raises(AssertionError):
        checks.consumed(consumer,later_conditional=True)
        checks.finish(public_only=True)
    assert checks.model.value==before==Value(True,65533,252)
    assert checks.coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('public_only',(False,True))
def test_preparation_or_recovery_without_the_required_endpoint_is_not_success(public_only):
    checks,_,r,_,_=fixture(public_only=public_only)
    if public_only:restore_fixture(checks,r)
    with pytest.raises(AssertionError):checks.finish(public_only=public_only)
    assert checks.coverage.groups['checked'].coverage==0


def test_expected_recovery_without_a_post_restore_comparison_cannot_receive_endpoint_credit():
    checks,_,r,_,_=fixture();sample(checks,100,redirect=r);sample(checks,102)
    assert checks.model.value==Value(False,65534,254)
    with pytest.raises(AssertionError,match='post-restore'):checks.recovered(100)
    assert checks.coverage.groups['checked'].coverage==0


def test_reset_invalidates_all_original_receipts_and_pending_semantic_closure():
    checks,_,r,_,_=fixture();restore_fixture(checks,r)
    checks.capture_state(NS(tick=106),dict(reset=1))
    assert checks.original is checks.last_recovery is checks.completed_recovery is checks.consumer is None
    assert checks.model.value==Value() and not checks.sources and not checks.plans
    with pytest.raises(AssertionError):checks.finish(public_only=False)
    assert checks.coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('fault',('missing','out-of-order'))
def test_common_observation_requires_the_same_pipeline_event_before_advancing(fault):
    checks,_,r,_,_=fixture();checks.pipeline.last_tick=98 if fault=='missing' else 102
    before=checks.model.value,checks.model.pending
    checks.capture_state(NS(tick=100),dict(reset=0,state=checks.model.value.mapping(),redirect=r))
    with pytest.raises(AssertionError,match='lossless'):checks.raise_failure()
    assert (checks.model.value,checks.model.pending)==before


@pytest.mark.parametrize('interruption',('none','stall','middle-repair','final-repair','redirect'))
def test_lookup_sources_require_an_uninterrupted_full_window_of_independently_unchanged_history(interruption):
    from bpuverify.bpu.model.common_history import LOOKUP_WINDOW_CAPACITY
    checks,actual,r,_,_=fixture(public_only=True)
    checks.plans.clear();checks.sources.clear();checks.stable=0
    token=actual.token
    checks.pipeline.model.stages=(token,None,None)
    checks.pipeline.last_cycle.fires=(True,)*4
    for index in range(LOOKUP_WINDOW_CAPACITY-1):sample(checks,110+2*index)
    assert not checks.sources and checks.stable==LOOKUP_WINDOW_CAPACITY-1
    cycle=checks.pipeline.last_cycle;redirect=None
    if interruption=='stall':cycle.fires=(False,True,True,True)
    elif interruption=='middle-repair':cycle.middle_repair=True
    elif interruption=='final-repair':cycle.final_repair=True
    elif interruption=='redirect':
        checks.sources[token.history.sequence]=checks.original[1]
        checks.plan(actual,NS(cfi_pc=PC+1,pc=PC+3,branch_type=1,taken=0))
        checks.sources.clear();redirect=r
    sample(checks,130,redirect=redirect)
    assert bool(checks.sources)==(interruption=='none')
    if interruption!='none':assert checks.stable==0
