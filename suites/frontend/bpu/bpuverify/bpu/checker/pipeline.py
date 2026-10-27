"""Compare a self-clocked semantic pipeline; stage wires are actuals only."""
from collections import Counter, deque
from copy import deepcopy

from toffee import CheckContext, Scoreboard, ScoreboardMode

from bpuverify.bpu.model.micro_sources import MicroOnlySources
from bpuverify.bpu.model.pipeline import Commit, Events, Outcome, PipelineReference, Redirect, Resolution
from bpuverify.bpu.model.selection import Kind, StackAction
from bpuverify.bpu.bundle.tage_semantic import HISTORY_PORTS
from bpuverify.bpu.checker.ahead import live_values,fast_values
from bpuverify.bpu.checker.early_direction import live_values as early_live_values,fast_values as early_fast_values

# The AheadBTB module contract services buffered writes in an eight-cycle quiet
# window.  A duplicate copy may remain visible under sustained reads, but a copy
# that survives far past several such windows is no longer a delayed write back.
DUPLICATE_ALLOWANCE_LIMIT = 64


def environment(row, model, *, origin=None,redirect_origin=None,commit_origin=None):
    owned_ras = getattr(model.sources,'has_own_ras',False)
    if not row['reset'] and row['commit_valid'] and not owned_ras:
        raise NotImplementedError('FTQ commit requires the composed RAS source-bank adapter')
    commit = None
    if not row['reset'] and row['commit_valid']:
        if commit_origin is None:
            raise ValueError('return-stack commit requires the exact planned public original')
        commit = Commit(commit_origin,StackAction(row['commit']['action']))
    redirect = None
    if not row['reset'] and row['redirect']['valid']:
        request = row['redirect']
        if owned_ras and redirect_origin is None:
            raise ValueError('return-stack recovery requires the exact planned public original')
        checkpoint=model.checkpoint_for(request['history']) if redirect_origin is None else redirect_origin.history
        kind = request.get('kind')
        redirect = Redirect(checkpoint, request['pc'], request['target'], bool(request['taken']),
            None if kind is None else Kind(kind),StackAction(request.get('action',0)))
    training, feedback = row['training'], None
    if not row['reset'] and row.get('training_accepted',bool(training['valid'] and training['ready'])):
        if getattr(model.sources,'requires_explicit_origin',False) and origin is None:
            raise ValueError('learned MainBTB requires an explicitly associated published origin')
        source = model.checkpoint_for(training['history'], source_pc=training['pc']) if origin is None else origin.history
        branches = tuple(None if not branch['valid'] else Outcome(branch['position'], branch['target'],
            Kind(branch['kind']), bool(branch['taken']), StackAction(branch['action']), bool(branch['mispredict']))
            for branch in training['branches'])
        feedback = Resolution(source, training['pc'], branches,origin=origin)
    return Events(row['reset_vector'], bool(row['prediction_ready']), bool(row['metadata_ready']),
        all(row['initialization']), tuple(map(bool, row['enabled'])), redirect, feedback, bool(row['reset']),
        row.get('consumed_reset'),feedback_at_edge='training_accepted' in row,commit=commit)


def _buffered_invalidation(reference, banks, row, way):
    """Return the bank whose invalidation of one entry is not visible in the DUT.

    The write may still be outstanding or already retired in the reference: the
    single-port bank keeps the DUT copy until a read-free window services the
    same write.  Requiring the reference memory to be invalid (and an issued
    invalidation version to exist) keeps this from matching an unrelated extra
    hit or a copy the reference still considers resident.
    """
    for bank in range(4):
        if not banks & (1 << bank):
            continue
        entry = reference.memory.get((bank, row, way))
        if entry is not None and entry.valid:
            continue
        pending = reference.pending[bank]
        if any(not version.write.entry.valid and version.write.row == row
               and version.write.way == way for version in pending.versions.values()):
            return bank
    return None


def _drop_absence_keys(expected, actual, way, fields):
    removed = []
    for key in tuple(expected):
        if '.' not in key or key.split('.')[0] != str(way):
            continue
        if key.split('.')[1] not in fields or key not in actual:
            continue
        expected.pop(key)
        actual.pop(key)
        removed.append(key)
    return removed


