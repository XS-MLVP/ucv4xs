"""SplitCtrl checks valid payloads and valid feedback only."""
from toffee import CheckContext, Scoreboard, ScoreboardMode


class Checker:
    def __init__(self):
        self.board = Scoreboard('split.outputs')
        self.cycles = 0

    @staticmethod
    def _normalize(value):
        lsu, empty, updates, excp = value.lsu, value.empty, value.update, value.excp
        return (
            lsu,
            empty,
            tuple(u if u.valid else (False, 0, 0) for u in updates),
            excp if excp.valid else (False, 0, 0),
        )

    def compare(self, expected, actual, *, phase, beat):
        self.board.check(
            expected=self._normalize(expected), actual=self._normalize(actual),
            context=CheckContext(self.board.name, ScoreboardMode.DIRECT,
                                 sequence_id=self.cycles, request={'phase': phase, 'beat': beat}),
        )

    def complete(self):
        self.cycles += 1
