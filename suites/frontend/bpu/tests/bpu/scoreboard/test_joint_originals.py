"""Independent read-view and latest-direction obligations, without a DUT."""
from pathlib import Path
import ast
import json
import pytest
from suites.frontend.bpu.bpu.model.joint_originals import Program,PROFILES,RULES
from suites.frontend.bpu.bpu.coverage.joint_originals import Coverage
from suites.frontend.bpu.sc.model.semantic import ScReference,Events,Context,decide
from suites.frontend.bpu.sc.transaction.types import ScHistory,ScBaseBranch,ScBatchTraining,ScBranchFeedback
from suites.frontend.bpu.tage.model.semantic import TageReference,Events as TageEvents,Context as TageContext,Feedback,Branch,Hint,coordinate

pytestmark=pytest.mark.toffee_functional_coverage(False)


@pytest.mark.parametrize('profile',PROFILES)
def test_program_separates_executable_outcomes_and_feedback_age_order(profile):
    p=Program(profile)
    assert p.truths[0] and p.iterations[1]==p.iterations[0]+1 and p.old_iteration>0
    assert tuple(p.truths[i] for i in p.arrival_order)==p.arrival_truths
    assert p.fresh_counter in (6,7) and not p.state()['physical_enumeration']
    assert not p.state()['serialized_shared_atomicity_required']
    assert p.require_feedback_window(110,100)==20


@pytest.mark.parametrize('profile',PROFILES)
@pytest.mark.parametrize('gap',(1,5))
def test_shared_experience_follows_the_owned_read_view_not_assumed_serial_equivalence(profile,gap):
    p=Program(profile);m=ScReference()
    branches=(ScBaseBranch(p.position,6),*(ScBaseBranch(i,0,0,0,0) for i in (0,2,3,4,5,6,7,8,9)))
    histories=tuple(ScHistory(0x93,255,15,i) for i in p.iterations)
    if p.trained:
        teacher=decide(m.snapshot(p.b,Context.from_history(histories[0])),branches,m.thresholds.values)
        tx=ScBatchTraining(p.b,teacher.metadata(),(ScBranchFeedback(p.position,1,0),),histories[0])
        m.advance(Events(feedback=tx,feedback_context=Context.from_history(histories[0])))
        for _ in range(12):m.advance()
    originals=tuple(decide(m.snapshot(p.b,Context.from_history(h)),branches,m.thresholds.values) for h in histories)
    tx=tuple(ScBatchTraining(p.b,o.metadata(),(ScBranchFeedback(p.position,int(t),0),),h)
        for o,t,h in zip(originals,p.truths,histories,strict=True))
    accepted=[]
    for tick in range(gap+12):
        age=p.arrival_order[0] if tick==0 else p.arrival_order[1] if tick==gap else None
        m.advance(Events(feedback=None if age is None else tx[age],feedback_context=Context() if age is None else Context.from_history(histories[age])))
        if age is not None:accepted.append(m.learning[1])
    for i,h in zip(p.iterations,histories,strict=True):
        assert m.snapshot(p.b,Context.from_history(h)).weights==p.expected_weights(i,serial=gap==5)
    assert accepted[0].weights==p.training_weights(p.iterations[p.arrival_order[0]])
    if gap==1:
        assert all(read.weights==p.training_weights(p.iterations[age]) for read,age in zip(accepted,p.arrival_order,strict=True))
    shared=lambda read:tuple(read.weights[i] for i in (0,1,2,3,4,5,7))
    assert (shared(accepted[0])==shared(accepted[1]))==(gap==1)


