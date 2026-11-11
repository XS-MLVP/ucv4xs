"""Immutable frame and complete before/after action snapshots."""
from dataclasses import dataclass

from suites.frontend.ifu.testbenches.frontend_trigger.model.trigger import Inputs
from suites.frontend.ifu.testbenches.frontend_trigger.model.trigger import LANES


@dataclass(frozen=True)
class Frame:
    inputs: Inputs = Inputs()
    reset: int = 0

    def __post_init__(self):
        if not isinstance(self.inputs, Inputs):
            raise TypeError('FrontendTrigger frame requires semantic Inputs')
        if not isinstance(self.reset, int) or self.reset not in (0, 1):
            raise ValueError('reset must be a boolean encoding')


@dataclass(frozen=True)
class Actions:
    actions: tuple[int, ...]

    def __post_init__(self):
        if not isinstance(self.actions, (list, tuple)) or len(self.actions) != LANES:
            raise ValueError('action snapshot must contain exactly36 lanes')
        if any(not isinstance(value, int) or not 0 <= value < 16 for value in self.actions):
            raise ValueError('each action must be an unsigned4-bit integer')
        object.__setattr__(self, 'actions', tuple(self.actions))


@dataclass(frozen=True)
class CheckedCycle:
    sequence: int
    before_tick: int
    after_tick: int
    before: Actions
    after: Actions
