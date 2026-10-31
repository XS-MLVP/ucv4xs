"""Two complete logical-record rewrites; synthetic tests give no DUT credit."""
from copy import deepcopy
from types import SimpleNamespace as NS
import pytest
from suites.frontend.bpu.bpu.coverage.main_service import MainServiceCoverage,main_service_rules
from suites.frontend.bpu.bpu.checker.main_service import MainServiceChecks
from suites.frontend.bpu.bpu.model.main_service import PCS,PEER_POSITION,POSITION,old_target,new_target,reclassification_effect,after_earlier_branch,entry_plan
from suites.frontend.bpu.bpu.model.main_sources import source_entries
from tests.bpu.scoreboard.test_main_service import armed,fixture,consumers,raw_counter,revisit


def release_and_service(checks,row,program):
    consumers(checks,program,committed=False);checks.release()
    for port in (checks.owner,4):
        effects=checks.counter_plan if port==4 else checks.plan[port]
        for i,effect in enumerate(effects):checks.write_accepted(port,NS(accepted_tick=280+2*i,
            value=raw_counter(effect) if port==4 else deepcopy(effect)))
    empty=deepcopy(row)
    for p in empty['writes']:p.update(valid=0,ready=1)
    checks.capture_state(NS(tick=300),empty);checks.raise_failure()
    consumers(checks,program,committed=True)
    model,event,anchor=program
    for i,pc in enumerate(PCS):
        token=revisit(model,event,anchor,after_earlier_branch(pc))
        checks.sibling(NS(token=token,prediction_tick=400+i*10,meta_tick=404+i*10),i)


def test_two_distinct_records_reclassify_completely_and_both_later_siblings_survive():
    checks,row,program,retired=armed(reclassify=True);main=program[0].sources.main
    checks.pending()
    assert entry_plan(main,0,0)==((),(),tuple(reclassification_effect(pc) for pc in PCS),())
    assert main.entries[0,0].overflows==main.directions[0,0].drops==0
    assert checks.coverage.groups['checked'].coverage==0
    release_and_service(checks,row,program)
    assert checks.coverage.groups['checked'].coverage==0 and not retired
    for i,pc in enumerate(PCS):
        token=checks.new[i].token
        assert (token.middle.branch.position,token.middle.branch.target)==(PEER_POSITION,new_target(pc))
        entries=source_entries(token.lookup)[0]
        assert tuple((e.position,e.kind,e.counter) for e in entries)==((0,0,0),(0,0,0),(PEER_POSITION,3,2),(POSITION,3,2),(0,0,0))
        assert token.lookup.banks[0].entries[3].target.at(pc)==old_target(pc)
    checks.finish()
    assert len(retired)==10 and checks.closed and all(g.coverage==100 for g in checks.coverage.groups.values())


@pytest.mark.parametrize('field',('row','tag','position','kind','action','carry','offset'))
def test_every_full_proposal_field_remains_compared_for_both_logical_records(field):
    checks,_,_,row,_,_=fixture(reclassify=True);actual=deepcopy(row)
    wrong=deepcopy(checks.plan[2][1]);wrong[field]^=1
    # A valid proposal for record A precedes the deliberately wrong record B.
    actual['incoming'][2].update(valid=1,bits=checks.plan[2][0]);checks.capture_state(NS(tick=202),actual)
    checks.raise_failure()
    actual['incoming'][2]['bits']=wrong;checks.capture_state(NS(tick=204),actual)
    with pytest.raises(AssertionError):checks.raise_failure()
    assert len(checks.proposals)==1 and checks.coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('fault',('missing-record','wrong-head-record','stale-type','wrong-direction-owner','wrong-counter','lost-direction','dirty-loss','read-gap'))