def buffered_duplicate_allowances(model, expected, actual, observed):
    """Allow content-identical AheadBTB copies whose cleanup is still buffered.

    The standalone AheadBTB contract services bank writes only in a read-free
    window; sustained S0 reads can therefore leave two identical copies visible
    after the reference retired the invalidation.  This allowance is bounded:
    the extra DUT way must be *content identical* to a reference hit in the same
    read (position, kind, action and target), the reference must still own an
    outstanding invalidation for that exact row/way, and only the absence
    markers are dropped.  Every published prediction field stays compared.
    Each use is recorded by the caller.
    """
    if not getattr(model.sources, 'has_own_ahead', False):
        return []
    reference = model.sources.ahead
    allowances = []

    def duplicate_way(section, section_actual, presence, entries):
        for way in range(4):
            if section.get(f'{way}.{presence}') != 0 or section_actual.get(f'{way}.{presence}') != 1:
                continue
            entry = entries[way]
            survivor = next((other for other in range(4) if other != way
                and section.get(f'{other}.{presence}') == 1
                and all(section.get(f'{other}.{field}') == entry[field]
                        for field in ('position', 'kind', 'action', 'target_low'))), None)
            if survivor is None:
                continue
            return way, survivor
        return None

    ahead, ahead_actual = expected.get('ahead'), actual.get('ahead')
    if isinstance(ahead, dict) and isinstance(ahead_actual, dict) and isinstance(ahead.get('banks'), int):
        found = duplicate_way(ahead, ahead_actual, 'valid',
            observed['ahead']['meta']['entries'])
        if found is not None:
            way, survivor = found
            bank = _buffered_invalidation(reference, ahead['banks'], ahead['row'], way)
            if bank is not None:
                keys = _drop_absence_keys(ahead, ahead_actual, way, ('valid', 'micro_valid', 'meta_hit'))
                if keys:
                    allowances.append(dict(section='ahead', way=way, survivor=survivor,
                        bank=bank, row=ahead['row'], keys=keys))
        early, early_actual = expected.get('early_direction'), actual.get('early_direction')
        if allowances and isinstance(early, dict) and isinstance(early_actual, dict):
            record = allowances[0]
            way = record['way']
            if early.get(f'{way}.valid') == 0 and early_actual.get(f'{way}.valid') == 1:
                keys = _drop_absence_keys(early, early_actual, way, ('valid',))
                if keys:
                    allowances.append(dict(section='early_direction', way=way,
                        survivor=record['survivor'], bank=record['bank'], row=record['row'], keys=keys))

    fast, fast_actual = expected.get('fast_ahead'), actual.get('fast_ahead')
    fast_meta = fast.get('meta') if isinstance(fast, dict) else None
    fast_actual_meta = fast_actual.get('meta') if isinstance(fast_actual, dict) else None
    fast_record = None
    if (isinstance(fast_meta, dict) and isinstance(fast_actual_meta, dict)
            and isinstance(fast_meta.get('banks'), int)):
        found = duplicate_way(fast_meta, fast_actual_meta, 'hit',
            observed['ahead']['fast']['meta']['entries'])
        if found is not None:
            way, survivor = found
            bank = _buffered_invalidation(reference, fast_meta['banks'], fast_meta['row'], way)
            if bank is not None:
                keys = _drop_absence_keys(fast_meta, fast_actual_meta, way, ('hit',))
                if keys:
                    fast_record = dict(section='fast_ahead', way=way, survivor=survivor,
                        bank=bank, row=fast_meta['row'], keys=keys)
                    allowances.append(fast_record)
    fast_early, fast_early_actual = expected.get('fast_early_direction'), actual.get('fast_early_direction')
    fe_meta = fast_early.get('meta') if isinstance(fast_early, dict) else None
    fe_actual_meta = fast_early_actual.get('meta') if isinstance(fast_early_actual, dict) else None
    if fast_record is not None and isinstance(fe_meta, dict) and isinstance(fe_actual_meta, dict):
        way = fast_record['way']
        if fe_meta.get(f'{way}.valid') == 0 and fe_actual_meta.get(f'{way}.valid') == 1:
            keys = _drop_absence_keys(fe_meta, fe_actual_meta, way, ('valid',))
            if keys:
                allowances.append(dict(section='fast_early_direction', way=way,
                    survivor=fast_record['survivor'], bank=fast_record['bank'],
                    row=fast_record['row'], keys=keys))
    return allowances


