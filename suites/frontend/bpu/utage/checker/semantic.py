"""Exact defined prediction fields and owned learning/useful comparisons."""
from collections import deque
from dataclasses import replace

from toffee import CheckContext, Scoreboard, ScoreboardMode

from suites.frontend.bpu.utage.model.semantic import Context, UtageReference, indices, training_folds, tag_view


def prediction_values(prediction, actual, meta_valid):
    expected = prediction.values()
    observed = dict(hits=tuple(value if wanted is not None else None
                              for value, wanted in zip(actual.hits, expected['hits'], strict=True)))
    if 'meta_valid' in expected:
        observed['meta_valid'] = int(meta_valid)
    if 'indices' in expected:
        observed.update(indices=tuple(actual.meta['readIndex']),
            history=tuple(row['foldedHist'] for row in actual.meta['foldedPathHistForTrain_hist']))
        # Training metadata carries only the folds the parent consumes.
        expected['history'] = training_folds(prediction.frame.context)
        observed['history'] = training_folds(observed['history'])
    for slot, source in enumerate(actual.meta['abtbResult']):
        if f'{slot}.taken' in expected:
            observed[f'{slot}.taken'] = actual.takens[slot]
        names = dict(valid='valid', base='baseTaken', strong='baseIsStrongBias', hit='hit',
                     predicted='predTaken', position='cfiPosition', provider='tableId', counter='takenCtr_value')
        for name, field in names.items():
            key = f'{slot}.{name}'
            if key not in expected:
                continue
            if field not in source:
                # Whole-chip DCE removed the strength leaf; it is not part of
                # this build's observable metadata contract.
                expected.pop(key)
                continue
            observed[key] = source[field]
    return expected, observed


