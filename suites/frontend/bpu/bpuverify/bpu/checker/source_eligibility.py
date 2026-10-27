"""Compare environment guarantees without granting predictor PASS credit."""
from toffee import CheckContext,Scoreboard,ScoreboardMode


class EligibilityChecks:
    def __init__(self,program):
        self.program=program;self.board=Scoreboard('environment.original-source-lifetime')

    def check(self,expected,actual,point,*,state=None):
        self.board.check(expected=expected,actual=actual,context=CheckContext(self.board.name,
            ScoreboardMode.DIRECT,request=dict(point=point,program=self.program.state(),state=state)))

    def summary(self):
        status=self.board.status
        return dict(checked=status.checked,passed=status.passed,failed=status.failed)
