"""Independent ITTAGE table model at an integrated component cut point.

Upstream PC/history/feedback routing is observed input, not independently
predicted whole-BPU behavior. Existing PHR checks remain a separate obligation.
"""
from collections import deque
from copy import deepcopy
from dataclasses import asdict, replace

from toffee import CheckContext, Scoreboard, ScoreboardMode

from suites.frontend.bpu.bpu.model.ittage import IttageContextModel, Entry as ContextEntry
from suites.frontend.bpu.ittage.checker.semantic import IttageSemanticChecker


def read_context(model, read):
    """Project only owned immutable read data and the pre-selection directory."""
    if read is None:
        return None
    result = IttageContextModel()
    for table, entry in enumerate(read.entries):
        if entry.valid and entry.tag == read.tags[table]:
            result.entries[table] = ContextEntry(model._decode(read.pc, entry.target) // 2,
                                               entry.confidence, entry.useful)
    return result


class IttageSemanticComponentChecker(IttageSemanticChecker):
    def __init__(self, *, audit=None):
        super().__init__()
        self.board = Scoreboard('bpu.ittage.semantic-component')
        self.selection = None
        self.frames = deque(maxlen=64)
        self.public_checks = 0
        self.audit = audit

    def capture_input(self, event, events):
        if events.reset:
            self.selection = None
        elif events.enabled and events.select:
            self.selection = read_context(self.model, self.model.read)
        super().capture_input(event, events)

    def capture_output(self, event, actual, *, visible, baseline):
        super().capture_output(event, actual, visible=visible)
        if self.failure is None and self.initialized:
            if self.audit is not None and not self.events.reset:
                try:
                    self.audit.raise_failure()
                    self.board.check(
                        expected=dict(tick=self.model.tick,
                            maintenance=[(int(busy),index) for busy,index in self.model.maintenance]),
                        actual=dict(tick=self.audit.counter,maintenance=self.audit.tables),
                        context=CheckContext(self.board.name,ScoreboardMode.DIRECT,
                            sequence_id=event.tick,request=dict(point='semantic timing versus checked hardware audit')))
                except Exception as error:
                    self.failure=error
                    return
            self.frames.append(dict(tick=event.tick, prediction=self.model.prediction,
                context=deepcopy(self.selection), visible=visible, baseline=baseline))

    def source_context(self, source):
        self.raise_failure()
        matches = [frame for frame in self.frames if frame['tick'] == source.meta_tick]
        context = CheckContext(self.board.name, ScoreboardMode.DIRECT,
                               sequence_id=source.meta_tick, request=dict(point='public source snapshot', pc=source.prediction.start_pc))
        self.board.check(expected=1, actual=len(matches), context=context)
        frame, = matches
        self.board.check(expected=True,
                         actual=bool(frame['visible'] and frame['prediction'] is not None and frame['context'] is not None),
                         context=context)
        self.board.check(expected=source.prediction.start_pc * 2,
                         actual=frame['prediction'].pc, context=context)
        self.public_checks += 1
        return deepcopy(frame['context']), frame['baseline']

    def summary(self):
        self.raise_failure()
        return dict(checks=asdict(replace(self.board.status, first_failure=None)),
            public_sources_checked=self.public_checks, commits=self.model.commits,
            global_tick=self.model.tick, maintenance=self.model.maintenance,
            model_state_seeded_from_DUT=False, full_BPU_reference_claimed=False,
            cycle_tick_and_maintenance_cross_checked=self.audit is not None,
            interface_scope='ITTAGE component PC/history/feedback inputs observed; table state independently owned')
