"""Compare complete new-instruction payloads with useful failure context."""
from toffee import CheckContext, Scoreboard, ScoreboardMode
from bpuverify.ubtb.transaction.types import UbtbPrediction


def expected(branch):
    return UbtbPrediction(1, 1, branch.target, branch.position, branch.branch_type, branch.ras_action)


class Checks:
    def __init__(self, program):
        self.program = program
        self.board = Scoreboard('ubtb.reset-instruction-lifetime')

    def check(self, wanted, actual, point, *, phase):
        self.board.check(expected=wanted, actual=actual,
            context=CheckContext(self.board.name, ScoreboardMode.DIRECT,
                request=dict(program=self.program.state(), phase=phase, point=point)))
