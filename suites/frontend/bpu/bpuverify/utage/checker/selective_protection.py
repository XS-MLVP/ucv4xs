"""Compare declared semantic effects, complete inputs and actual read ownership."""
from toffee import Scoreboard,TransferState
from bpuverify.utage.model.semantic import Context
from bpuverify.utage.checker.query_cohort import Checks as OriginalChecks
from bpuverify.utage.checker.read_lifetime import values
from bpuverify.utage.model.selective_protection import PC,POSITION,READ_PCS


class Checks(OriginalChecks):
    def __init__(self,program):
        super().__init__(program)
        self.board=Scoreboard('utage.full-index-selective-protection')
        self.sent=[];self.compared=0;self.cadences=[]

    def source(self,step,source):
        self.prediction(step.owner,step.history,source,step.expected)
        return self.remember(source)

    def prediction(self,owner,history,source,expected):
        indices=getattr(self.program,'read_indices',lambda owner:(owner*256,owner*256))(owner)
        self.check(indices,tuple(source.meta['readIndex']),'complete read identity survives public metadata')
        self.check(Context.from_recent(history).folds,tuple(row['foldedHist'] for row in source.meta['foldedPathHistForTrain_hist']),
            'all original matching-history folds survive; short-provider isolation is not metadata mutation')
        self.check(expected,values(source),'independently declared short/long provider, counter and direction')

    def owned_feedback(self,step,ordinal,transaction):
        self.check(len(self.sent),step.ordinal,'declared learning occurrences cannot be skipped or reordered')
        self.check((PC,POSITION,step.actual,step.indices),
            (transaction.pc,transaction.position,transaction.actual_taken,tuple(transaction.meta['readIndex'])),
            'learning belongs to the declared original complete index and outcome')
        self.original_feedback(ordinal,transaction)
        self.sent.append(step.ordinal)

    def prefix(self,monitor,count):
        if monitor.failure is not None:raise monitor.failure
        self.check(count,len(monitor.records),'every learning write, including no-useful-effect writes, is observed once')
        long_sequence=sum(step.companion_allocation for step in self.program.steps[:self.compared])
        for step,row in zip(self.program.steps[self.compared:count],monitor.records[self.compared:count],strict=True):
            self.check(False,row['aged'],'no invented maintenance is needed for the declared protection events')
            self.check(step.changes,row['changes'],'each actual full-state delta belongs to its original provider; all non-target cells preserve')
            keys={'0','1'} if step.companion_allocation else {'0'}
            self.check(keys,set(row['versions']),'real wrong feedback legitimately allocates a companion; base agreement still writes direction')
            for table in sorted(keys):
                actual=row['versions'][table]
                sequence=step.ordinal if table=='0' else long_sequence
                self.check((sequence,8,(sequence+1)%8),(actual['sequence'],actual['depth'],actual['next']),
                    'real retained chronology and pointer advance, not a fabricated loop count')
                self.check(step.counter_cell if table=='0' else step.companion_cell,actual['new_cell'],
                    'actual retained version keeps declared complete identity and learned direction')
            long_sequence+=int(step.companion_allocation)
        self.compared=count
        self.check(self.program.protection_after(count),monitor.all_protection(),'entire reset-derived protection state after this declared prefix')

    def cadence(self,group,public):
        self.check(len(group),len(public),'every complete original feedback is actually admitted')
        if len(group)>1:
            delta=public[1]['tick']-public[0]['tick']
            self.check(True,delta==2 if self.program.mode=='adjacent' else delta>2,
                'actual two-original feedback cadence matches the selected existing driver')
            self.cadences.append(dict(phase=group[0].phase,delta=delta,mode=self.program.mode))

    def check_cohort(self,transfers,actuals,monitor,effect):
        p=self.program;owners=p.cohort_owners
        history=getattr(p,'cohort_history',64)
        self.check(7,len(transfers),'all mixed-owner original queries are retained')
        self.check(7,len(actuals),'one actual response per original occurrence')
        accepted=tuple(t.accepted_event.tick for t in transfers)
        self.check(tuple(accepted[0]+2*i for i in range(7)),accepted,'actual adjacent query admissions')
        self.check(tuple(t+4 for t in accepted),tuple(t.completed_event.tick for t in transfers),
            'actual original responses use the established two-cycle protocol')
        self.check(True,all(a.accepted_event.tick<b.accepted_event.tick<a.completed_event.tick
            for a,b in zip(transfers,transfers[1:])),'original requests overlap before prior completion')
        result=[];entries=[];ages=set();other=0
        for owner,transfer,actual in zip(owners,transfers,actuals,strict=True):
            self.check(TransferState.COMPLETED,transfer.state,'framework scoreboard owns original completion')
            read=monitor.at(transfer.accepted_event.tick+2);response=monitor.at(transfer.completed_event.tick)
            relation='before' if read['tick']<effect['tick'] else 'same-boundary' if read['tick']==effect['tick'] else 'after'
            self.check((True,READ_PCS[owner],Context(),(owner*256,owner*256)),
                (bool(read['events'].select),read['events'].read_pc,read['events'].read_context,read['read'].indices),
                'each original retains its complete read ancestor')
            self.check((PC,Context.from_recent(history)),(response['frame'].pc,response['frame'].context),
                'real matching history rejects the companion but preserves the original short provider')
            self.check(True,response['frame'].read.entries is read['read'].entries,'response retains the exact original immutable read tuple')
            self.check(True,all(read['read'].entries is not previous for previous in entries),'equal-valued queries remain distinct occurrences')
            wanted=p.cohort_expected(owner,relation)
            self.prediction(owner,history,actual,wanted);self.prediction(owner,history,response['actual'],wanted)
            if owner==p.first:ages.add(relation)
            else:other+=1
            self.remember(actual);entries.append(read['read'].entries)
            result.append(dict(owner=owner,accepted=transfer.accepted_event.tick,read=read['tick'],
                completed=transfer.completed_event.tick,relation=relation,expected=wanted,actual=values(actual),
                exact_original_read_tuple=True))
        self.check({'before','same-boundary','after'},ages,'one real lower-boundary direction correction spans all three query ages')
        self.check(4,other,'the other opposed identity is checked throughout the same burst')
        return result

    def finish(self,monitor):
        self.check(list(range(len(self.program.steps))),self.sent,'each declared feedback owns a distinct original source once')
        self.check(len(self.program.steps),self.compared,'every declared learning effect has been compared')
        super().finish(monitor)
