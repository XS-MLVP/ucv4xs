"""Defined prediction fields and request context against independent TAGE state."""
from collections import deque
from dataclasses import replace

from toffee import CheckContext, Scoreboard, ScoreboardMode

from suites.frontend.bpu.tage.model.semantic import Base, Context, TageReference, decide


def prediction_values(wanted, actual, extras=None):
    expected, observed = {}, {}
    names = dict(has_provider='hasProvider', has_alt='hasAlt', use_provider='useProvider',
                 alternative='altOrBasePred', alt_conf='altConf', table='providerTableIdx', way='providerWayIdx',
                 counter='providerTakenCtr_value', useful='providerUsefulCtr_value')
    for slot, meta in enumerate(actual.metas):
        values = dict(valid=actual.valids[slot], taken=actual.takens[slot], sc_valid=actual.provider_counter_valids[slot])
        values.update({name: meta[field] for name, field in names.items()})
        if extras is not None:
            values.update(fast_valid=extras['fast_valids'][slot], fast_taken=extras['fast_takens'][slot],
                          sc_counter=extras['sc_counters'][slot])
        for name, value in values.items():
            key = f'{slot}.{name}'
            if key in wanted:
                expected[key], observed[key] = wanted[key], value
    return expected, observed


class TageSemanticChecker:
    def __init__(self):
        self.model = TageReference()
        self.board = Scoreboard('tage.semantic-reference')
        self.failure = None
        self.initialized = self.failure_observed = False
        self.events = self.input_tick = None
        self.expected = deque(maxlen=128)
        from suites.frontend.bpu.tage.model.semantic import VISIBLE_HISTORY_INDICES
        self.history_indices: tuple[int, ...] = VISIBLE_HISTORY_INDICES
        self.accepted_feedback = deque(maxlen=64)

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
                if not events.reset and events.ready and self.model.accepted is not None:
                    self.accepted_feedback.append((event.tick, self.model.accepted.feedback))
            self.events, self.input_tick = events, event.tick
        except Exception as error:
            self.failure = error

    def _check(self, wanted, actual, context, extras=None):
        expected, observed = prediction_values(wanted, actual, extras)
        self.board.check(expected=expected, actual=observed, context=context)

    def capture_output(self, event, actual, *, bases, enabled, extras):
        if self.failure is not None or not self.initialized:
            return
        try:
            if self.input_tick != event.tick - 1:
                raise AssertionError('TAGE reference requires one public input boundary per clock')
            frame = self.model.frame
            wanted = decide(frame, bases, self.model.selectors, enabled=enabled) if frame is not None else None
            self.expected.append((event.tick, frame, wanted, self.events.enabled, bases))
            if self.events.reset or not self.events.ready or wanted is None:
                return
            self._check(wanted, actual, CheckContext(self.board.name, ScoreboardMode.DIRECT,
                sequence_id=event.tick, request=dict(events=self.events, bases=bases, state=self.model.state()),
                observed_event=event), extras)
        except Exception as error:
            self.failure = error

    def _visible(self, context):
        from suites.frontend.bpu.tage.monitor.semantic import visible_context
        return visible_context(context, self.history_indices)

    def response_expected(self, request, context):
        tick = context.accepted_event.tick + 4

        def compare(actual):
            self.raise_failure()
            matches = [(frame, wanted, enabled, bases) for at, frame, wanted, enabled, bases in self.expected if at == tick]
            if len(matches) != 1 or matches[0][0] is None:
                raise AssertionError(f'no independent TAGE response at {tick}')
            frame, wanted, enabled, bases = matches[0]
            if enabled:
                self.board.check(expected=(request.pc, self._visible(Context.from_recent(request.history))),
                                 actual=(frame.read.pc, self._visible(frame.read.context)), context=context)
                branches = request.branches if request.branches is not None else (request,)
                for slot in range(len(bases)):
                    branch = branches[slot] if slot < len(branches) else None
                    wanted_base = Base() if branch is None else Base(True, branch.position,
                        bool(branch.taken if request.branches is not None else branch.base_taken),
                        bool(branch.base_conf), branch.branch_type)
                    # Whole-chip DCE removed the MainBTB attribute leaf and
                    # the s2 cfiPosition leaf: a completed result exposes only
                    # validity, direction and confidence. Position ownership
                    # is checked on the request/model side below; the live
                    # s1_positions input belongs to a different pipeline
                    # request at this output boundary, so it is not an
                    # observable field of this result.
                    wanted_base = replace(wanted_base, kind=0)
                    observed_base = Base(
                        valid=bases[slot].valid,
                        position=wanted_base.position,
                        taken=bases[slot].taken,
                        confident=bases[slot].confident,
                        kind=0)
                    self.board.check(expected=wanted_base, actual=observed_base, context=context)
                    if wanted_base.valid:
                        self.board.check(expected=wanted_base.position, actual=frame.positions[slot], context=context)
            self._check(wanted, actual, context)

        return compare
