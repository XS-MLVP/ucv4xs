"""Actual owned path windows and an outcome-driven long-history ledger."""
import asyncio
from collections import deque
from copy import deepcopy
from dataclasses import asdict

from suites.frontend.bpu.bpu.checker.ahead_working_set import AheadWorkingSetChecks
from suites.frontend.bpu.bpu.checker.history_maintenance import HistoryMaintenanceChecks
from suites.frontend.bpu.bpu.model.early_aging import allocation
from suites.frontend.bpu.bpu.model.early_opposition import resident
from suites.frontend.bpu.bpu.model.history_working_set import (ANCHOR, FEATURES, POSITION, RULES,
    FALLBACK, SHORT_POSITION, HistoryLearningLedger)
from suites.frontend.bpu.utage.model.semantic import tag
from suites.frontend.bpu.bpu.model.early_protection import Identity,ProtectionLedger,guidance
from suites.frontend.bpu.bpu.model.history_working_set import SHORT_RULES
from suites.frontend.bpu.bpu.monitor.service import decode_short_entry


class HistoryWorkingSetChecks(AheadWorkingSetChecks):
    def __init__(self, program, coverage):
        super().__init__(program, coverage)
        self.ledger = HistoryLearningLedger(program)
        self.maintenance = HistoryMaintenanceChecks(self)
        self.path_by_index = {path.read_indices[1]:path for path in program.paths}
        self.acceptance = self.selected = self.window_path = None
        self.window_final_position = None
        self.window_pc = ANCHOR
        self.selected_tick = None
        self.path_visits, self.visit_owners = {}, set()
        self.confirmed_learning = self.path_captures = self.path_recoveries = 0
        self.pending_protection = None
        self.phase_progress = []
        self.admitted, self.penalized, self.recovered, self.revisited = set(), set(), set(), set()
        self.original_window_states = {}
        self.expected_results = {}
        self.reversed_consumers,self.restored_consumers,self.mixed_consumers = set(),set(),{}
        self.public_consumers = {phase:{} for phase in ('reversed','mixed','restored','maintenance','maintenance-seed')}
        self.micro_origins = deque(maxlen=8)

    def consumer(self, events, cycle, sources):
        token = cycle.metadata
        if (token is not None and self.selected is not None and token.history is self.selected.history
                and self.window_final_position is not None):
            branch = cycle.decisions[2].branch
            self.check((self.window_final_position, self.program.helper.pcs[0],
                        3 if self.window_final_position == 12 else 1, True),
                       (branch.position, branch.target, int(branch.kind), branch.taken),
                       'actual final guidance belongs to this declared original path window')
        return ()

    def open_window(self, path, final_position, *, pc=ANCHOR):
        self.check(True, self.acceptance is None or self.acceptance.done(), 'one owned source window at a time')
        self.acceptance = asyncio.get_running_loop().create_future()
        self.selected, self.selected_tick = None, None
        self.window_path, self.window_final_position = path, final_position
        self.window_pc = pc
        return self.acceptance

    def candidates(self, row, events, cycle, model, phase, previous):
        # Bounded exception context only; not an exported cycle trace or a
        # source of expected values/stimulus.
        third = cycle.tokens[2]
        expected_fast = dict(valid=int(third is not None))
        if third is not None:
            branch = cycle.decisions[2].branch
            expected_fast.update(pc=third.pc,target=branch.target,taken=int(branch.taken),
                position=branch.position,kind=int(branch.kind),action=int(branch.action))
        self.check(expected_fast,{key:row['observed']['micro_fast'][key] for key in expected_fast},
                   'MicroBTB fast outcome belongs to the independently composed original S3')
        expected_resolve = dict(fire=int(events.feedback is not None))
        if events.feedback is not None:
            branch = events.feedback.branches[0]
            expected_resolve.update(pc=events.feedback.pc,valid=1,target=branch.target,taken=int(branch.taken),
                position=branch.position,kind=int(branch.kind),action=int(branch.action),mispredict=int(branch.mispredict))
        self.check(expected_resolve,{key:row['observed']['micro_resolve'][key] for key in expected_resolve},
                   'MicroBTB resolve input belongs to the exact accepted public source')
        self.micro_origins.append(dict(tick=self.pipeline.current_event.tick,
            pending=model.sources.micro.learning,entries=tuple(model.sources.micro.entries),
            actual_confidence=tuple(entry['confidence'] for entry in row['observed']['micro_entries']),
            fast=None if third is None else (third.pc,cycle.decisions[2].branch),
            resolve=None if events.feedback is None else (events.feedback.pc,events.feedback.branches)))
        if model.sources.micro.learning is None and third is None and events.feedback is None:
            expected,actual = [],[]
            for entry,observed in zip(model.sources.micro.entries,row['observed']['micro_entries'],strict=True):
                value = dict(confidence=entry.confidence)
                if entry.confidence:
                    value.update(key=entry.key,target=entry.target//2,position=entry.position,
                                 kind=entry.branch_type,action=entry.ras_action)
                expected.append(value)
                actual.append({key:observed[key] for key in value})
            self.check(expected,actual,'quiescent complete MicroBTB identity and payload before history preparation')
        result = super().candidates(row, events, cycle, model, phase, previous)
        self._first = cycle.tokens[0] if cycle.fires[1] and not cycle.flushes[0] else None
        self._applied = model.sources.short.learning
        self._short_enabled = cycle.enabled[1]
        if self.pending_protection is not None:
            path, state, written = self.pending_protection
            self.check(written+2, self.pipeline.current_event.tick, 'lossless next-boundary physical protection confirmation')
            self.check(state.useful, row['observed']['early_direction']['useful'][1][path.read_indices[1]],
                       'actual protection confirms the outcome-owned ledger, not merely an offered write')
            self.pending_protection = None
            self.confirmed_learning += 1
        self.maintenance.before(row,model.sources,self.pipeline.current_event.tick)
        return result

    def checked(self, tick, *candidates):
        super().checked(tick, *candidates)
        short = self.pipeline.model.sources.short
        learning = self._applied
        state = path = None
        if learning is not None and learning.feedback.pc == ANCHOR:
            feedback = learning.feedback
            path = self.path_by_index.get(feedback.indices[1])
            signature = tuple(feedback.context.folds[i] for i in FEATURES)
            canonical = (path is not None and feedback.indices == path.read_indices
                         and signature == path.tag_features and tag(ANCHOR,feedback.context,1) == path.tags[1])
            target = next((source for source in feedback.sources if source.valid and source.position == POSITION
                           and source.position <= feedback.position), None)
            decision = allocation(feedback, learning.useful)
            state = None
            if canonical and path.ordinal in self.ledger.states and target is not None and target.hit and target.provider == 1:
                self.check(self.ledger.states[path.ordinal].counter, target.counter,
                           'fresh original provider counter belongs to the retained logical history')
                actual = int(feedback.taken and feedback.position == POSITION)
                self.check(int(self.expected_results.get(path.ordinal,True)),actual,
                    'actual guidance belongs to the declared history outcome; setup cannot change another path')
                state = self.ledger.feedback(path,predicted=int(target.predicted),base=int(target.base),actual=actual)
            elif (canonical and path not in self.program.helpers and decision.candidate == 1
                    and decision.wrong_position == POSITION):
                self.check(True, feedback.taken and feedback.position == POSITION,
                           'new declared positive identity is admitted by its own actual taken guidance')
                state = self.ledger.allocate(path,taken=True)
            elif path is not None and path.ordinal in self.ledger.states:
                # Wrong-context updates/replacements cannot be hidden behind
                # an index-only association to an already admitted identity.
                self.check(True, canonical, 'retained long identity keeps complete original context, not only its index')
                self.check(False, decision.candidate == 1, 'admitted identity is not silently replaced during another path')
        self.maintenance.after(tick,self.pipeline.model.sources)
        if state is not None:
            state = self.ledger.states[path.ordinal]
            entry = resident(self.pipeline.model.sources,(1,path.read_indices[1]))
            self.check((True,path.tags[1],POSITION,state.counter,state.useful),
                (entry.valid,entry.tag,entry.position,entry.counter,short.useful[1].get(path.read_indices[1],0)),
                'independent outcome ledger agrees with complete predicted long record')
            self.pending_protection = path,state,tick
        first = self._first
        if (self.acceptance is None or self.acceptance.done() or first is None or first.pc != self.window_pc):
            return
        path = self.window_path
        if path is not None:
            snapshot = self.pipeline.model.sources.short_snapshot(first)
            frame = snapshot.prediction.frame
            self.check(True, frame is not None, 'path endpoint owns an original MicroTAGE read frame')
            self.check((path.read_indices,path.tag_features),
                (frame.read.indices,tuple(frame.context.folds[i] for i in FEATURES)),
                'read-index and tag ancestry are the declared predecessor path, not the current token')
            ahead = self.pipeline.model.sources.snapshot(first).frame
            self.check(path.ahead_key,(ahead.read.bank,ahead.read.row),
                       'distinct long histories retain the declared shared early branch identity')
            state = self.ledger.states.get(path.ordinal)
            self.original_window_states[first.history.sequence] = state
        self.selected, self.selected_tick = first,tick
        self.path_captures += 1
        self.acceptance.set_result(self.pipeline.current_event)

    def close_window(self, source, *, path=None):
        token = self.pipeline.source_token(source)
        self.check(self.window_pc,source.prediction.start_pc,'completed source is the declared program instruction')
        self.check(True, token.history is self.selected.history and source.prediction_tick == self.selected_tick,
                   'completed public receipt is the exact accepted original window')
        self.check(False, token.sequence in self.visit_owners, 'a path consumer is not credited twice')
        self.visit_owners.add(token.sequence)
        self.originals.append((source,deepcopy(source.meta.resolve),deepcopy(source.meta.redirect)))
        if path is not None:
            self.path_visits[path.ordinal] = self.path_visits.get(path.ordinal,0)+1
        self.selected = None
        self.checkpoint()
        if self.path_captures % 16 == 0:self.coverage.progress(self)

    def checkpoint(self):
        sources = self.pipeline.model.sources
        self.check(None,self.pending_protection,'all ledger effects crossed actual complete-state comparisons')
        self.check(None,self.maintenance.pending,'maintenance crossed its actual complete-state comparison')
        for ordinal,state in self.ledger.states.items():
            path = self.program.paths[ordinal]
            entry = resident(sources,(1,path.read_indices[1]))
            self.check((True,path.tags[1],POSITION,state.counter,state.useful),
                (entry.valid,entry.tag,entry.position,entry.counter,sources.short.useful[1].get(path.read_indices[1],0)),
                f'old long identity{ordinal} survives other histories and cache turnover')

    def provider(self, source, path, position):
        token = self.pipeline.source_token(source)
        saved = self.pipeline.model.sources.short_snapshot(token)
        values = saved.prediction.values()
        found = [(values[f'{way}.provider'],values[f'{way}.counter'],bool(values[f'{way}.predicted']))
                 for way in range(4) if values.get(f'{way}.valid') and values.get(f'{way}.hit')
                 and values.get(f'{way}.position') == position]
        self.check(1,len(found),'one complete original provider at the declared branch position')
        table,counter,taken = found[0]
        if path.ordinal in self.ledger.states and position == POSITION:
            original = self.original_window_states[token.history.sequence]
            self.check(original.counter,counter,'fresh consumer returns the independently retained original confidence')
        return table,counter,taken

    def declare_result(self, path, taken):
        if (type(taken) is not bool or path.ordinal not in self.ledger.states
                or path != self.program.paths[path.ordinal]):
            raise ValueError('one admitted history and an explicit logical outcome are required')
        self.expected_results[path.ordinal] = taken

    def direction(self, source, path, *, taken, phase):
        if type(taken) is not bool or phase not in self.public_consumers:
            raise ValueError('direction consumer requires an explicit outcome and lifecycle phase')
        self.check(taken,self.expected_results.get(path.ordinal,path not in self.program.helpers),
                   'consumer has its declared path outcome')
        value = self.provider(source,path,POSITION)
        self.check((1,taken),(value[0],value[2]),'fresh long history has its own declared direction')
        position = POSITION if taken else FALLBACK
        actual = source.prediction
        self.check((ANCHOR,position,self.program.helper.pcs[0],1),
            (actual.start_pc,actual.position,actual.target,actual.taken),
            'PUBLIC prediction selects the conditional or real fallback for this history')
        self.check((position,self.program.helper.pcs[0]),
            (source.meta.perf.s1_position,source.meta.perf.s1_target),
            'PUBLIC metadata preserves the exact original branch selection')
        self.public_consumers[phase][path.ordinal] = dict(prediction_tick=source.prediction_tick,
            meta_tick=source.meta_tick,position=actual.position,target=actual.target,
            original_position=source.meta.perf.s1_position,expected_taken=taken)
        if phase == 'reversed':self.reversed_consumers.add(path.ordinal)
        elif phase == 'mixed':self.mixed_consumers[path.ordinal] = taken
        elif phase == 'restored':self.restored_consumers.add(path.ordinal)

    def reached_phase(self, rule, **witness):
        self.mark(rule,**witness)
        self.phase_progress.append(dict(rule=rule,**witness))
        self.coverage.progress(self)

    def finish(self):
        self.raise_failure()
        self.checkpoint()
        self.check({path.ordinal for path in self.program.paths},set(self.path_visits),
                   'all declared real predecessor contexts were consumed')
        wanted = {path.ordinal for path in self.program.positives}
        selected = {path.ordinal for path in self.program.selected}
        self.check(wanted,self.admitted,'all declared long identities were actually admitted and consumed')
        self.check(wanted,self.revisited,'all retained long histories have fresh late consumers')
        self.check(selected,self.penalized,'only the declared paths received their error checks')
        self.check(selected,self.recovered,'every selectively weakened path was genuinely rewarded again')
        self.check(selected,self.reversed_consumers,'each selected history publicly changed its prediction direction')
        self.check({path.ordinal:path.ordinal not in selected for path in self.program.positives},
                   self.mixed_consumers,'all histories publicly distinguish selected NT from retained T learning')
        self.check(wanted,self.restored_consumers,'all histories have fresh public consumers after restoration')
        self.check(True,all(self.expected_results.get(ordinal,True) for ordinal in wanted),
                   'all selected paths restored their declared original outcomes')
        if not self.maintenance.failures.ages:
            self.check({path.ordinal:3 for path in self.program.positives},
                       {ordinal:state.useful for ordinal,state in self.ledger.states.items()},
                       'without global maintenance all positive histories retain upper protection')
        self.check(tuple((resolve,redirect) for _,resolve,redirect in self.originals),
                   tuple((source.meta.resolve,source.meta.redirect) for source,_,_ in self.originals),
                   'all original public metadata remain immutable')
        self.reached_phase('immutable-original-sources',snapshots=len(self.originals))
        self.check(set(RULES),self.completed,'all declared semantic lifetime obligations completed')
        self.maintenance.finish()
        for rule in RULES:self.coverage.record('checked',rule,**self.witnesses[rule])

    def summary(self):
        return dict(super().summary(),history_ledger=self.ledger.state(),
            actual_path_captures=self.path_captures,actual_path_recoveries=self.path_recoveries,
            actual_history_visits=dict(self.path_visits),confirmed_long_learning=self.confirmed_learning,
            phase_progress=deepcopy(self.phase_progress),admitted=sorted(self.admitted),
            penalized=sorted(self.penalized),recovered=sorted(self.recovered),revisited=sorted(self.revisited),
            public_direction_consumers=deepcopy(self.public_consumers),declared_outcomes=dict(self.expected_results),
            maintenance=self.maintenance.summary())


