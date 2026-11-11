"""Typed cycle observations for the InstrUncacheEntry agent."""

from __future__ import annotations

from dataclasses import dataclass

from suites.frontend.instr_uncache.testbenches.instr_uncache_entry.model import Inputs
from suites.frontend.instr_uncache.testbenches.instr_uncache_entry.model import Outputs


@dataclass(frozen=True)
class Events:
    req_fire: int
    acquire_fire: int
    grant_fire: int
    resp_fire: int


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
    state_before: str
    state_after: str