def compared_values(model, cycle, observed, events):
    expected = dict(valids=tuple(int(token is not None) for token in cycle.tokens), fires=tuple(map(int,cycle.fires)),
        flushes=tuple(map(int,cycle.flushes)), repair2=int(cycle.middle_repair), repair3=int(cycle.final_repair),
        initialized=int(model.initialized), prediction_valid=int(cycle.presented is not None),
        metadata_valid=int(cycle.metadata is not None))
    actual = {key:observed[key] for key in ('valids','fires','flushes','repair2','repair3','initialized')}
    actual.update(prediction_valid=observed['prediction']['valid'], metadata_valid=observed['metadata']['valid'])
    for slot, token in enumerate(cycle.tokens):
        if token is not None:
            expected[f'pc{slot+1}'], actual[f'pc{slot+1}'] = token.pc, observed['pcs'][slot]
            branch = cycle.decisions[slot].branch
            expected[f'choice{slot+1}'] = dict(taken=int(branch.taken), target=branch.target, position=branch.position,
                                               kind=int(branch.kind), action=int(branch.action))
            actual[f'choice{slot+1}'] = observed['choices'][slot]
    if model.control_samples >= 2:
        expected['enabled'], actual['enabled'] = tuple(map(int,cycle.enabled)), tuple(observed['enabled'])
    if cycle.presented is not None:
        token, choice = cycle.presented
        expected['prediction'] = dict(pc=token.pc,target=choice.branch.target,taken=int(choice.branch.taken),
            position=choice.branch.position,repair2=int(cycle.middle_repair),repair3=int(cycle.final_repair))
        actual['prediction'] = {key:observed['prediction'][key] for key in expected['prediction']}
    if cycle.metadata is not None:
        expected['metadata'] = dict(pc=cycle.metadata.pc, history=cycle.metadata.history.metadata())
        actual['metadata'] = {key:observed['metadata'][key] for key in expected['metadata']}
        if getattr(model.sources,'requires_explicit_origin',False):
            expected['main_metadata'],actual['main_metadata'] = main_metadata_values(cycle.metadata.lookup,observed['metadata']['main'])
        if getattr(model.sources,'has_own_tage',False):
            expected['tage_metadata'],actual['tage_metadata'] = tage_metadata_values(model.sources,cycle.metadata,observed['metadata']['tage'])
        if getattr(model.sources,'has_own_ittage',False):
            expected['ittage_metadata'],actual['ittage_metadata']=ittage_metadata_values(model.sources,cycle.metadata,
                observed['metadata']['ittage'],service_enabled=bool(cycle.enabled[2] and cycle.enabled[5]))
        if getattr(model.sources,'has_own_sc',False):
            from bpuverify.bpu.checker.statistical import history_values, metadata_values
            expected['common_metadata'],actual['common_metadata']=history_values(model.sources,cycle.metadata,observed['metadata']['common'])
            expected['sc_metadata'],actual['sc_metadata']=metadata_values(model.sources,cycle.metadata,observed['metadata']['sc'])
        if getattr(model.sources,'has_own_ahead',False):
            expected['early_source']={'micro':0,'ahead':1,'ahead-direction':3,'fallthrough':4}[cycle.metadata.early.source]
            actual['early_source']=observed['metadata']['source']
    if getattr(model.sources,'has_own_ahead',False):
        expected['ahead'],actual['ahead']=live_values(model.sources,cycle.enabled[1],observed['ahead'])
        expected['fast_ahead'],actual['fast_ahead']=fast_values(model.sources,cycle,observed['ahead']['fast'])
    if getattr(model.sources,'has_own_utage',False):
        expected['early_direction'],actual['early_direction']=early_live_values(model.sources,cycle.enabled[1],observed['early_direction'])
        expected['fast_early_direction'],actual['fast_early_direction']=early_fast_values(model.sources,cycle,observed['early_direction']['fast'])
    if getattr(model.sources,'has_own_sc',False):
        from bpuverify.bpu.checker.statistical import live_values as statistical_live_values
        expected['statistical'],actual['statistical']=statistical_live_values(model.sources,events,cycle,observed['statistical'])
    if getattr(model.sources,'has_own_ras',False):
        from bpuverify.ras.checker.semantic import values
        stack = observed['return_stack']
        expected['return_stack'],actual['return_stack'] = values(model.sources.ras,stack['public'],stack['retained'])
        micro = model.sources.micro_ras.result
        expected['micro_return'] = dict(usable=micro.usable)
        if micro.usable:
            expected['micro_return']['target'] = micro.target
        actual['micro_return'] = {key:stack['micro'][key] for key in expected['micro_return']}
        if cycle.metadata is not None:
            saved = model.sources.return_snapshot(cycle.metadata)
            expected['ras_metadata'] = dict(redirect=saved.redirect_metadata(),commit=saved.commit_metadata())
            actual['ras_metadata'] = observed['ras_metadata']
    if getattr(model.sources,'has_own_ittage',False) and cycle.fires[1] and cycle.enabled[2] and cycle.enabled[5]:
        from bpuverify.bpu.model.indirect_sources import context_for
        token=cycle.tokens[0]
        expected['indirect_read']=dict(pc=token.pc,folds=context_for(token.history).folds)
        actual['indirect_read']=observed['indirect_read']
    if getattr(model.sources,'has_own_ittage',False):
        expected['indirect_random']=model.sources.random_at_sample(events)
        actual['indirect_random']=sum(bit<<index for index,bit in enumerate(observed['indirect_random']))
    if model.initialized:
        folds = model.lookup_history(events,cycle).folds()
        expected['lookup_folds'] = tuple(folds[index] for index in HISTORY_PORTS)
        actual['lookup_folds'] = tuple(observed['lookup_folds'])
    allowances = buffered_duplicate_allowances(model, expected, actual, observed)
    return expected, actual, allowances


