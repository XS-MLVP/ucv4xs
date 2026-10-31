"""Logical owner transfer and original-result ledgers over the same golden."""
from copy import deepcopy
from dataclasses import asdict
from toffee import Scoreboard

from suites.frontend.bpu.bpu.checker.short_context_ownership import ShortContextChecks
from suites.frontend.bpu.bpu.model.early_protection import Identity,ProtectionLedger,guidance
from suites.frontend.bpu.bpu.model.early_opposition import resident
from suites.frontend.bpu.bpu.model.history_working_set import SHORT_POSITION,FALLBACK
from suites.frontend.bpu.bpu.model.short_competition import RULES
from suites.frontend.bpu.utage.model.semantic import tag


class Checks(ShortContextChecks):
    def __init__(self,program,coverage):
        super().__init__(program,coverage)
        self.board=Scoreboard('bpu.protected-short-branch-competition')
        self.active_owner=None
        self.declared_results={program.old:program.old_taken,program.new:program.new_taken}
        self.admissions=[];self.long_records={};self.long_events=[];self.pending_long=[]
        self.native_storage=self.storage_layout=None
        self.storage_checks=[];self.queries=[];self.actual_long_writes=[]

    def candidates(self,row,*args):
        result=super().candidates(row,*args)
        self.native_storage=deepcopy(row['observed']['short_storage'])
        for key,expected,written in self.pending_long:
            self.check(True,self.pipeline.current_event.tick>written,'long protection reaches its next actual observation')
            self.check(expected,row['observed']['early_direction']['useful'][1][key[1]],
                'actual companion protection agrees with the independent original ledger')
            native=row['observed']['competition_long']
            cell=native['cells'][(native['enq']-1)%len(native['cells'])]
            wanted=dict(valid=1,data_valid=1,index=key[1],tag=key[2],position=SHORT_POSITION,counter=self.long_records[key].counter)
            self.check(wanted,cell,'actual long retained write preserves its own complete owner and counter')
            self.actual_long_writes.append(dict(tick=self.pipeline.current_event.tick,branch=key[0],
                expected=wanted,actual=deepcopy(cell),source_effect_tick=written))
        self.pending_long=[]
        return result

    def learning_effect(self,feedback,owner,decision,tick):
        branch=next((branch for branch,path in self.identity_paths.items() if path.branch_pc==feedback.pc),None)
        if branch is None or feedback.indices[0]!=self.identities[branch].index:return
        identity=self.identities[branch]
        event=guidance(feedback,identity)
        if decision.candidate==0 and decision.wrong_position==SHORT_POSITION:
            self.check(identity.tag,tag(feedback.pc,feedback.context,0),'admission keeps the complete declared short identity')
            actual=bool(feedback.taken and feedback.position==SHORT_POSITION)
            self.check(self.declared_results[branch],actual,'new admission uses the declared original conditional result')
            if self.active_owner is not None:
                self.check(self.program.new,branch,'only the declared newcomer may replace the old short owner')
                old=self.ledgers[self.active_owner]
                self.check((self.program.old,0),(self.active_owner,old.protection),
                    'a protected old owner cannot be displaced')
                self.check(7 if self.program.old_taken else 0,old.counter,
                    'replacement must distinguish new weak confidence from a strong old owner')
            else:self.check(self.program.old,branch,'the declared old branch establishes the shared owner first')
            self.check(False,branch in self.ledgers,'one declared admission for each logical branch')
            self.ledgers[branch]=ProtectionLedger(counter=4 if actual else 3,protection=1)
            self.admissions.append(dict(tick=tick,owner=owner.sequence,branch=branch,previous=self.active_owner,
                tag=identity.tag,counter=self.ledgers[branch].counter,protection=1))
            self.active_owner=branch;self.pending_protection=branch,1,tick
        elif event is not None:
            self.check(branch,self.active_owner,'fresh short feedback cannot borrow the current different owner')
            self.check(self.declared_results[branch],event[0],'short learning belongs to its predeclared branch result')
            transition=self.ledgers[branch].apply(owner.sequence,*event)
            self.learning.append(dict(tick=tick,branch=branch,**asdict(transition)))
            self.pending_protection=branch,transition.after,tick
        key=(branch,feedback.indices[1],tag(feedback.pc,feedback.context,1))
        if decision.candidate==1 and decision.wrong_position==SHORT_POSITION:
            actual=bool(feedback.taken and feedback.position==SHORT_POSITION)
            self.check(False,key in self.long_records,'long companion is a fresh declared original context')
            self.long_records[key]=ProtectionLedger(counter=4 if actual else 3,protection=2)
            self.long_events.append(dict(tick=tick,branch=branch,index=key[1],tag=key[2],owner=owner.sequence,
                kind='allocate',counter=self.long_records[key].counter,protection=2))
            self.pending_long.append((key,2,tick))
        else:
            long_event=guidance(feedback,Identity(1,key[1],key[2],SHORT_POSITION))
            if long_event is not None:
                self.check(True,key in self.long_records,'long feedback follows its own independently admitted source')
                transition=self.long_records[key].apply(owner.sequence,*long_event)
                self.long_events.append(dict(tick=tick,branch=branch,index=key[1],tag=key[2],**asdict(transition)))
                self.pending_long.append((key,transition.after,tick))

    def residents(self,sources):
        if self.active_owner is not None:
            identity,ledger=self.identities[self.active_owner],self.ledgers[self.active_owner]
            entry=resident(sources,identity.key)
            self.check((True,identity.tag,identity.position,ledger.counter,ledger.protection),
                (entry.valid,entry.tag,entry.position,entry.counter,sources.short.useful[0].get(identity.index,0)),
                'exactly the active logical short owner occupies the shared row')
        for key,ledger in self.long_records.items():
            entry=resident(sources,(1,key[1]))
            self.check((True,key[2],SHORT_POSITION,ledger.counter,ledger.protection),
                (entry.valid,entry.tag,entry.position,entry.counter,sources.short.useful[1].get(key[1],0)),
                'replacement and other contexts preserve each independent long companion')

    def inspect(self,source,path,expected,*,public_taken):
        token=self.pipeline.source_token(source)
        values=self.pipeline.model.sources.short_snapshot(token).prediction.values()
        slots=[way for way in range(4) if values.get(f'{way}.valid') and values.get(f'{way}.position')==SHORT_POSITION]
        self.check(1,len(slots),'the actual original Ahead request contains the intended conditional')
        way,=slots
        hit=bool(values[f'{way}.hit'])
        actual=(values[f'{way}.provider'],values[f'{way}.counter'],bool(values[f'{way}.predicted'])) if hit else None
        self.check(expected,actual,'fresh original short/long/miss prediction has its declared owner and confidence')
        position=SHORT_POSITION if public_taken else FALLBACK
        self.check((path.branch_pc,position,path.pcs[0],1),
            (source.prediction.start_pc,source.prediction.position,source.prediction.target,source.prediction.taken),
            'actual public prediction uses its own branch or fallback, not the new resident direction')
        self.check((position,path.pcs[0]),(source.meta.perf.s1_position,source.meta.perf.s1_target),
            'public metadata belongs to the same original conditional/fallback choice')
        self.queries.append(dict(phase=self.phase,branch=path.branch,older_path=path.older_path,owner=token.sequence,
            query_tick=source.prediction_tick,metadata_tick=source.meta_tick,expected=expected,actual=actual,
            public_taken=public_taken,position=position))

    def check_storage(self,phase):
        from suites.frontend.bpu.bpu.monitor.service import decode_short_entry
        self.check(True,self.native_storage is not None and self.storage_layout is not None,'actual shared SRAM and cache required')
        self.check(1,len(self.native_storage['words']),'one genuinely shared physical row, not two coexisting records')
        identity,ledger=self.identities[self.active_owner],self.ledgers[self.active_owner]
        actual=decode_short_entry(self.native_storage['words'][0],self.storage_layout)
        expected=dict(valid=True,tag=identity.tag,position=SHORT_POSITION,counter=ledger.counter)
        self.check(expected,actual,'actual SRAM stores the declared old or new logical owner and confidence')
        self.storage_checks.append(dict(phase=phase,tick=self.pipeline.current_event.tick,owner=self.active_owner,
            index=identity.index,entry=actual,protection=ledger.protection))

    def finish_competition(self):
        p=self.program
        self.raise_failure()
        self.check(False,self.finished,'competition lifetime closes once')
        self.check((None,[]),(self.pending_protection,self.pending_long),'all real short and long effects were observed')
        self.check(set(RULES),self.completed,'all competition requirements completed')
        self.check([p.old,p.new],[row['branch'] for row in self.admissions],'old admission then one legitimate ownership transfer')
        self.check(p.new,self.active_owner,'the newcomer owns the shared short record')
        self.check(4 if p.new_taken else 3,self.admissions[-1]['counter'],'new confidence was weak at its real initial admission')
        self.check({'protected','released','new-owner'},{row['phase'] for row in self.storage_checks},'all shared SRAM stages completed')
        for row in self.storage_checks:
            owner=p.new if row['phase']=='new-owner' else p.old
            counter=(4 if p.new_taken else 3) if owner==p.new else 7 if p.old_taken else 0
            protection={'protected':3,'released':0,'new-owner':1}[row['phase']]
            self.check((owner,self.identities[owner].tag,counter,protection),
                (row['owner'],row['entry']['tag'],row['entry']['counter'],row['protection']),
                'actual SRAM phase must retain the declared protected, released or new weak owner')
        expected_phases={'new-long-while-old-protected','new-short-after-replacement','old-own-fallback',
            'new-original-long-preserved','old-original-long-preserved'}
        final=[row for row in self.queries if row['phase'] in expected_phases]
        self.check(expected_phases,{row['phase'] for row in final},'both original branches and long companions have real new consumers')
        self.check(5,len(final),'one original consumer per declared endpoint, not duplicate credit')
        for row in final:
            table=(None if row['phase']=='old-own-fallback' else 0 if row['phase']=='new-short-after-replacement' else 1)
            actual=row['actual']
            self.check(True,(actual is None) if table is None else
                (actual is not None and actual[0]==table and actual[2]==p.new_taken),
                'each consumer phase must exercise its actual short, long or own fallback role')
            if table==0:self.check(4 if p.new_taken else 3,actual[1],'first new short consumer retains its initial weak confidence')
        boundary=next(row['tick'] for row in self.storage_checks if row['phase']=='new-owner')
        self.check(True,all(row['query_tick']>boundary for row in final if row['phase']!='new-long-while-old-protected'),
            'replacement consumers are younger than the actual new SRAM owner')
        owners=[row['owner'] for row in self.queries]
        self.check(len(owners),len(set(owners)),'all consumers are distinct original queries')
        short_owners=[row['owner'] for row in (*self.admissions,*self.learning)]
        long_owners=[row['owner'] for row in self.long_events]
        self.check(len(short_owners),len(set(short_owners)),'each original short effect occurs once')
        self.check(len(long_owners),len(set(long_owners)),'each original long effect occurs once')
        self.check(len(self.long_events),len(self.actual_long_writes),'every long admission and update has an actual full retained-write comparison')
        self.check(tuple((resolve,redirect) for _,resolve,redirect in self.originals),
            tuple((source.meta.resolve,source.meta.redirect) for source,_,_ in self.originals),'all original metadata remain immutable')
        for rule in RULES:self.coverage.record('checked',rule,**self.witnesses[rule])
        self.finished=True

    def summary(self):
        return dict(super().summary(),active_short_owner=self.active_owner,admissions=deepcopy(self.admissions),
            long_experience={str(key):(ledger.counter,ledger.protection) for key,ledger in self.long_records.items()},
            long_events=deepcopy(self.long_events),actual_SRAM_snapshots=deepcopy(self.storage_checks),
            actual_long_writes=deepcopy(self.actual_long_writes),queries=deepcopy(self.queries),new_predictor_algorithm=False)
