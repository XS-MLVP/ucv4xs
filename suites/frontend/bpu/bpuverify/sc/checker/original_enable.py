"""Old active source -> ignored while disabled -> fresh enabled consumers."""
from copy import deepcopy

from bpuverify.sc.checker.eligibility import EligibilityChecks


class EnableChecks(EligibilityChecks):
    def __init__(self,program,coverage):
        super().__init__(program,coverage)
        self.old_sources={}
        self.disabled_queries={}
        self.disabled_feedback={}
        self.restored={}
        self.fresh_same_results=set()
        self.finalized=False

    def active_original(self,owner,transfer,prediction,actual_input):
        self.check(set(range(len(self.program.probes))),set(self.queries),'qualification episode precedes the active original sources')
        self.check(False,owner.name in self.old_sources,'one distinct old source per actual branch')
        self.source(owner,'eligible',transfer,prediction,actual_input)
        self.check(True,transfer.accepted_event.tick>max(view['completed_tick'] for view in self.queries.values()),
                   'active source is newly accepted before the disabling episode')
        expected,_=self.program.expected(owner,'eligible',self.counts)
        self.prediction(expected,prediction,transfer)
        self.old_sources[owner.name]=dict(source_id=transfer.sequence_id,completed_tick=transfer.completed_event.tick,
            owner=owner,expected=deepcopy(expected['meta']))

    def disabled_query(self,owner,transfer,prediction,actual_input):
        self.check({value.name for value in self.program.owners},set(self.old_sources),
                   'both real active originals precede the disabled query phase')
        self.check(False,owner.name in self.disabled_queries,'one actually disabled query per owner')
        self.check(False,transfer.sequence_id in self.sources,'disabled observation still has a unique query identity')
        self.check(self.program.request(owner),transfer.request,'disabled query retains the complete declared request')
        expected_input=dict(self.program.actual_input(owner),enabled=False)
        self.check(expected_input,actual_input,'actual new query is observed while the SC gate is disabled')
        self.check(True,transfer.completed_event.tick>transfer.accepted_event.tick,
                   'disabled response is an actual accepted/completed driver observation')
        self.check(True,transfer.accepted_event.tick>max(value['completed_tick'] for value in self.old_sources.values()),
                   'disabled query is a new occurrence after the active originals')
        self.check((0,0,0,0),prediction.useds,'global disable suppresses use for every branch slot')
        # Disabled raw metadata is not a defined semantic response. Keep the
        # immutable software snapshot only; do not predict it or train from it.
        self.sources[transfer.sequence_id]=(prediction,deepcopy(prediction.meta))
        self.disabled_queries[owner.name]=dict(source_id=transfer.sequence_id,
            accepted_tick=transfer.accepted_event.tick,completed_tick=transfer.completed_event.tick,
            useds=prediction.useds,actual_enabled=actual_input['enabled'])
        self.coverage.record('reached','disabled-use-suppressed',owner=owner.name)

    def old_feedback(self,owner):
        self.check(True,owner.name in self.old_sources,'disabled outcome retains a genuine earlier active source')
        record=self.old_sources[owner.name]
        source_id=record['source_id']
        self.check(False,source_id in self.spent,'the old outcome is offered exactly once')
        original,frozen=self.sources[source_id]
        self.check(frozen,original.meta,'old active source metadata is not rewritten during disable')
        self.spent.add(source_id)
        return (self.program.feedback(owner,deepcopy(frozen),reverse=True),
                self.program.feedback(owner,deepcopy(record['expected']),reverse=True))

    def ignored_old_feedback(self,owner,tick,*,actual_enabled):
        self.check(True,owner.name in self.old_sources,'actual ignored outcome has its declared original source')
        record=self.old_sources[owner.name]
        self.check(False,actual_enabled,'actual gate at old feedback acceptance is disabled')
        self.check(True,record['source_id'] in self.spent,'observed old outcome was explicitly offered')
        self.check(False,owner.name in self.disabled_feedback,'one actual old feedback acceptance per source')
        self.check(True,tick>record['completed_tick'],'disabled outcome follows its own active prediction')
        self.check(False,record['source_id'] in self.accepted_feedback_ids,'one actual acceptance per original source')
        self.accepted_feedback_ids.add(record['source_id'])
        self.disabled_feedback[owner.name]=dict(tick=tick,actual_enabled=actual_enabled,source_id=record['source_id'])
        self.coverage.record('reached','disabled-old-feedback-ignored',owner=owner.name,accepted_tick=tick)

    def restored_consumer(self,owner,transfer,prediction,actual_input):
        wanted={value.name for value in self.program.owners}
        self.check(wanted,set(self.disabled_feedback),'all old outcomes really arrived while disabled')
        self.check(wanted,set(self.disabled_queries),'new disabled queries actually exercised the gate')
        self.check(False,owner.name in self.restored,'one fresh restored consumer per owner')
        self.source(owner,'eligible',transfer,prediction,actual_input)
        self.check(True,transfer.accepted_event.tick>max(value['tick'] for value in self.disabled_feedback.values()),
                   'restored consumer is freshly accepted after ignored outcomes and reopening')
        expected,_=self.program.expected(owner,'eligible',self.counts)
        self.prediction(expected,prediction,transfer)
        self.check((1,owner.outcome),(prediction.useds[0],prediction.takens[0]),
                   'reopening consumes old usable learning before any new qualified outcome')
        self.restored[owner.name]=dict(source_id=transfer.sequence_id,accepted_tick=transfer.accepted_event.tick,
            completed_tick=transfer.completed_event.tick,taken=prediction.takens[0],used=prediction.useds[0])
        self.coverage.record('reached','reopen-without-relearning',owner=owner.name)

    def reverse_source(self,owner,transfer,prediction,actual_input):
        self.check({value.name for value in self.program.owners},set(self.restored),
                   'each owner has its own retained public consumer before reenabled learning')
        self.check(True,transfer.accepted_event.tick>max(value['completed_tick'] for value in self.restored.values()),
                   'positive control is a fresh query after all restored consumers')
        super().reverse_source(owner,transfer,prediction,actual_input)
        if self.reversals[owner.name]==0:
            _,old_meta=self.sources[self.old_sources[owner.name]['source_id']]
            self.check(old_meta,prediction.meta,'fresh enabled source carries the same legal payload as the ignored old source')
            self.fresh_same_results.add(owner.name)

    def finish(self):
        self.check(False,self.finalized,'one source/gate lifetime publishes checked evidence once')
        wanted={owner.name for owner in self.program.owners}
        for values in (self.old_sources,self.disabled_queries,self.disabled_feedback,self.restored):
            self.check(wanted,set(values),'both independent original branches complete each enable phase')
        self.check(wanted,self.fresh_same_results,'fresh same-payload enabled positive controls exist for both old outcomes')
        self.check(56,len(self.sources),'complete active/disabled/restored query occurrences are all unique')
        self.check(19,len(self.spent),'six warm, two disabled and eleven qualified reverse outcomes only')
        super().finish()
        for rule in ('disabled-use-suppressed','disabled-old-feedback-ignored','reopen-without-relearning'):
            self.coverage.record('checked',rule,owners=len(wanted))
        self.finalized=True

    def summary(self):
        return dict(super().summary(),old_active_sources={name:{key:value for key,value in record.items()
            if key not in ('owner','expected')} for name,record in self.old_sources.items()},
            disabled_queries=dict(self.disabled_queries),actual_disabled_feedback=dict(self.disabled_feedback),
            restored_before_learning=dict(self.restored),same_payload_fresh_controls=sorted(self.fresh_same_results))
