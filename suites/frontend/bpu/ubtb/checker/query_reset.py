"""Declared instruction records plus existing full-field semantic comparison."""
from toffee import CheckContext, Scoreboard, ScoreboardMode
from suites.frontend.bpu.ubtb.checker.semantic import prediction_value
from suites.frontend.bpu.ubtb.transaction.types import UbtbPrediction

class Checks:

    def __init__(self, program):
        self.program = program
        self.phase = 'old execution'
        self.board = Scoreboard('ubtb' + '.query-reset-lifetime')

    def check(self, expected, actual, point):
        self.board.check(expected=expected, actual=actual, context=CheckContext(self.board.name, ScoreboardMode.DIRECT, request=dict(program=self.program.state(), phase=self.phase, point=point)))

    def prediction(self, actual, pc, branches):
        records = [b for b in branches if b.pc == pc]
        self.check(True, len(records) <= 1, 'MicroBTB returns one instruction record')
        expected = dict(valid=0) if not records else prediction_value(UbtbPrediction(1, 1, records[0].target, records[0].position, records[0].kind, records[0].action))
        self.check(expected, prediction_value(actual), 'complete old/new instruction payload')

    def old_response(self, expected, actual):
        self.check(prediction_value(expected), prediction_value(actual), 'exact old semantic response')
        self.prediction(actual, self.program.old[0].pc, self.program.old)
