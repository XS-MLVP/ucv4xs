"""OrderedPermitCtrl comparisons over immutable domain observations."""
from toffee import CheckContext, Scoreboard, ScoreboardMode


class Checker:
    def __init__(self):
        self.board = Scoreboard('ordered-permit.outputs')
        self.cycles = 0

    def compare(self, expected, actual, *, phase, beat):
        self.board.check(
            expected=expected.ordered_can_proceed,
            actual=actual.ordered_can_proceed,
            context=CheckContext(
                self.board.name, ScoreboardMode.DIRECT,
                sequence_id=self.cycles,
                request={'phase': phase, 'beat': beat},
            ),
        )

    def complete(self):
        self.cycles += 1
