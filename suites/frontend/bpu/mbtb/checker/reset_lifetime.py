"""Public result obligations; actual fields never seed expected state."""
from toffee import CheckContext, Scoreboard, ScoreboardMode


class Checks:
    def __init__(self, program):
        self.program, self.phase = program, 'preparation'
        self.board = Scoreboard('mbtb.reset-instruction-lifetime')

    def check(self, expected, actual, point):
        self.board.check(expected=expected, actual=actual,
            context=CheckContext(self.board.name, ScoreboardMode.DIRECT,
                request=dict(program=self.program.state(), phase=self.phase, point=point)))

    def cold(self, prediction):
        self.check((0, 0), (sum(e.valid for e in prediction.entries),
            sum(source['rawHit'] for row in prediction.meta_entries for source in row)),
            'old instruction has no visible or raw resident after reset')

    def resident(self, prediction, branch, *, counter=None):
        matches = [e for e in prediction.entries if e.valid and e.position == branch.position]
        self.check(1, len(matches), 'exactly one logical branch at the expected instruction')
        entry = matches[0]
        self.check((branch.target, branch.kind, 0), (entry.target, entry.branch_type, entry.ras_action),
                   'complete payload belongs to this old/new instruction lifetime')
        if counter is not None:
            matches = [s for row in prediction.meta_entries for s in row
                       if s['rawHit'] and s['position'] == branch.position]
            self.check(1, len(matches), 'one owned direction source')
            self.check(counter, matches[0]['counter_value'], 'direction has correct lifetime and learning state')
            self.check(int(counter >= 2), entry.taken, 'public direction matches new learning')
