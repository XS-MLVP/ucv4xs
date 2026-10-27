"""One actual ignored outcome per original source and a fresh consumer."""
from bpuverify.common.model.configuration import RESULT_SLOTS
from copy import deepcopy

from bpuverify.sc.checker.eligibility import EligibilityChecks


class FeedbackChecks(EligibilityChecks):
    def __init__(self,program,coverage):
        super().__init__(program,coverage)
        self.rejected_sources={}
        self.rejected_acceptances={}
        self.rejected_consumers={}
        self.finalized=False

    def rejected_source(self,owner,transfer,prediction,actual_input):
        self.check(set(range(len(self.program.probes))),set(self.queries),'original query qualification episode is complete')
        self.check(False,owner.name in self.rejected_sources,'one new original rejection source per declared owner')
        gate=self.program.rejection_gate
        self.source(owner,gate,transfer,prediction,actual_input)
        self.check(True,transfer.accepted_event.tick>max(view['completed_tick'] for view in self.queries.values()),
                   'rejected original is a newly accepted query after the qualification episode')
        expected,_=self.program.expected(owner,gate,self.counts)
        self.prediction(expected,prediction,transfer)
        self.rejected_sources[owner.name]=dict(source_id=transfer.sequence_id,responded=transfer.completed_event.tick,
            expected=deepcopy(expected['meta']),owner=owner)

    def rejected_feedback(self,owner):
        self.check(True,owner.name in self.rejected_sources,'rejected feedback names its real query owner')
        record=self.rejected_sources[owner.name]
        source_id=record['source_id']
        self.check(False,source_id in self.spent,'ignored feedback still consumes its original occurrence exactly once')
        original,frozen=self.sources[source_id]
        self.check(frozen,original.meta,'ignored outcome cannot rewrite its original metadata')
        self.spent.add(source_id)
        return (self.program.rejected_feedback(owner,deepcopy(frozen)),
                self.program.rejected_feedback(owner,deepcopy(record['expected'])))

    def accepted_rejection(self,owner,tick):
        self.check(True,owner.name in self.rejected_sources,'actual rejection needs its designated original source')
        record=self.rejected_sources[owner.name]
        self.check(True,record['source_id'] in self.spent,'actual rejection follows the designated original offer')
        self.check(False,owner.name in self.rejected_acceptances,'one actual acceptance per ignored source')
        self.check(True,tick>record['responded'],'actual feedback follows its own original response')
        self.check(False,record['source_id'] in self.accepted_feedback_ids,'ignored source cannot acquire duplicate acceptance')
        self.accepted_feedback_ids.add(record['source_id'])
        self.rejected_acceptances[owner.name]=tick
        self.coverage.record('reached','ignored-original-feedback',owner=owner.name,
            cause=self.program.rejection_gate,source_id=record['source_id'],accepted_tick=tick)

    def retained_consumer(self,owner,transfer,prediction,actual_input):
        self.check(True,owner.name in self.rejected_acceptances,'restoration requires actual ignored feedback')
        self.check(False,owner.name in self.rejected_consumers,'one fresh retention witness per ignored source')
        self.source(owner,'eligible',transfer,prediction,actual_input)
        self.check(True,transfer.accepted_event.tick>self.rejected_acceptances[owner.name],
                   'retention is a newly accepted consumer after the real ignored outcome')
        expected,_=self.program.expected(owner,'eligible',self.counts)
        self.prediction(expected,prediction,transfer)
        self.check((1,owner.outcome),(prediction.useds[0],prediction.takens[0]),
                   'restored valid branch still actually uses its original learned correction')
        self.rejected_consumers[owner.name]=dict(source_id=transfer.sequence_id,
            accepted_tick=transfer.accepted_event.tick,completed_tick=transfer.completed_event.tick,
            feedback_tick=self.rejected_acceptances[owner.name],taken=prediction.takens[0],used=prediction.useds[0])
        self.coverage.record('reached','fresh-after-rejection',owner=owner.name,accepted_tick=transfer.accepted_event.tick)

    def reverse_source(self,owner,transfer,prediction,actual_input):
        self.check({value.name for value in self.program.owners},set(self.rejected_consumers),
                   'each original rejection has a real preserved consumer before positive-control learning')
        super().reverse_source(owner,transfer,prediction,actual_input)

    def finish(self):
        self.check(False,self.finalized,'one complete original-feedback lifetime gets checked credit once')
        wanted={owner.name for owner in self.program.owners}
        self.check(wanted,set(self.rejected_sources),'each owner supplies its own original rejected query')
        self.check(wanted,set(self.rejected_acceptances),'each ignored source is actually accepted')
        self.check(wanted,set(self.rejected_consumers),'each ignored outcome has a new preserved consumer')
        self.check(2*self.program.warm_votes+2+sum(self.program.reversal_steps(o) for o in self.program.owners),len(self.spent),'all declared warm, ignored and genuine opposite outcomes only')
        self.check(2*self.program.warm_votes+len(self.program.probes)+2*sum(self.program.reversal_steps(o) for o in self.program.owners)+4,len(self.sources),'no duplicate source or missing fresh consumer can be hidden')
        self.check(True,any(self.program.feedback_outcome(owner)!=owner.outcome for owner in self.program.owners),
                   'at least one legal ignored outcome actually opposes its strong learned correction')
        super().finish()
        self.coverage.record('checked','ignored-original-feedback',cause=self.program.rejection_gate)
        self.coverage.record('checked','fresh-after-rejection',owners=len(wanted))
        self.finalized=True

    def summary(self):
        return dict(super().summary(),ignored_cause=self.program.rejection_gate,
            ignored_outcomes={owner.name:self.program.feedback_outcome(owner) for owner in self.program.owners},
            ignored_sources={name:dict(source_id=record['source_id'],responded=record['responded'])
                for name,record in self.rejected_sources.items()},
            ignored_acceptances=dict(self.rejected_acceptances),retained_after_ignored=dict(self.rejected_consumers))
