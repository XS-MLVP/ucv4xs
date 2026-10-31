"""Semantic phase intent over existing drivers, monitor and one predictor golden."""
from copy import deepcopy
from hashlib import sha256
import json
from suites.frontend.bpu.utage.transaction.types import UtageTraining
from suites.frontend.bpu.utage.model.selective_protection import PC,POSITION,READ_PCS,RULES
from suites.frontend.bpu.utage.checker.selective_protection import Checks
from suites.frontend.bpu.utage.monitor.selective_protection import Monitor
from suites.frontend.bpu.utage.checker.read_lifetime import values


async def run(agent,p,coverage,evidence,*,checks_type=Checks,monitor_type=Monitor):
    await agent.reset()
    checks=checks_type(p);monitor=monitor_type(agent).start()
    cohort_history=getattr(p,'cohort_history',64)
    expected_feedback=getattr(p,'expected_feedback',28)
    expected_ticks=getattr(p,'expected_tick_failures',(6,6))
    read_pcs=getattr(p,'read_pcs',READ_PCS)
    before=agent.reference.model.accepted_feedback
    def submit(owner,history,base):
        return agent.submit_predict(PC,POSITION,base,folded_history=history,index_pc=read_pcs[owner],index_history=0)
    def tx(step,source):
        predicted=step.base if step.before is None else step.before.taken
        return UtageTraining(PC,POSITION,step.actual,deepcopy(source.meta),mispredict=int(predicted!=step.actual))
    async def ordinary(group):
        receipts=len(monitor.public)
        if p.mode=='serial':
            for step in group:
                source=await submit(step.owner,step.history,step.base)
                ordinal=checks.source(step,source);transaction=tx(step,source)
                checks.owned_feedback(step,ordinal,transaction)
                await agent.train(transaction)
                checks.prefix(monitor,step.ordinal+1)
        else:
            pending=[submit(step.owner,step.history,step.base) for step in group]
            await agent.drain_predictions()
            sources=tuple([await transfer for transfer in pending]);transactions=[]
            for step,source in zip(group,sources,strict=True):
                ordinal=checks.source(step,source);transaction=tx(step,source)
                checks.owned_feedback(step,ordinal,transaction);transactions.append(transaction)
            await agent.train_many(tuple(transactions))
            checks.prefix(monitor,group[-1].ordinal+1)
        checks.cadence(group,monitor.public[receipts:])
    try:
        checks.check(p.protection_after(0),monitor.all_protection(),'normal reset before all real learning sources')
        for group in p.groups:
            phase=group[0].phase
            if phase=='lower-boundary':
                step,=group
                source=await submit(step.owner,step.history,step.base)
                ordinal=checks.source(step,source);transaction=tx(step,source)
                pending=[submit(p.cohort_owners[0],cohort_history,p.cohort_owners[0])]
                await pending[0].wait_processing()
                pending.extend(submit(owner,cohort_history,owner) for owner in p.cohort_owners[1:])
                checks.owned_feedback(step,ordinal,transaction)
                await agent.train(transaction)
                await agent.drain_predictions()
                actuals=tuple([await transfer for transfer in pending])
                checks.prefix(monitor,step.ordinal+1)
                cohort=checks.check_cohort(pending,actuals,monitor,monitor.records[step.ordinal])
                evidence.update(cohort=cohort,boundary_tick=monitor.records[step.ordinal]['tick'])
                for rule in ('lower-bound-still-corrects-direction','three-actual-read-ages','other-identity-preserved-in-cohort'):coverage.reach(rule)
            else:await ordinary(group)
            mapping={'allocate':'normally-learned-opposed-identities','reward-3':'qualified-reward',
                'penalty-3':'selective-penalty-to-lower-bound','base-agreement-lower':'base-agreement-lower-holds',
                'recover-3':'reverse-and-recover-protection','upper-hold':'upper-bound-reward-holds',
                'base-agreement-upper':'base-agreement-upper-holds'}
            mapping=getattr(p,'phase_rules',mapping)
            if phase in mapping:coverage.reach(mapping[phase])
        if hasattr(checks,'consumer_lifetime'):
            evidence['consumer_lifetime']=checks.consumer_lifetime(monitor)
            coverage.reach('declared-consumer-lifetime',**evidence['consumer_lifetime'])
        consumers=[]
        for owner in (0,1):
            declared=(p.final_consumers(owner) if hasattr(p,'final_consumers') else
                ((64,0,0 if owner==0 else 7,owner),(0,1,3 if owner==0 else 4,owner)))
            for history,provider,counter,taken in declared:
                source=await submit(owner,history,owner)
                checks.prediction(owner,history,source,(1,provider,counter,taken));checks.remember(source)
                consumers.append(dict(owner=owner,history=history,actual=values(source)))
        coverage.reach('both-provider-consumers')
        checks.check(expected_ticks,(agent.reference.model.low_tick,agent.reference.model.high_tick),
            'only declared allocation failures, not invented maintenance or idle waits')
        checks.check(expected_feedback,agent.reference.model.accepted_feedback-before,'all original feedbacks were accepted once')
        checks.finish(monitor);agent.reference.raise_failure()
        for rule in ('fresh-owned-sources-once','all-protection-effects-preserved','immutable-originals','actual-feedback-cadence'):coverage.reach(rule)
        coverage.finish()
        fingerprint=lambda value:sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()
        evidence.update(status='PASS',completed=list(getattr(p,'rules',RULES)),actual_learning=monitor.records,actual_cadences=checks.cadences,
            public_feedbacks=len(monitor.public),accepted_feedbacks=agent.reference.model.accepted_feedback-before,
            feedback_receipts=[dict(tick=row['tick'],payload_sha256=fingerprint(row['bits'])) for row in monitor.public],
            expected_feedback_sha256=[fingerprint(bits) for bits in checks.expected_feedback],
            original_sources=len(checks.originals),consumers=consumers,all_protection_cells_compared=1024,
            protection_endpoint_sha256=fingerprint(monitor.all_protection()),
            expected_protection_endpoint_sha256=fingerprint(p.protection_after(expected_feedback)),
            no_maintenance=True,reference_checks=agent.reference.board.status.checked,reference_failures=agent.reference.board.status.failed)
    except BaseException as error:
        evidence.update(status='FAIL',error_type=type(error).__name__,error=str(error)[:6000],
            first_differences=[dict(path=d.path,expected=repr(d.expected),actual=repr(d.actual)) for d in getattr(error,'differences',())[:12]],
            observed_learning=monitor.records,observed_public_feedbacks=len(monitor.public),sent_steps=checks.sent)
        raise
    finally:await monitor.aclose()
