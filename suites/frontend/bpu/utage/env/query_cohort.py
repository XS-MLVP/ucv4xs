"""Cohort concurrency through existing drivers; fresh queries teach once."""
from copy import deepcopy
from hashlib import sha256
import json

from suites.frontend.bpu.utage.transaction.types import UtageTraining
from suites.frontend.bpu.utage.case.definitions import SHADOW_CAPACITY
from suites.frontend.bpu.utage.env.read_lifetime import ReadLifetime
from suites.frontend.bpu.utage.checker.read_lifetime import values
from suites.frontend.bpu.utage.model.query_cohort import PC,POSITION,NEIGHBOR,COHORT_SIZE,RULES
from suites.frontend.bpu.utage.checker.query_cohort import Checks
from suites.frontend.bpu.utage.monitor.query_cohort import Monitor


async def run(agent,p,coverage,evidence):
    checks=Checks(p)
    preparation=ReadLifetime(agent,p.legacy,None,{})
    teacher=await preparation.prepared()
    for source,_ in preparation.sources:checks.remember(source)
    teacher_ordinal=next(i for i,(source,_) in enumerate(checks.originals) if source is teacher)
    monitor=Monitor(agent,p.target_table).start()
    baseline_feedback=agent.reference.model.accepted_feedback
    try:
        checks.check(p.protection('before'),monitor.all_protection(),'entire reset-derived prestate')
        coverage.reach('normally-learned-prestate')
        def submit():return agent.submit_predict(p.match_pc,POSITION,0,folded_history=p.match_history,
            index_pc=PC,index_history=p.history)
        transfers=[submit()]
        await transfers[0].wait_processing()
        # The first original is already accepted but has not returned. All
        # remaining queries enqueue now; driver/scoreboard own their overlap.
        transfers.extend(submit() for _ in range(COHORT_SIZE-1))
        tx=UtageTraining(p.teacher_pc,POSITION,p.actual,deepcopy(teacher.meta),
            mispredict=int((teacher.taken if teacher.hit else 0)!=p.actual))
        checks.original_feedback(teacher_ordinal,tx)
        await agent.train(tx)
        await agent.drain_predictions()
        actuals=tuple([await transfer for transfer in transfers])
        agent.reference.raise_failure()
        checks.check(1,len(monitor.effects),'one actual initial learning effect around this cohort')
        effect=monitor.effects[0]
        checks.check(p.first_changes(),tuple(sorted(effect['native'].get('changes',()))),
            'actual native protection delta confirms the semantic effect boundary')
        cohort=checks.responses(transfers,actuals,monitor,effect)
        initial_sequence=monitor.versions[0]['logical_sequence']
        evidence.update(cohort=cohort,first_effect=effect['tick'],first_changes=effect['native'].get('changes',()))
        coverage.reach('adjacent-overlapping-originals')
        coverage.reach('three-actual-read-ages',ages=tuple(row['relation'] for row in cohort))
        coverage.reach('each-response-owns-original-read')
        checks.check(p.protection('first-effect'),monitor.all_protection(),'all protection after the first version change')
        # Each subsequent version is taught by a NEW real query. The earlier
        # completed cohort is retained only as immutable response evidence;
        # it is not described as hardware work still in flight after turnover.
        teachers=[]
        for version in range(SHADOW_CAPACITY):
            source=await agent.predict(p.teacher_pc,POSITION,p.teacher_base,folded_history=p.history)
            checks.check(p.teacher_expected(version),values(source),'fresh original teacher consumes the latest version')
            ordinal=checks.remember(source)
            tx=UtageTraining(p.teacher_pc,POSITION,p.actual,deepcopy(source.meta),mispredict=0)
            checks.original_feedback(ordinal,tx)
            await agent.train(tx)
            teachers.append(dict(version=version+1,counter_before=p.counter(version)))
        checks.turnover(monitor)
        recent=agent.reference.model.updates[p.target_table].recent
        checks.check(False,any(v.sequence==initial_sequence for v in recent),'the initial learned version really left the retained chronological window')
        checks.check(SHADOW_CAPACITY+1,agent.reference.model.accepted_feedback-baseline_feedback,
            'initial original plus one fresh source per subsequent version')
        coverage.reach('actual-version-retention-turnover',versions=len(monitor.versions))
        transfer=submit();fresh=await transfer
        checks.check(p.final_query(),values(fresh),'fresh original-context consumer sees only the latest correct identity/version')
        checks.remember(fresh)
        latest=await agent.predict(p.teacher_pc,POSITION,p.teacher_base,folded_history=p.history)
        checks.check(p.teacher_expected(SHADOW_CAPACITY),values(latest),'latest teacher identity consumes its own retained version')
        checks.remember(latest)
        if p.ancestry=='distinct-ancestors':
            own=await agent.predict(p.match_pc,POSITION,0,folded_history=p.match_history)
            checks.check((0,None,None,None),values(own),'matching context alone cannot borrow the original read identity')
            checks.remember(own)
        coverage.reach('fresh-latest-consumers')
        neighbor=await agent.predict(NEIGHBOR,POSITION,1)
        checks.check((1,0,3,0),values(neighbor),'unrelated learned branch remains independent')
        checks.remember(neighbor)
        checks.check(p.protection('turnover'),monitor.all_protection(),'all1024 protection cells retain exactly the declared effects')
        coverage.reach('all-protection-and-neighbor-preserved')
        checks.finish(monitor)
        coverage.reach('complete-original-feedbacks-once',feedbacks=len(checks.expected_feedback))
        coverage.reach('completed-originals-stay-immutable')
        agent.reference.raise_failure()
        coverage.finish()
        fingerprint=lambda payload:sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()
        evidence.update(status='PASS',completed=list(RULES),teachers=teachers,actual_versions=monitor.versions,
            original_sources=len(checks.originals),public_feedbacks=len(monitor.public),
            accepted_original_feedbacks=agent.reference.model.accepted_feedback-baseline_feedback,
            fresh_query=values(fresh),fresh_teacher=values(latest),
            original_read_tuples_retained=True,inflight_only_during_actual_response_window=True,
            feedback_receipts=[dict(tick=row['tick'],payload_sha256=fingerprint(row['bits'])) for row in monitor.public],
            expected_feedback_sha256=[fingerprint(bits) for bits in checks.expected_feedback],
            all_protection_cells_compared=1024,
            protection_endpoint_sha256=fingerprint(monitor.all_protection()),
            expected_protection_endpoint_sha256=fingerprint(p.protection('turnover')),
            reference_checks=agent.reference.board.status.checked,reference_failures=agent.reference.board.status.failed)
    except BaseException as error:
        evidence.update(status='FAIL',error_type=type(error).__name__,error=str(error),
            observed_public_feedbacks=len(monitor.public),observed_versions=monitor.versions)
        raise
    finally:await monitor.aclose()
