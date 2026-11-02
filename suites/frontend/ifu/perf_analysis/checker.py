"""Reason comparisons shared by the agent and independently injected controls."""
from toffee import Scoreboard

from suites.frontend.ifu.model.perf import WIDTH


def check_reasons(observed, expected, *, note='PerfAnalysis'):
    for name, value in (('observation', observed), ('expectation', expected)):
        if not isinstance(value, int) or not 0 <= value < (1 << WIDTH):
            raise TypeError(f'PerfAnalysis {name} must be a complete unsigned{WIDTH}-bit snapshot')
    Scoreboard(note).check(expected=expected, actual=observed)
