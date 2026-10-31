"""Original semantic outcomes own two short ledgers, never sampled state."""
import asyncio
from collections import deque
from copy import deepcopy
from dataclasses import asdict
from toffee import Scoreboard

from suites.frontend.bpu.bpu.checker.ahead_working_set import AheadWorkingSetChecks
from suites.frontend.bpu.bpu.model.early_aging import allocation
from suites.frontend.bpu.bpu.model.early_opposition import resident
from suites.frontend.bpu.bpu.model.early_protection import Identity, ProtectionLedger, guidance
from suites.frontend.bpu.bpu.model.history_working_set import FEATURES, SHORT_POSITION
from suites.frontend.bpu.bpu.model.short_context_ownership import OWNERS, RULES
from suites.frontend.bpu.utage.model.semantic import tag


class ShortContextChecks(AheadWorkingSetChecks):
    def __init__(self, program, coverage):
        super().__init__(program, coverage)
        self.board = Scoreboard('bpu.short-context-ownership')
        identity_paths=(program.paths if hasattr(program,'identity_owner') else
            tuple(next(path for path in program.paths if path.branch==branch) for branch in OWNERS))
        self.identity_paths={self.identity_owner(path):path for path in identity_paths}
        self.identities={owner:Identity(0,*path.short_identity) for owner,path in self.identity_paths.items()}
        self.ledgers, self.learning = {}, []
        self.offers = deque(maxlen=16)
        self.acceptance = self.selected = self.selected_tick = None
        self.window_pc = self.window_path = self.window_final_position = None
        self.path_captures = self.path_recoveries = 0
        self.pending_protection = None
        self.window_states, self.consumers = {}, []
        self.visited = set()
        self.long_allocations = []
        self.penalty_confirmed_tick = None
        self.finished = False

    def identity_owner(self,path):
        return self.program.identity_owner(path) if hasattr(self.program,'identity_owner') else path.branch

    def consumer(self, events, cycle, sources):
        token = cycle.metadata
        if token is not None and self.selected is not None and token.history is self.selected.history:
            if self.window_final_position is not None:
                helper = next(self.program.helper(branch) for branch in OWNERS
                              if self.program.helper(branch).branch_pc == token.pc)
                branch = cycle.decisions[2].branch
                self.check((self.window_final_position, helper.pcs[0],
                            3 if self.window_final_position==12 else 1, True),
                    (branch.position,branch.target,int(branch.kind),branch.taken),
                    'actual final guidance belongs to this declared branch program')
        return ()

    def open_window(self, path, final_position, *, pc):
        self.check(True, self.acceptance is None or self.acceptance.done(), 'one owned issue window')
        self.acceptance = asyncio.get_running_loop().create_future()
        self.selected = self.selected_tick = None
        self.window_path, self.window_final_position, self.window_pc = path, final_position, pc
        return self.acceptance

    def candidates(self, row, events, cycle, model, phase, previous):
        result = super().candidates(row,events,cycle,model,phase,previous)
        self.first = cycle.tokens[0] if cycle.fires[1] and not cycle.flushes[0] else None
        self.third = cycle.tokens[2]
        self.applied = model.sources.short.learning
        if self.pending_protection is not None:
            branch, expected, written = self.pending_protection
            self.check(True,self.pipeline.current_event.tick > written,'learning reaches the next lossless actual boundary')
            identity = self.identities[branch]
            self.check(expected,row['observed']['early_direction']['useful'][0][identity.index],
                       'original event ledger agrees with actual short protection')
            if self.long_allocations and self.long_allocations[-1]['tick'] == written:
                self.penalty_confirmed_tick = self.pipeline.current_event.tick
                self.long_allocations[-1]['confirmed_tick'] = self.penalty_confirmed_tick
            self.pending_protection = None
        return result

    def checked(self, tick, *candidates):
        super().checked(tick,*candidates)
        sources = self.pipeline.model.sources
        feedback = sources.last_short_events.feedback
        if feedback is not None:
            self.check(True,self.third is not None,'fast teaching owns a genuine original S3 request')
            self.offers.append((feedback,self.third))
        applied = self.applied
        if applied is not None:
            feedback = applied.feedback
            owner = next((owner for offered,owner in self.offers if offered is feedback),None)
            self.check(True,owner is not None,'applied teaching retains its exact original S3 owner')
            decision = allocation(feedback,applied.useful)
            self.learning_effect(feedback,owner,decision,tick)
        self.check(False,sources.short.aged,'no undeclared global maintenance in the sharing/isolation lifetime')
        self.residents(sources)
        first = self.first
        if self.acceptance is None or self.acceptance.done() or first is None or first.pc != self.window_pc:
            return
        path = self.window_path
        if path is not None:
            frame = sources.short_snapshot(first).prediction.frame
            self.check(True,frame is not None,'original path owns its read snapshot')
            self.check((path.read_indices,tuple(path.match_context.folds[index] for index in FEATURES)),
                (frame.read.indices,tuple(frame.context.folds[index] for index in FEATURES)),
                'read-index and tag ancestry are derived from the actual predecessor program')
            ledger = self.ledgers.get(self.identity_owner(path))
            self.window_states[first.history.sequence] = None if ledger is None else (ledger.counter,ledger.protection)
        self.selected, self.selected_tick = first,tick
        self.path_captures += 1
        self.acceptance.set_result(self.pipeline.current_event)

    def learning_effect(self,feedback,owner,decision,tick):
        for branch, identity in self.identities.items():
            if feedback.pc != self.identity_paths[branch].branch_pc or feedback.indices[0] != identity.index:
                continue
            event = guidance(feedback,identity)
            if event is not None:
                self.check(True,branch in self.ledgers,'a hit update requires independently admitted original learning')
                transition = self.ledgers[branch].apply(owner.sequence,*event)
                self.learning.append(dict(tick=tick,branch=branch,**asdict(transition)))
                self.pending_protection = branch,transition.after,tick
                if decision.candidate == 1 and decision.wrong_position == SHORT_POSITION:
                    self.long_allocations.append(dict(tick=tick,branch=branch,index=feedback.indices[1],
                        source_id=owner.sequence,target_taken=int(event[0])))
            elif (decision.candidate == 0 and decision.wrong_position == SHORT_POSITION
                  and tag(feedback.pc,feedback.context,0) == identity.tag):
                self.check(False,branch in self.ledgers,'another source cannot silently reallocate a protected original')
                taken = bool(feedback.taken and feedback.position==SHORT_POSITION)
                self.ledgers[branch] = ProtectionLedger(counter=4 if taken else 3,protection=1)
                self.pending_protection = branch,1,tick

    def residents(self,sources):
        for branch, ledger in self.ledgers.items():
            identity = self.identities[branch]
            entry = resident(sources,identity.key)
            self.check((True,identity.tag,identity.position,ledger.counter,ledger.protection),
                (entry.valid,entry.tag,entry.position,entry.counter,sources.short.useful[0].get(identity.index,0)),
                'independent short learning remains owned by its branch through all other work')

    def close_window(self, source, *, path=None):
        token = self.pipeline.source_token(source)
        self.check(self.window_pc,source.prediction.start_pc,'public response owns the declared branch PC')
        self.check(True,self.selected is not None and token.history is self.selected.history
            and source.prediction_tick==self.selected_tick,'public response belongs to the exact accepted occurrence')
        self.check(False,token.sequence in self.visited,'original source cannot be consumed twice')
        self.visited.add(token.sequence)
        self.originals.append((source,deepcopy(source.meta.resolve),deepcopy(source.meta.redirect)))
        self.selected = None

    def provider(self, source, path,*,taken=False):
        token = self.pipeline.source_token(source)
        prediction = self.pipeline.model.sources.short_snapshot(token).prediction
        values = prediction.values()
        providers = [(values[f'{way}.provider'],values[f'{way}.counter']) for way in range(4)
            if values.get(f'{way}.valid') and values.get(f'{way}.hit')
            and values.get(f'{way}.position')==SHORT_POSITION]
        self.check(1,len(providers),'a real provider owns the requested original short branch')
        expected = self.window_states[token.history.sequence]
        self.check(True,expected is not None,'fresh consumers follow independently admitted learning')
        self.check((0,expected[0]),providers[0],'longer provider cannot substitute for the original short record')
        self.check(taken,expected[0]>=4,'the independently owned short read has the declared direction')
        if self.phase == 'final-consumers':
            self.check(True,self.penalty_confirmed_tick is not None
                and source.prediction_tick > self.penalty_confirmed_tick,
                'final consumers must be accepted after the actual selected correction')
        self.check((path.branch_pc,SHORT_POSITION if taken else 12,path.pcs[0],1),
            (source.prediction.start_pc,source.prediction.position,source.prediction.target,source.prediction.taken),
            'public short experience selects the declared conditional or real fallback')
        self.consumers.append(dict(phase=self.phase,branch=path.branch,older_path=path.older_path,
            source_id=token.sequence,query_tick=source.prediction_tick,metadata_tick=source.meta_tick,
            counter=providers[0][1],protection=expected[1],provider=providers[0][0]))
        return providers[0]

    def states(self):
        return {branch:(ledger.counter,ledger.protection) for branch,ledger in self.ledgers.items()}

    def finish_sharing(self):
        self.raise_failure()
        self.check(False,self.finished,'a complete lifetime can only publish once')
        self.check(set(OWNERS),set(self.ledgers),'both original branches were genuinely admitted')
        self.check(None,self.pending_protection,'all actual protection effects were compared')
        final = {(row['branch'],row['older_path']) for row in self.consumers if row['phase']=='final-consumers'}
        self.check({(path.branch,path.older_path) for path in self.program.paths},final,
                   'both old paths at both branches have fresh original short consumers')
        final_rows = [row for row in self.consumers if row['phase']=='final-consumers']
        self.check((4,4),(len(final_rows),len({row['source_id'] for row in final_rows})),
                   'exactly four distinct final original consumers, without duplicate credit')
        self.check(True,self.penalty_confirmed_tick is not None and all(
            row['query_tick'] > self.penalty_confirmed_tick and row['provider']==0 for row in final_rows),
            'all final consumers follow actual correction and genuinely use the short record')
        self.check(tuple((resolve,redirect) for _,resolve,redirect in self.originals),
            tuple((source.meta.resolve,source.meta.redirect) for source,_,_ in self.originals),
            'all complete original public snapshots remain immutable')
        self.mark('immutable-original-snapshots',sources=len(self.originals))
        self.check(set(RULES),self.completed,'every declared sharing/isolation obligation was proved')
        for rule in RULES:self.coverage.record('checked',rule,**self.witnesses[rule])
        self.finished = True

    def summary(self):
        return dict(program=self.program.state(),phase=self.phase,states=self.states(),
            actual_source_windows=self.path_captures,actual_recoveries=self.path_recoveries,
            actual_feedback=len(self.feedback_receipts),counter_comparisons=self.counter_comparisons,
            recency_comparisons=self.recency_comparisons,learning=deepcopy(self.learning),
            consumers=deepcopy(self.consumers),long_allocations=deepcopy(self.long_allocations),
            original_snapshots=len(self.originals),completed=sorted(self.completed))


