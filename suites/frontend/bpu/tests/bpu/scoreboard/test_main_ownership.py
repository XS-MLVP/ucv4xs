"""Synthetic exact-source and corruption contracts, not native DUT evidence."""
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace as NS

import pytest

from suites.frontend.bpu.bpu.checker.pipeline import PipelineChecker,public_main_metadata
from suites.frontend.bpu.bpu.model.main_sources import BranchTargetSources,source_entries
from suites.frontend.bpu.bpu.model.selection import Kind
from suites.frontend.bpu.bpu.model.pipeline import Redirect
from suites.frontend.bpu.bpu.transaction.types import BpuBatchTraining,BpuBranchFeedback
from tests.bpu.scoreboard.test_main_sources import ENABLED
from tests.bpu.scoreboard.test_pipeline_checking import fixture_row
from tests.bpu.scoreboard.test_semantic_pipeline import PC,boot


def step(checker,event,*,training=None):
    row = fixture_row(checker,event)
    if training is not None:row['inputs']['training'] = training
    checker.capture(row,NS(tick=checker.last_tick+2))
    checker.raise_failure()


def ready():
    checker = PipelineChecker(sources=BranchTargetSources())
    checker.model,event = boot(checker.model.sources)
    checker.initialized,checker.last_tick = True,100
    event = replace(event,enabled=ENABLED)
    for _ in range(8):step(checker,event)
    tick,token = next((tick,token) for tick,token in checker.source_receipts.items() if token.lookup is not None)
    branch = token.early.branch
    entries = source_entries(token.lookup)
    public = tuple(tuple(dict(rawHit=int(source.hit),position=source.position,
        attribute=dict(branchType=source.kind,rasAction=source.action),counter_value=source.counter)
        for source in row) for row in entries)
    source = NS(prediction_tick=checker.s1_accepts[token.sequence],meta_tick=tick,
        prediction=NS(start_pc=token.pc,target=branch.target,taken=int(branch.taken),position=branch.position,
            s2_override=0,s3_override=0),
        meta=NS(perf=NS(start_pc=token.pc),redirect=dict(phr=token.history.metadata()),
            resolve=dict(phr=token.history.metadata(),mbtb_entries=public)))
    tx = BpuBatchTraining(token.pc,source.meta.resolve,(BpuBranchFeedback(4,token.pc+0x400,1,mispredict=1),))
    return checker,event,source,tx


def input_bits(source,tx):
    branches = []
    for index in range(8):
        branch = tx.branches[index] if index<len(tx.branches) else None
        branches.append(dict(valid=int(branch is not None),position=0 if branch is None else branch.position,
            target=0 if branch is None else branch.target,kind=0 if branch is None else branch.branch_type,
            action=0 if branch is None else branch.ras_action,taken=0 if branch is None else branch.taken,
            mispredict=0 if branch is None else branch.mispredict))
    return dict(valid=1,ready=1,pc=tx.pc,history=tx.resolve_meta['phr'],
        main=public_main_metadata(source.meta.resolve['mbtb_entries']),branches=branches)


def test_feedback_uses_the_exact_published_token_and_release_removes_its_receipt():
    checker,event,source,tx = ready()
    token = checker.source_token(source)
    checker.plan_feedback(source,tx)
    idle = replace(event,prediction_ready=False)
    for _ in range(4):step(checker,idle)
    step(checker,idle,training=input_bits(source,tx))
    assert checker.last_resolution[1].origin is token
    assert not checker.feedback_plans
    assert checker.resolutions_for_source(source)==(checker.last_resolution,)
    checker.retire_source(source.meta_tick)
    assert token.sequence not in checker.source_resolutions
    assert token.sequence not in checker.s1_accepts and source.meta_tick not in checker.source_receipts
    with pytest.raises(ValueError,match='already retired'):checker.retire_source(source.meta_tick)
    with pytest.raises(AssertionError):checker.source_token(source)


@pytest.mark.parametrize('fault',('prediction-tick','metadata-tick','pc','target','taken','position','history','raw-hit'))
def test_forged_receipt_never_chooses_a_nearby_same_pc_source_or_changes_owned_state(fault):
    checker,event,source,tx = ready()
    if fault=='prediction-tick':source.prediction_tick += 2
    elif fault=='metadata-tick':source.meta_tick += 1
    elif fault=='pc':source.prediction.start_pc ^= 1
    elif fault=='target':source.prediction.target ^= 1
    elif fault=='taken':source.prediction.taken ^= 1
    elif fault=='position':source.prediction.position ^= 1
    elif fault=='history':source.meta.redirect['phr']['phrLowBits'] ^= 1
    else:source.meta.resolve['mbtb_entries'][0][0]['rawHit'] ^= 1
    state = deepcopy(checker.model.state()),deepcopy(checker.model.sources.main.state())
    with pytest.raises(AssertionError) as first:checker.plan_feedback(source,tx)
    with pytest.raises(AssertionError) as second:checker.source_token(source)
    assert first.value is second.value
    assert not checker.feedback_plans
    assert (checker.model.state(),checker.model.sources.main.state())==state


@pytest.mark.parametrize('fault',('unplanned','pc','history','metadata','target','taken','position','kind','action','mispredict','extra-valid'))
def test_wrong_actual_feedback_cannot_borrow_a_planned_owner(fault):
    checker,event,source,tx = ready()
    if fault!='unplanned':checker.plan_feedback(source,tx)
    bits = input_bits(source,tx)
    if fault=='pc':bits['pc'] ^= 1
    elif fault=='history':bits['history']=deepcopy(bits['history']);bits['history']['phrLowBits'] ^= 1
    elif fault=='metadata':bits['main'][0][0]['hit'] ^= 1
    elif fault=='extra-valid':bits['branches'][3]['valid']=1
    elif fault!='unplanned':bits['branches'][0][fault] ^= 1
    state = deepcopy(checker.model.state()),deepcopy(checker.model.sources.main.state())
    with pytest.raises(AssertionError):step(checker,event,training=bits)
    assert (checker.model.state(),checker.model.sources.main.state())==state


