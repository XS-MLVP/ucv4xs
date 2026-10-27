"""Pure rejection controls: equivalent contents cannot impersonate query age."""
from dataclasses import replace
from types import SimpleNamespace
import pytest

from toffee import ScoreboardMismatch
from bpuverify.utage.model.semantic import Context,Events
from tests.utage.scoreboard.test_semantic_model import feedback,POSITIONS
from bpuverify.utage.model.read_lifetime import Program,PROFILES,RELATIONS,PC,RULES
from tests.utage.scoreboard.test_read_lifetime_model import prepared,bases
from bpuverify.utage.checker.read_lifetime import Checks,values
from bpuverify.utage.coverage.read_lifetime import Coverage



def witnesses(p):
    model,teacher=prepared(p)
    request=feedback(teacher,taken=bool(p.actual))
    query=Events(read_pc=PC,read_context=Context.from_recent(p.history),select=True,pc=PC,
        context=Context.from_recent(p.history),positions=POSITIONS,bases=bases(0),advance=True)
    model.advance(Events(feedback=request))
    model.advance()
    if p.relation=='read-with-write':
        model.advance(query)
        original=model.read
        effects=model.effects
    else:
        model.advance()
        effects=model.effects
        model.advance(query)
        original=model.read
    model.advance(query)
    expected=model.prediction.values()
    actual=SimpleNamespace(hit=expected['0.hit'],taken=expected.get('0.taken',0),
        meta=dict(abtbResult=[dict(tableId=expected.get('0.provider',0),takenCtr_value=expected.get('0.counter',0))]))
    read=dict(tick=20 if p.relation=='read-with-write' else 24,events=query,read=original)
    response=dict(tick=read['tick']+2,frame=model.frame,actual=actual)
    effect=dict(tick=20,effects=effects,native=dict(changes=p.changes()))
    return read,response,effect


@pytest.mark.parametrize('profile',PROFILES)
@pytest.mark.parametrize('relation',RELATIONS)
def test_model_derived_complete_lifetime_is_accepted(profile,relation):
    p=Program(profile,relation)
    Checks(p).lifetime(*witnesses(p))


FAULTS=('equal-but-younger-read','wrong-temporal-relation','wrong-read-pc','wrong-read-history',
    'wrong-read-index','wrong-response-pc','wrong-response-history','wrong-response-hit',
    'native-effect-missing','native-other-cell','wrong-reference-effect')


@pytest.mark.parametrize('profile',PROFILES)
@pytest.mark.parametrize('relation',RELATIONS)
@pytest.mark.parametrize('fault',FAULTS)
def test_wrong_version_wrong_owner_or_fabricated_overlap_is_rejected(profile,relation,fault):
    p=Program(profile,relation)
    read,response,effect=witnesses(p)
    if fault=='equal-but-younger-read':
        previous=read['read']
        read['read']=replace(previous,entries=tuple(list(previous.entries)))
        assert read['read']==previous and read['read'].entries is not previous.entries
    elif fault=='wrong-temporal-relation':read['tick']=22 if relation=='read-with-write' else 20
    elif fault=='wrong-read-pc':read['events']=replace(read['events'],read_pc=PC+2)
    elif fault=='wrong-read-history':read['events']=replace(read['events'],read_context=Context.from_recent(p.history^1))
    elif fault=='wrong-read-index':read['read']=replace(read['read'],indices=(1,1))
    elif fault=='wrong-response-pc':response['frame']=replace(response['frame'],pc=PC+2)
    elif fault=='wrong-response-history':response['frame']=replace(response['frame'],context=Context.from_recent(p.history^1))
    elif fault=='wrong-response-hit':response['actual'].hit^=1
    elif fault=='native-effect-missing':effect['native']['changes']=()
    elif fault=='native-other-cell':effect['native']['changes']+=((3,0,1),)
    else:effect['effects']=()
    with pytest.raises(ScoreboardMismatch) as error:Checks(p).lifetime(read,response,effect)
    assert error.value.context.request['program']==p.state()
    assert error.value.context.request['point']


@pytest.mark.parametrize('profile',PROFILES)
@pytest.mark.parametrize('relation',RELATIONS)
@pytest.mark.parametrize('missing',RULES)
def test_any_missing_semantic_obligation_prevents_checked_credit(profile,relation,missing):
    coverage=Coverage(Program(profile,relation))
    for rule in RULES:
        if rule!=missing:coverage.reach(rule)
    with pytest.raises(AssertionError,match='incomplete'):coverage.finish()
    assert coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('profile',PROFILES)