class ShortDirectionChecks(ShortContextChecks):
    """The same outcome ledger, with T/NT consumers and actual storage proof."""
    def __init__(self,program,coverage):
        super().__init__(program,coverage)
        self.native_storage=self.storage_layout=None
        self.storage_checks=[]
        self.direction_changes=[]

    def candidates(self,row,*args):
        result=super().candidates(row,*args)
        self.native_storage=deepcopy(row['observed']['short_storage'])
        return result

    def direction_consumer(self,source,path,*,taken):
        result=self.provider(source,path,taken=taken)
        position=SHORT_POSITION if taken else 12
        self.check((position,path.pcs[0]),(source.meta.perf.s1_position,source.meta.perf.s1_target),
            'public metadata retains the same original conditional or fallback choice')
        self.consumers[-1]['expected_taken']=taken
        return result

    def changed_by_original(self,source,path,before,after,start,*,taken):
        token=self.pipeline.source_token(source)
        events=self.learning[start:]
        self.check(1,len(events),'one declared original outcome advances one short experience')
        event=events[0]
        self.check((path.branch,token.sequence,before.counter,after.counter,before.useful,after.useful),
            (event['branch'],event['owner'],event['counter_before'],event['counter_after'],event['before'],event['after']),
            'exact S3 original advances the predeclared independent direction transition')
        self.check((after.counter,after.useful),self.states()[path.branch],
            'current retained experience agrees with the declared transition')
        self.direction_changes.append(dict(branch=path.branch,older_path=path.older_path,
            source=token.sequence,taken=taken,counter_before=before.counter,counter_after=after.counter,
            protection_before=before.useful,protection_after=after.useful))

    def check_storage(self,phase):
        from suites.frontend.bpu.bpu.monitor.service import decode_short_entry
        self.check(set(OWNERS),set(self.ledgers),'both logical short experiences are present')
        self.check(True,self.native_storage is not None and self.storage_layout is not None,
            'actual memory-direct SRAM and cache snapshots required')
        rows=[]
        for path,word in zip(self.program.storage_paths,self.native_storage['words'],strict=True):
            identity,state=self.identities[path.branch],self.ledgers[path.branch]
            actual=decode_short_entry(word,self.storage_layout)
            self.check(dict(valid=True,tag=identity.tag,position=identity.position,counter=state.counter),actual,
                'actual SRAM preserves independently learned branch experience after direction change')
            rows.append(dict(branch=path.branch,index=identity.index,entry=actual))
        cached={row['index'] for row in self.native_storage['cells'] if row['valid']}
        self.storage_checks.append(dict(phase=phase,tick=self.pipeline.current_event.tick,words=rows,
            cached_indices=sorted(cached),uncached_branches=[branch for branch,identity in self.identities.items()
                if identity.index not in cached]))

    def finish_direction(self):
        from suites.frontend.bpu.bpu.model.short_context_ownership import DIRECTION_RULES,TURNAROUND_PATHS,RESTORATION_PATHS
        self.raise_failure()
        self.check(False,self.finished,'a direction lifetime closes once')
        self.check(None,self.pending_protection,'every actual protection effect crossed observation')
        self.check(set(DIRECTION_RULES),self.completed,'every short-direction lifetime requirement completed')
        wanted={(path.branch,path.older_path) for path in self.program.paths}
        for phase in ('initial-NT-consumers','mixed-T-NT-consumers','final-direction-consumers'):
            rows=[row for row in self.consumers if row['phase']==phase]
            self.check((wanted,4,4),({(row['branch'],row['older_path']) for row in rows},len(rows),
                len({row['source_id'] for row in rows})),'all four real original short consumers complete each phase')
            for row in rows:
                self.check(phase=='mixed-T-NT-consumers' and row['branch']==self.program.selected,
                    row['expected_taken'],'mixed and restored public directions remain branch-owned')
        self.check(8,len(self.direction_changes),'complete two-sided short direction transition')
        self.check(8,len(self.long_allocations),'each wrong short original owns a distinct longer companion')
        expected={path.read_indices[1] for older in (*TURNAROUND_PATHS,*RESTORATION_PATHS)
            for path in (self.program.reversal_path(self.program.selected,older),)}
        self.check(expected,{row['index'] for row in self.long_allocations},
            'no longer companion masks an original consumer or a preceding learning-only path')
        self.check({branch:(0,3) for branch in OWNERS},self.states(),'both original short experiences end at their NT protection boundary')
        self.check(True,len(self.storage_checks)>=2,'actual SRAM is checked at opposite direction endpoints')
        self.check(tuple((resolve,redirect) for _,resolve,redirect in self.originals),
            tuple((source.meta.resolve,source.meta.redirect) for source,_,_ in self.originals),
            'complete original metadata remain immutable across both direction changes')
        for rule in DIRECTION_RULES:self.coverage.record('checked',rule,**self.witnesses[rule])
        self.finished=True

    def summary(self):
        return dict(super().summary(),direction_changes=deepcopy(self.direction_changes),
            actual_SRAM_snapshots=deepcopy(self.storage_checks),long_companions_not_original_consumers=True)


