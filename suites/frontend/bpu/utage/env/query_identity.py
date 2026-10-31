"""Real input sources, bound drivers/monitor and independent semantic checks."""
from copy import deepcopy
from hashlib import sha256
import json

from suites.frontend.bpu.utage.transaction.types import UtageTraining
from suites.frontend.bpu.utage.monitor.query_cohort import Monitor
from suites.frontend.bpu.utage.checker.query_identity import Checks
from suites.frontend.bpu.utage.model.query_identity import PC,POSITION,READ_PCS,RULES
from suites.frontend.bpu.utage.checker.read_lifetime import values


async def run(agent,p,coverage,evidence):
    await agent.reset()
    checks=Checks(p);monitor=Monitor(agent,0).start()
    before_feedback=agent.reference.model.accepted_feedback
    def submit(owner):
        return agent.submit_predict(PC,POSITION,owner,index_pc=READ_PCS[owner],index_history=0)
    def transaction(owner,source):
        return UtageTraining(PC,POSITION,p.actual(owner),deepcopy(source.meta),mispredict=int(not source.hit))
    async def read(owner):
        source=await submit(owner);agent.reference.raise_failure()
        return source,checks.remember(source)
    try:
        checks.check(p.protection('reset'),monitor.all_protection(),'normal reset precedes all learned identities')
        coverage.reach('same-match-distinct-complete-read-identities',indices=tuple(p.read_indices(o) for o in (0,1)))
        for owner in (0,1):
            cold,ordinal=await read(owner)
            checks.prediction(owner,cold,(0,None,None,None))
            tx=transaction(owner,cold);checks.owned_feedback(owner,ordinal,tx)
            await agent.train(tx)
        teachers=[]
        for owner in (0,1):
            source,ordinal=await read(owner)
            checks.prediction(owner,source,p.expected(owner,relation='before'))
            teachers.append((source,ordinal))
        checks.check(p.protection('prepared'),monitor.all_protection(),'both opposed identities were normally allocated independently')
        coverage.reach('opposed-normally-learned-prestate')
        owners=p.cohort_owners
        transfers=[submit(owners[0])]
        await transfers[0].wait_processing()
        transfers.extend(submit(owner) for owner in owners[1:])
        source,ordinal=teachers[p.teacher]
        tx=transaction(p.teacher,source);checks.owned_feedback(p.teacher,ordinal,tx)
        await agent.train(tx)
        await agent.drain_predictions()
        actuals=tuple([await transfer for transfer in transfers])
        checks.check(3,len(monitor.effects),'only two normal allocations and one learning surround the mixed cohort')
        effect=monitor.effects[-1]
        expected_changes=tuple((i,a,b) for i,(a,b) in enumerate(zip(p.protection('prepared'),p.protection('first-effect'),strict=True)) if a!=b)
        checks.check(expected_changes,tuple(sorted(effect['native'].get('changes',()))),
            'actual protection delta identifies the target learning boundary and preserves the other identity')
        cohort=checks.responses(transfers,actuals,monitor,effect)
        initial_sequence=monitor.versions[-1]['logical_sequence']
        evidence.update(cohort=cohort,first_effect=effect['tick'],first_changes=expected_changes)
        for rule in ('adjacent-overlapping-originals','target-three-actual-read-ages','other-originals-preserved'):coverage.reach(rule)
        checks.check(p.protection('first-effect'),monitor.all_protection(),'only the taught full-index protection changed')
        if p.mode=='serial':
            for number,owner in enumerate(p.turnover_owners):
                source,ordinal=await read(owner)
                checks.prediction(owner,source,p.expected(owner,subsequent=number))
                tx=transaction(owner,source);checks.owned_feedback(owner,ordinal,tx)
                await agent.train(tx)
        else:
            # Every adjacent feedback comes from a different real original.
            # Equal PC/tag/metadata contents do not turn these into one source.
            pending=[submit(owner) for owner in p.turnover_owners]
            await agent.drain_predictions()
            sources=tuple([await transfer for transfer in pending]);transactions=[]
            for owner,source in zip(p.turnover_owners,sources,strict=True):
                checks.prediction(owner,source,p.expected(owner))
                ordinal=checks.remember(source)
                tx=transaction(owner,source);checks.owned_feedback(owner,ordinal,tx)
                transactions.append(tx)
            await agent.train_many(tuple(transactions))
        checks.turnover(monitor)
        checks.check(False,any(version.sequence==initial_sequence for version in agent.reference.model.updates[0].recent),
            'the cohort learning version really left the retained chronological window')
        coverage.reach('mixed-owner-version-turnover',actual_versions=len(monitor.versions))
        coverage.reach('actual-feedback-cadence',mode=p.mode)
        for owner in (0,1):
            source,_=await read(owner)
            checks.prediction(owner,source,p.expected(owner,subsequent=len(p.turnover_owners)))
        coverage.reach('fresh-both-identity-consumers')
        checks.check(p.protection('turnover'),monitor.all_protection(),'both target identities and all1022 non-target cells retain exact declared protection')
        coverage.reach('all-protection-preserved')
        checks.finish(monitor)
        coverage.reach('complete-fresh-feedbacks-once',feedbacks=len(checks.expected_feedback))
        coverage.reach('completed-originals-immutable')
        agent.reference.raise_failure()
        coverage.finish()
        fingerprint=lambda value:sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()
        evidence.update(status='PASS',completed=list(RULES),actual_versions=monitor.versions,
            protection_effects=[dict(tick=row['tick'],changes=row['native'].get('changes',())) for row in monitor.effects],
            original_sources=len(checks.originals),actual_feedback_owners=checks.feedback_owners,
            public_feedbacks=len(monitor.public),accepted_feedbacks=agent.reference.model.accepted_feedback-before_feedback,
            feedback_receipts=[dict(tick=row['tick'],payload_sha256=fingerprint(row['bits'])) for row in monitor.public],
            expected_feedback_sha256=[fingerprint(bits) for bits in checks.expected_feedback],
            all_protection_cells_compared=1024,protection_endpoint_sha256=fingerprint(monitor.all_protection()),
            expected_protection_endpoint_sha256=fingerprint(p.protection('turnover')),
            original_read_tuples_retained=True,reference_checks=agent.reference.board.status.checked,
            reference_failures=agent.reference.board.status.failed)
    except BaseException as error:
        evidence.update(status='FAIL',error_type=type(error).__name__,error=str(error),
            observed_versions=monitor.versions,observed_public_feedbacks=len(monitor.public),
            prepared_feedback_owners=checks.feedback_owners)
        raise
    finally:await monitor.aclose()