def test_pending_owner_cannot_be_released_and_reset_expires_all_old_receipts():
    checker,event,source,tx = ready()
    checker.plan_feedback(source,tx)
    with pytest.raises(ValueError,match='planned'):checker.retire_source(source.meta_tick)
    step(checker,replace(event,reset=True))
    assert not checker.feedback_plans and not checker.source_receipts and not checker.s1_accepts
    assert not checker.source_resolutions
    with pytest.raises(AssertionError):checker.source_token(source)


def test_wrong_public_main_metadata_is_not_ignored_while_publishing_source():
    checker,event,_,_ = ready()
    for _ in range(8):
        row = fixture_row(checker,event)
        if row['observed']['metadata']['valid']:
            row['observed']['metadata']['main'][1][1]['hit'] ^= 1
            before = set(checker.source_receipts)
            checker.capture(row,NS(tick=checker.last_tick+2))
            with pytest.raises(AssertionError):checker.raise_failure()
            assert set(checker.source_receipts)==before
            return
        step(checker,event)
    raise AssertionError('synthetic publication boundary was not reached')


def test_mutating_a_planned_payload_does_not_rewrite_the_expected_accepted_input():
    checker,event,source,tx = ready()
    checker.plan_feedback(source,tx)
    tx.resolve_meta['phr']['phrLowBits'] ^= 1
    with pytest.raises(AssertionError):step(checker,event,training=input_bits(source,tx))
    assert len(checker.feedback_plans)==1


def learned_receipt():
    checker,event,source,tx = ready()
    idle = replace(event,prediction_ready=False)
    for _ in range(4):step(checker,idle)
    checker.plan_feedback(source,tx)
    step(checker,idle,training=input_bits(source,tx))
    for _ in range(8):step(checker,idle)
    anchor = checker.source_receipts[source.meta_tick]
    step(checker,replace(idle,redirect=Redirect(anchor.history,anchor.pc+4,anchor.pc,False)))
    for _ in range(5):step(checker,event)
    at,token = next((at,token) for at,token in reversed(tuple(checker.source_receipts.items()))
        if token.pc==anchor.pc and token.sequence!=anchor.sequence and any(
            entry.hit for row in source_entries(token.lookup) for entry in row))
    branch = token.early.branch
    entries = tuple(tuple(dict(rawHit=int(entry.hit),position=entry.position,
        attribute=dict(branchType=entry.kind,rasAction=entry.action),counter_value=entry.counter)
        for entry in row) for row in source_entries(token.lookup))
    actual = NS(prediction_tick=checker.s1_accepts[token.sequence],meta_tick=at,
        prediction=NS(start_pc=token.pc,target=branch.target,taken=int(branch.taken),position=branch.position,
            s2_override=0,s3_override=0),meta=NS(perf=NS(start_pc=token.pc),
                redirect=dict(phr=token.history.metadata()),resolve=dict(phr=token.history.metadata(),mbtb_entries=entries)))
    return checker,event,actual,anchor,token


def test_equal_pc_history_can_have_different_reads_but_exact_receipt_keeps_new_owner():
    checker,event,source,old,new = learned_receipt()
    assert old.pc==new.pc and old.history.metadata()==new.history.metadata()
    assert source_entries(old.lookup)!=source_entries(new.lookup)
    assert checker.source_token(source) is new
    assert checker.source_token(source) is not old


@pytest.mark.parametrize('field',('position','kind','action','counter'))
def test_each_defined_hit_field_is_compared_without_rebasing_to_another_lookup(field):
    checker,event,source,old,new = learned_receipt()
    actual = next(entry for row in source.meta.resolve['mbtb_entries'] for entry in row if entry['rawHit'])
    if field=='kind':actual['attribute']['branchType'] ^= 1
    elif field=='action':actual['attribute']['rasAction'] ^= 1
    else:actual['counter_value' if field=='counter' else field] ^= 1
    before = deepcopy(checker.model.sources.main.state())
    with pytest.raises(AssertionError):checker.source_token(source)
    assert checker.model.sources.main.state()==before


def test_undefined_miss_payload_is_not_compared_as_a_real_branch():
    checker,event,source,_ = ready()
    for row in source.meta.resolve['mbtb_entries']:
        for entry in row:
            assert entry['rawHit']==0
            entry['position'],entry['counter_value'] = 15,3
            entry['attribute'].update(branchType=3,rasAction=3)
    assert checker.source_token(source).lookup is not None


def test_owned_acceptance_receipts_are_not_limited_by_recent_diagnostic_history():
    checker,event,source,tx=ready()
    idle=replace(event,prediction_ready=False)
    for _ in range(4):step(checker,idle)
    expected=[]
    # This deliberately exercises more than the diagnostic deque's capacity,
    # not a required hardware delay or physical-address coverage sweep.
    for _ in range(checker.resolutions.maxlen+1):
        checker.plan_feedback(source,tx)
        step(checker,idle,training=input_bits(source,tx))
        expected.append(checker.last_resolution)
        for _ in range(8):step(checker,idle)
    assert len(checker.resolutions)<len(expected)
    assert checker.resolutions_for_source(source)==tuple(expected)
    checker.retire_source(source.meta_tick)
    assert not checker.source_resolutions
