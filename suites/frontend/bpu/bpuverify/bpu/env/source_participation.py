"""Read genuine old/new participation; do not adopt an unresolved policy."""
from copy import deepcopy

from bpuverify.bpu.model.pipeline import Outcome, Resolution
from bpuverify.bpu.model.selection import Kind
from bpuverify.bpu.transaction.types import BpuBranchFeedback

PC, DONOR, TARGET, POSITION = 0x40001800, 0x40000800, 0x40002800, 4
PROFILES = ('cold-direct-control','cold-indirect-gap','warm-indirect-gap')


async def observe_source_participation(env, profile):
    if profile not in PROFILES:
        raise ValueError('declared participation diagnostic required')
    checker,agent=env.checker,env.agent
    bank=checker.model.sources
    donor=None
    if profile=='warm-indirect-gap':
        source=await env.capture_source(DONOR)
        snapshot=bank.snapshot(checker.source_token(source),resolved=True)
        assert snapshot.prediction is not None and snapshot.allocation is not None
        await env.resolve(source,BpuBranchFeedback(POSITION,DONOR,3,mispredict=1))
        donor=await env.capture_source(DONOR)
        actual=bank.snapshot(checker.source_token(donor),resolved=True)
        assert actual.prediction is not None
    await env.pause()
    await agent.configure_predictors(ittage=False,settle=True)
    old=await env.capture_source(PC)
    old_token=checker.source_token(old)
    original=bank.snapshot(old_token,resolved=True)
    assert original.prediction is None and not original.enabled and original.published_enabled is False
    assert old.meta.resolve['ittage']['valid']==0
    old_resolve,old_redirect=deepcopy(old.meta.resolve),deepcopy(old.meta.redirect)
    await agent.configure_predictors(ittage=True,settle=True)
    await env.pause()
    fresh=await env.capture_source(PC)
    current=bank.snapshot(checker.source_token(fresh),resolved=True)
    assert current.prediction is not None and current.enabled and current.published_enabled is True
    assert fresh.meta.resolve['ittage']['valid']==1
    assert old.meta.resolve==old_resolve and old.meta.redirect==old_redirect
    kind=Kind.DIRECT if profile=='cold-direct-control' else Kind.INDIRECT
    feedback=Resolution(old_token.history,old_token.pc,
        (Outcome(POSITION,TARGET,kind,True,mispredict=True),),origin=old_token)
    before=deepcopy(bank.main.state()),deepcopy(bank.indirect.state())
    result=bank.feedback_for(feedback)
    assert result is None
    assert before==(bank.main.state(),bank.indirect.state())
    consumer=None
    if kind==Kind.DIRECT:
        assert result is None
        await env.resolve(old,BpuBranchFeedback(POSITION,TARGET,2,mispredict=1))
        consumer=await env.capture_source(PC)
        choice=bank.snapshot(checker.source_token(consumer),resolved=True).late.branch
        assert (choice.kind,choice.target,choice.position)==(Kind.DIRECT,TARGET,POSITION)
    else:
        # The adopted ownership policy skips ITTAGE for this unpublished
        # original. The diagnostic still does not send the unresolved indirect
        # feedback to the DUT, so it earns no hardware credit.
        assert result is None
    checker.raise_failure()
    return dict(profile=profile,status='POLICY_ADOPTED_MODEL_SKIP',
        old_source=dict(prediction_tick=old.prediction_tick,metadata_tick=old.meta_tick,
            read_participated=False,published_valid=0,actual_component_metadata=old_resolve['ittage']),
        fresh_source=dict(prediction_tick=fresh.prediction_tick,metadata_tick=fresh.meta_tick,
            read_participated=True,published_valid=1),
        donor_source=None if donor is None else donor.meta_tick,
        modeled_learning_policy='unpublished original skips ITTAGE learning; other components keep their own qualification',
        default_reference_rejection=None,
        modeled_skip=True,
        ambiguous_feedback_sent_to_DUT=False,
        direct_control_feedback_sent=kind==Kind.DIRECT,
        direct_control_consumer=None if consumer is None else dict(metadata_tick=consumer.meta_tick,target=TARGET),
        original_metadata_unchanged=True,checked_metadata_sources=checker.counts['metadata'],
        unresolved_indirect_function_credit=0)
