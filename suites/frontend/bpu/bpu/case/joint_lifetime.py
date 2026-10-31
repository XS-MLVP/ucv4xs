"""Establish real opposed learning, then exercise both meaningful selections."""
from suites.frontend.bpu.bpu.transaction.types import BpuBranchFeedback
from suites.frontend.bpu.bpu.model.joint_lifetime import (
    PC,VIA,CONDITION,Step,condition)
from suites.frontend.bpu.bpu.model.direction_sources import context_for as direction_context
from suites.frontend.bpu.bpu.model.indirect_sources import context_for as target_context
from suites.frontend.bpu.bpu.env.joint_lifetime import joint_program
from suites.frontend.bpu.bpu.checker.joint_lifetime import Checks


def transactions(step):
    return tuple(BpuBranchFeedback(b.position,b.target,int(b.kind),taken=int(b.taken),mispredict=int(b.wrong))
                 for b in step.branches)


async def run(agent,program,coverage,evidence):
    async with joint_program(agent,PC) as env:
        checks=Checks(env.checker,program,coverage,evidence)
        enabled=True
        for step in program.establishment():
            if step.enable is not None:
                if not step.enable:checks.late_retention=checks.retained_state()
                else:checks.check(checks.late_retention,checks.retained_state(),
                    'Main-only target and direction learning preserves both independent late predictors')
                await env.configure_late(step.enable)
                enabled=step.enable
                continue
            source=await env.capture_source(PC)
            checks.save(source)
            event=await env.resolve(source,*transactions(step))
            checks.accepted_feedback(source,event,step,enabled)
        source=await env.capture_source(PC)
        checks.selected(source)
        for rule in ('same-original-window','both-independent-read-stages','both-late-sources-learned',
                'main-only-learning-preserves-late-sources','two-opposed-base-predictions'):
            coverage.reach(rule,tick=source.meta_tick)
        if program.mode=='conditional-suppresses-indirect':
            original_target=checks.retained_state()[1]
            # A 3-bit NT provider may promote a new weak T provider, or be the
            # longest one already. At most three genuine T outcomes establish
            # a qualified T decision in either case; this is not a time delay.
            for ordinal in range(3):
                token=env.checker.source_token(source)
                late=env.checker.model.sources.snapshot(token,resolved=True).late
                wrong=not (late.branch.position==CONDITION and late.branch.taken)
                step=Step('learn-executed-condition-'+str(ordinal+1),(condition(True,wrong),))
                event=await env.resolve(source,*transactions(step))
                checks.accepted_feedback(source,event,step,True)
                checks.check(original_target,checks.retained_state()[1],
                    'real conditional-only feedback cannot change the unexecuted target predictor')
                source=await env.capture_source(PC)
                fact=checks.fact(source)
                if fact.qualified_direction and fact.direction_uses_provider:break
            else:raise AssertionError('genuine executed conditional learning did not establish taken direction')
            checks.selected(source,blocked=True)
        coverage.reach('original-target-selected-only-for-indirect',tick=source.meta_tick)
        coverage.reach('complete-executed-prefix-feedback',accepted=len(checks.accepted))
        coverage.reach('fresh-selected-consumer',tick=source.meta_tick)
        original=env.checker.source_token(source)
        other=await env.capture_via(PC,VIA)
        token,tagged,target=checks.save(other)
        checks.check(True,token.pc==original.pc and token.history.metadata()!=original.history.metadata(),
            'one fixed alternate predecessor gives the same PC a genuinely different original history')
        checks.check((direction_context(token.history),target_context(token.history)),
            (tagged.read.context,target.read.context),'both new read snapshots use the new original, not a nearby same-PC owner')
        evidence['different_history']=dict(old=original.history.metadata(),new=token.history.metadata(),
            original_owner=original.sequence,new_owner=token.sequence,metadata_tick=other.meta_tick)
        coverage.reach('same-pc-different-original-history',tick=other.meta_tick)
        checks.finish()


async def check_joint_cold(bpu_agent, evidence):
    async with joint_program(bpu_agent, PC) as env:
        source = await env.capture_source(env.pc)
        token = env.checker.source_token(source)
        direction = env.checker.model.sources.snapshot(token, resolved=True)
        target = env.checker.model.sources.target_snapshot(token, resolved=True)
        assert direction.owner is target.owner is token.history
        assert direction.read is not None and target.read is not None
        assert target.prediction is not None and target.prediction.provider is None
        evidence.update(status='PASS', prediction_tick=source.prediction_tick, meta_tick=source.meta_tick, token=token.sequence, history=token.history.metadata(), compared=dict(env.checker.counts))