@pytest.mark.parametrize('profile',PROFILES)
def test_TAGE_latest_experience_composes_while_original_hints_remain_six(profile):
    p=Program(profile);m=TageReference();context=TageContext.from_recent(0x93)
    def outcome(taken,counter):
        return Feedback(p.b,context,(Branch(p.position,taken,1,not taken,True,
            hint=Hint(provider=True,use_provider=True,table=3,counter=counter)),))
    m.advance(TageEvents(feedback=outcome(True,5)))
    for _ in range(12):m.advance()
    bank,row,tag=coordinate(p.b,context,3)
    assert m.memory[3,bank,row,0].counter==6
    originals=tuple(outcome(v,6) for v in p.truths)
    accepted=[];mature=[]
    for i in p.arrival_order:
        m.advance(TageEvents(feedback=originals[i]));accepted.append(m.accepted.feedback)
    for _ in range(12):
        m.advance()
        if m.mature is not None:mature.append(m.mature.feedback)
    assert len(mature)==2 and all(a is b for a,b in zip(accepted,mature,strict=True))
    if p.truths==(True,True):
        assert accepted[0]==accepted[1] and accepted[0] is not accepted[1]
    assert m.memory[3,bank,row,0].counter==p.fresh_counter
    assert all(o.branches[0].hint.counter==6 for o in originals)


@pytest.mark.parametrize('missing',RULES)
def test_every_original_and_effect_is_required_before_checked_credit(missing):
    c=Coverage(PROFILES[0])
    for rule in RULES:
        if rule!=missing:c.record(rule,10)
    with pytest.raises(AssertionError):c.finish()
    assert c.groups['checked'].coverage==0


@pytest.mark.parametrize('profile',PROFILES)
def test_each_program_owns_only_its_sixteen_obligations(profile):
    c=Coverage(profile)
    for rule in RULES:c.record(rule,10)
    c.finish();counts=c.groups['checked'].report()['points'][0]['counts']
    assert len(counts)==256 and {k for k,v in counts.items() if v}=={profile+'.'+r for r in RULES}


def test_contract_is_human_semantics_and_exactly_matches_the_registered_point():
    root=Path(__file__).resolve().parents[3]
    contract=json.loads((root/'docs/bpu-joint-originals-contract.json').read_text())
    point=next(r for r in json.loads((root/'verification_plan.json').read_text())['features'] if r['id']==contract['feature'])
    assert point['contract']=={k:contract[k] for k in ('event','owner','effect','observation','preservation','scope')}
    assert point['metadata']['semantic_requirements']==contract['program']
    assert not contract['bank_set_way_enumeration'] and not contract['RTL_DUT_SDK_changes']


def test_public_memory_direct_layout_has_every_complete_training_response_word():
    import yaml
    from suites.frontend.bpu.bpu.bundle.statistical import TABLES
    root=Path(__file__).resolve().parents[3]
    layout=yaml.load((root/'dut/bpu/BpuDut_offset.yaml').read_bytes(),Loader=yaml.CSafeLoader)
    names={r['name'] for field in ('variables','signals') for r in layout.get(field,())}
    anchor,=[n for n in names if n.endswith('.sc.io_trainReady')]
    prefix=anchor.removesuffix('io_trainReady')
    assert {prefix+f'{table}.io_trainReadResp_{i}_ctr_value' for table in TABLES for i in range(32 if table=='biasTable' else 8)}<=names


def test_case_and_bundle_keep_dynamic_and_static_responsibilities_separate():
    root=Path(__file__).resolve().parents[3]/'bpu'
    case=ast.parse((root/'case/joint_originals.py').read_text())
    names={n.id for n in ast.walk(case) if isinstance(n,ast.Name)}|{n.attr for n in ast.walk(case) if isinstance(n,ast.Attribute)}
    assert not names&{'FallingEdge','RisingEdge','ClockCycles','gather','create_task','sleep','set_','get'}
    bundle=ast.parse((root/'bundle/joint_originals.py').read_text())
    assert not any(isinstance(n,(ast.Await,ast.AsyncFunctionDef)) for n in ast.walk(bundle))


def test_reused_single_source_setup_cannot_award_two_original_credit():
    from suites.frontend.bpu.bpu.checker.joint_originals import Checks
    c=Checks.__new__(Checks);c.phase='prepare';c.preparation=set();c.coverage=Coverage(PROFILES[0])
    def check(expected,actual,point):assert expected==actual,point
    c.check=check
    c.mark('valid-nonzero-original')
    assert c.preparation=={'valid-nonzero-original'} and not c.coverage.reached
    c.phase='learning'
    with pytest.raises(AssertionError):c.mark('cold-unused-control')