class ShortCrossBranchChecks(ShortDirectionChecks):
    """One original-outcome ledger per logical branch AND incoming path."""
    def __init__(self,program,coverage):
        super().__init__(program,coverage)
        self.declared_results={path.ordinal:False for path in program.paths}

    def declare_result(self,path,taken):
        if path not in self.program.paths or type(taken) is not bool:raise ValueError('one original working-set owner and actual result required')
        self.check(None,self.pending_protection,'previous original effect completes before declaring a new result')
        self.declared_results[path.ordinal]=taken

    def checked(self,tick,*candidates):
        if self.applied is not None:
            for owner,identity in self.identities.items():
                if self.applied.feedback.pc!=self.identity_paths[owner].branch_pc:continue
                event=guidance(self.applied.feedback,identity)
                if event is not None:self.check(self.declared_results[owner],event[0],
                    'the predeclared branch/path outcome, not current wires, qualifies original learning')
        super().checked(tick,*candidates)

    def direction_consumer(self,source,path,*,taken):
        result=super().direction_consumer(source,path,taken=taken)
        self.consumers[-1]['path']=path.ordinal
        return result

    def changed_by_original(self,source,path,before,after,start,*,taken):
        token=self.pipeline.source_token(source)
        rows=self.learning[start:]
        self.check(1,len(rows),'one declared feedback changes one working-set owner')
        row=rows[0]
        self.check((path.ordinal,token.sequence,before.counter,after.counter,before.useful,after.useful),
            (row['branch'],row['owner'],row['counter_before'],row['counter_after'],row['before'],row['after']),
            'the exact original branch/path owns the preplanned confidence and protection transition')
        self.check((after.counter,after.useful),self.states()[path.ordinal],'learned owner agrees with the independent outcome transition')
        self.direction_changes.append(dict(path=path.ordinal,branch=path.branch,owner=token.sequence,taken=taken,
            before=(before.counter,before.useful),after=(after.counter,after.useful)))

    def check_storage(self,phase):
        from suites.frontend.bpu.bpu.monitor.service import decode_short_entry
        self.check(set(self.identities),set(self.ledgers),'all fourteen branch/path identities coexist')
        self.check(True,self.native_storage is not None and self.storage_layout is not None,'actual MEM_DIRECT SRAM and cache required')
        snapshot=self.native_storage;rows=[]
        for path,word in zip(self.program.storage_paths,snapshot['words'],strict=True):
            identity,ledger=self.identities[path.ordinal],self.ledgers[path.ordinal]
            actual=decode_short_entry(word,self.storage_layout)
            self.check(dict(valid=True,tag=identity.tag,position=identity.position,counter=ledger.counter),actual,
                'actual SRAM preserves this independent branch/path, not merely its recent forwarding copy')
            rows.append(dict(branch=path.branch,path=path.ordinal,index=identity.index,entry=actual))
        cached={cell['index'] for cell in snapshot['cells'] if cell['valid']}
        uncached=[path.ordinal for path in self.program.paths if path.read_indices[0] not in cached]
        self.check(True,len(self.identities)>len(snapshot['cells']) and bool(uncached),
            'actual shared storage pressure exceeds recent retention, without a physical coordinate sweep')
        self.storage_checks.append(dict(phase=phase,tick=self.pipeline.current_event.tick,words=rows,
            cached_indices=sorted(cached),uncached_paths=uncached))

    def finish_working_set(self):
        from suites.frontend.bpu.bpu.model.short_context_ownership import WORKING_SET_RULES
        self.raise_failure()
        self.check(False,self.finished,'working-set lifetime closes once')
        self.check(None,self.pending_protection,'all actual learning crossed its comparison boundary')
        self.check(set(self.identities),set(self.ledgers),'all original branch/path owners remain learned')
        self.check(set(WORKING_SET_RULES),self.completed,'every declared cross-branch working-set obligation completed')
        expected={path.ordinal for path in self.program.paths}
        mixed={path.ordinal for path in self.program.mixed}
        self.check({'mixed','turned','final'},{row['phase'] for row in self.storage_checks},'all three storage lifetimes completed')
        for phase,positive in (('initial-working-set-consumers',set()),('mixed-working-set-consumers',mixed),
                ('turned-working-set-consumers',mixed|{self.program.selected_path.ordinal}),('final-working-set-consumers',mixed)):
            rows=[row for row in self.consumers if row['phase']==phase]
            self.check((expected,len(expected)),({row['path'] for row in rows},len(rows)),
                'each phase has exactly one fresh consumer for every branch and incoming path')
            self.check(positive,{row['path'] for row in rows if row['expected_taken']},'mixed direction remains owned by its declared branch/path')
            self.check(True,all(row['provider']==0 and (row['counter']>=4)==row['expected_taken'] for row in rows),
                'longer providers or wrong confidence cannot impersonate the original short consumers')
            if phase!='initial-working-set-consumers':
                snapshot=next(row for row in self.storage_checks if row['phase']==phase.split('-')[0])
                self.check(True,all(row['query_tick']>snapshot['tick'] for row in rows),
                    'every phase consumer is younger than its actual complete SRAM comparison')
        uncached={owner for row in self.storage_checks for owner in row['uncached_paths']}
        self.check(set(OWNERS),{path.branch for path in self.program.paths if path.ordinal in uncached},
            'neither branch may rely exclusively on recent forwarding throughout the lifetime')
        owners=[row['source_id'] for row in self.consumers]
        self.check(len(owners),len(set(owners)),'all public consumers are distinct original requests')
        changed=[row['owner'] for row in self.direction_changes]
        self.check(20,len(changed),'three mixed directions and one complete selected round trip use preplanned real outcomes')
        self.check(len(changed),len(set(changed)),'no original guidance source learns twice')
        self.check(tuple((resolve,redirect) for _,resolve,redirect in self.originals),
            tuple((source.meta.resolve,source.meta.redirect) for source,_,_ in self.originals),'all original metadata remain immutable')
        for rule in WORKING_SET_RULES:self.coverage.record('checked',rule,**self.witnesses[rule])
        self.finished=True

    def summary(self):
        return dict(super().summary(),declared_results=dict(self.declared_results),
            declared_identity_count=len(self.identities),actual_identity_count=len(self.ledgers),
            recent_capacity_exceeded=bool(self.native_storage is not None and len(self.ledgers)>len(self.native_storage['cells'])),
            new_predictor_algorithm=False)
