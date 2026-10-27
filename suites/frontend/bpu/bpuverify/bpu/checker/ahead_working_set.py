"""Independent program ownership and complete actual counter-state closure."""
from copy import deepcopy
from dataclasses import asdict, fields

from toffee import CheckContext, Scoreboard, ScoreboardMode

from bpuverify.abtb.model.semantic import Recency
from bpuverify.bpu.model.ahead_working_set import expected_branch, strong_counter


def prefix_main_counts(token):
    values=token.lookup.values()
    return {values[f'{slot}.position']:values[f'{slot}.counter'] for slot in range(4)
        if values[f'{slot}.valid']}


def prefix_ahead_view(bank,token):
    frame=bank.snapshot(token).frame
    if frame is None or not frame.valid:return {}
    values={entry.position:dict(key=(frame.read.bank,frame.read.row,way),counter=frame.counters[way],
        tag=entry.tag,target=entry.target,kind=entry.kind)
        for way,(entry,hit) in enumerate(zip(frame.read.entries,frame.hits,strict=True)) if hit}
    return values if len(values)==sum(frame.hits) else {}


def prefix_consumer_matches(bank,token,program,index,counts):
    from bpuverify.bpu.model.selection import Kind,fallthrough
    view=prefix_ahead_view(bank,token)
    if set(view)!={2,12} or tuple(view[pos]['counter'] for pos in (2,12))!=counts:return False
    edges=program.branches(index)
    if any((view[e.position]['tag'],view[e.position]['target'],view[e.position]['kind'])
        !=(token.pc%(1<<24),e.target%(1<<22),1) for e in edges):return False
    wanted=edges[0] if counts[0]>=2 else edges[1] if counts[1]>=2 else None
    choice=token.early.branch
    return ((choice==fallthrough(token.pc).branch) if wanted is None else
        (choice.taken and (choice.position,choice.target,choice.kind)==(wanted.position,wanted.target,Kind.CONDITIONAL)))