@pytest.mark.parametrize('relation',RELATIONS)
def test_complete_lifetime_credits_only_its_own_version_and_age_once(profile,relation):
    coverage=Coverage(Program(profile,relation))
    for rule in RULES:coverage.reach(rule)
    coverage.finish()
    assert coverage.groups['checked'].coverage==25
    with pytest.raises(AssertionError):coverage.finish()
    with pytest.raises(ValueError):coverage.reach(RULES[0])


def test_miss_does_not_turn_undefined_provider_or_direction_payload_into_an_oracle():
    p=Program('different-identity-replacement','read-after-write')
    read,response,effect=witnesses(p)
    response['actual'].taken=1
    response['actual'].meta['abtbResult'][0].update(tableId=1,takenCtr_value=7)
    assert values(response['actual'])==(0,None,None,None)
    Checks(p).lifetime(read,response,effect)


from copy import deepcopy
from bpuverify.utage.model.semantic import UtageReference
from bpuverify.utage.model.read_lifetime import LateReplacementProgram,REBUILD_PROFILES,REBUILD_RULES,MODES
from bpuverify.utage.coverage.read_lifetime import LateReplacementCoverage
from bpuverify.utage.checker.read_lifetime import LateReplacementChecks
from tests.utage.scoreboard.test_semantic_model import lookup,learn
from tests.utage.scoreboard.test_read_lifetime_model import values as model_values


def derived_rebuild(program):
    model=UtageReference();held={};saved=[];records=[];previous=[0]*1024;sequences=[0,0]
    def source(spec,expected=None):
        result=lookup(model,spec.pc,spec.history,read_pc=spec.read_pc,read_history=spec.history,bases=bases(spec.base))
        assert model_values(result)==(spec.expected if expected is None else expected)
        saved.append((result,deepcopy(result.frame)))
        return result
    def capture():
        nonlocal previous,sequences
        current=[values.get(index,0) for values in model.useful for index in range(512)]
        versions={}
        for table,cache in enumerate(model.updates):
            if sequences[table]==cache.sequence:continue
            version=cache.recent[-1];entry=version.entry
            versions[str(table)]=dict(sequence=version.sequence,depth=8,next=cache.sequence%8,
                new_cell=dict(valid=int(entry.valid),data_valid=int(entry.valid),index=version.index,
                    tag=entry.tag,position=entry.position,counter=entry.counter))
        ordinal=len(records)
        records.append(dict(tick=24+ordinal*2,versions=versions,aged=model.aged,
            changes=tuple((i,a,b) for i,(a,b) in enumerate(zip(previous,current,strict=True)) if a!=b)))
        previous=current;sequences=[cache.sequence for cache in model.updates]
    for step in program.steps[:-2]:
        if step.name=='B-enter':held['old-A-return']=source(program.old_a)
        original=source(step.source)
        learn(model,feedback(original,taken=bool(step.actual)));capture()
        assert tuple(previous)==program.protection_after(step.ordinal+1)
    held['old-B-return']=source(program.old_b)
    if program.mode=='adjacent':
        for step in program.steps[-2:]:model.advance(Events(feedback=feedback(held[step.name],taken=bool(step.actual))))
        model.advance();capture();model.advance();capture()
    else:
        for step in program.steps[-2:]:
            learn(model,feedback(held[step.name],taken=bool(step.actual)));capture()
            if step.name=='old-A-return':
                for spec,expected in program.consumers(after_a=True):source(spec,expected)
    for spec,expected in program.consumers(after_a=False):source(spec,expected)
    assert all(original.frame==snapshot for original,snapshot in saved)
    assert tuple(previous)==program.protection_after(len(program.steps))
    failures=int(program.mode=='serial')
    assert (model.low_tick,model.high_tick)==(failures,failures)
    return model,records


def rebuild_witnesses(program):
    model,records=derived_rebuild(program)
    checks=LateReplacementChecks(program)
    checks.sent=list(range(len(program.steps)))
    checks.originals=[dict(completed=1) for _ in program.steps]
    monitor=SimpleNamespace(records=records,failure=None,
        public=[dict(tick=20+i*2) for i in range(len(records))],
        all_protection=lambda:tuple(values.get(index,0) for values in model.useful for index in range(512)))
    return checks,monitor