def test_full_retention_cannot_be_satisfied_by_a_pulse_or_one_record_only(fault):
    checks,row,_,_=armed(reclassify=True);checks.pending();actual=deepcopy(row)
    if fault=='missing-record':actual['writes'][2]['valid']=0
    elif fault=='wrong-head-record':actual['writes'][2]['bits']=checks.plan[2][1]
    elif fault=='stale-type':actual['writes'][2]['bits']['kind']=1
    elif fault=='wrong-direction-owner':actual['writes'][4]['bits']['mask']=2
    elif fault=='wrong-counter':actual['writes'][4]['bits']['counters']=(0,2)
    elif fault=='lost-direction':actual['queue']['full']=1
    elif fault=='dirty-loss':actual['dirty']=((1,0),(0,0))
    else:actual['read']['valid']=0
    before=deepcopy(checks.pipeline.model.sources.main.state())
    checks.capture_state(NS(tick=222),actual)
    with pytest.raises(AssertionError):checks.finish()
    assert checks.pipeline.model.sources.main.state()==before and checks.coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('fault',('wrong-owner','partial-type','other-record','duplicate','before-release'))
def test_only_two_complete_ordered_services_on_the_owned_record_path_are_allowed(fault):
    checks,row,program,_=armed(reclassify=True);checks.pending()
    if fault!='before-release':consumers(checks,program,committed=False);checks.release()
    value=deepcopy(checks.plan[2][0]);port=2
    if fault=='wrong-owner':port=1
    elif fault=='partial-type':value['kind']=1
    elif fault=='other-record':value=checks.plan[2][1]
    elif fault=='duplicate':
        checks.write_accepted(2,NS(accepted_tick=280,value=value))
        checks.write_accepted(2,NS(accepted_tick=282,value=checks.plan[2][1]))
    with pytest.raises(AssertionError):checks.write_accepted(port,NS(accepted_tick=284,value=value))
    assert checks.coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('fault',('no-old-consumer','no-service','wrong-repair-window','changed-original','missing-endpoint','missing-sibling'))
def test_endpoint_and_sibling_comparisons_cannot_be_omitted(fault):
    checks,row,program,_=armed(reclassify=True);checks.pending()
    with pytest.raises(AssertionError):
        if fault=='no-old-consumer':checks.release()
        elif fault=='no-service':consumers(checks,program,committed=True)
        else:
            release_and_service(checks,row,program)
            if fault=='changed-original':checks.snapshots=();checks.finish()
            elif fault=='missing-endpoint':checks.new.pop(1);checks.finish()
            elif fault=='missing-sibling':checks.siblings.clear();checks.finish()
            else:
                checks.pipeline.corrections_for_source=lambda _:((999,3),)
                checks.consumed(checks.new[0],0,committed=True)
    assert checks.coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('fault',('base-PC','old-request','wrong-target','wrong-position','wrong-counter','wrong-repair','duplicate'))
def test_sibling_credit_requires_a_new_actual_selected_offset_consumer(fault):
    from dataclasses import replace
    checks,row,program,_=armed(reclassify=True);checks.pending();release_and_service(checks,row,program)
    source=checks.siblings.pop(0);token=source.token
    if fault=='duplicate':checks.siblings[0]=source
    elif fault=='base-PC':token=checks.new[0].token
    elif fault=='old-request':source=NS(token=token,prediction_tick=100,meta_tick=104)
    elif fault=='wrong-repair':checks.pipeline.corrections_for_source=lambda _:((999,2),)
    elif fault in ('wrong-target','wrong-position'):
        branch=token.middle.branch;field='target' if fault=='wrong-target' else 'position'
        token=replace(token,middle=replace(token.middle,branch=replace(branch,**{field:getattr(branch,field)^1})))
    else:
        bank=token.lookup.banks[0];bank=replace(bank,counters=(*bank.counters[:3],0))
        token=replace(token,lookup=replace(token.lookup,banks=(bank,*token.lookup.banks[1:])))
    source=NS(token=token,prediction_tick=source.prediction_tick,meta_tick=source.meta_tick)
    with pytest.raises(AssertionError):checks.sibling(source,0)
    assert checks.coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('missing',range(6))
def test_every_reclassification_event_obligation_is_required_in_each_group(missing):
    coverage=MainServiceCoverage(reclassify=True);rules=main_service_rules('reclassification')
    for status in ('reached','checked'):
        for i,rule in enumerate(rules):
            if i!=missing:coverage.record(status,rule,10+i)
    with pytest.raises(AssertionError):coverage.finish()


def test_stale_nomination_is_not_silently_mixed_with_current_reclassification_profile():
    with pytest.raises(ValueError):MainServiceCoverage(stale=True,reclassify=True)
    with pytest.raises(ValueError):MainServiceChecks(None,None,stale=True,reclassify=True)
