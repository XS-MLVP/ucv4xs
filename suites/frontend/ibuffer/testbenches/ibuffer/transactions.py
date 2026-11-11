"""Typed cycle observations for the IBuffer top-level agent."""

from __future__ import annotations

from dataclasses import dataclass

from suites.frontend.ibuffer.testbenches.ibuffer.model import Events
from suites.frontend.ibuffer.testbenches.ibuffer.model import Inputs
from suites.frontend.ibuffer.testbenches.ibuffer.model import Outputs


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
    events: Events
    state_before: dict[str, object]
    state_after: dict[str, object]
