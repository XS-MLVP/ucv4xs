"""Only exact compared public sources may supply indirect feedback metadata."""
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace as NS

import pytest

from suites.frontend.bpu.bpu.checker.pipeline import PipelineChecker
from suites.frontend.bpu.bpu.model.indirect_sources import IndirectSources
from suites.frontend.bpu.bpu.model.main_sources import source_entries
from suites.frontend.bpu.bpu.transaction.types import BpuBatchTraining,BpuBranchFeedback
from tests.bpu.scoreboard.test_indirect_sources import ENABLED
from tests.bpu.scoreboard.test_main_ownership import step,input_bits
from tests.bpu.scoreboard.test_pipeline_checking import fixture_row
from tests.bpu.scoreboard.test_semantic_pipeline import boot


def ready():
    checker=PipelineChecker(sources=IndirectSources());checker.model,event=boot(checker.model.sources)
    checker.initialized,checker.last_tick=True,100;event=replace(event,enabled=ENABLED)
    for _ in range(9):step(checker,event)
    at,token=next((at,t) for at,t in checker.source_receipts.items() if t.lookup is not None
        and checker.model.sources.snapshot(t,resolved=True).prediction is not None)
    branch=token.early.branch
    entries=tuple(tuple(dict(rawHit=int(e.hit),position=e.position,attribute=dict(branchType=e.kind,rasAction=e.action),
        counter_value=e.counter) for e in row) for row in source_entries(token.lookup))
    source=NS(prediction_tick=checker.s1_accepts[token.sequence],meta_tick=at,
        prediction=NS(start_pc=token.pc,target=branch.target,taken=int(branch.taken),position=branch.position,s2_override=0,s3_override=0),
        meta=NS(perf=NS(start_pc=token.pc),redirect=dict(phr=token.history.metadata()),
            resolve=dict(phr=token.history.metadata(),mbtb_entries=entries,
                ittage=deepcopy(checker.model.sources.defined_ittage_metadata(token)))))
    tx=BpuBatchTraining(token.pc,source.meta.resolve,(BpuBranchFeedback(4,token.pc+0x400,3,mispredict=1),))
    return checker,event,source,tx


@pytest.mark.parametrize('fault',('valid','provider','alternate','allocation','prediction-tick','metadata-tick','history'))
def test_wrong_public_source_is_latched_before_any_model_or_feedback_plan_advances(fault):
    checker,event,source,tx=ready();meta=source.meta.resolve['ittage']
    if fault=='valid':meta['valid']^=1
    elif fault=='provider':meta['provider']['valid']^=1
    elif fault=='alternate':meta['altProvider']['valid']^=1
    elif fault=='allocation':meta['allocate']['bits']^=1
    elif fault=='prediction-tick':source.prediction_tick+=2
    elif fault=='metadata-tick':source.meta_tick+=1
    else:source.meta.redirect['phr']['phrLowBits']^=1
    before=deepcopy(checker.model.state()),deepcopy(checker.model.sources.indirect.state())
    with pytest.raises(AssertionError) as first:checker.plan_feedback(source,tx)
    with pytest.raises(AssertionError) as second:checker.source_token(source)
    assert first.value is second.value and not checker.feedback_plans
    assert (checker.model.state(),checker.model.sources.indirect.state())==before


@pytest.mark.parametrize('fault',('unplanned','valid','provider','alternate','allocation','target','mispredict'))
def test_actual_training_must_match_the_planned_original_indirect_source(fault):
    checker,event,source,tx=ready()
    if fault!='unplanned':checker.plan_feedback(source,tx)
    actual=input_bits(source,tx);actual['ittage']=deepcopy(source.meta.resolve['ittage'])
    if fault=='valid':actual['ittage']['valid']^=1
    elif fault=='provider':actual['ittage']['provider']['valid']^=1
    elif fault=='alternate':actual['ittage']['altProvider']['valid']^=1
    elif fault=='allocation':actual['ittage']['allocate']['bits']^=1
    elif fault!='unplanned':actual['branches'][0][fault]^=1
    before=deepcopy(checker.model.state()),deepcopy(checker.model.sources.indirect.state())
    with pytest.raises(AssertionError):step(checker,event,training=actual)
    assert (checker.model.state(),checker.model.sources.indirect.state())==before


@pytest.mark.parametrize('fault',('read-pc','read-folds','prng','public-allocation'))
def test_wrong_live_read_context_prng_and_metadata_fail_without_repairing_golden_state(fault):
    checker,event,_,_=ready();row=fixture_row(checker,event)
    if fault=='read-pc':row['observed']['indirect_read']['pc']^=1
    elif fault=='read-folds':
        folds=list(row['observed']['indirect_read']['folds']);folds[2]=(0,0,0)
        # Ensure an actual change even if the original fold happens to be zero.
        folds[0]=(1,0,0);row['observed']['indirect_read']['folds']=tuple(folds)
    elif fault=='prng':row['observed']['indirect_random']=(0,)*15
    else:row['observed']['metadata']['ittage']['allocate']['bits']^=1
    before=deepcopy(checker.model.state()),deepcopy(checker.model.sources.indirect.state())
    checker.capture(row,NS(tick=checker.last_tick+2))
    with pytest.raises(AssertionError):checker.raise_failure()
    assert (checker.model.state(),checker.model.sources.indirect.state())==before


def test_accepted_input_keeps_exact_owner_and_retirement_expires_indirect_snapshots():
    checker,event,source,tx=ready();token=checker.source_token(source)
    idle=replace(event,prediction_ready=False)
    for _ in range(4):step(checker,idle)
    checker.plan_feedback(source,tx);actual=input_bits(source,tx);actual['ittage']=deepcopy(source.meta.resolve['ittage'])
    step(checker,idle,training=actual)
    assert checker.last_resolution[1].origin is token
    checker.retire_source(source.meta_tick)
    with pytest.raises(ValueError):checker.model.sources.snapshot(token,resolved=True)
    with pytest.raises(AssertionError):checker.source_token(source)
