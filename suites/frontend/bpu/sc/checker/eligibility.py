"""Original source, real input qualification and warm restoration obligations."""
from copy import deepcopy

from toffee import CheckContext,Scoreboard,ScoreboardMode
from suites.frontend.bpu.sc.model.eligibility import META,FAMILIES,GATES,RULES


class EligibilityChecks:
    def __init__(self,program,coverage):
        self.program,self.coverage=program,coverage
        self.board=Scoreboard('sc.warm-eligibility')
        self.sources={};self.warm={};self.spent=set();self.accepted_feedback_ids=set();self.queries={}
        self.warm_ready=False
        self.counts={owner.name:0 for owner in program.owners}
        self.reversals={owner.name:0 for owner in program.owners}
        self.reverse_sources={};self.reverse_views={};self.reverse_feedback_ticks={}

    def check(self,expected,actual,point,transfer=None):
        self.board.check(expected=expected,actual=actual,context=CheckContext(self.board.name,
            ScoreboardMode.DIRECT,sequence_id=None if transfer is None else transfer.sequence_id,
            request=dict(point=point,program=self.program,qualified_votes=dict(self.counts),
                         reverse_votes=dict(self.reversals)),
            accepted_event=None if transfer is None else transfer.accepted_event,
            observed_event=None if transfer is None else transfer.completed_event))

    def source(self,owner,gate,transfer,prediction,actual_input):
        self.check(False,transfer.sequence_id in self.sources,'every original occurrence has a unique identity',transfer)
        self.check(self.program.request(owner,gate),transfer.request,'driver owns the complete declared lookup',transfer)
        self.check(True,transfer.accepted_event is not None and transfer.completed_event is not None and
            transfer.accepted_event.tick<transfer.completed_event.tick,'source actually accepted and responded',transfer)
        # This is an independently monitored INPUT witness, not model output
        # or sampled weights used to seed an expectation. Distinguish two
        # different gate failures even when both publicly return used=0.
        self.check(self.program.actual_input(owner,gate),actual_input,
                   'actual request qualification belongs to this original occurrence',transfer)
        self.sources[transfer.sequence_id]=(prediction,deepcopy(prediction.meta))

    def prediction(self,expected,actual,transfer):
        observed=dict(takens=actual.takens,useds=actual.useds,
            meta={key:tuple(actual.meta[key]) for key in META},
            families={key:tuple(actual.meta['debug'][key]) for key in FAMILIES})
        self.check(expected,observed,'complete defined warm decision and metadata',transfer)

    def cold_source(self,owner,transfer,prediction,actual_input):
        self.check(set(),self.spent,'all cold occurrences must respond before any learning')
        self.source(owner,'eligible',transfer,prediction,actual_input)
        expected,_=self.program.expected(owner,'eligible',{owner.name:0 for owner in self.program.owners})
        self.prediction(expected,prediction,transfer)
        self.warm[transfer.sequence_id]=(owner,deepcopy(expected['meta']),transfer.completed_event.tick)

    def feedback(self,source_id,*,reverse=False):
        sources=self.reverse_sources if reverse else self.warm
        self.check(True,source_id in sources,'feedback owns a designated original occurrence')
        self.check(False,source_id in self.spent,'one real feedback per original source')
        owner,expected,_=sources[source_id]
        actual,frozen=self.sources[source_id]
        self.check(frozen,actual.meta,'warm metadata cannot be rewritten by later learning')
        self.spent.add(source_id)
        return (self.program.feedback(owner,deepcopy(frozen),reverse=reverse),
                self.program.feedback(owner,deepcopy(expected),reverse=reverse))

    def accepted_feedback(self,source_id,accepted_tick,*,reverse=False):
        self.check(True,source_id in self.spent,'accepted feedback was explicitly designated')
        self.check(False,source_id in self.accepted_feedback_ids,'one actual accepted feedback per source')
        sources=self.reverse_sources if reverse else self.warm
        self.check(True,source_id in sources,'actual accepted feedback retains its declared phase')
        owner,_,responded=sources[source_id]
        self.check(True,accepted_tick>responded,'learning follows its own original public response')
        self.check(True,accepted_tick>max(record[2] for record in self.warm.values()),
                   'all designated cold responses precede the first warm learning')
        if reverse:
            self.reversals[owner.name]+=1
            self.check(True,self.reversals[owner.name]<=self.program.reversal_steps(owner),
                       'reverse count was frozen before driving and stops at the declared strong opposite result')
            self.reverse_feedback_ticks[owner.name,self.reversals[owner.name]]=accepted_tick
        else:
            self.counts[owner.name]+=1
            self.check(True,self.counts[owner.name]<=self.program.warm_votes,'no extra outcome silently increases warm state')
        self.accepted_feedback_ids.add(source_id)

    def warm_complete(self):
        self.check(set(self.warm),self.spent&self.warm.keys(),'all designated warm sources consumed exactly once')
        self.check(set(self.warm),self.accepted_feedback_ids&self.warm.keys(),'every warm source has an actual accepted feedback')
        self.program.require_strong_warm_state(self.counts)
        if not self.warm_ready:
            self.coverage.record('reached','qualified-warm-learning',votes=dict(self.counts))
            self.warm_ready=True

    def query(self,probe,transfer,prediction,actual_input):
        self.program.require_strong_warm_state(self.counts)
        self.check(self.program.probes[probe.ordinal],probe,'each declared semantic query has its own identity')
        self.check(False,probe.ordinal in self.queries,'no response is credited twice')
        self.source(probe.owner,probe.gate,transfer,prediction,actual_input)
        rule=probe.gate if probe.gate in GATES else 'original-query-ownership'
        self.coverage.record('reached',rule,owner=probe.owner.name,ordinal=probe.ordinal,
                             accepted_tick=transfer.accepted_event.tick)
        expected,_=self.program.expected(probe.owner,probe.gate,self.counts)
        self.prediction(expected,prediction,transfer)
        self.queries[probe.ordinal]=dict(owner=probe.owner.name,gate=probe.gate,
            accepted_tick=transfer.accepted_event.tick,completed_tick=transfer.completed_event.tick,
            source_id=transfer.sequence_id,observed_pc=actual_input['pc'],
            observed_qualification=dict(position=actual_input['branches'][0].position,
                provider_valid=actual_input['branches'][0].provider_valid,
                main_hit=actual_input['branches'][0].mbtb_valid,
                branch_type=actual_input['branches'][0].branch_type))

    def reverse_source(self,owner,transfer,prediction,actual_input):
        self.check(set(range(len(self.program.probes))),set(self.queries),
                   'preservation consumers finish before the deliberate reverse learning test')
        self.source(owner,'eligible',transfer,prediction,actual_input)
        self.check(True,transfer.accepted_event.tick>max(view['completed_tick'] for view in self.queries.values()),
                   'every reverse source is fresh after the qualification episode')
        expected,_=self.program.expected(owner,'eligible',self.counts,self.reversals)
        self.prediction(expected,prediction,transfer)
        self.reverse_sources[transfer.sequence_id]=(owner,deepcopy(expected['meta']),transfer.completed_event.tick)

    def reverse_consumer(self,owner,transfer,prediction,actual_input):
        step=self.reversals[owner.name]
        self.check(True,step>0,'reverse consumer follows a real accepted opposite outcome')
        self.check(False,(owner.name,step) in self.reverse_views,'one fresh consumer per opposite outcome')
        self.source(owner,'eligible',transfer,prediction,actual_input)
        self.check(True,transfer.accepted_event.tick>self.reverse_feedback_ticks[owner.name,step],
                   'reverse consumer is freshly accepted after its actual opposite feedback')
        expected,_=self.program.expected(owner,'eligible',self.counts,self.reversals)
        self.prediction(expected,prediction,transfer)
        self.reverse_views[owner.name,step]=dict(owner=owner.name,step=step,
            feedback_tick=self.reverse_feedback_ticks[owner.name,step],
            accepted_tick=transfer.accepted_event.tick,completed_tick=transfer.completed_event.tick,
            source_id=transfer.sequence_id,taken=prediction.takens[0],used=prediction.useds[0],
            family_directions=tuple(prediction.meta['debug'][key][0] for key in FAMILIES))

    def finish(self):
        self.check(0,self.board.status.failed,'a prior mismatch cannot acquire final checked credit')
        self.warm_complete()
        self.check(set(range(len(self.program.probes))),set(self.queries),'every original query has a compared response')
        records=tuple(self.queries[i] for i in range(len(self.program.probes)))
        for owner in self.program.owners:
            for gate in GATES:
                rejected=[item for item in records if item['owner']==owner.name and item['gate']==gate]
                self.check(1,len(rejected),'one real rejection witness per owner and eligibility cause')
                restored=[item for item in records if item['owner']==owner.name and item['gate']=='eligible'
                    and item['accepted_tick']>rejected[0]['completed_tick']]
                self.check(True,bool(restored),'fresh valid consumer follows each rejection without relearning')
        if self.program.mode=='pipelined':
            self.check((2,)*(len(records)-1),tuple(b['accepted_tick']-a['accepted_tick']
                for a,b in zip(records,records[1:])),'actual adjacent input cycles prove pipeline submission')
        else:
            self.check(True,all(b['accepted_tick']>a['completed_tick'] for a,b in zip(records,records[1:])),
                       'serial control waits each real response before the next lookup')
        for prediction,frozen in self.sources.values():
            self.check(frozen,prediction.meta,'all original metadata survive qualification changes')
        expected_reversals={owner.name:self.program.reversal_steps(owner) for owner in self.program.owners}
        self.check(expected_reversals,self.reversals,'all declared opposite outcomes were independently qualified')
        self.check({(owner.name,step) for owner in self.program.owners
            for step in range(1,expected_reversals[owner.name]+1)},set(self.reverse_views),
            'every learning-strength step has a new exact family and public consumer')
        self.check(set(self.reverse_sources),self.spent&self.reverse_sources.keys(),
                   'all original reverse sources consumed once')
        self.check(set(self.reverse_sources),self.accepted_feedback_ids&self.reverse_sources.keys(),
                   'every reverse source was actually accepted')
        for owner in self.program.owners:
            final=self.reverse_views[owner.name,expected_reversals[owner.name]]
            self.check((1,1-owner.outcome),(final['used'],final['taken']),
                       'final real correction opposes the unchanged original TAGE base')
        self.coverage.record('reached','fresh-restoration',owners=len(self.program.owners))
        self.coverage.record('reached','immutable-originals',sources=len(self.sources))
        self.coverage.record('reached','retained-learning-strength',reverse_votes=dict(self.reversals))
        for rule in RULES:self.coverage.record('checked',rule,sources=len(self.sources),queries=len(records))

    def summary(self):
        return dict(profile=self.program.profile,qualified_votes=dict(self.counts),
            warm_sources=len(self.warm),spent_sources=len(self.spent),query_sources=len(self.queries),
            spent_warm_sources=len(self.spent&self.warm.keys()),reverse_sources=len(self.reverse_sources),
            spent_reverse_sources=len(self.spent&self.reverse_sources.keys()),reverse_votes=dict(self.reversals),
            source_input_checks=len(self.sources),comparisons=self.board.status.checked,
            accepted_queries=tuple(self.queries[i] for i in sorted(self.queries)),
            reverse_consumers=tuple(self.reverse_views[key] for key in sorted(self.reverse_views)))
