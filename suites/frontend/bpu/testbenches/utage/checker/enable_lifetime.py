"""Compare qualification lifetime obligations through the shared Scoreboard."""
from toffee import CheckContext, Scoreboard, ScoreboardMode


class EnableLifetimeChecks:
    def __init__(self, reference, program):
        self.reference, self.program = reference, program
        self.board = Scoreboard('utage.enable-learning-lifetime')

    def check(self, expected, actual, point):
        self.reference.raise_failure()
        self.board.check(expected=expected, actual=actual, context=CheckContext(
            self.board.name, ScoreboardMode.DIRECT,
            request=dict(point=point, program=self.program.state()),
            observed_event=self.reference.last_event))