def _watch_duplicate_reads(checker, tick, expected, actual):
    """Record later reads of a row whose buffered duplicate was allowed."""
    if not checker.duplicate_watch:
        return
    ahead, seen = expected.get('ahead'), actual.get('ahead')
    if not isinstance(ahead, dict) or not isinstance(seen, dict):
        return
    row, banks = ahead.get('row'), ahead.get('banks')
    if not isinstance(row, int) or not isinstance(banks, int):
        return
    for bank, watched_row, way in checker.duplicate_watch:
        if watched_row != row or banks != 1 << bank:
            continue
        value = ahead.get(f'{way}.valid')
        if value is None:
            continue
        checker.duplicate_history.setdefault((bank, row, way), deque(maxlen=16)).append(
            dict(tick=tick, expected=value, actual=seen.get(f'{way}.valid')))


def main_metadata_values(frame,actual):
    from bpuverify.bpu.model.main_sources import source_entries
    sources = source_entries(frame) if frame is not None else None
    expected,observed = {},{}
    for alignment in range(2):
        for way in range(2):
            source = None if sources is None else sources[alignment][way]
            fields = dict(hit=int(source is not None and source.hit))
            if fields['hit']:
                fields.update(position=source.position,kind=source.kind,action=source.action,counter=source.counter)
            for field,value in fields.items():
                key = f'{alignment}.{way}.{field}'
                expected[key],observed[key] = value,actual[alignment][way][field]
    return expected,observed


def public_main_metadata(value):
    return tuple(tuple(dict(hit=entry['rawHit'],position=entry['position'],kind=entry['attribute']['branchType'],
        action=entry['attribute']['rasAction'],counter=entry['counter_value']) for entry in row) for row in value)


def tage_metadata_values(sources,token,actual):
    expected = sources.defined_tage_metadata(token)
    return expected,{key:actual[int(key.split('.')[0])][key.split('.')[1]] for key in expected}


def ittage_metadata_values(sources,token,actual,*,service_enabled=None):
    from bpuverify.bpu.checker.ittage import defined_fields
    expected=(sources.defined_ittage_metadata(token) if service_enabled is None else
        sources.defined_ittage_metadata(token,service_enabled=service_enabled))
    return expected,defined_fields(actual,expected)