@pytest.mark.parametrize('profile',REBUILD_PROFILES)
@pytest.mark.parametrize('mode',MODES)
def test_original_counter_rebuild_and_overlap_allocation_are_derived_from_normal_semantic_learning(profile,mode):
    program=LateReplacementProgram(profile,mode)
    checks,monitor=rebuild_witnesses(program)
    checks.prefix(monitor,len(program.steps))
    a,b=program.steps[-2:]
    assert a.after.counter!=(7 if not program.inverse else 0)
    assert b.after.counter!=(3 if not program.inverse else 4)
    assert b.companion==(mode=='adjacent')
    assert (program.old_a.indices[0],program.old_b.indices[0])==(0,0)
    assert program.state()['complete_short_tags']==(0,65)


REBUILD_FAULTS=('first-old-write-hidden-by-correct-second','second-old-uses-current-counter',
    'wrong-complete-tag','wrong-companion-owner','wrong-companion-cadence-policy',
    'missing-intermediate-write','wrong-write-chronology','wrong-pointer','other-protection-changed',
    'wrong-protection-endpoint','feedback-before-own-source-completes')


@pytest.mark.parametrize('profile',REBUILD_PROFILES)
@pytest.mark.parametrize('mode',MODES)
@pytest.mark.parametrize('fault',REBUILD_FAULTS)
def test_each_late_write_is_checked_even_when_the_final_other_owner_is_correct(profile,mode,fault):
    program=LateReplacementProgram(profile,mode)
    checks,monitor=rebuild_witnesses(program)
    row=monitor.records[-2]
    if fault=='first-old-write-hidden-by-correct-second':row['versions']['0']['new_cell']['counter']=0 if program.inverse else 7
    elif fault=='second-old-uses-current-counter':monitor.records[-1]['versions']['0']['new_cell']['counter']=4 if program.inverse else 3
    elif fault=='wrong-complete-tag':row['versions']['0']['new_cell']['tag']^=1<<8
    elif fault=='wrong-companion-owner':row['versions']['1']['new_cell']['tag']^=2
    elif fault=='wrong-companion-cadence-policy':
        if mode=='adjacent':monitor.records[-1]['versions'].pop('1')
        else:monitor.records[-1]['versions']['1']=deepcopy(row['versions']['1'])
    elif fault=='missing-intermediate-write':monitor.records.pop(-2)
    elif fault=='wrong-write-chronology':row['versions']['0']['sequence']-=1
    elif fault=='wrong-pointer':row['versions']['0']['next']^=1
    elif fault=='other-protection-changed':row['changes']+=((7,0,1),)
    elif fault=='wrong-protection-endpoint':
        values=list(monitor.all_protection());values[7]=1;monitor.all_protection=lambda:tuple(values)
    else:checks.originals[checks.sent[-2]]['completed']=monitor.public[-2]['tick']
    with pytest.raises(ScoreboardMismatch) as failure:checks.prefix(monitor,len(program.steps))
    assert failure.value.context.request['program']==program.state()
    assert failure.value.context.request['point']


@pytest.mark.parametrize('profile',REBUILD_PROFILES)
@pytest.mark.parametrize('mode',MODES)
@pytest.mark.parametrize('missing',REBUILD_RULES)
def test_any_unproved_old_owner_requirement_blocks_all_checked_credit(profile,mode,missing):
    coverage=LateReplacementCoverage(LateReplacementProgram(profile,mode))
    for rule in REBUILD_RULES:
        if rule!=missing:coverage.reach(rule)
    with pytest.raises(AssertionError,match='incomplete'):coverage.finish()
    assert coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('profile',REBUILD_PROFILES)
@pytest.mark.parametrize('mode',MODES)
def test_closed_old_owner_program_only_credits_its_own_direction_and_cadence(profile,mode):
    coverage=LateReplacementCoverage(LateReplacementProgram(profile,mode))
    for rule in REBUILD_RULES:coverage.reach(rule)
    coverage.finish()
    assert coverage.groups['checked'].coverage==25
    with pytest.raises(AssertionError):coverage.finish()
    with pytest.raises(ValueError):coverage.reach(REBUILD_RULES[0])


@pytest.mark.parametrize('profile,mode',((None,'serial'),('bank-sweep','serial'),(REBUILD_PROFILES[0],'queued')))
def test_unknown_or_physical_enumeration_rebuild_programs_are_rejected(profile,mode):
    with pytest.raises(ValueError):LateReplacementProgram(profile,mode)
