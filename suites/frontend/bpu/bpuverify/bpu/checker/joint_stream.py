"""Check waiting, progress and subsequent two-owner effects independently."""
from copy import deepcopy
from bpuverify.bpu.checker.joint_originals import Checks as OriginalChecks
from bpuverify.bpu.model.joint_stream import Program,NEW_RULES


class Checks(OriginalChecks):
    program_type=Program

    def __init__(self,profile,coverage):
        super().__init__(profile,coverage)
        self.wait_before=None;self.waiting=[];self.stream_consumers=[];self.stream_issues=[]
        self.queue_submitted=None;self.release_requested=None;self.release_committed=None
        self.stream_open=False

    def SC_learning_state(self):
        return deepcopy((self.bank.sc.memory,self.bank.sc.thresholds.values))

    def begin_many(self,sources):
        super().begin_many(sources)
        self.wait_before=self.tage_learning_state(),self.SC_learning_state()
        self.stream_open=True

    def guard_waiting(self,tick):
        self.check([],self.accepted_order,'neither queued old result is accepted during the head conflict')
        self.check((None,None),tuple(r['accepted'] for r in self.many),'the queued tail cannot bypass its waiting head')
        self.check(self.wait_before,(self.tage_learning_state(),self.SC_learning_state()),
            'neither direction nor correction learning advances before shared acceptance')
        tage_valid=tuple(bool(r['valid']) for r in self.actual_tage)
        sc_valid=tuple(bool(r['valid']) for r in self.observed['statistical']['updates'])
        self.check((False,)*4,tage_valid,'all actual direction offers remain inactive before acceptance')
        self.check((False,)*5,sc_valid,'all actual correction families remain inactive before acceptance')
        self.check((),self.expected_patches,'waiting cannot schedule a hidden correction effect')
        self.check(True,self.cycle.fires[0],'an actual younger prediction causes this declared conflict')
        self.check(self.program.b,self.cycle.next_pc,'waiting is caused by the genuine continuing loop, not a forged read')
        self.waiting.append(dict(tick=tick,head=self.many[0]['source'].sequence,
            tail=self.many[1]['source'].sequence,accepted=(None,None),
            actual_TAGE_valid=tage_valid,actual_SC_valid=sc_valid,actual_prediction_progress=True,
            both_learning_states_unchanged=True))

    def checked(self,tick,*args):
        super().checked(tick,*args)
        if self.many is None or not self.stream_open:return
        if self.cycle.fires[0]:
            self.check(self.program.b,self.cycle.next_pc,'continuing predictions remain real loop occurrences')
            token=self.pipeline.model.stages[0]
            self.check(True,token is not None,'actual issue has a fresh independently owned source')
            self.stream_issues.append(dict(tick=tick,owner=token.sequence))
        second=self.cycle.tokens[1]
        if second is not None:self.numeric_stream_consumer(second,tick)
        if self.training['valid'] and not self.observed['statistical']['ready']:
            self.guard_waiting(tick)

    def numeric_stream_consumer(self,token,tick):
        # The pipeline's numerical proof is keyed by the owned CHECKPOINT,
        # not its separate prediction sequence. These counters need not agree.
        proof=self.pipeline.sc_numeric_checked.get(token.history.sequence,{})
        if proof.get('composition')!=tick:return
        self.check({'read','consume','composition'},set(proof),'streaming consumer has all numeric comparison boundaries')
        history=self.bank.queries.snapshot(token)
        self.check(True,history.read.valid,'continuing loop has genuine valid conditional history')
        read=self.bank.statistical_snapshot(token).read
        self.stream_consumers.append(dict(owner=token.sequence,history_owner=token.history.sequence,iteration=history.loop,
            read_tick=proof['read'],consumed_tick=tick,composition_tick=tick,
            indices=read.indices,weights=read.weights,all32_read_and_consumed_words_compared=True))

    def submitted(self,transfers):
        self.check((None,None),tuple(t.accepted_event for t in transfers),'both old results are actually queued before awaiting the head')
        self.queue_submitted=self.pipeline.current_event.tick
        self.mark('submissions-before-await')

    def end_many(self,accepted):
        super().end_many(accepted)
        self.check(True,bool(self.waiting),'the DUT actually held the queued head under prediction traffic')
        self.check(True,self.queue_submitted is not None and self.release_requested is not None,'queue submission and actual conflict release were observed')
        first=self.many[0]['accepted']
        self.check(True,self.queue_submitted<=self.waiting[0]['tick']<=self.waiting[-1]['tick']<=self.release_requested<first,
            'actual waiting precedes release and the first shared acceptance')
        consumed=[r for r in self.stream_consumers if self.queue_submitted<=r['consumed_tick']<first]
        self.check(True,bool(consumed),'real numeric prediction consumers progress while both old results wait')
        self.check(True,all(r['iteration']>max(self.program.iterations) for r in consumed),
            'streaming consumers have younger private loop identities, not a renamed old feedback source')
        self.check(True,any(any(v for family in r['weights'] for v in family) for r in consumed),
            'streaming prediction compares genuinely nonzero shared experience, not all-zero reset data')
        for rule in NEW_RULES:self.mark(rule)
        self.stream_open=False

    def summary(self):
        return dict(super().summary(),queue_submitted=self.queue_submitted,release_requested=self.release_requested,
            release_committed=self.release_committed,waiting=deepcopy(self.waiting),
            stream_issues=deepcopy(self.stream_issues),stream_consumers=deepcopy(self.stream_consumers))