class AheadWorkingSetChecks:
    def __init__(self, program, coverage):
        self.program, self.coverage = program, coverage
        self.pipeline = None
        self.board = Scoreboard('bpu.ahead-working-set')
        self.failure = None
        self.phase, self.cohort = 'setup', 0
        self.originals, self.feedback_receipts, self.redirect_receipts = [], [], []
        self.completed, self.witnesses = set(), {}
        self.seen, self.snapshots, self.lifetimes = {}, {}, []
        self.counter_comparisons = self.recency_comparisons = self.services = self.strong_resets = 0
        self.pending_services, self.service_examples = [], []
        self.frozen_survivors, self.revisited_survivors = {}, set()
        self.last_late_snapshots = {}
        self._pending = ()
        self.main_service_counts = [0]*4
        self.main_service_examples, self.last_main_state = [], None
        self.first_main_direction_failure = None

    def raise_failure(self):
        if self.failure is not None: raise self.failure
        if self.pipeline is not None: self.pipeline.raise_failure()

    def check(self, expected, actual, point):
        self.board.check(expected=expected, actual=actual, context=CheckContext(self.board.name,
            ScoreboardMode.DIRECT, request=dict(point=point, program=self.program.state(),
                phase=self.phase, cohort=self.cohort, feedback=len(self.feedback_receipts),
                compared_counter_cells=self.counter_comparisons),
            observed_event=None if self.pipeline is None else self.pipeline.current_event))

    def mark(self, rule, **witness):
        self.coverage.record('reached', rule, **witness)
        self.completed.add(rule)
        self.witnesses[rule] = witness

    def begin(self, cohort, phase):
        self.cohort, self.phase, self.seen = cohort, phase, {}

    def accepted(self, source, event, edge, *, bridge=False, taken=True):
        token = self.pipeline.source_token(source)
        tick, resolution = event
        self.check(True, resolution.origin is token and tick > source.meta_tick,
                   'actual feedback belongs to exact original public source')
        self.check(edge.pc, token.pc, 'logical branch belongs to this original source PC')
        self.check(False, any(row['source_tick'] == source.meta_tick for row in self.feedback_receipts),
                   'each original feedback source is consumed only once')
        self.check(False, any(row['accepted_tick'] == tick for row in self.feedback_receipts),
                   'actual feedback acceptance is not credited twice')
        branches = tuple(branch for branch in resolution.branches if branch is not None)
        self.check(1, len(branches), 'one declared real branch outcome')
        actual = branches[0]
        self.check((edge.position, edge.target, edge.kind, taken, 0),
            (actual.position, actual.target, int(actual.kind), actual.taken, int(actual.action)),
            'complete logical branch guidance')
        self.originals.append((source, deepcopy(source.meta.resolve), deepcopy(source.meta.redirect)))
        self.feedback_receipts.append(dict(cohort=self.cohort, phase=self.phase, pc=token.pc,
            source_tick=source.meta_tick, accepted_tick=tick, target=edge.target, kind=edge.kind,
            bridge=bridge, taken=taken))

    def candidates(self, row, events, cycle, model, phase, previous):
        sources = model.sources
        ahead = sources.ahead
        state = row['observed']['ahead_working_state']
        self.last_main_state = deepcopy(dict(services=state['main_service'], response=state['main_response'],
                                             tage_fast=state['tage_fast']))
        for owner, bank in enumerate(state['main_service']):
            for way, port in enumerate(bank['writes']):
                if way < 2 and port['valid'] and port['ready']:
                    self.main_service_counts[owner] += 1
                    if len(self.main_service_examples) < 32:
                        self.main_service_examples.append(dict(tick=self.pipeline.current_event.tick,
                            owner=owner, way=way, bits=deepcopy(port['bits'])))
        self._direction_snapshot = tuple(deepcopy(bank['direction']) for bank in state['main_service'])
        launch = getattr(self.coverage, 'observe_launch', None)
        if launch is not None:
            launch(cycle.enabled, events.initialization_complete, self.pipeline.current_event.tick)
        expected = tuple(ahead.counters.get((bank, index, way), 0)
            for bank in range(4) for index in range(64) for way in range(4))
        self.check(expected, tuple(state['counters']), 'all1024 reset-derived independent direction counters')
        recent = tuple(ahead.recency.get((bank, index), Recency()) for bank in range(4) for index in range(64))
        encoded = tuple((age.oldest_half << 2) | age.oldest_members[0] | (age.oldest_members[1] << 1) for age in recent)
        self.check(encoded, tuple(state['recency']), 'all256 independently encoded replacement relations')
        self.counter_comparisons += 1024
        self.recency_comparisons += 256
        for service in self.pending_services:
            self.services += 1
            self.strong_resets += int(service['old_counter'] == 3)
            if len(self.service_examples) < 8: self.service_examples.append(service)
        self.pending_services.clear()
        self._before_memory, self._before_counters = dict(ahead.memory), dict(ahead.counters)
        self._pending = ()
        return self.consumer(events, cycle, sources)

    def consumer(self, events, cycle, sources):
        """Scenario qualification follows the shared complete-state comparison."""
        token = cycle.metadata
        if token is None or not events.metadata_ready or not self.phase.startswith(('warm', 'late')):
            return ()
        edges = {edge.pc: edge for edge in self.program.edges(self.cohort)}
        if token.pc not in edges:
            return ()
        edge = edges[token.pc]
        branch = cycle.decisions[2].branch
        self.check(expected_branch(edge), dict(taken=bool(branch.taken), target=branch.target,
            position=branch.position, kind=int(branch.kind), action=int(branch.action)),
            'actual final guidance is the declared natural control-flow edge')
        frame = sources.snapshot(token).frame
        if token.early.source not in ('ahead', 'ahead-direction') or frame is None:
            return ()
        early = token.early.branch
        self.check(expected_branch(edge), dict(taken=bool(early.taken), target=early.target,
            position=early.position, kind=int(early.kind), action=int(early.action)),
            'fresh early consumer retains complete logical identity')
        ways = tuple(way for way, (hit, entry) in enumerate(zip(frame.hits, frame.read.entries, strict=True))
                     if hit and entry.position == edge.position and entry.kind == edge.kind)
        self.check(1, len(ways), 'one matching original Ahead identity')
        way = ways[0]
        key = frame.read.bank, frame.read.row, way
        # Saturation is observed through a real immutable read snapshot, not
        # inferred from elapsed cycles or taken direction alone.
        if frame.counters[way] == strong_counter(edge):
            self._pending = (token.pc, dict(tick=self.pipeline.current_event.tick,
                counter=frame.counters[way], kind=edge.kind, key=key, target=edge.target,
                source_sequence=token.sequence, source_history=token.history.history))
        return ()

    def compare_direction_proposals(self):
        # Post-rise combinational requests include the just-accepted public
        # feedback. Compare after semantic advance, before any predicted SRAM
        # service is used to confirm its effect; no observed qualifier enters
        # the reference model.
        main = self.pipeline.model.sources.main
        patches = main.direction_proposals()
        for owner, direction in enumerate(self._direction_snapshot):
            patch = patches.get(divmod(owner, 2))
            wanted = dict(valid=int(patch is not None))
            actual = dict(valid=direction['valid'])
            if patch is not None:
                wanted.update(row=patch.row, mask=sum(1 << way for way, value in enumerate(patch.values) if value is not None),
                    values={str(way):value for way,value in enumerate(patch.values) if value is not None})
                data = direction['bits']
                actual.update(row=data['row'], mask=data['mask'],
                    values={str(way):value for way,value in enumerate(data['counters']) if data['mask'] & (1 << way)})
            if wanted != actual and self.first_main_direction_failure is None:
                self.first_main_direction_failure = dict(owner=owner, expected=deepcopy(wanted), actual=deepcopy(actual),
                    original_public_feedback=None if main.offered is None else asdict(main.offered.feedback))
            self.check(wanted, actual, f'Main direction proposal requires original hit and selected allocation ownership: owner{owner}')

    def reached(self, tick, *candidates): pass

    def checked(self, tick, *candidates):
        self.compare_direction_proposals()
        ahead = self.pipeline.model.sources.ahead
        for key, entry in ahead.memory.items():
            old = self._before_memory.get(key)
            if entry.valid and entry != old and (old is None or not old.valid or old.tag != entry.tag):
                self.check(2, ahead.counters.get(key, 0), 'new identity has its own initial confidence')
                self.pending_services.append(dict(predicted_tick=tick, key=key,
                    old_counter=self._before_counters.get(key, 0), tag=entry.tag, target=entry.target))
        if self._pending:
            pc, witness = self._pending
            self.seen[pc] = witness
            key = tuple(witness['key'])
            frozen = self.frozen_survivors.get(key)
            if frozen is not None and frozen['tag'] == pc % (1 << 24):
                self.revisited_survivors.add(key)

    def cohort_complete(self):
        return set(self.seen) == {edge.pc for edge in self.program.edges(self.cohort)}

    def close_lap(self):
        self.check(True, self.cohort_complete(), 'all declared branches have fresh complete Ahead consumers')
        self.check(True, all(witness['source_history'] != 0 for witness in self.seen.values()),
                   'natural program carries real nonzero history')
        self.lifetimes.append(dict(cohort=self.cohort, phase=self.phase, consumers=len(self.seen),
            first_tick=min(w['tick'] for w in self.seen.values()), last_tick=max(w['tick'] for w in self.seen.values()),
            conditional=sum(w['kind'] == 1 for w in self.seen.values()),
            unconditional=sum(w['kind'] != 1 for w in self.seen.values())))
        if self.phase.startswith('late'):
            self.last_late_snapshots[self.cohort] = deepcopy(self.seen)

    def freeze_survivors(self, cohort):
        ahead = self.pipeline.model.sources.ahead
        self.frozen_survivors = {}
        for pc, snapshot in self.last_late_snapshots[cohort].items():
            key = tuple(snapshot['key'])
            entry = ahead.memory.get(key)
            if entry is not None and entry.valid and entry.tag == pc % (1 << 24):
                self.frozen_survivors[key] = dict(tag=entry.tag, counter=ahead.counters.get(key, 0))
        self.check(True, bool(self.frozen_survivors), 'declare retained older identities before resuming their program')

    def finish(self):
        self.raise_failure()
        self.check(2*self.program.cohorts + int(self.program.cohorts > 1), len(self.lifetimes),
                   'warm and late full laps plus the declared older survivor revisit')
        expected_feedback = self.program.cohorts*len(self.program.edges(0))
        if self.program.cohorts > 1:
            expected_feedback += len(self.program.edges(0))
            self.check(set(self.frozen_survivors), self.revisited_survivors,
                       'every predeclared older survivor really consumed again')
        self.check(expected_feedback, sum(not row['bridge'] for row in self.feedback_receipts),
                   'complete real Main preparation, including older revisit')
        self.check(self.program.cohorts-1 + int(self.program.cohorts > 1),
                   sum(row['bridge'] for row in self.feedback_receipts), 'every inter-program bridge is a real resolved indirect branch')
        self.check(tuple((resolve, redirect) for _, resolve, redirect in self.originals),
                   tuple((source.meta.resolve, source.meta.redirect) for source, _, _ in self.originals),
                   'every complete original metadata snapshot remains immutable')
        self.check(0, len(self.pending_services), 'all predicted services confirmed at actual full-state boundaries')
        if self.program.cohorts > 1:
            self.check(True, self.services > 0 and self.strong_resets > 0,
                       'actual new identity service clears a genuinely strong old confidence')
        for rule in self.program.rules:
            self.mark(rule, feedback=len(self.feedback_receipts), consumers=sum(x['consumers'] for x in self.lifetimes))
        for rule in self.program.rules:
            self.coverage.record('checked', rule, **self.witnesses[rule])

    def summary(self):
        status = self.board.status
        counters = {field.name: (str(value) if isinstance(value := getattr(status, field.name), BaseException) else value)
                    for field in fields(status)}
        return dict(program=self.program.state(), phase=self.phase, cohort=self.cohort,
            actual_feedback=len(self.feedback_receipts), actual_recoveries=len(self.redirect_receipts),
            complete_laps=deepcopy(self.lifetimes), partial_current_consumers=len(self.seen),
            actual_counter_cell_comparisons=self.counter_comparisons,
            actual_recency_comparisons=self.recency_comparisons,
            new_identity_services=self.services, strong_old_identity_resets=self.strong_resets,
            service_examples=deepcopy(self.service_examples), older_survivors_declared=len(self.frozen_survivors),
            older_survivors_consumed=len(self.revisited_survivors), completed=sorted(self.completed),
            original_snapshots=len(self.originals), checks=counters,
            actual_main_services=list(self.main_service_counts),
            actual_main_service_examples=deepcopy(self.main_service_examples),
            last_main_state=deepcopy(self.last_main_state),
            first_main_direction_failure=deepcopy(self.first_main_direction_failure))


