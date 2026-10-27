"""Direct program comparison, independent of monitor timing and decoding."""
from toffee import CheckContext,Scoreboard,ScoreboardMode


class CommitActionChecks:
    def __init__(self,program):
        self.program=program
        self.board=Scoreboard('ras.original-commit-action')

    def check(self,expected,actual,point):
        self.board.check(expected=expected,actual=actual,context=CheckContext(self.board.name,
            ScoreboardMode.DIRECT,request=dict(point=point,program=self.program.state())))
