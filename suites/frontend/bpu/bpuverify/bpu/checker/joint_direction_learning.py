"""Associate one accepted original with both complete learning obligations."""
from collections import deque
from copy import deepcopy
from bpuverify.bpu.checker.sc_loop_experience import Checks as LoopChecks
from bpuverify.bpu.checker.statistical_prefix import Checks as PrefixChecks
from bpuverify.bpu.model.joint_direction_learning import Program,CORE_LABELS,tage_offer_values
from bpuverify.bpu.bundle.tage_semantic import HISTORY_PORTS


class Checks(LoopChecks):
    program_type=Program

    def __init__(self,profile,coverage):
        super().__init__(profile,coverage)
        self.expected_provider=5;self.young_private_before=None
        self.tage_offers=[];self.joint_receipts=[];self.tage_recent=deque(maxlen=12)

    def provider(self,receipt):
        token,value=self.source(receipt,self.program.old_iteration)
        slot,=[i for i,b in enumerate(value.branches) if b is not None and b.position==self.program.position]
        fields=dict(self.bank.tage_snapshot(token,resolved=True).wanted)
        self.check((True,self.expected_provider),(bool(fields[f'{slot}.has_provider']),fields[f'{slot}.counter']),
            'a fresh original consumes the independently learned direction confidence')
        return slot,value

    def candidates(self,row,*args):
        result=super().candidates(row,*args)
        self.actual_tage=deepcopy(row['observed']['joint_tage'])
        if self.probe is not None and self.probe['label'] in CORE_LABELS and self.training['valid']:
            token=self.probe['source']
            age=self.program.require_feedback_window(self.pipeline.model.history.taken_edges,token.history.taken_edges)
            expected=tuple(token.history.folds()[i] for i in HISTORY_PORTS)
            self.check(expected,row['observed']['joint_train_folds'],
                'actual TAGE training folds still belong to the live original, including during backpressure')
            self.probe['history_windows'].append(dict(tick=self.pipeline.current_event.tick,displacement_bits=age,
                budget_bits=self.program.state()['retained_history_budget_bits'],actual_folds_compared=True))
        return result

    def begin(self,receipt,taken,label):
        super().begin(receipt,taken,label)
        self.probe['tage_feedbacks']=self.bank.tage.feedbacks
        self.probe['tage_offers']=[]
        self.probe['tage_before']=self.tage_learning_state()
        self.probe['history_windows']=[]
        if label in CORE_LABELS:
            self.program.require_feedback_window(self.pipeline.model.history.taken_edges,self.probe['source'].history.taken_edges)

    def tage_learning_state(self):
        m=self.bank.tage
        return deepcopy((m.feedbacks,m.memory,m.useful,tuple(m.selectors),
            {k:(v.records,v.pending,v.recency) for k,v in m.cache.items()}))

    def checked(self,tick,*args):
        super().checked(tick,*args)
        probe=self.probe
        if probe is None:return
        joint=probe['label'] in CORE_LABELS
        if self.events.feedback is not None:
            self.check((joint,True),(bool(self.cycle.enabled[2] and self.cycle.enabled[3]),
                bool(self.cycle.enabled[2] and self.cycle.enabled[4])),
                'actual core acceptance keeps both learners enabled; preparation explicitly freezes only TAGE')
        if self.training['valid'] and not self.observed['statistical']['ready']:
            self.check(probe['tage_before'],self.tage_learning_state(),
                'whole-feedback backpressure cannot prematurely train the direction predictor')
        writes,useful,start=self.bank.tage.preview_learning()
        expected,actual=tage_offer_values(writes,useful,self.actual_tage)
        self.tage_recent.append(dict(tick=tick,label=probe['label'],accepted=self.events.feedback is not None,
            mature=self.bank.tage.mature is not None,expected=expected,actual=actual))
        self.check(expected,actual,'all actual TAGE offer identities, masks and data match independent original learning')
        if writes or useful:
            self.check(True,joint and bool(probe['accepted']),'actual direction effect belongs to one accepted joint owner')
            self.check(False,start,'this bounded feedback does not silently start unrelated aging')
            probe['tage_offers'].append(dict(tick=tick,expected=expected,actual=actual))
            self.tage_offers.append(dict(label=probe['label'],owner=probe['source'].sequence,tick=tick,
                expected=expected,actual=actual))

    def end(self,accepted_tick):
        probe=self.probe;joint=probe['label'] in CORE_LABELS
        self.check(probe['tage_feedbacks']+int(joint),self.bank.tage.feedbacks,
            'each shared acceptance reaches TAGE once, including SC no-read agreement')
        self.check(int(joint),len(probe['tage_offers']),'every joint result produces its complete direction learning offer once')
        if joint:self.joint_receipts.append(dict(label=probe['label'],owner=probe['source'].sequence,
            accepted=accepted_tick,tage_offers=deepcopy(probe['tage_offers']),
            history_windows=deepcopy(probe['history_windows'])))
        super().end(accepted_tick)

    def finish_joint(self,fresh):
        p=self.program
        self.check(None,self.probe,'all original feedback and both learner effects completed')
        self.check(['used-cold',*(f'teaching-{i}' for i in range(1,p.teaching_count)),'used-correct','used-wrong'],
            [r['label'] for r in self.receipts],'complete cold, no-read and wrong joint learning lifecycle')
        self.check(len(self.receipts),len({r['owner'] for r in self.receipts}),'every result names a distinct real original')
        self.check(p.teaching_count,len({self.save(r).sequence for r in self.warm_sources}),'distinct genuinely cold teaching originals')
        self.check(list(CORE_LABELS),[r['label'] for r in self.joint_receipts],'all three independent joint qualifications completed')
        self.check(3,len(self.tage_offers),'three separately compared complete TAGE effects')
        self.check({'after-cold','strong','after-correct','after-wrong','young-after-wrong'},
            {r['phase'] for r in self.consumers},'each shared outcome has its own fresh actual numeric consumer')
        self.check(1,len(self.private_loop),'one unselected young private-experience preservation check')
        self.check(self.private_loop[0]['before'],self.private_loop[0]['after'],'shared outcomes never train the younger private loop feature')
        for rule in ('distinct-real-teaching','original-qualification','complete-original-admission','five-family-effects',
                'fresh-old-iteration-consumer','private-younger-loop-preserved','SC-no-read-preserves-TAGE-learning',
                'joint-wrong-teaches-both','actual-TAGE-learning-offers'):
            self.mark(rule)
        return dict(PrefixChecks.finish(self,fresh),**self.summary(),status='PASS')

    def summary(self):
        result=dict(super().summary(),joint_receipts=deepcopy(self.joint_receipts),actual_tage_offers=deepcopy(self.tage_offers))
        if self.pipeline.failure is not None:result['tage_failure_context']=tuple(self.tage_recent)
        return result