class PipelineChecker:
    def __init__(self, coverage=None, *, sources=None):
        self.model = PipelineReference(MicroOnlySources() if sources is None else sources)
        self.board = Scoreboard('bpu.owned-pipeline')
        self.initialized = False
        self.failure = self.last_cycle = self.last_events = None
        self.last_tick = None
        self.current_event = None
        self.counts = Counter()
        self.records = deque(maxlen=8)
        self.duplicate_allowances = deque(maxlen=64)
        self.duplicate_watch = set()
        self.duplicate_history = {}
        self.duplicate_allowance_counts = Counter()
        self.coverage, self.phase = coverage, 'setup'
        self.last_resolution = None
        self.last_resolution_controls = None
        self.resolutions = deque(maxlen=8)
        self.micro_checked = None
        self.source_receipts,self.s1_accepts = {},{}
        self.feedback_plans = deque()
        self.redirect_plans = deque()
        self.commit_plans = deque()
        self.source_repairs = {}
        self.source_resolutions = {}
        self.sc_previous_cycle=None
        self.sc_numeric_checked={}

    def raise_failure(self):
        if self.failure is not None:
            raise self.failure

    def capture(self, row, event):
        if self.failure is not None:
            return
        self.current_event = event
        try:
            if not self.initialized:
                if not row['inputs']['reset']:
                    return
                self.initialized = True
            origin = redirect_origin = commit_origin = None
            inputs = row['inputs']
            if (not inputs['reset'] and inputs.get('training_accepted',bool(inputs['training']['valid'] and inputs['training']['ready']))
                    and getattr(self.model.sources,'requires_explicit_origin',False)):
                origin = self._accepted_origin(inputs['training'],event)
            if not inputs['reset'] and inputs['redirect']['valid'] and self.redirect_plans:
                redirect_origin=self._accepted_redirect_origin(inputs['redirect'],event)
            if not inputs['reset'] and inputs['commit_valid'] and getattr(self.model.sources,'has_own_ras',False):
                commit_origin=self._accepted_commit_origin(inputs['commit'],event)
            events = environment(inputs, self.model,origin=origin,redirect_origin=redirect_origin,commit_origin=commit_origin)
            if events.reset:
                self.model.advance(events)
                self.last_resolution = None
                self.last_resolution_controls = None
                self.resolutions.clear()
                self.micro_checked = None
                self.source_receipts.clear()
                self.s1_accepts.clear()
                self.feedback_plans.clear()
                self.redirect_plans.clear()
                self.commit_plans.clear()
                self.source_repairs.clear()
                self.source_resolutions.clear()
                self.sc_previous_cycle=None
                self.sc_numeric_checked.clear()
                self.last_tick = event.tick
                return
            if self.last_tick is not None and self.last_tick + 2 != event.tick:
                raise AssertionError('BPU semantic pipeline requires lossless cycle observation')
            cycle = self.model.evaluate(events)
            candidates = None if self.coverage is None else self.coverage.candidates(
                row,events,cycle,self.model,self.phase,self.last_events)
            if candidates is not None:
                self.coverage.reached(event.tick,*candidates)
            expected, actual, allowances = compared_values(self.model, cycle, row['observed'], events)
            if allowances:
                self.counts['abtb-buffered-duplicate-cycles'] += 1
                self.counts['abtb-buffered-duplicate-ways'] += len(allowances)
                self.duplicate_allowances.extend(dict(record, tick=event.tick) for record in allowances)
                for record in allowances:
                    key = record['bank'], record['row'], record['way']
                    self.duplicate_watch.add(key)
                    self.duplicate_allowance_counts[key] += 1
                for key, count in self.duplicate_allowance_counts.items():
                    if count > DUPLICATE_ALLOWANCE_LIMIT:
                        raise AssertionError(
                            'AheadBTB buffered duplicate stayed visible beyond the bounded window: '
                            f'bank/row/way={key} allowed_cycles={count} limit={DUPLICATE_ALLOWANCE_LIMIT}; '
                            'the single-port write back is not merely delayed')
            _watch_duplicate_reads(self, event.tick, expected, actual)
            numeric={}
            if getattr(self.model.sources,'has_own_sc',False):
                from bpuverify.bpu.checker.statistical import numeric_origins,numeric_values,composition_values
                numeric=numeric_origins(self.model.sources,cycle,self.sc_previous_cycle)
                for name,token in numeric.items():
                    port='prediction_evidence' if name=='consume' else 'prediction_read'
                    expected['sc_numeric_'+name],actual['sc_numeric_'+name]=numeric_values(
                        self.model.sources,token,row['observed']['statistical'][port],consumed=name=='consume')
                    if name=='consume':
                        expected['sc_composition'],actual['sc_composition']=composition_values(
                            self.model.sources,token,row['observed']['statistical']['prediction_composition'],
                            tage_enabled=bool(cycle.enabled[3]))
            if getattr(self.model.sources,'has_own_sc',False) and inputs['training']['valid']:
                from bpuverify.bpu.checker.statistical import readiness
                planned = self._accepted_origin(inputs['training'],event)
                _, transaction = self.feedback_plans[0]
                branches = tuple(None if branch is None else Outcome(branch.position,branch.target,
                    Kind(branch.branch_type),bool(branch.taken),StackAction(branch.ras_action),bool(branch.mispredict))
                    for branch in transaction.branches)
                proposal = Resolution(planned.history,planned.pc,branches,origin=planned)
                expected['sc_ready'] = readiness(self.model.sources,cycle,proposal)
                actual['sc_ready'] = bool(row['observed']['statistical']['ready'])
                if not expected['sc_ready']:
                    expected['whole_training_blocked'],actual['whole_training_blocked']=True,not bool(inputs['training']['ready'])
            request=dict(events=events,state=self.model.state())
            if numeric:
                request['sc_numeric_originals']={name:dict(sequence=token.sequence,pc=token.pc,
                    history=self.model.sources.statistical_snapshot(token).history) for name,token in numeric.items()}
            if getattr(self.model.sources,'has_own_utage',False):
                request['short_history']=dict(reference=self.model.sources.short.state(),
                    observed_read_tags=row['observed']['early_direction']['read_tags'])
            self.board.check(expected=expected, actual=actual, context=CheckContext(self.board.name,
                ScoreboardMode.DIRECT, sequence_id=event.tick,
                request=request, observed_event=event))
            for name,token in numeric.items():
                self.sc_numeric_checked.setdefault(token.history.sequence,{})[name]=event.tick
                self.counts['sc-numeric-'+name]+=1
                self.counts['sc-numeric-'+name+'-words']+=sum(len(values) for key,values in
                    expected['sc_numeric_'+name].items() if key in ('path','global','backward','loop','bias'))
                if name=='consume':
                    self.sc_numeric_checked[token.history.sequence]['composition']=event.tick
                    self.counts['sc-composition-originals']+=1
                    self.counts['sc-composition-values']+=20+len(expected['sc_composition']['selected'])
            learning_before = self.model.sources.micro.learning
            self.model.advance(events)
            # Raw storage and public presentations have different visibility
            # boundaries. Compare confidence at an independently known quiet
            # point; never choose a nearby phase based on matching actual data.
            if (learning_before is None and self.model.sources.micro.learning is None
                    and cycle.tokens[2] is None and events.feedback is None):
                expected['micro_confidence'] = tuple(entry.confidence for entry in self.model.sources.micro.entries)
                actual['micro_confidence'] = tuple(row['observed']['micro_confidence'])
                self.board.check(expected=expected['micro_confidence'],actual=actual['micro_confidence'],
                    context=CheckContext(self.board.name,ScoreboardMode.DIRECT,sequence_id=event.tick,
                        request=dict(point='quiescent independently owned MicroBTB confidence',events=events,
                            reference=self.model.sources.micro.state()),observed_event=event))
                self.micro_checked = event.tick,actual['micro_confidence']
            if candidates is not None:
                self.coverage.checked(event.tick,*candidates)
            self.last_tick, self.last_cycle, self.last_events = event.tick, cycle, events
            self.sc_previous_cycle=cycle
            if (getattr(self.model.sources,'requires_explicit_origin',False)
                    and cycle.fires[1] and not cycle.flushes[0]):
                self.s1_accepts[cycle.tokens[0].sequence] = event.tick
            if (getattr(self.model.sources,'requires_explicit_origin',False)
                    and cycle.metadata is not None and events.redirect is None):
                self.source_receipts[event.tick] = cycle.metadata
            if getattr(self.model.sources,'requires_explicit_origin',False):
                for token,stage,repair in ((cycle.tokens[1],2,cycle.middle_repair),(cycle.tokens[2],3,cycle.final_repair)):
                    if token is not None and repair:self.source_repairs.setdefault(token.sequence,[]).append((event.tick,stage))
                retained = set(self.model.published)|{token.sequence for token in self.model.stages if token is not None}
                self.source_repairs = {key:value for key,value in self.source_repairs.items() if key in retained}
            self.records.append(dict(tick=event.tick, expected=expected, actual=actual))
            self.counts['cycles'] += 1
            self.counts['metadata'] += int(cycle.metadata is not None)
            self.counts['metadata-unready'] += int(cycle.metadata is not None and not events.metadata_ready)
            self.counts['held'] += int(cycle.presented is not None and not events.prediction_ready)
            self.counts['redirect-held'] += int(events.redirect is not None and not events.prediction_ready and cycle.fires[0])
            self.counts['middle-repair'] += int(cycle.middle_repair)
            self.counts['late-repair'] += int(cycle.final_repair)
            self.counts['feedback'] += int(events.feedback is not None)
            if redirect_origin is not None:self.redirect_plans.popleft()
            if commit_origin is not None:
                self.commit_plans.popleft()
                self.counts['ras-commits'] += 1
            if events.feedback is not None:
                self.last_resolution = event.tick,events.feedback
                self.last_resolution_controls = event.tick,cycle.enabled
                self.resolutions.append(self.last_resolution)
                if origin is not None:
                    self.source_resolutions.setdefault(origin.sequence,[]).append(self.last_resolution)
                    self.feedback_plans.popleft()
        except Exception as error:
            self.failure = error

    def finish(self):
        self.raise_failure()
        if not self.initialized or not self.model.initialized or not self.counts['metadata']:
            raise AssertionError('BPU pipeline checking requires reset, initialized service and a retired source')
        if self.feedback_plans:
            raise AssertionError('planned owned feedback was not accepted')
        if self.redirect_plans:
            raise AssertionError('planned owned redirect was not accepted')
        if self.commit_plans:
            raise AssertionError('planned owned commit was not accepted')

    def source_token(self,source):
        """Associate one coherent receipt to an already predicted exact owner."""
        self.raise_failure()
        try:
            context = CheckContext(self.board.name,ScoreboardMode.DIRECT,sequence_id=source.meta_tick,
                request=dict(point='exact published feedback source',source=source))
            token = self.source_receipts.get(source.meta_tick)
            self.board.check(expected=True,actual=token is not None,context=context)
            self.board.check(expected=True,actual=self.model.published.get(token.sequence) is token,context=context)
            self.board.check(expected=(self.s1_accepts.get(token.sequence),token.pc,token.pc,token.history.metadata()),
                actual=(source.prediction_tick,source.prediction.start_pc,source.meta.perf.start_pc,source.meta.redirect['phr']),context=context)
            branch = token.early.branch
            self.board.check(expected=(branch.target,int(branch.taken),branch.position,0,0),
                actual=(source.prediction.target,source.prediction.taken,source.prediction.position,
                    source.prediction.s2_override,source.prediction.s3_override),context=context)
            expected,actual = main_metadata_values(token.lookup,public_main_metadata(source.meta.resolve['mbtb_entries']))
            self.board.check(expected=expected,actual=actual,context=context)
            if getattr(self.model.sources,'has_own_tage',False):
                expected,actual = tage_metadata_values(self.model.sources,token,source.meta.resolve['tage_entries'])
                self.board.check(expected=expected,actual=actual,context=context)
            if getattr(self.model.sources,'has_own_ittage',False):
                expected,actual=ittage_metadata_values(self.model.sources,token,source.meta.resolve['ittage'])
                self.board.check(expected=expected,actual=actual,context=context)
            if getattr(self.model.sources,'has_own_sc',False):
                from bpuverify.bpu.checker.statistical import history_values, metadata_values
                for comparator,key in ((history_values,'commonHR'),(metadata_values,'sc')):
                    expected,actual=comparator(self.model.sources,token,source.meta.resolve[key])
                    self.board.check(expected=expected,actual=actual,context=context)
            if getattr(self.model.sources,'has_own_ras',False):
                expected=self.model.sources.return_snapshot(token).redirect_metadata()
                self.board.check(expected=expected,actual={key:source.meta.redirect['ras'][key] for key in expected},context=context)
            return token
        except Exception as error:
            self.failure = error
            raise

    def plan_feedback(self,source,transaction):
        """Compare a real receipt before making its exact owner a driver input."""
        token = self.source_token(source)
        try:
            self.board.check(expected=(token.pc,source.meta.resolve),actual=(transaction.pc,transaction.resolve_meta),
                context=CheckContext(self.board.name,ScoreboardMode.DIRECT,sequence_id=source.meta_tick,
                    request=dict(point='original metadata passed unmodified',source=source)))
            self.feedback_plans.append((token,deepcopy(transaction)))
        except Exception as error:
            self.failure = error
            raise

    def _accepted_origin(self,training,event):
        context = CheckContext(self.board.name,ScoreboardMode.DIRECT,sequence_id=event.tick,
            request=dict(point='planned origin at actual feedback acceptance',pending=len(self.feedback_plans)))
        self.board.check(expected=True,actual=bool(self.feedback_plans),context=context)
        token,transaction = self.feedback_plans[0]
        self.board.check(expected=(token.pc,transaction.resolve_meta['phr']),
            actual=(training['pc'],training['history']),context=context)
        expected,actual = main_metadata_values(token.lookup,training['main'])
        self.board.check(expected=expected,actual=actual,context=context)
        if getattr(self.model.sources,'has_own_tage',False):
            expected,actual = tage_metadata_values(self.model.sources,token,training['tage'])
            self.board.check(expected=expected,actual=actual,context=context)
        if getattr(self.model.sources,'has_own_ittage',False):
            expected,actual=ittage_metadata_values(self.model.sources,token,training['ittage'])
            self.board.check(expected=expected,actual=actual,context=context)
        if getattr(self.model.sources,'has_own_sc',False):
            from bpuverify.bpu.checker.statistical import history_values, metadata_values
            for comparator,key in ((history_values,'common'),(metadata_values,'sc')):
                expected,actual=comparator(self.model.sources,token,training[key])
                self.board.check(expected=expected,actual=actual,context=context)
        for index in range(8):
            branch = transaction.branches[index] if index<len(transaction.branches) else None
            actual_branch = training['branches'][index]
            wanted = dict(valid=int(branch is not None))
            if branch is not None:
                wanted.update(position=branch.position,target=branch.target,kind=branch.branch_type,
                    action=branch.ras_action,taken=branch.taken,mispredict=branch.mispredict)
            self.board.check(expected=wanted,actual={key:actual_branch[key] for key in wanted},context=context)
        return token

    def plan_redirect(self,source,transaction):
        """Associate a real published source BEFORE its redirect is driven.

        Metadata encodings can alias across histories. Preserve the exact
        verified owner instead of guessing newest/oldest or repairing history
        from observed low bits. This is verification ownership, not a full FTQ.
        """
        token=self.source_token(source)
        try:
            payload=transaction.payload()
            self.board.check(expected=source.meta.redirect,actual=payload['meta'],
                context=CheckContext(self.board.name,ScoreboardMode.DIRECT,sequence_id=source.meta_tick,
                    request=dict(point='original redirect metadata passed unmodified',source=source)))
            self.redirect_plans.append((token,deepcopy(payload)))
        except Exception as error:self.failure=error;raise

    def _accepted_redirect_origin(self,actual,event):
        context=CheckContext(self.board.name,ScoreboardMode.DIRECT,sequence_id=event.tick,
            request=dict(point='exact planned redirect at actual acceptance',pending=len(self.redirect_plans)))
        self.board.check(expected=True,actual=bool(self.redirect_plans),context=context)
        token,payload=self.redirect_plans[0]
        self.board.check(expected=True,actual=self.model.published.get(token.sequence) is token,context=context)
        expected=dict(pc=payload['cfi_pc'],target=payload['target'],taken=payload['taken'],
            kind=payload['branch_type'],action=payload['ras_action'],history=token.history.metadata())
        self.board.check(expected=expected,actual={key:actual[key] for key in expected},context=context)
        if getattr(self.model.sources,'has_own_ras',False):
            self.board.check(expected=self.model.sources.return_snapshot(token).redirect_metadata(),actual=actual['ras'],context=context)
        return token

    def source_expected(self,source):
        """Independent commit metadata for the existing retirement driver."""
        token=self.source_token(source)
        return self.model.sources.return_snapshot(token).commit_metadata()

    def plan_commit(self,source,action):
        token=self.source_token(source)
        saved=self.model.sources.return_snapshot(token)
        if type(action) is not int or action not in range(4) or saved.decision is None:
            raise ValueError('commit needs a published semantic action and final decision')
        if any(owner is token for owner,_ in self.commit_plans):
            raise ValueError('this exact original already owns a planned commit')
        from bpuverify.ras.model.semantic import Events as RasEvents, Retirement
        group,calls=saved.original.program.commit_key()
        self.model.sources.ras.preview(RasEvents(retirement=Retirement(group,calls,action,saved.original)))
        payload=dict(action=action,branch_type=int(saved.decision.branch.kind),meta=saved.commit_metadata())
        self.commit_plans.append((token,payload))

    def _accepted_commit_origin(self,actual,event):
        context=CheckContext(self.board.name,ScoreboardMode.DIRECT,sequence_id=event.tick,
            request=dict(point='exact planned commit at actual acceptance',pending=len(self.commit_plans)))
        self.board.check(expected=True,actual=bool(self.commit_plans),context=context)
        token,payload=self.commit_plans[0]
        self.board.check(expected=True,actual=self.model.published.get(token.sequence) is token,context=context)
        self.board.check(expected=payload,actual=actual,context=context)
        return token

    def retire_source(self,meta_tick):
        """Release a verification owner, not an RTL FTQ commit operation."""
        self.raise_failure()
        token = self.source_receipts.get(meta_tick)
        if token is None:
            raise ValueError('source receipt is absent or already retired')
        if any(owner is token for owner,_ in self.feedback_plans):
            raise ValueError('source still owns planned unaccepted feedback')
        if any(owner is token for owner,_ in self.redirect_plans):
            raise ValueError('source still owns a planned unaccepted redirect')
        if any(owner is token for owner,_ in self.commit_plans):
            raise ValueError('source still owns a planned unaccepted commit')
        self.model.retire_source(token.sequence)
        del self.source_receipts[meta_tick]
        self.s1_accepts.pop(token.sequence,None)
        self.source_repairs.pop(token.sequence,None)
        self.source_resolutions.pop(token.sequence,None)

    def resolutions_for_source(self,source):
        """Owned acceptance receipts live until explicit source retirement.

        The small recent ``resolutions`` deque is diagnostic only; it must
        not define the maximum batch a semantic program can verify.
        """
        token=self.source_token(source)
        return tuple(self.source_resolutions.get(token.sequence,()))

    def corrections_for_source(self,source):
        """Return only repairs already compared for this exact public owner."""
        token = self.source_token(source)
        return tuple(self.source_repairs.get(token.sequence,()))