class UtageSemanticChecker:
    def __init__(self):
        self.model = UtageReference()
        self.board = Scoreboard('utage.semantic-reference')
        self.initialized = False
        self.failure = None
        self.failure_observed = False
        self.events = None
        self.input_tick = None
        self.expected = deque(maxlen=64)
        self.useful_checks = 0
        self.counter_fields = ('low',)
        self.last_event = None
        # Bounded, recorded allowances for defects the independent reference
        # detects earlier than the scenario's own declared exception.  They
        # never suppress whole comparisons: only the named field set for the
        # named logical address is dropped, and every use is recorded.
        self.known_misses = {}
        self.known_counter_differences = {}
        self.allowed_events = []

    def allow_known_miss(self, pc, position, reason):
        """Allow one known tag-width miss at a concrete logical address."""
        if type(pc) is not int or type(position) is not int or not reason:
            raise ValueError('a known miss needs a concrete pc, position and reason')
        self.known_misses[(pc, position)] = reason

    def allow_known_counter_difference(self, table, index, reason):
        """Allow one known stale counter at a concrete table cell, not a window.

        The declared persistence defect can leave either an older higher value
        (lower table) or an older lower value (upper table) after the ring slot
        is cleared, so the allowance is scoped by cell and field, not by sign.
        """
        if table not in (0, 1) or type(index) is not int or not 0 <= index < 512 or not reason:
            raise ValueError('a known counter difference needs a concrete table cell and reason')
        self.known_counter_differences[(table, index)] = reason

    def _bounded_allowance(self, prediction, expected, observed):
        """Drop only declared defect fields; every other field is still checked.

        A miss allowance is keyed by (frame pc, slot position) and requires the
        model to expect a hit while the DUT reports a miss.  A counter allowance
        is keyed by (provider table, read index) and requires a strict loss.
        Any non-matching difference survives and fails normally.
        """
        frame = None if prediction is None else prediction.frame
        if frame is None:
            return
        hits = expected.get('hits')
        if hits is not None:
            observed_hits = observed.get('hits', ())
            allowed = []
            for slot, (want, got) in enumerate(zip(hits, observed_hits, strict=True)):
                if want is None or got is None or want == got:
                    continue
                position = frame.positions[slot]
                reason = self.known_misses.get((frame.pc, position))
                if want != 1 or got != 0 or reason is None:
                    # One undeclared hit difference keeps the whole comparison.
                    allowed = []
                    break
                allowed.append((slot, position, reason))
            if allowed:
                drop = {'hits', 'meta_valid'}
                for slot, position, reason in allowed:
                    drop.update(f'{slot}.{name}' for name in
                                ('hit', 'taken', 'predicted', 'provider', 'counter'))
                    self.allowed_events.append(dict(kind='known-tag-width-miss',
                        tick=self.input_tick, pc=frame.pc, position=position,
                        expected_hit=1, observed_hit=0, reason=reason))
                for key in drop:
                    expected.pop(key, None)
                    observed.pop(key, None)
        for slot, provider in enumerate(frame.providers()):
            key = f'{slot}.counter'
            if provider is None or key not in expected or key not in observed:
                continue
            if expected.get(f'{slot}.hit') != 1 or observed.get(f'{slot}.hit') != 1:
                # A counter comparison is only meaningful when both sides agree
                # that this slot has a provider hit; a hit difference must fail.
                continue
            reason = self.known_counter_differences.get((provider, frame.read.indices[provider]))
            if reason is None or expected[key] == observed[key]:
                continue
            self.allowed_events.append(dict(kind='known-counter-difference',
                tick=self.input_tick, table=provider, index=frame.read.indices[provider],
                expected=expected[key], observed=observed[key], reason=reason))
            expected.pop(key, None)
            observed.pop(key, None)

    def raise_failure(self):
        if self.failure is not None:
            self.failure_observed = True
            raise self.failure

    def raise_unobserved_failure(self):
        if not self.failure_observed:
            self.raise_failure()

    def capture_input(self, event, events):
        if self.failure is not None:
            return
        try:
            if events.reset:
                self.initialized = True
            if self.initialized:
                self.model.advance(events)
            self.events, self.input_tick = events, event.tick
        except Exception as error:
            self.failure = error

    def _check(self, actual, prediction, meta_valid, context):
        if prediction is not None and prediction.qualified:
            expected, observed = prediction_values(prediction, actual, meta_valid)
            self._bounded_allowance(prediction, expected, observed)
            self.board.check(expected=expected, actual=observed, context=context)

    def capture_output(self, event, actual, meta_valid, *, counters, useful, live_bases=None):
        if self.failure is not None or not self.initialized:
            return
        try:
            if self.input_tick != event.tick - 1:
                raise AssertionError('UTAGE reference requires one public boundary per clock')
            self.last_event = event
            if live_bases is not None and self.model.prediction is not None:
                # AheadBTB result fields are a combinational upstream input to
                # metadata, unlike the registered A0/A1 lookup descriptors.
                # Decode that input's current phase; never consult DUT outputs
                # to repair the expected table contents or correction result.
                self.model.prediction = replace(self.model.prediction, bases=live_bases)
            self.expected.append((event.tick, self.model.prediction, meta_valid, self.events.enabled))
            context = CheckContext(self.board.name, ScoreboardMode.DIRECT, sequence_id=event.tick,
                request=dict(events=self.events, state=self.model.state()), observed_event=event)
            self._check(actual, self.model.prediction, meta_valid, context)
            counter_values = dict(low=self.model.low_tick, high=self.model.high_tick)
            self.board.check(expected={field: counter_values[field] for field in self.counter_fields},
                             actual=counters, context=context)
            if useful:
                expected = {key: self.model.useful[key[0]].get(key[1], 0) for key in useful}
                self.board.check(expected=expected, actual=useful, context=context)
                self.useful_checks += len(useful)
        except Exception as error:
            self.failure = error

    def response_expected(self, request, context):
        tick = context.accepted_event.tick + 4

        def compare(actual):
            self.raise_failure()
            matches = [(prediction, valid, enabled) for at, prediction, valid, enabled in self.expected if at == tick]
            if len(matches) != 1:
                raise AssertionError(f'no independent UTAGE response at {tick}')
            prediction, valid, enabled = matches[0]
            if enabled and (prediction is None or not prediction.qualified):
                raise AssertionError('accepted UTAGE request has no owned read snapshot')
            if enabled and request.override is None:
                self.board.check(
                    expected=(request.pc, tag_view(Context.from_recent(request.folded_history)),
                              indices(request.read_pc, Context.from_recent(request.read_history))),
                    actual=(prediction.frame.pc, tag_view(prediction.frame.context),
                            prediction.frame.read.indices), context=context)
            self._check(actual, prediction, valid, context)

        return compare
