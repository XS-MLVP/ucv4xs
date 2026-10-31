"""Source-lifetime and discriminating consumers for signed-weight bounds."""
from copy import deepcopy

from toffee import CheckContext, Scoreboard, ScoreboardMode

from suites.frontend.bpu.sc.model.boundary import FAMILY_FIELDS, META_FIELDS
from suites.frontend.bpu.sc.transaction.types import ScLookup


class ScBoundaryChecks:
    def __init__(self, program):
        self.program = program
        self.board = Scoreboard('sc.weight-boundary')
        self.sources = {}
        self.spent = set()

    def check(self, expected, actual, *, request=None):
        self.board.check(expected=expected, actual=actual,
            context=CheckContext(self.board.name, ScoreboardMode.DIRECT,
                request=dict(program=self.program, detail=request,
                    source_ids=tuple(self.sources), consumed_ids=tuple(sorted(self.spent)))))

    def prediction(self, expected, actual, *, state):
        observed = dict(takens=actual.takens, useds=actual.useds,
            meta={key: tuple(actual.meta[key]) for key in META_FIELDS},
            families={key: tuple(actual.meta['debug'][key]) for key in FAMILY_FIELDS})
        self.check(expected, observed, request=state)

    def source(self, transfer, actual, expected, *, state):
        self.check(True, transfer.sequence_id not in self.sources, request='unique source identity')
        self.check(ScLookup(self.program.pc, 0, 0, branches=self.program.layout),
                   transfer.request, request='original lookup owns source')
        self.check(True, transfer.accepted_event is not None and transfer.completed_event is not None
                   and transfer.accepted_event.tick < transfer.completed_event.tick,
                   request='actual acceptance and response precede feedback')
        self.prediction(expected, actual, state=state)
        self.sources[transfer.sequence_id] = dict(prediction=actual,
            frozen=deepcopy(actual.meta), expected=deepcopy(expected['meta']),
            accepted=transfer.accepted_event.tick, completed=transfer.completed_event.tick)
        return transfer.sequence_id

    def feedback(self, source_id, *, reverse=False):
        self.check(True, source_id in self.sources, request='feedback requires a published source')
        self.check(False, source_id in self.spent, request='one feedback per prediction lifetime')
        source = self.sources[source_id]
        self.check(source['frozen'], source['prediction'].meta, request='original metadata immutable')
        self.spent.add(source_id)
        return (self.program.feedback(deepcopy(source['frozen']), reverse=reverse),
                self.program.feedback(deepcopy(source['expected']), reverse=reverse))

    def finish(self):
        self.check(set(self.sources), self.spent, request='every designated source consumed exactly once')
        for source_id, source in self.sources.items():
            self.check(source['frozen'], source['prediction'].meta,
                       request=dict(source_id=source_id, obligation='original source survives later learning'))

    def accepted(self, source_id, tick):
        self.check(True, source_id in self.sources and source_id in self.spent,
                   request='accepted feedback has a designated source')
        self.check(True, self.sources[source_id]['completed'] < tick,
                   request=dict(source_id=source_id, feedback_tick=tick,
                                obligation='response must precede its feedback'))
