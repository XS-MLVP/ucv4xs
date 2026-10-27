"""Compare complete age ownership and independent current learning effects."""
from copy import deepcopy
from toffee import Scoreboard
from bpuverify.utage.checker.query_cohort import Checks as OriginalChecks
from bpuverify.utage.checker.dual_source import Checks as VectorChecks
from bpuverify.utage.model.semantic import Context,tag


class Checks(OriginalChecks):
    def __init__(self,program):
        super().__init__(program)
        self.board=Scoreboard('utage.whole-vector-saved-age')
        self.expected_writes=[]
        self.protection=[0]*1024
        self.queries=[]
        self.recovery_evidence=None

    def vector(self,profile,source,state,positions=None,*,history=None):
        p=self.program
        positions=p.positions() if positions is None else positions
        history=profile.history if history is None else history
        expected=VectorChecks.expected_vector(positions,state)
        if history!=profile.history:
            expected=tuple(None if value is None else dict(value,hit=0,provider=None,counter=None,taken=None) for value in expected)
            self.check(True,all(tag(profile.pc,profile.context,t)!=tag(profile.pc,Context.from_recent(history),t) for t in (0,1)),
                'declared changed history must genuinely reject both original identities')
        self.check(expected,VectorChecks.actual_vector(source,positions),'complete vector belongs to ONE original age')
        self.check(profile.indices,tuple(source.meta['readIndex']),'both read indices belong to selected original ancestry')
        self.check(Context.from_recent(history).folds,tuple(h['foldedHist'] for h in source.meta['foldedPathHistForTrain_hist']),
            'complete matching history belongs to this interpretation')
        self.check(tuple(int(v is not None) for v in positions),tuple(v['valid'] for v in source.meta['abtbResult']),
            'all holes stay invalid through vector recovery')
        return expected

    def query(self,profile,handle,source,state,positions=None):
        expected=self.vector(profile,source,state,positions)
        self.check(handle.accepted_event.tick+4,handle.completed_event.tick,'normal public vector response protocol')
        ordinal=self.remember(source)
        self.queries.append(dict(profile=profile.name,accepted=handle.accepted_event.tick,
            completed=handle.completed_event.tick,original=ordinal,expected=expected,
            actual=VectorChecks.actual_vector(source,self.program.positions() if positions is None else positions),
            indices=tuple(source.meta['readIndex']),history=profile.history))
        return ordinal

    def learning(self,profile,step=None):
        before=tuple(self.protection)
        state=self.program.latest if step is None else step.after
        writes=(0,1) if step is None else step.writes
        for table,value in enumerate(state):
            if value is not None:self.protection[table*512+profile.indices[table]]=value.useful
        changes=tuple((i,a,b) for i,(a,b) in enumerate(zip(before,self.protection,strict=True)) if a!=b)
        self.expected_writes.append(dict(cells={str(t):profile.cell(t,state[t]) for t in writes},
            tables=writes,changes=changes))

    def native(self,monitor):
        if monitor.failure is not None: raise monitor.failure
        self.check(len(self.expected_writes),len(monitor.native_updates),'no extra writes from queries, holes or recovery')
        self.check(len(self.expected_writes),len(monitor.records),'one complete learning effect per original feedback')
        cursors=[0,0]
        for expected,actual,logical in zip(self.expected_writes,monitor.native_updates,monitor.records,strict=True):
            self.check((expected['tables'],expected['cells']),(tuple(actual['tables']),actual['cells']),
                'actual two-provider write mask, identity and confidence')
            self.check(tuple(cursors),tuple(actual['before']),'each table keeps its own chronological write cursor')
            for table in expected['tables']:cursors[table]=(cursors[table]+1)%8
            self.check(tuple(cursors),tuple(actual['after']),'every declared native write advances exactly once')
            self.check((actual['tick'],expected['changes'],False),
                (logical['tick'],tuple(logical['changes']),logical['aged']),'actual protection effect and no hidden maintenance')
        self.check(tuple(self.protection),monitor.all_protection(),'all1024 protection cells, including both unrelated come-froms')

    def recovery(self,rows,transfers,monitor):
        p=self.program
        actual=tuple((r['events'].read_pc,r['events'].read_context,r['events'].override) for r in rows)
        expected=tuple((profile.pc,profile.context,None) for profile in p.profiles)+((p.decoy.pc,p.decoy.context,p.stage),)
        self.check(expected,actual,'three real input ancestors then one recovery, not fabricated snapshots')
        self.check(4,len(transfers),'all four compound input-only transfers accepted')
        self.check(tuple(transfers[0].accepted_event.tick+2*i for i in range(4)),
            tuple(t.accepted_event.tick for t in transfers),'actual consecutive compound admissions')
        self.check(True,all(row['events'].select and row['events'].advance for row in rows),'actual pipeline advances through all declared ancestors')
        self.check((p.target.pc,Context.from_recent(p.history)),
            (rows[-1]['events'].override_pc,rows[-1]['events'].override_context),'actual recovery reinterpretation')
        for profile,row in zip(p.profiles[:2],rows[1:3],strict=True):self.vector(profile,row['actual'],profile.prepared)
        selected=rows[2 if p.stage=='s2' else 1]
        saved,restored=selected['frame'],rows[-1]['frame']
        self.check(True,restored.read.entries is saved.read.entries,'the WHOLE recovered read is this exact saved occurrence')
        self.check(True,restored.read.entries is not rows[-1]['read'].entries,'recovery cannot silently reread the current decoy')
        self.vector(p.target,rows[-1]['actual'],p.target.prepared,history=p.history)
        if p.learning:
            self.check(True,monitor.native_updates[-1]['tick']<=rows[-1]['tick'],
                'both changed current values must already exist when the old vector is recovered')
            self.check(True,all(a.counter!=b.counter for a,b in zip(p.target.prepared,p.latest,strict=True)),
                'both providers independently distinguish saved from current confidence')
        self.recovery_evidence=dict(tick=rows[-1]['tick'],source_tick=selected['tick'],
            input_ticks=[t.accepted_event.tick for t in transfers],selected=p.target.name,
            saved=[v.counter for v in p.target.prepared],current=[v.counter for v in p.latest],
            matched=not p.retag,exact_original_read=True,
            actual=VectorChecks.actual_vector(rows[-1]['actual'],p.positions()),
            indices=tuple(rows[-1]['actual'].meta['readIndex']),
            folds=tuple(v['foldedHist'] for v in rows[-1]['actual'].meta['foldedPathHistForTrain_hist']),
            current_write_tick=monitor.native_updates[-1]['tick'] if p.learning else None)

    def snapshot(self):
        return deepcopy(dict(program=self.program.state(),queries=self.queries,recovery=self.recovery_evidence,
            expected_native_writes=self.expected_writes,expected_feedback=self.expected_feedback,
            originals=len(self.originals),compared=self.board.status.checked))
