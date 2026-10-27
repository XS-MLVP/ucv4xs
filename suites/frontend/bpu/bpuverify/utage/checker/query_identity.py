"""Occurrence/index association over the unchanged independent UtageReference."""
from toffee import Scoreboard,TransferState
from bpuverify.utage.model.semantic import Context
from bpuverify.utage.case.definitions import SHADOW_CAPACITY
from bpuverify.utage.checker.query_cohort import Checks as OriginalChecks
from bpuverify.utage.checker.read_lifetime import values
from bpuverify.utage.model.query_identity import PC,POSITION,READ_PCS


class Checks(OriginalChecks):
    def __init__(self,program):
        super().__init__(program)
        self.board=Scoreboard('utage.complete-index-alias')
        self.feedback_owners=[]

    def owned_feedback(self,owner,ordinal,transaction):
        self.check((PC,POSITION,self.program.actual(owner),self.program.read_indices(owner)),
            (transaction.pc,transaction.position,transaction.actual_taken,tuple(transaction.meta['readIndex'])),
            'complete original feedback belongs to the declared full index, not matching PC/tag alone')
        self.original_feedback(ordinal,transaction)
        self.feedback_owners.append(owner)

    def prediction(self,owner,actual,expected):
        self.check(self.program.read_indices(owner),tuple(actual.meta['readIndex']),
            'complete index identity survives the returned public metadata')
        self.check(expected,values(actual),'opposed original identities keep their independently declared versions')

    def responses(self,transfers,actuals,monitor,effect):
        p=self.program;owners=p.cohort_owners
        self.check(len(owners),len(transfers),'all declared mixed-owner query occurrences are present')
        self.check(len(owners),len(actuals),'one completed actual response per mixed-owner original')
        accepted=tuple(t.accepted_event.tick for t in transfers)
        self.check(tuple(accepted[0]+2*i for i in range(len(owners))),accepted,'actual adjacent mixed-owner admissions')
        self.check(tuple(t+4 for t in accepted),tuple(t.completed_event.tick for t in transfers),
            'each original completes its established two-cycle response protocol')
        self.check(True,all(a.accepted_event.tick<b.accepted_event.tick<a.completed_event.tick
            for a,b in zip(transfers,transfers[1:])),'the existing driver keeps original queries overlapped')
        entries=[];target_ages=set();other_count=0;result=[]
        for ordinal,(owner,transfer,actual) in enumerate(zip(owners,transfers,actuals,strict=True)):
            self.check(TransferState.COMPLETED,transfer.state,'framework scoreboard owns each completion')
            read=monitor.at(transfer.accepted_event.tick+2);response=monitor.at(transfer.completed_event.tick)
            relation='before' if read['tick']<effect['tick'] else 'same-boundary' if read['tick']==effect['tick'] else 'after'
            self.check((True,READ_PCS[owner],Context(),p.read_indices(owner)),
                (bool(read['events'].select),read['events'].read_pc,read['events'].read_context,read['read'].indices),
                'the original read ancestry identifies this occurrence even when current matching PC/tag are equal')
            self.check((PC,Context()),(response['frame'].pc,response['frame'].context),'common matching context is not an association key')
            self.check(True,response['frame'].read.entries is read['read'].entries,
                'the exact original immutable read tuple reaches this response')
            self.check(True,all(read['read'].entries is not prior for prior in entries),
                'equal-content original occurrences remain separate')
            wanted=p.expected(owner,relation=relation)
            self.prediction(owner,actual,wanted);self.prediction(owner,response['actual'],wanted)
            if owner==p.teacher:target_ages.add(relation)
            else:other_count+=1
            self.remember(actual);entries.append(read['read'].entries)
            result.append(dict(owner=owner,ordinal=ordinal,accepted=transfer.accepted_event.tick,
                read=read['tick'],completed=transfer.completed_event.tick,relation=relation,
                full_indices=p.read_indices(owner),expected=wanted,actual=values(actual),exact_original_read_tuple=True))
        self.check({'before','same-boundary','after'},target_ages,'one target identity spans all three actual learning ages')
        self.check(4,other_count,'the other opposed identity is checked throughout the same burst')
        return result

    def turnover(self,monitor):
        p=self.program;expected=p.versions();rows=monitor.versions
        self.check(len(expected),len(rows),'two normal allocations, first learning and full mixed-source retention turnover')
        self.check(len(expected),len(monitor.effects),'every learning effect is compared, including saturation holds')
        self.check(tuple(range(len(expected))),tuple(row['logical_sequence'] for row in rows),
            'each actual retained write has one independent chronological learning obligation')
        self.check(True,all(a['tick']<b['tick'] for a,b in zip(rows,rows[1:])),
            'distinct actual learning boundaries produce the versions')
        for ordinal,(row,wanted) in enumerate(zip(rows,expected,strict=True)):
            self.check(SHADOW_CAPACITY,row['depth'],'real retention capacity is not shortened')
            self.check((ordinal+1)%SHADOW_CAPACITY,row['next'],'actual retention allocation advances once per owned write')
            self.check(wanted['cell'],row['new_cell'],'actual retained entry belongs to the correct complete identity and version')
            self.check(wanted['protection_changes'],tuple(sorted(monitor.effects[ordinal]['native'].get('changes',()))),
                'each learning changes only its own complete-index protection or holds at saturation; transient other-cell writes are forbidden')
        tail=monitor.public[-SHADOW_CAPACITY:]
        deltas=tuple(b['tick']-a['tick'] for a,b in zip(tail,tail[1:]))
        self.check(True,all(delta==2 if p.mode=='adjacent' else delta>2 for delta in deltas),
            'actual feedback cadence agrees with the selected existing driver communication mode')

    def finish(self,monitor):
        self.check([0,1,self.program.teacher,*self.program.turnover_owners],self.feedback_owners,
            'every expected learning has its distinct declared original owner')
        super().finish(monitor)
