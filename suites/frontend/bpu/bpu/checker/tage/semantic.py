"""Owned TAGE state at a declared component cut point, not full BPU golden."""
from collections import deque
from toffee import CheckContext, Scoreboard, ScoreboardMode

from suites.frontend.bpu.tage.checker.semantic import TageSemanticChecker


class TageSemanticComponentChecker(TageSemanticChecker):
    def __init__(self):
        super().__init__()
        self.board = Scoreboard('bpu.tage.semantic-component')
        self.resolve_slots = deque(maxlen=64)

    def capture_input(self, event, events, *, resolve_slots=()):
        super().capture_input(event, events)
        if self.failure is None and self.initialized and not events.reset and self.model.accepted is not None:
            self.resolve_slots.append((event.tick, resolve_slots))

    def source_expected(self, source, position):
        self.raise_failure()
        try:
            return self._source_expected(source, position)
        except Exception as error:
            self.failure = error
            raise

    def _source_expected(self, source, position):
        # BpuAgent's normal ReadyValidMonitor snapshots S3 before the edge
        # and stamps its following acceptance. The independently checked TAGE
        # S2 post-edge frame is therefore two cycles before this timestamp.
        # A coherent PHR observation uses a different, explicit stream phase;
        # do not search for a convenient nearby frame with the same PC.
        matches = [(frame, wanted, bases, enabled) for tick, frame, wanted, enabled, bases in self.expected
                   if tick == source.meta_tick - 4]
        context = CheckContext(self.board.name, ScoreboardMode.DIRECT, sequence_id=source.meta_tick,
                               request=dict(point='public TAGE metadata from owned component state', position=position))
        self.board.check(expected=1, actual=len(matches), context=context)
        frame, wanted, bases, enabled = matches[0]
        if not enabled:
            raise ValueError('disabled TAGE source retains an old frame, not this request identity')
        self.board.check(expected=True, actual=frame is not None and wanted is not None, context=context)
        self.board.check(expected=source.prediction.start_pc, actual=frame.read.pc, context=context)
        slots = [slot for slot, base in enumerate(bases) if base.valid and frame.positions[slot] == position]
        self.board.check(expected=1, actual=len(slots), context=context)
        slot, = slots
        names = dict(hasProvider='has_provider', hasAlt='has_alt', useProvider='use_provider',
            providerTableIdx='table', providerWayIdx='way', providerTakenCtr_value='counter',
            providerUsefulCtr_value='useful', altOrBasePred='alternative', altConf='alt_conf')
        expected = {name: wanted[f'{slot}.{key}'] for name, key in names.items() if f'{slot}.{key}' in wanted}
        self.board.check(expected=expected, actual={key: source.meta.resolve['tage_entries'][slot][key]
                                                  for key in expected}, context=context)
        return expected