class PrefixWorkingSetChecks(AheadWorkingSetChecks):
    """Whole-state oracle plus logical window/prefix lifetime obligations."""
    def __init__(self,program,coverage):
        super().__init__(program,coverage)
        self.redirect_count,self.last_redirect=0,None
        self.saved={}
        self.accepted_sources=set()
        self.accepted_count=0
        self.feedback_classes={}
        self.prefix_consumers=[]
        self.original_residents={}
        self.prefix_closed=False

    def candidates(self,row,events,*args):
        self.events=events
        return super().candidates(row,events,*args)

    def consumer(self,*args):return ()

    def checked(self,tick,*args):
        super().checked(tick,*args)
        if self.events.redirect is not None:
            self.redirect_count+=1
            self.last_redirect=tick,self.events.redirect.source,self.events.prediction_ready

    def save(self,source):
        token=self.pipeline.source_token(source)
        bank=self.pipeline.model.sources
        self.saved.setdefault(token.sequence,(source,token,deepcopy(source.meta),
            bank.snapshot(token),bank.short_snapshot(token)))
        return token

    def accepted_prefix(self,source,resolution):
        token=self.save(source)
        self.check(True,resolution.origin is token,'complete backend result owns its exact public original')
        self.check(False,token.sequence in self.accepted_sources,'one real original is accepted only once')
        self.accepted_sources.add(token.sequence)
        self.accepted_count+=1
        key=tuple((b.position,b.taken) for b in resolution.branches if b is not None)
        self.feedback_classes[key]=self.feedback_classes.get(key,0)+1

    def prefix_consumer(self,source,index,counts,phase):
        bank=self.pipeline.model.sources
        token=self.save(source)
        view=prefix_ahead_view(bank,token)
        self.check(True,prefix_consumer_matches(bank,token,self.program,index,counts),
            'full original Ahead records, direction strengths and selected branch form the declared prefix')
        choice=token.early.branch
        self.check((token.pc,choice.position,choice.target,int(choice.taken)),
            (source.prediction.start_pc,source.prediction.position,source.prediction.target,source.prediction.taken),
            'actual public receipt consumes that exact independently owned early selection')
        if phase=='selected-NT' and index in self.program.selected:
            self.check((0,0),tuple(bank.ahead.counters[view[pos]['key']] for pos in (2,12)),
                'fresh whole-window NT guidance also holds both original lower boundaries')
        if phase=='initial-late':
            self.original_residents[index]=deepcopy(view)
        else:
            original=self.original_residents[index]
            self.check({p:{k:v for k,v in row.items() if k!='counter'} for p,row in original.items()},
                {p:{k:v for k,v in row.items() if k!='counter'} for p,row in view.items()},
                'both original branch identities and targets survive the entire direction lifetime')
            if index not in self.program.selected:
                self.check(original,view,'unselected code windows preserve both resident experiences')
            elif phase=='selected-early':
                self.check(original[12],view[12],'unexecuted later conditional keeps its original experience')
        self.prefix_consumers.append(dict(phase=phase,index=index,owner=token.sequence,
            counters=counts,position=choice.position,target=choice.target,taken=bool(choice.taken),
            residents=deepcopy(view)))

    def finish_prefix(self):
        self.raise_failure()
        self.check(False,self.prefix_closed,'prefix working set closes once')
        self.check(set(range(self.program.count)),set(self.original_residents),'every original window has both resident branches')
        for phase in ('initial-late','selected-early','selected-NT','restored-early'):
            rows=[row for row in self.prefix_consumers if row['phase']==phase]
            self.check((set(range(self.program.count)),self.program.count),
                ({row['index'] for row in rows},len(rows)),'every phase checks all selected and unselected windows')
        self.check(4*self.program.count,len({row['owner'] for row in self.prefix_consumers}),
            'all phase consumers are distinct fresh original predictions')
        self.check(True,all(self.feedback_classes.get(key,0)>0 for key in (
            ((2,True),),((2,False),(12,True)),((2,False),(12,False)))),
            'real backend feedback includes early-taken, later-taken and whole-window not-taken')
        bank=self.pipeline.model.sources
        for source,token,metadata,ahead,short in self.saved.values():
            self.check(True,self.pipeline.source_token(source) is token,'original public association is immutable')
            self.check(metadata,source.meta,'complete original metadata is immutable')
            self.check((ahead,short),(bank.snapshot(token),bank.short_snapshot(token)),
                'old Ahead read and short-history evidence are never recomputed from new state')
        self.check(True,self.counter_comparisons>0 and self.recency_comparisons>0,
            'all actual direction cells and replacement relations were compared')
        self.check([],self.pending_services,'all new identity services reach actual full-state comparison')
        for rule in self.program.rules:self.mark(rule,windows=self.program.count,consumers=len(self.prefix_consumers))
        for rule in self.program.rules:self.coverage.record('checked',rule,**self.witnesses[rule])
        self.prefix_closed=True

    def summary(self):
        result=super().summary()
        result.update(actual_feedback=self.accepted_count,original_sources=len(self.saved),
            feedback_classes={str(key):value for key,value in self.feedback_classes.items()},
            fresh_prefix_consumers=deepcopy(self.prefix_consumers),prefix_closed=self.prefix_closed,
            no_bank_sweep=True,new_predictor_algorithms=0,complete_FTQ=False)
        return result
