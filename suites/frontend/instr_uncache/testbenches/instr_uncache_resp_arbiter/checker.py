"""Independent checker for the one-input response arbiter."""

from __future__ import annotations

from toffee import Scoreboard

from suites.frontend.instr_uncache.testbenches.instr_uncache_resp_arbiter.model import Inputs
from suites.frontend.instr_uncache.testbenches.instr_uncache_resp_arbiter.model import Outputs
from suites.frontend.instr_uncache.testbenches.instr_uncache_resp_arbiter.model import arbiter_outputs


def check_outputs(expected: Outputs, observed: Outputs, *, phase: str = "evaluate") -> None:
    if not isinstance(expected, Outputs) or not isinstance(observed, Outputs):
        raise TypeError("resp arbiter checker requires complete semantic snapshots")
    Scoreboard(f"instr_uncache_resp_arbiter.{phase}").check(
        expected=expected.as_dict(), actual=observed.as_dict())


def check_identity(inputs: Inputs, observed: Outputs) -> None:
    """The 1:1 wiring obligation, stated independently of Scoreboard formatting."""
    expected = arbiter_outputs(inputs)
    assert observed == expected, (
        f"arbiter identity violated: expected {expected.as_dict()}, "
        f"actual {observed.as_dict()}")
