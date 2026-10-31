"""Closed-form version changes and exact original-read association."""
from copy import deepcopy
from toffee import CheckContext,Scoreboard,ScoreboardMode,TransferState
from suites.frontend.bpu.utage.model.semantic import (Context, indices, tag, index_view, tag_view,
    training_folds)
from suites.frontend.bpu.utage.model.read_lifetime import PC
from suites.frontend.bpu.utage.model.read_ownership import FeedbackLedger
from suites.frontend.bpu.utage.checker.checking import UtageUsefulChecker
from suites.frontend.bpu.utage.case.definitions import SHADOW_CAPACITY


def values(prediction):
    if not prediction.hit:return 0,None,None,None
    source=prediction.meta['abtbResult'][0]
    return prediction.hit,source['tableId'],source['takenCtr_value'],prediction.taken


class Checks:
    def __init__(self,program):
        self.program,self.phase=program,'normal preparation'
        self.board=Scoreboard('utage.original-read-version')

    def check(self,expected,actual,point):
        self.board.check(expected=expected,actual=actual,context=CheckContext(self.board.name,
            ScoreboardMode.DIRECT,request=dict(program=self.program.state(),phase=self.phase,point=point)))

    def lifetime(self,read,response,effect):
        p=self.program
        same=p.relation=='read-with-write'
        self.check(True,read['tick']==effect['tick'] if same else read['tick']>effect['tick'],
            'actual original A0 read meets, or strictly follows, the actual learning effect')
        self.check((True,PC,index_view(Context.from_recent(p.history)),indices(PC,Context.from_recent(p.history))),
            (bool(read['events'].select),read['events'].read_pc,index_view(read['events'].read_context),read['read'].indices),
            'declared original read has its own PC and complete history, not an idle equal-PC frame')
        self.check(True,response['frame'].read.entries is read['read'].entries,
            'this exact immutable read tuple reaches matching and response; content equality is insufficient')
        self.check(p.expected,values(response['actual']),'complete declared original response version')
        self.check((PC,tag_view(Context.from_recent(p.history))),(response['frame'].pc,tag_view(response['frame'].context)),
            'response tag/history ancestor is the original request')
        if same:
            entry=read['read'].entries[0]
            self.check((True,tag(PC,Context.from_recent(p.history),0),p.old_counter),
                (entry.valid,entry.tag,entry.counter),'same-boundary physical read retains original branch version')
        logical=tuple(sorted((table*512+index,old,new) for table,index,old,new,*_ in effect['effects'] if old!=new))
        self.check(p.changes(),logical,'independent reset-derived learning effects')
        self.check(p.changes(),tuple(sorted(effect['native'].get('changes',()))),
            'actual full-protection delta witnesses the same effect boundary')


class LateReplacementChecks(Checks):
    def __init__(self,program):
        super().__init__(program)
        self.board=Scoreboard('utage.late-original-owner-reconstruction')
        self.originals=[]
        self.feedback=FeedbackLedger()
        self.sent=[]
        self.expected_feedback=[]
        self.compared=0

    def source(self,spec,transfer,source,expected=None):
        self.check(TransferState.COMPLETED,transfer.state,'the public original transfer actually completed')
        self.check(True,transfer.accepted_event.tick<transfer.completed_event.tick,'source response follows its original admission')
        self.check(True,all(source is not row['source'] for row in self.originals),'equal queries remain distinct original occurrences')
        self.check(spec.expected if expected is None else expected,values(source),'declared fresh original provider, direction and counter')
        self.check(spec.indices,tuple(source.meta['readIndex']),'source retains both original read indices')
        self.check(training_folds(Context.from_recent(spec.history)),
            training_folds(tuple(row['foldedHist'] for row in source.meta['foldedPathHistForTrain_hist'])),
            'source retains every original matching-history fold')
        branch=source.meta['abtbResult'][0]
        from suites.frontend.bpu.utage.model.read_lifetime import POSITION
        self.check((1,POSITION,spec.base),(branch['valid'],branch['cfiPosition'],branch['baseTaken']),
            'source belongs to the original conditional branch and base direction')
        token=len(self.originals)
        self.originals.append(dict(source=source,metadata=deepcopy(source.meta),spec=spec,
            accepted=transfer.accepted_event.tick,completed=transfer.completed_event.tick))
        self.feedback.capture(token,spec,source.meta)
        return token

    def owned_feedback(self,step,token,transaction):
        self.check(len(self.sent),step.ordinal,'no declared original feedback can be omitted or reordered')
        original=self.originals[token]
        self.check(step.source,original['spec'],'feedback uses the exact declared old or fresh source, not a replacement query')
        from suites.frontend.bpu.utage.model.read_lifetime import POSITION
        predicted=step.source.base if step.source.counter is None else int(step.source.counter>=4)
        self.check((step.source.pc,POSITION,step.actual,int(predicted!=step.actual),original['metadata']),
            (transaction.pc,transaction.position,transaction.actual_taken,transaction.mispredict,transaction.meta),
            'complete feedback retains its original identity, qualification and metadata')
        self.feedback.consume(token)
        self.expected_feedback.append(UtageUsefulChecker._payload(transaction))
        self.sent.append(token)

    def prefix(self,monitor,count):
        if monitor.failure is not None:raise monitor.failure
        self.check(count,len(monitor.records),'each original learning has exactly one observed actual write boundary')
        steps=self.program.steps
        long_sequence=sum(step.companion for step in steps[:self.compared])
        for step,row in zip(steps[self.compared:count],monitor.records[self.compared:count],strict=True):
            self.phase=step.name
            self.check(False,row['aged'],'this bounded lifetime does not invent an aging event')
            self.check(step.changes,row['changes'],'actual protection deltas preserve every non-target identity')
            self.check(True,self.originals[self.sent[step.ordinal]]['completed']<monitor.public[step.ordinal]['tick']<row['tick'],
                'actual feedback and learning follow completion of their own original response')
            keys={'0','1'} if step.companion else {'0'}
            self.check(keys,set(row['versions']),'only the declared short update and legitimate companion allocation occur')
            for key in sorted(keys):
                actual=row['versions'][key]
                sequence=step.ordinal if key=='0' else long_sequence
                self.check((sequence,SHADOW_CAPACITY,(sequence+1)%SHADOW_CAPACITY),
                    (actual['sequence'],actual['depth'],actual['next']),'actual full-version chronology cannot be inferred from equal endpoint values')
                self.check(step.cell(int(key)),actual['new_cell'],'actual retained write has the complete original tag, position and independently expected counter')
            long_sequence+=int(step.companion)
        self.compared=count
        self.check(self.program.protection_after(count),monitor.all_protection(),'all1024 actual protection values after this learning prefix')

    def cadence(self,monitor):
        late=monitor.public[-2:]
        self.check(2,len(late),'both late original feedbacks are actually observed')
        delta=late[1]['tick']-late[0]['tick']
        self.check(True,delta==2 if self.program.mode=='adjacent' else delta>2,
            'actual late-feedback acceptance matches the requested serial or adjacent driver mode')
        return delta

    def finish(self,monitor):
        self.check(self.expected_feedback,[row['bits'] for row in monitor.public],'every observed complete feedback matches its own original source')
        self.check(len(self.program.steps),self.compared,'both intermediate retags and all preparation writes were compared')
        self.check(len(self.program.steps),len(self.feedback.consumed),'each source teaches exactly once, including both old originals')
        self.check(tuple(row['metadata'] for row in self.originals),tuple(row['source'].meta for row in self.originals),
            'later predictions and feedback do not mutate any original complete metadata')
