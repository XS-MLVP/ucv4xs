"""Age/occurrence comparison around the unchanged independent UtageReference."""
from copy import deepcopy
from toffee import CheckContext,Scoreboard,ScoreboardMode,TransferState
from bpuverify.utage.model.semantic import Context,indices,tag
from bpuverify.utage.model.read_ownership import FeedbackLedger
from bpuverify.utage.checker.checking import UtageUsefulChecker
from bpuverify.utage.case.definitions import SHADOW_CAPACITY
from bpuverify.utage.checker.read_lifetime import values
from bpuverify.utage.model.query_cohort import PC,POSITION,COHORT_SIZE


class Checks:
    def __init__(self,program):
        self.program=program
        self.board=Scoreboard('utage.query-cohort-and-version-turnover')
        self.originals=[]
        self.feedback=FeedbackLedger()
        self.expected_feedback=[]
        self.cohort=[]

    def check(self,expected,actual,point):
        self.board.check(expected=expected,actual=actual,context=CheckContext(self.board.name,
            ScoreboardMode.DIRECT,request=dict(point=point,program=self.program.state())))

    def remember(self,source):
        self.check(True,all(source is not prior for prior,_ in self.originals),
            'an original query occurrence cannot be renamed as another fresh source')
        ordinal=len(self.originals)
        self.originals.append((source,deepcopy(source.meta)))
        return ordinal

    def original_feedback(self,ordinal,transaction):
        source,metadata=self.originals[ordinal]
        self.check(metadata,transaction.meta,'complete feedback retains the exact original public metadata')
        self.feedback.capture(ordinal,self.program,metadata)
        self.feedback.consume(ordinal)
        self.expected_feedback.append(UtageUsefulChecker._payload(transaction))

    def responses(self,transfers,actuals,monitor,effect):
        p=self.program
        self.check(COHORT_SIZE,len(transfers),'one complete declared cohort, not selected passing samples')
        self.check(COHORT_SIZE,len(actuals),'one response per original query')
        accepted=tuple(t.accepted_event.tick for t in transfers)
        completed=tuple(t.completed_event.tick for t in transfers)
        self.check(tuple(accepted[0]+2*i for i in range(COHORT_SIZE)),accepted,'actual adjacent pipeline admissions')
        self.check(tuple(t+4 for t in accepted),completed,'each original uses the established two-cycle response protocol')
        self.check(True,all(a.accepted_event.tick<b.accepted_event.tick<a.completed_event.tick
            for a,b in zip(transfers,transfers[1:])),'adjacent requests overlap before their predecessors return')
        relations=[];entries=[]
        for ordinal,(transfer,actual) in enumerate(zip(transfers,actuals,strict=True)):
            self.check(TransferState.COMPLETED,transfer.state,'framework scoreboard owns actual completion')
            read=monitor.at(transfer.accepted_event.tick+2)
            response=monitor.at(transfer.completed_event.tick)
            relation='before' if read['tick']<effect['tick'] else 'same-boundary' if read['tick']==effect['tick'] else 'after'
            self.check((True,PC,p.read_context,p.read_indices),
                (bool(read['events'].select),read['events'].read_pc,read['events'].read_context,read['read'].indices),'original read ancestry is not replaced by current matching wires')
            self.check((p.match_pc,p.match_context),(response['frame'].pc,response['frame'].context),'matching belongs to this query occurrence')
            self.check(True,response['frame'].read.entries is read['read'].entries,
                'each response retains its exact original immutable read tuple')
            self.check(True,all(read['read'].entries is not prior for prior in entries),
                'equal same-PC values cannot merge distinct original query occurrences')
            self.check(p.query_expected(relation),values(actual),'actual response consumes its own pre/post-learning version')
            self.check(p.query_expected(relation),values(response['actual']),'cycle monitor and completed transfer agree on their original version')
            self.cohort.append(dict(ordinal=ordinal,accepted=transfer.accepted_event.tick,
                read=read['tick'],completed=transfer.completed_event.tick,relation=relation,
                expected=p.query_expected(relation),actual=values(actual),exact_original_read_tuple=True))
            entries.append(read['read'].entries);relations.append(relation)
            self.remember(actual)
        self.check({'before','same-boundary','after'},set(relations),'one actual burst spans all three semantic read ages')
        return self.cohort

    def turnover(self,monitor):
        p=self.program
        self.check(SHADOW_CAPACITY+1,len(monitor.versions),'first effect plus one full chronological retention turnover')
        start=monitor.versions[0]['next']
        sequence=monitor.versions[0]['logical_sequence']
        ticks=tuple(row['tick'] for row in monitor.versions)
        self.check(True,all(a<b for a,b in zip(ticks,ticks[1:])),
            'distinct actual learning boundaries cause the chronological versions')
        for ordinal,row in enumerate(monitor.versions):
            self.check(SHADOW_CAPACITY,row['depth'],'declared retention capacity, not a shortened artificial lap')
            self.check(sequence+ordinal,row['logical_sequence'],'each actual write has the next independent semantic version')
            self.check((start+ordinal)%SHADOW_CAPACITY,row['next'],'actual retention allocation advances on each fresh owned learning')
            cell=row['new_cell']
            self.check(dict(valid=1,data_valid=1,index=p.target_index,tag=tag(p.teacher_pc,p.read_context,p.target_table),
                position=POSITION,counter=p.counter(ordinal)),cell,'actual retained version has the declared logical identity and chronological counter')

    def finish(self,monitor):
        self.check(self.expected_feedback,[row['bits'] for row in monitor.public],
            'every complete actual feedback has one fresh original source')
        ticks=tuple(row['tick'] for row in monitor.public)
        self.check(True,all(a<b for a,b in zip(ticks,ticks[1:])),
            'each complete original feedback has a distinct chronological acceptance')
        self.check(len(self.expected_feedback),len(self.feedback.consumed),'no original source is replayed for turnover')
        self.check(tuple(saved for _,saved in self.originals),tuple(source.meta for source,_ in self.originals),
            'completed original response snapshots are not mutated by later queries or buffer turnover')
