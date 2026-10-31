"""Declared instruction records plus existing full-field semantic comparison."""
from toffee import CheckContext, Scoreboard, ScoreboardMode
from suites.frontend.bpu.mbtb.checker.semantic import prediction_values

class Checks:

    def __init__(self, program):
        self.program = program
        self.phase = 'old execution'
        self.board = Scoreboard('mbtb' + '.query-reset-lifetime')

    def check(self, expected, actual, point):
        self.board.check(expected=expected, actual=actual, context=CheckContext(self.board.name, ScoreboardMode.DIRECT, request=dict(program=self.program.state(), phase=self.phase, point=point)))

    def prediction(self, actual, pc, branches):
        records = [b for b in branches if b.pc == pc]
        self.check(sorted(((b.position, b.target, b.kind, b.action, 1) for b in records)), sorted(((e.position, e.target, e.branch_type, e.ras_action, e.taken) for e in actual.entries if e.valid)), 'all declared instructions, no resurrected or mixed sibling')
        if not records:
            self.check(0, sum((s['rawHit'] for row in actual.meta_entries for s in row)), 'no hidden old raw source after reset')

    def old_response(self, expected, actual):
        wanted, observed = prediction_values(expected, actual)
        self.check(wanted, observed, 'all defined fields from exact old source snapshot')
        self.prediction(actual, self.program.old[0].pc, self.program.old)
