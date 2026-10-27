"""Original iteration, complete accepted effects, and actual numeric consumers."""
from copy import deepcopy
from collections import deque
from dataclasses import asdict

from bpuverify.bpu.checker.statistical_prefix import Checks as PrefixChecks
from bpuverify.bpu.model.pipeline import Resolution
from bpuverify.bpu.model.sc_loop_experience import Program,RULES
from bpuverify.sc.model.semantic import Context,FAMILIES,coordinates,feedback_needs_read


class Checks(PrefixChecks):
    program_type=Program

    def __init__(self,profile,coverage):
        super().__init__(profile,coverage)
        self.probe=None
        self.receipts=[]
        self.consumers=[]
        self.private_loop=[]
        self.warm_sources=()
        self.cold_read=None
        self.expected_patches=()
        # Failure-only, bounded context; never a whole-run cycle trace.
        self.micro_recent=deque(maxlen=12)

    def candidates(self,row,*args):
        super().candidates(row,*args)
        self.training=row['inputs']['training']
        self.expected_patches=self.bank.sc.preview_learning()[0]
        third=self.cycle.tokens[2]
        late=self.cycle.decisions[2]
        pending=self.bank.micro.learning
        self.micro_recent.append(dict(tick=self.pipeline.current_event.tick,
            input_valid=bool(self.training['valid']),input_ready=bool(self.training['ready']),
            accepted=self.events.feedback is not None,
            prediction_ready=self.events.prediction_ready,
            fast=None if third is None else dict(owner=third.sequence,pc=third.pc,
                branch=asdict(late.branch),repair=self.cycle.final_repair),
            pending=None if pending is None else asdict(pending),
            expected=tuple((i,e.confidence) for i,e in enumerate(self.bank.micro.entries) if e.confidence),
            observed=tuple((i,v) for i,v in enumerate(row['observed']['micro_confidence']) if v)))
        return ()

    def source(self,receipt,iteration):
        token=self.save(receipt)
        value=self.bank.statistical_snapshot(token,resolved=True)
        history=self.bank.queries.snapshot(token)
        self.check((self.program.b,iteration),(token.pc,history.loop),
            'a genuine original belongs to the declared loop instruction and iteration')
        self.check(True,history.read.valid,'natural loop has valid conditional experience at the query')
        self.check(history.read,history.metadata,'uninterrupted loop source retains its original history view')
        self.check(self.bank.queries.sc_history(token),value.original.history,
            'SC original uses the independently scheduled path, condition and iteration experience')
        self.numeric_consumer(receipt)
        return token,value

    def provider(self,receipt):
        token,value=self.source(receipt,self.program.old_iteration)
        slot,=[i for i,branch in enumerate(value.branches)
            if branch is not None and branch.position==self.program.position]
        fields=dict(self.bank.tage_snapshot(token,resolved=True).wanted)
        self.check((True,self.program.provider_counter),
            (bool(fields[f'{slot}.has_provider']),fields[f'{slot}.counter']),
            'loop SC eligibility follows a real retained TAGE provider')
        return slot,value

    def consume(self,receipt,iteration,phase):
        token,value=self.source(receipt,iteration)
        numeric=self.numeric_consumer(receipt)
        self.consumers.append(dict(phase=phase,owner=token.sequence,iteration=iteration,
            indices=value.original.read.indices,weights=value.original.read.weights,
            numeric=numeric,used=value.prediction.used,scores=value.prediction.sums))
        return value

    def begin(self,receipt,taken,label):
        self.check(None,self.probe,'one complete original feedback at a time')
        token,value=self.source(receipt,self.program.old_iteration)
        outcome=self.program.outcome(token,value.late,taken)
        resolution=Resolution(token.history,token.pc,(outcome,),origin=token)
        transaction=self.bank.sc_feedback(resolution,True)
        expected_read=label!='used-correct'
        self.check(expected_read,feedback_needs_read(transaction),
            'original SC evidence, not current iteration or confidence, determines read qualification')
        current=self.bank.queries.iterations.cursor
        if label.startswith('used-'):
            self.check(True,current>=self.program.young_iteration,
                'younger genuine loop predictions precede the old original feedback')
            self.mark('younger-distinct-iteration')
        self.probe=dict(label=label,source=token,resolution=resolution,needs_read=expected_read,
            concurrent=label.startswith('used-') and self.program.overlap,
            current_iteration=current,before=(deepcopy(self.bank.sc.memory),self.bank.sc.thresholds.values),
            reads=[],offers=[],accepted=[],blocked=[],overlap=[],payload=None)

    def checked(self,tick,*args):
        super().checked(tick,*args)
        probe=self.probe
        if probe is None:return
        request=self.events.feedback
        feedback=None if request is None else self.bank.sc_feedback(request,True)
        needed=feedback is not None and feedback_needs_read(feedback)
        context=Context() if feedback is None else Context.from_history(feedback.history)
        bank,indices=coordinates(0 if feedback is None else feedback.pc,context)
        ports=self.observed['statistical']['accepted_reads']
        for family,port,index in zip(FAMILIES,ports,indices,strict=True):
            active=needed and (context.common_valid or family not in ('global','backward'))
            self.check(active,bool(port['valid']),'each actual training read follows the original qualification')
            if active:self.check((index,1<<bank),(port['index'],port['bank']),
                'actual learning reads the original iteration, not the current loop')
        if needed:
            self.check(self.program.old_iteration,context.loop,'accepted learning keeps its original nonzero iteration')
            probe['reads'].append(dict(tick=tick,iteration=context.loop,ports=deepcopy(ports)))
        if self.training['valid']:
            payload={key:deepcopy(value) for key,value in self.training.items() if key not in ('valid','ready')}
            if probe['payload'] is None:probe['payload']=payload
            self.check(probe['payload'],payload,'all held original fields remain immutable')
            if self.cycle.fires[0]:
                self.check(True,probe['concurrent'],'serial original feedback has no continuing prediction')
                self.check(self.program.b,self.cycle.next_pc,'overlap belongs to the genuine conditional loop')
                probe['overlap'].append(tick)
            if not self.observed['statistical']['ready']:
                self.check(True,probe['concurrent'] and probe['needs_read'],'only a declared original read conflict waits')
                self.check([],probe['accepted'],'held old original has not already been accepted')
                self.check(probe['before'],(self.bank.sc.memory,self.bank.sc.thresholds.values),
                    'unaccepted feedback cannot learn from any younger iteration')
                probe['blocked'].append(tick)
        if request is not None:
            self.check(True,request.origin is probe['source'],'actual acceptance retains the exact old original')
            self.check(probe['resolution'].branches,tuple(b for b in request.branches if b is not None),
                'accepted conditional truth is unchanged')
            self.check([],probe['accepted'],'each complete old original is accepted once')
            self.check(probe['concurrent'] and not probe['needs_read'],bool(self.cycle.fires[0]),
                'actual acceptance follows release or coexists with no-read prediction')
            probe['accepted'].append(tick)
        if self.expected_patches:
            self.check(True,bool(probe['accepted']),'a real accepted owner precedes every learning offer')
            self.check(tuple(range(len(FAMILIES))),tuple(patch[0] for patch in self.expected_patches),
                'each declared learning event includes all five independently compared families')
            probe['offers'].append(dict(tick=tick,patches=self.expected_patches))

    def end(self,accepted_tick):
        probe=self.probe
        self.check([accepted_tick],probe['accepted'],'driver completion equals the actual monitor acceptance')
        self.check(int(probe['needs_read']),len(probe['reads']),'old qualification controls exact training-read count')
        self.check(int(probe['needs_read']),len(probe['offers']),'cold or wrong originals learn once; used correct agreement does not')
        self.check(probe['concurrent'],bool(probe['overlap']),'declared feedback mode actually occurred')
        self.check(probe['concurrent'] and probe['needs_read'],bool(probe['blocked']),
            'actual resource conflict depends on the original read requirement')
        if not probe['needs_read']:
            self.check(probe['before'],(self.bank.sc.memory,self.bank.sc.thresholds.values),
                'confident original correct agreement preserves all learned weights and thresholds')
        self.receipts.append(dict(label=probe['label'],owner=probe['source'].sequence,
            original_iteration=self.program.old_iteration,current_iteration=probe['current_iteration'],
            reads=deepcopy(probe['reads']),offers=deepcopy(probe['offers']),accepted=probe['accepted'][0],
            blocked=tuple(probe['blocked']),overlap=tuple(probe['overlap'])))
        self.probe=None

    def finish_loop(self,fresh):
        p=self.program
        self.check(None,self.probe,'all original feedback and actual effects completed')
        self.check([*(f'cold-{i}' for i in range(p.teaching_count)),'used-correct','used-wrong'],
            [row['label'] for row in self.receipts],'the complete declared loop learning lifecycle occurred')
        self.check(len(self.receipts),len({row['owner'] for row in self.receipts}),
            'every feedback belongs to a distinct original, not duplicate evidence')
        self.check(p.teaching_count,len({self.save(source).sequence for source in self.warm_sources}),
            'cold teaching uses distinct captured original snapshots')
        self.check({'strong','after-correct','after-wrong','young-after-wrong'},
            {row['phase'] for row in self.consumers},'old and younger iterations have full actual new consumers')
        self.check(1,len(self.private_loop),'one exact before/after younger private-experience comparison')
        self.check(self.private_loop[0]['before'],self.private_loop[0]['after'],
            'old learning does not train the younger private loop feature')
        self.mark('distinct-real-teaching')
        self.mark('original-qualification')
        self.mark('complete-original-admission')
        self.mark('five-family-effects')
        self.mark('fresh-old-iteration-consumer')
        self.mark('private-younger-loop-preserved')
        return dict(super().finish(fresh),**self.summary(),status='PASS')

    def summary(self):
        result=dict(program=self.program.state(),receipts=deepcopy(self.receipts),
            numeric_consumers=deepcopy(self.consumers),private_loop=deepcopy(self.private_loop),
            completed=sorted(self.coverage.reached),original_snapshots=len(self.saved),
            pending_label=None if self.probe is None else self.probe['label'])
        if self.pipeline.failure is not None:
            result['micro_failure_context']=tuple(self.micro_recent)
        return result