class ShortPathRetentionChecks(HistoryWorkingSetChecks):
    """Reuse full pipeline checks, adding an outcome-owned short ledger."""
    def __init__(self,program,coverage):
        super().__init__(program,coverage)
        self.short_identities={path.ordinal:Identity(0,path.read_indices[0],path.tags[0],SHORT_POSITION)
            for path in program.positives}
        self.short_ledgers,self.short_windows = {},{}
        self.short_offers=deque(maxlen=16)
        self.short_learning,self.short_consumers,self.storage_checks=[],[],[]
        self.short_pending=self.native_storage=self.storage_layout=None
        self.short_results={ordinal:False for ordinal in self.short_identities}

    def candidates(self,row,events,cycle,model,phase,previous):
        result=super().candidates(row,events,cycle,model,phase,previous)
        self.native_storage=deepcopy(row['observed']['short_storage'])
        self.short_third=cycle.tokens[2]
        if self.short_pending is not None:
            ordinal,protection,written=self.short_pending
            self.check(True,self.pipeline.current_event.tick>written,'short protection reaches its actual next observation')
            identity=self.short_identities[ordinal]
            self.check(protection,row['observed']['early_direction']['useful'][0][identity.index],
                'actual short protection agrees with the original-outcome ledger')
            self.short_pending=None
        return result

    def checked(self,tick,*candidates):
        super().checked(tick,*candidates)
        sources=self.pipeline.model.sources
        feedback=sources.last_short_events.feedback
        if feedback is not None:
            self.check(True,self.short_third is not None,'fast learning retains a genuine S3 original')
            self.short_offers.append((feedback,self.short_third))
        learning=self._applied
        if learning is not None:
            feedback=learning.feedback
            owner=next((owner for offered,owner in self.short_offers if offered is feedback),None)
            self.check(True,owner is not None,'applied short learning keeps its exact S3 original')
            decision=allocation(feedback,learning.useful)
            for ordinal,identity in self.short_identities.items():
                if feedback.pc!=ANCHOR or feedback.indices[0]!=identity.index:
                    continue
                event=guidance(feedback,identity)
                if event is not None:
                    self.check(self.short_results[ordinal],event[0],'the declared incoming branch owns its actual result')
                    self.check(True,ordinal in self.short_ledgers,'a hit update follows its own independent admission')
                    transition=self.short_ledgers[ordinal].apply(owner.sequence,*event)
                    self.short_learning.append(dict(tick=tick,path=ordinal,**asdict(transition)))
                    self.short_pending=ordinal,transition.after,tick
                elif (decision.candidate==0 and decision.wrong_position==SHORT_POSITION
                        and tag(ANCHOR,feedback.context,0)==identity.tag):
                    self.check(False,ordinal in self.short_ledgers,'protected incoming learning cannot be silently reallocated')
                    self.check(False,feedback.taken and feedback.position==SHORT_POSITION,'new incoming short experience is NT')
                    self.short_ledgers[ordinal]=ProtectionLedger(counter=3,protection=1)
                    self.short_pending=ordinal,1,tick
        first=self._first
        if (first is not None and self.selected is not None and first.history is self.selected.history
                and self.window_path is not None):
            state=self.short_ledgers.get(self.window_path.ordinal)
            self.short_windows.setdefault(first.history.sequence,None if state is None else (state.counter,state.protection))
        self.checkpoint()

    def checkpoint(self):
        super().checkpoint()
        for ordinal,state in self.short_ledgers.items():
            identity=self.short_identities[ordinal]
            entry=resident(self.pipeline.model.sources,identity.key)
            self.check((True,identity.tag,identity.position,state.counter,state.protection),
                (entry.valid,entry.tag,entry.position,entry.counter,
                    self.pipeline.model.sources.short.useful[0].get(identity.index,0)),
                'every incoming short identity preserves its own independent learning')

    def short_consumer(self,source,path,*,taken=False):
        if type(taken) is not bool:raise ValueError('an explicit consumer direction is required')
        token=self.pipeline.source_token(source)
        values=self.pipeline.model.sources.short_snapshot(token).prediction.values()
        providers=[(values[f'{way}.provider'],values[f'{way}.counter']) for way in range(4)
            if values.get(f'{way}.valid') and values.get(f'{way}.hit') and values.get(f'{way}.position')==SHORT_POSITION]
        self.check(1,len(providers),'one owned short incoming provider required')
        expected=self.short_windows[token.history.sequence]
        self.check(True,expected is not None,'consumer follows its own earlier admission')
        self.check((0,expected[0]),providers[0],'a longer provider cannot substitute for the original short record')
        self.check(taken,expected[0]>=4,'the independently owned short read has its declared direction')
        position=SHORT_POSITION if taken else FALLBACK
        self.check((ANCHOR,position,self.program.helper.pcs[0],1),
            (source.prediction.start_pc,source.prediction.position,source.prediction.target,source.prediction.taken),
            'actual short experience selects its declared conditional or real fallback')
        self.check((position,self.program.helper.pcs[0]),(source.meta.perf.s1_position,source.meta.perf.s1_target),
            'public metadata retains the same original short direction choice')
        self.short_consumers.append(dict(path=path.ordinal,phase=self.phase,owner=token.sequence,
            query_tick=source.prediction_tick,counter=providers[0][1],protection=expected[1],provider=0,expected_taken=taken))

    def short_states(self):
        return {ordinal:(state.counter,state.protection) for ordinal,state in self.short_ledgers.items()}

    def check_storage(self,phase):
        self.check(set(self.short_identities),set(self.short_ledgers),'all declared incoming short identities were admitted')
        snapshot=self.native_storage
        self.check(True,snapshot is not None and self.storage_layout is not None,'actual SRAM and shadow observation required')
        words=[]
        for path,word in zip(self.program.positives,snapshot['words'],strict=True):
            identity,state=self.short_identities[path.ordinal],self.short_ledgers[path.ordinal]
            actual=decode_short_entry(word,self.storage_layout)
            expected=dict(valid=True,tag=identity.tag,position=identity.position,counter=state.counter)
            self.check(expected,actual,'actual SRAM retains each learned incoming identity, not only shadow forwarding')
            words.append(dict(path=path.ordinal,index=identity.index,entry=actual))
        cached={cell['index'] for cell in snapshot['cells'] if cell['valid']}
        uncached=[ordinal for ordinal,identity in self.short_identities.items() if identity.index not in cached]
        if len(self.program.positives)>len(snapshot['cells']):
            self.check(True,bool(uncached),'actual eight-entry shadow cannot retain the full incoming workset')
        self.storage_checks.append(dict(phase=phase,tick=self.pipeline.current_event.tick,
            words=words,actual_cached_indices=sorted(cached),uncached_paths=uncached))

    def finish(self):
        self.raise_failure();self.checkpoint()
        self.check(set(SHORT_RULES),self.completed,'all short retention obligations completed')
        self.check(None,self.short_pending,'all actual protection transitions observed')
        self.check(set(self.short_identities),{row['path'] for row in self.short_consumers if row['phase']=='final-short-consumers'},
            'every learned incoming identity has a fresh late consumer')
        self.check(True,len(self.storage_checks)>=2,'actual SRAM checked before and after fresh consumers')
        self.check(tuple((resolve,redirect) for _,resolve,redirect in self.originals),
            tuple((source.meta.resolve,source.meta.redirect) for source,_,_ in self.originals),
            'complete original incoming metadata remain immutable')
        self.maintenance.finish()
        for rule in SHORT_RULES:self.coverage.record('checked',rule,**self.witnesses[rule])

    def summary(self):
        return dict(super().summary(),short_ledger=self.short_states(),short_learning=deepcopy(self.short_learning),
            short_consumers=deepcopy(self.short_consumers),native_storage=deepcopy(self.storage_checks),
            new_predictor_algorithm=False)


