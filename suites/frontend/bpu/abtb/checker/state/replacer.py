"""Compare all physical/shadow PLRU states without observed-state refill."""
from copy import deepcopy
from toffee import CheckContext
from toffee import Scoreboard
from toffee import ScoreboardMode
from suites.frontend.bpu.abtb.model.state.replacer import update
from suites.frontend.bpu.abtb.model.state.replacer import victim


class ReplacerChecker:
    def __init__(self, *, scope):
        self.scope = scope
        self.scoreboard = Scoreboard('abtb.replacer_state')
        self.expected = [[0] * 64 for _ in range(4)]
        self.records = []
        self.failure = None
        self.last_tick = None
        self.initialized = False

    def raise_failure(self):
        if self.failure is not None:
            raise self.failure

    def capture(self, observation):
        if self.failure is not None:
            return
        try:
            self.observe(observation)
        except Exception as error:
            self.failure = error

    def observe(self, observation):
        row, event = observation.value, observation.event
        self.records.append(dict(tick=event.tick, **deepcopy(row)))
        context = CheckContext(scoreboard=self.scoreboard.name, mode=ScoreboardMode.DIRECT,
            sequence_id=len(self.records), request=dict(scope=self.scope,
                ports=[{k: v for k, v in port.items() if k not in ('states', 'shadow')}
                       for port in row['banks']]), observed_event=event)
        check = lambda exp, actual: self.scoreboard.check(expected=exp, actual=actual, context=context)
        if self.last_tick is not None:
            check(self.last_tick + 2, event.tick)
        self.last_tick = event.tick
        if not self.initialized:
            check(1, row['reset'])
            self.initialized = True
        else:
            for bank, port in enumerate(row['banks']):
                check(tuple(self.expected[bank]), port['states'])
                check(tuple(self.expected[bank]), port['shadow'])
                check(victim(self.expected[bank][port['replace_set']]), port['victim'])
        self.expected = ([[0] * 64 for _ in range(4)] if row['reset'] else
                         [update(old, port) for old, port in zip(self.expected, row['banks'], strict=True)])

    def conflicts(self, *, bank, same_set):
        self.raise_failure()
        return [dict(tick=row['tick'], bank=bank, **row['banks'][bank])
                for row in self.records if row['banks'][bank]['read_valid']
                and row['banks'][bank]['write_valid']
                and ((row['banks'][bank]['read_set'] == row['banks'][bank]['write_set']) == same_set)]
