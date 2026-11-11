"""Typed cycle observations for the VTypeGen agent."""

from __future__ import annotations

from dataclasses import dataclass

from suites.frontend.ibuffer.testbenches.vtype_gen.model import Inputs
from suites.frontend.ibuffer.testbenches.vtype_gen.model import Outputs


@dataclass(frozen=True)
class CheckedCycle:
    index: int
    before_tick: int
    after_tick: int
    inputs: Inputs
    before: Outputs
    after: Outputs
    expected_before: Outputs
    expected_after: Outputs
