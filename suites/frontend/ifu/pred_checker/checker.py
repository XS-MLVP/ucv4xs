"""Independent ordered-lane oracle comparisons, qualified by redirect validity."""
from toffee import Scoreboard

from suites.frontend.ifu.model.pred_checker import LANES


def check_redirect(observed, expected):
    assert observed.valid == expected.valid, (
        f'PredChecker redirect valid: expected {expected.valid}, observed {observed.valid}')
    if expected.valid:
        Scoreboard('ifu.pred_checker.redirect').check(expected=expected, actual=observed)


def check_prediction(observed, expected, previous):
    assert observed.combinational_tick + 1 == observed.registered_tick, (
        'PredChecker stage1/stage2 samples must bracket the same rising edge')
    Scoreboard('ifu.pred_checker.fixed_instr_valid').check(
        expected=expected.fixed_instr_valid[:LANES], actual=observed.fixed_instr_valid)
    check_redirect(observed.previous_redirect, previous)
    check_redirect(observed.redirect, expected.redirect)
