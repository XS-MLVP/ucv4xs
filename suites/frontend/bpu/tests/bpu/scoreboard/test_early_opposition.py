"""Independent semantic program plus corrupted actual/proof boundaries."""
from dataclasses import replace
from types import SimpleNamespace as NS
import pytest

from suites.frontend.bpu.bpu.checker.early_direction import live_values,fast_values
from suites.frontend.bpu.bpu.checker.early_opposition import EarlyOppositionChecks
from suites.frontend.bpu.bpu.coverage.early_opposition import EarlyOppositionCoverage,RULES,EXTRA_RULES
from suites.frontend.bpu.bpu.model.early_opposition import provider,ahead_owner,main_counter,is_opposed,stable_negative,steady_history,loop_history,FALLBACK
from suites.frontend.bpu.bpu.model.pipeline import Redirect
from suites.frontend.bpu.bpu.model.selection import Kind
from tests.bpu.scoreboard.test_early_direction_checking import Program as LearningProgram,actual_live,actual_fast


class Program(LearningProgram):
    fallback_position = FALLBACK
    def __init__(self,pc=0x40000000):
        super().__init__(pc)
        self.named=[];self.corrections={}
        self.checks.pipeline.corrections_for_source=lambda source:tuple(self.corrections.get(source.token.sequence,()))
        self.checks.pipeline.source_receipts={}
        def retire(tick):self.retired.append(tick);self.checks.pipeline.source_receipts.pop(tick,None)
        self.checks.pipeline.retire_source=retire

    def make_checks(self,pc,tag_class):return EarlyOppositionChecks(EarlyOppositionCoverage(),pc)

    def receipt(self,token):
        source=NS(token=token,prediction_tick=self.tick-4,meta_tick=self.tick)
        self.named.append(source);self.checks.pipeline.source_receipts[source.meta_tick]=token
        return source

    def step(self,event=None,*,mutate=None):
        event=self.event if event is None else event;cycle=self.model.evaluate(event);self.tick+=2
        self.checks.candidates({},event,cycle,self.model,'synthetic',None);self.checks.reached(self.tick)
        observed=actual_live(self.model.sources,cycle.enabled[1])
        if mutate is not None:mutate(observed)
        expected,actual=live_values(self.model.sources,cycle.enabled[1],observed)
        try:self.checks.pipeline.board.check(expected=expected,actual=actual)
        except Exception as error:self.checks.failure=error;raise
        expected,actual=fast_values(self.model.sources,cycle,actual_fast(self.model.sources,cycle))
        assert expected==actual
        for token,stage,repair in ((cycle.tokens[1],2,cycle.middle_repair),(cycle.tokens[2],3,cycle.final_repair)):
            if token is not None and repair:self.corrections.setdefault(token.sequence,[]).append((self.tick,stage))
        self.model.advance(event);self.checks.checked(self.tick)
        return cycle

    def quiet(self):
        idle=super().quiet()
        # A learning write is only predicted at this boundary. Close the next
        # actual-state comparison if it still has an outstanding obligation.
        if self.checks.pending_effect is not None:self.step(idle)
        return idle

    def query(self,source):
        result=super().query(source);self.named.append(result)
        self.checks.pipeline.source_receipts[result.meta_tick]=result.token
        return result

    def enable(self,value):
        self.event=replace(self.event,enabled=(False,value,True,False,False,False,False))
        self.quiet()

    def until(self,source,predicate,*,settle=True):
        idle=self.quiet();self.step(replace(idle,redirect=Redirect(source.token.history,(self.pc//16)*16+FALLBACK,self.pc,True)))
        for _ in range(256):
            token=self.step().metadata
            if token is not None and token.pc==self.pc and predicate(token):
                result=self.receipt(token)
                if settle:self.quiet()
                return result
        raise AssertionError('independent semantic opposition precondition did not retire')

    def steer(self,source,goal):
        self.enable(False);source=self.query(source)
        for _ in range(4):
            counter=main_counter(source.token)
            if counter==goal:return self.until(source,lambda token:main_counter(token)==goal and steady_history(token,2 if goal else FALLBACK))
            taken=counter<goal;idle=self.quiet()
            request=self.feedback(source.token,2,Kind.CONDITIONAL,taken)
            request=replace(request,branches=(replace(request.branches[0],mispredict=(counter>=2)!=taken),))
            self.step(replace(idle,feedback=request));self.quiet();source=self.query(source)
        raise AssertionError('Main direction did not reach its semantic endpoint')

    def strong(self):
        negative=self.learned();self.checks.negative_consumer(negative)
        result=self.until(negative,lambda token:stable_negative(self.model.sources,token))
        self.checks.strong_negative(result);return result

    def prepared(self):
        strong=self.strong();positive=self.steer(strong,3);self.enable(True)
        def biased(token):
            sources=self.model.sources;owner=ahead_owner(sources,token);frame=sources.short_snapshot(token).prediction.frame
            return main_counter(token)==3 and steady_history(token,2) and owner is not None and owner[1]==3 and frame is not None and frame.read.indices[self.checks.protected[0]]!=self.checks.protected[1]
        positive=self.until(positive,biased);self.checks.positive_base(positive)
        negative=self.steer(positive,0);self.checks.main_negative(negative);return negative

    def opposed(self,*,settle=True):
        prepared=self.prepared();self.enable(True)
        return self.until(prepared,lambda token:is_opposed(self.model.sources,token),settle=settle)


def test_complete_independent_program_changes_first_taken_branch_and_proves_useful_later():
    program=Program();source=program.opposed();checks=program.checks
    assert checks.confirmed_increases and checks.coverage.groups['checked'].coverage==0
    assert all(written+2==compared and after>before for _,written,compared,before,after in checks.confirmed_increases)
    checks.opposed_consumer(source);checks.finish_opposition(program.named)
    assert checks.closed and len(set(program.retired))==len(program.retired)>4
    assert not checks.pipeline.source_receipts
    assert all(group.coverage==100 for group in checks.coverage.groups.values())


@pytest.mark.parametrize('fault',('no-preparation','too-early','not-opposed','wrong-position','wrong-target','wrong-kind','not-taken',
    'wrong-source-code','wrong-key','uncompared-owner','extra-repair'))
def test_wrong_or_unqualified_opposed_consumer_latches_without_checked_credit(fault):
    program=Program();source=program.opposed();checks=program.checks
    if fault=='no-preparation':checks.prepared=None
    elif fault=='too-early':source=NS(token=source.token,prediction_tick=checks.prepared.meta_tick,meta_tick=source.meta_tick)
    elif fault=='not-opposed':source=checks.positive
    elif fault=='wrong-key':checks.protected=(checks.protected[0],checks.protected[1]+1)
    elif fault=='uncompared-owner':checks.opposed_owners.clear()
    elif fault=='extra-repair':program.corrections[source.token.sequence]=[(source.prediction_tick+2,2)]
    else:
        token=source.token
        if fault=='wrong-source-code':token=replace(token,early=replace(token.early,source='ahead'))
        else:
            field,value={'wrong-position':('position',2),'wrong-target':('target',program.pc+2),
                'wrong-kind':('kind',Kind.CONDITIONAL),'not-taken':('taken',False)}[fault]
            token=replace(token,early=replace(token.early,branch=replace(token.early.branch,**{field:value})))
        source=NS(token=token,prediction_tick=source.prediction_tick,meta_tick=source.meta_tick)
    with pytest.raises(AssertionError) as first:checks.opposed_consumer(source)
    with pytest.raises(AssertionError) as repeated:checks.finish_opposition()
    assert repeated.value is first.value and checks.coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('fault',('no-consumer','no-confirmation','pending-effect','old-snapshot-rebased'))
def test_incomplete_or_rebased_effects_cannot_close_opposition(fault):
    program=Program();source=program.opposed();checks=program.checks
    if fault!='no-consumer':checks.opposed_consumer(source)
    if fault=='no-confirmation':checks.confirmed_increases.clear()
    elif fault=='pending-effect':checks.pending_effect=('not-confirmed',)
    elif fault=='old-snapshot-rebased':
        receipt,snapshot=next(iter(checks.saved_sources.values()))
        checks.saved_sources[receipt.meta_tick]=(receipt,replace(snapshot,end_position=15))
    with pytest.raises(AssertionError):checks.finish_opposition(program.named)
    assert checks.coverage.groups['checked'].coverage==0 and not program.retired


def test_model_useful_increase_is_not_credit_before_next_actual_sample():
    program=Program();source=program.opposed(settle=False);checks=program.checks
    checks.opposed_consumer(source)
    for _ in range(8):
        if checks.pending_effect is not None:break
        program.step()
    assert checks.pending_effect is not None and not checks.confirmed_increases
    assert EXTRA_RULES[4] not in checks.reached_rules
    with pytest.raises(AssertionError):checks.finish_opposition()
    assert checks.coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('cell',((0,0),(1,511)))
def test_bad_complete_useful_state_blocks_effect_confirmation_and_keeps_reference_unchanged(cell):
    program=Program();source=program.opposed(settle=False);checks=program.checks
    checks.opposed_consumer(source)
    for _ in range(8):
        if checks.pending_effect is not None:break
        program.step()
    assert checks.pending_effect is not None and not checks.confirmed_increases
    before=program.model.sources.short.state()
    def corrupt(actual):
        table,index=cell;values=[list(row) for row in actual['useful']];values[table][index]^=1
        actual['useful']=tuple(tuple(row) for row in values)
    with pytest.raises(AssertionError) as first:program.step(mutate=corrupt)
    assert program.model.sources.short.state()==before and not checks.confirmed_increases
    with pytest.raises(AssertionError) as repeated:checks.finish_opposition()
    assert repeated.value is first.value and checks.coverage.groups['checked'].coverage==0


def test_unknown_feedback_owner_cannot_claim_an_opposed_useful_effect():
    program=Program();source=program.opposed(settle=False);checks=program.checks
    checks.opposed_consumer(source)
    checks.offers.clear()
    # Invalidate subsequent associations too: none of the real writes may
    # claim a named original source merely because table/index happen to match.
    for _ in range(8):
        program.step(replace(program.event,prediction_ready=False));checks.offers.clear()
    assert not checks.confirmed_increases and EXTRA_RULES[4] not in checks.reached_rules
    with pytest.raises(AssertionError):checks.finish_opposition()


@pytest.mark.parametrize('enabled',(False,True))
def test_useful_corruption_in_untouched_cell_is_not_hidden_by_sparse_encoding_or_enable(enabled):
    program=Program();program.strong();sources=program.model.sources
    observed=actual_live(sources,enabled);values=[list(row) for row in observed['useful']];values[1][511]=3
    observed['useful']=tuple(tuple(row) for row in values)
    expected,actual=live_values(sources,enabled,observed)
    assert '1.511' not in expected['useful_nonzero'] and actual['useful_nonzero']['1.511']==3
    with pytest.raises(AssertionError):program.checks.pipeline.board.check(expected=expected,actual=actual)


def test_disabled_naked_hit_bits_are_not_valid_responses_but_validity_remains_checked():
    program=Program();program.strong();sources=program.model.sources
    observed=actual_live(sources,False);observed['hits']=(1,)*4;observed['taken']=(1,)*4
    expected,actual=live_values(sources,False,observed)
    assert expected==actual and 'raw_hits' not in expected
    observed['meta']['entries'][0]['valid']=1
    expected,actual=live_values(sources,False,observed)
    with pytest.raises(AssertionError):program.checks.pipeline.board.check(expected=expected,actual=actual)


def test_active_owned_ahead_beat_checks_even_raw_lanes_without_a_conditional_source():
    program=Program();program.strong();sources=program.model.sources
    observed=actual_live(sources,True);empty=next(way for way,row in enumerate(observed['meta']['entries']) if not row['valid'])
    values=list(observed['hits']);values[empty]^=1;observed['hits']=tuple(values)
    expected,actual=live_values(sources,True,observed)
    assert 'raw_hits' in expected
    with pytest.raises(AssertionError):program.checks.pipeline.board.check(expected=expected,actual=actual)


@pytest.mark.parametrize('position,expected',((2,0xA0),(FALLBACK,0x10)))
def test_steady_loop_history_is_the_semantic_edge_fixed_point_not_a_wait_count(position,expected):
    from suites.frontend.bpu.bpu.model.path_history import path_contribution
    from suites.frontend.bpu.bpu.model.early_opposition import PC
    word=loop_history(PC,position)
    assert word==expected
    assert ((word<<2)^path_contribution(PC+position,PC))%512==word
    assert word%16==0  # Same Ahead history feature, distinct MicroTAGE keys.


@pytest.mark.parametrize('fault',('missing-table','truncated','extra-cell'))
def test_sparse_state_encoding_rejects_incomplete_static_vector_shapes(fault):
    program=Program();program.strong();sources=program.model.sources
    observed=actual_live(sources,True)
    if fault=='missing-table':observed['useful']=observed['useful'][:1]
    elif fault=='truncated':observed['useful']=(observed['useful'][0][:-1],observed['useful'][1])
    else:observed['useful']=(observed['useful'][0]+(0,),observed['useful'][1])
    with pytest.raises(ValueError,match='complete'):live_values(sources,True,observed)


@pytest.mark.parametrize('field,value',(('valid',False),('tag',17),('position',7),('counter',1)))
def test_a_zero_counter_snapshot_does_not_prove_a_live_steady_owner(monkeypatch,field,value):
    import suites.frontend.bpu.bpu.model.early_opposition as semantic
    program=Program();source=program.strong();sources=program.model.sources
    assert stable_negative(sources,source.token)
    original=semantic.resident(sources,program.checks.protected)
    monkeypatch.setattr(semantic,'resident',lambda _sources,_key:replace(original,**{field:value}))
    assert not stable_negative(sources,source.token)