class ShortMixedPathChecks(ShortPathRetentionChecks):
    """Same autonomous predictor and outcome ledger, a wider lifetime contract."""
    def __init__(self,program,coverage):
        super().__init__(program,coverage)
        self.direction_changes=[]

    def declare_result(self,path,taken):
        if path not in self.program.positives or type(taken) is not bool:
            raise ValueError('one declared short owner and an explicit result required')
        self.check(None,self.short_pending,'old learning must finish before declaring a different outcome')
        self.short_results[path.ordinal]=taken

    def check_storage(self,phase):
        self.check(True,self.native_storage is not None,'actual mixed-experience storage observation required')
        cached={cell['index'] for cell in self.native_storage['cells'] if cell['valid']}
        self.check(True,any(identity.index not in cached for identity in self.short_identities.values()),
            'mixed experience must include a real identity no longer retained by the shadow')
        super().check_storage(phase)

    def changed_by_original(self,source,path,before,after,start):
        token=self.pipeline.source_token(source)
        rows=self.short_learning[start:]
        self.check(1,len(rows),'one real original outcome advances exactly one short experience')
        row=rows[0]
        self.check((path.ordinal,token.sequence,before.counter,before.useful,after.counter,after.useful),
            (row['path'],row['owner'],row['counter_before'],row['before'],row['counter_after'],row['after']),
            'the exact original advances the predeclared independent direction transition')
        self.direction_changes.append(dict(path=path.ordinal,owner=token.sequence,
            before=(before.counter,before.useful),after=(after.counter,after.useful)))

    def finish(self):
        from suites.frontend.bpu.bpu.model.history_working_set import SHORT_MIXED_RULES
        self.raise_failure();self.checkpoint()
        self.check(set(SHORT_MIXED_RULES),self.completed,'all mixed short-experience obligations completed')
        self.check(None,self.short_pending,'all actual mixed-experience effects were compared')
        expected={path.ordinal for path in self.program.positives}
        mixed={path.ordinal for path in self.program.mixed}
        selected=self.program.selected[0].ordinal
        for phase,positive in (('initial-short-consumers',set()),('mixed-short-consumers',mixed),
                ('turned-short-consumers',mixed|{selected}),('final-short-consumers',mixed)):
            rows=[row for row in self.short_consumers if row['phase']==phase]
            self.check(expected,{row['path'] for row in rows},'every mixed-experience phase needs all fresh original consumers')
            self.check(len(expected),len(rows),'no duplicate consumer credit within a mixed-experience phase')
            self.check(positive,{row['path'] for row in rows if row['expected_taken']},
                'each phase preserves the predeclared mixed directions')
        owners=[row['owner'] for row in self.short_consumers]
        self.check(len(owners),len(set(owners)),'all phase consumers are distinct original occurrences')
        self.check({'mixed','turned','restored'},{row['phase'] for row in self.storage_checks},
            'actual SRAM is checked for mixed, selected-turn and restored experience')
        changes=[row['owner'] for row in self.direction_changes]
        self.check(True,bool(changes) and len(changes)==len(set(changes)),
            'every direction change belongs to one distinct original')
        self.check(tuple((resolve,redirect) for _,resolve,redirect in self.originals),
            tuple((source.meta.resolve,source.meta.redirect) for source,_,_ in self.originals),
            'all original mixed-experience metadata remain immutable')
        self.maintenance.finish()
        for rule in SHORT_MIXED_RULES:self.coverage.record('checked',rule,**self.witnesses[rule])

    def summary(self):
        return dict(super().summary(),declared_short_outcomes=dict(self.short_results),
            direction_changes=deepcopy(self.direction_changes))
