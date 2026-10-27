"""Compare instruction-prefix effects without using sampled controls as golden."""
from copy import deepcopy
from toffee import Scoreboard, TransferState
from bpuverify.utage.checker.query_cohort import Checks as OriginalChecks
from bpuverify.utage.model.semantic import Context
from bpuverify.utage.model.dual_source import PC, EARLY


class Checks(OriginalChecks):
    def __init__(self, program):
        super().__init__(program)
        self.board = Scoreboard('utage.dual-source-executed-prefix')
        self.queries, self.consumers, self.read_entries, self.sent = [], [], [], []
        self.compared = 0

    @staticmethod
    def expected_vector(positions, state):
        result = []
        for position in positions:
            if position is None: result.append(None); continue
            table = next((t for t,e in enumerate(state) if e is not None and e.position == position),None)
            value = None if table is None else state[table]
            result.append(dict(position=position, base=int(position==EARLY), valid=1,
                hit=int(table is not None), provider=table, counter=None if value is None else value.counter,
                taken=None if value is None else value.taken))
        return tuple(result)

    @staticmethod
    def actual_vector(source, positions):
        result = []
        for slot,position in enumerate(positions):
            if position is None: result.append(None); continue
            entry = source.meta['abtbResult'][slot]
            hit = bool(source.hits[slot])
            result.append(dict(position=entry['cfiPosition'],base=entry['baseTaken'],valid=entry['valid'],
                hit=int(hit),provider=entry['tableId'] if hit else None,
                counter=entry['takenCtr_value'] if hit else None,taken=source.takens[slot] if hit else None))
        return tuple(result)

    def query(self, label, positions, state, transfer, source, monitor):
        self.check(TransferState.COMPLETED, transfer.state, 'actual full-vector transfer completed')
        accepted,completed = transfer.accepted_event.tick,transfer.completed_event.tick
        self.check(accepted+4,completed,'each vector keeps its declared original response protocol')
        request = transfer.request
        self.check((PC,PC,0,0),(request.pc,request.read_pc,request.folded_history,request.read_history),
            'query keeps its own complete PC/history ancestry')
        actual_positions = tuple(None if b is None else b.position for b in request.branches)
        self.check(positions,actual_positions,'logical instruction positions remain distinct from vector slots')
        expected = self.expected_vector(positions,state)
        self.check(expected,self.actual_vector(source,positions),'all active branch identities and complete original direction values')
        self.check((0,0),tuple(source.meta['readIndex']),'complete short/long read indices belong to the original vector')
        self.check(Context().folds,tuple(r['foldedHist'] for r in source.meta['foldedPathHistForTrain_hist']),
            'matching history is not rewritten after source capture')
        for slot,position in enumerate(positions):
            metadata = source.meta['abtbResult'][slot]
            self.check(int(position is not None),metadata['valid'],'empty vector slots never acquire learning eligibility')
            if position is not None:
                self.check(expected[slot]['hit'],metadata['hit'],'output and training metadata agree on each original provider')
        read,response = monitor.at(accepted+2),monitor.at(completed)
        self.check((True,PC,Context(),(0,0)),
            (bool(read['events'].select),read['events'].read_pc,read['events'].read_context,read['read'].indices),
            'vector response owns this actual original read')
        self.check((PC,Context()),(response['frame'].pc,response['frame'].context),'matching frame belongs to this original vector')
        self.check(True,response['frame'].read.entries is read['read'].entries,'exact original read tuple survives to its own response')
        self.check(True,all(read['read'].entries is not old for old in self.read_entries),'identical vectors are still different original occurrences')
        self.read_entries.append(read['read'].entries)
        token = self.remember(source)
        self.queries.append(dict(ordinal=token,label=label,accepted=accepted,read=read['tick'],completed=completed,
            positions=positions,expected=expected,actual=self.actual_vector(source,positions)))
        return token

    def owned_feedback(self, step, token, transaction):
        self.check(len(self.sent),step.ordinal,'every declared original feedback is sent once in the declared order')
        self.check((PC,step.position,step.taken,step.kind,int(step.error)),
            (transaction.pc,transaction.position,transaction.actual_taken,transaction.branch_type,transaction.mispredict),
            'resolved instruction outcome is not borrowed from a vector slot or another provider')
        self.original_feedback(token,transaction)
        self.sent.append(token)

    def prefix(self, monitor, count):
        if monitor.failure is not None: raise monitor.failure
        self.check(count,len(monitor.records),'each feedback has exactly one complete logical learning boundary')
        self.check(count,len(monitor.native_updates),'actual native writes include no hidden or missing boundaries')
        sequences = [sum(t in s.writes for s in self.program.steps[:self.compared]) for t in (0,1)]
        for step,row,native in zip(self.program.steps[self.compared:count],monitor.records[self.compared:count],
                monitor.native_updates[self.compared:count],strict=True):
            self.check(False,row['aged'],'no unrequested maintenance explains an extra protection change')
            self.check(step.changes,row['changes'],'original per-branch contribution changes only its own protection')
            for table in native['tables']:
                self.check(step.cell(table),native['cells'][str(table)],
                    'actual written branch state, including an ineligible provider that must preserve confidence')
            wanted = {str(t) for t in step.writes}
            self.check(wanted,set(row['versions']),'qualified providers each write; unexecuted and nonconditional providers do not')
            self.check((row['tick'],step.writes),(native['tick'],tuple(native['tables'])),
                'write/preserve mask is actual native cursor movement, not a reference-model inference')
            self.check(tuple(n%8 for n in sequences),tuple(native['before']),'actual pre-write cursors preserve every other provider')
            for table in step.writes:
                version = row['versions'][str(table)]
                self.check((sequences[table],8,(sequences[table]+1)%8),
                    (version['sequence'],version['depth'],version['next']),'each full branch version has the next real chronology')
                self.check(step.cell(table),version['new_cell'],'actual branch tag/position and current confidence match independent semantic learning')
                sequences[table] += 1
            self.check(tuple(n%8 for n in sequences),tuple(native['after']),'non-target actual write cursors stay still')
            self.check(True,self.queries[self.sent[step.ordinal]]['completed'] < monitor.public[step.ordinal]['tick'] < row['tick'],
                'each actual feedback follows completion of its own original vector')
        self.compared = count
        self.check(self.program.protection_after(count),monitor.all_protection(),'all1024 actual protection values after this learning prefix')

    def consume(self, label, step, transfer, source, monitor):
        token = self.query(label,self.program.positions(),step.after,transfer,source,monitor)
        effect = monitor.records[step.ordinal]['tick']
        self.check(True,transfer.accepted_event.tick>effect,'consumer is a fresh full-vector lookup after actual learning')
        self.consumers.append(dict(label=label,after=step.ordinal,original=token,
            accepted=transfer.accepted_event.tick,expected=self.expected_vector(self.program.positions(),step.after),
            actual=self.actual_vector(source,self.program.positions())))

    def finish(self, monitor):
        total=len(self.program.steps)
        self.check(total,self.compared,'all setup and both distinct original feedbacks must be checked')
        self.check(total,len(monitor.native_updates),'no extra actual writes during final consumers')
        super().finish(monitor)
        a,b = self.queries[self.sent[-2]],self.queries[self.sent[-1]]
        delta = monitor.public[-1]['tick']-monitor.public[-2]['tick']
        self.check(True,delta==2 if self.program.mode=='adjacent' else delta>2,'actual two-original feedback cadence')
        if self.program.mode=='adjacent':
            self.check((2,True),(b['accepted']-a['accepted'],b['accepted']<a['completed']),
                'distinct original vector requests overlap before the first response completes')
        self.check(self.program.preparation_count+(3 if self.program.mode=='serial' else 1),
            len(self.consumers),'all declared setup/intermediate/final consumers are mandatory')
        self.check(True,all(q['completed']<monitor.public[-2]['tick'] for q in (a,b)),
            'both late feedbacks really use completed pre-learning originals')
        return delta

    def snapshot(self):
        return deepcopy(dict(program=self.program.state(),sent=self.sent,compared=self.compared,
            queries=self.queries,consumers=self.consumers,originals=len(self.originals)))
