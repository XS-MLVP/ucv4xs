"""MicroRAS semantics: compose in-flight stack operations in age order.

This is an abstract stack, not a mirror of the DUT's push/pop registers or
priority muxes. Only the current main-RAS top is known: returning below it
makes the prediction unknown, whereas a subsequent call establishes a known
top again. Main-RAS state is a public input to this standalone UT.

All addresses are 50-bit guarded halfword addresses. Calls return after the
instruction at fetch-block-aligned PC plus its halfword position.
"""
from suites.frontend.bpu.models.configuration import *

from dataclasses import dataclass
from enum import IntEnum

from suites.frontend.bpu.uras.transaction.types import UrasResult


ADDRESS_BITS = 50


class Action(IntEnum):
    NEUTRAL = 0
    RETURN = 1
    CALL = 2
    RETURN_AND_CALL = 3


@dataclass(frozen=True, slots=True)
class Operation:
    action: Action = Action.NEUTRAL
    pc: int = 0
    position: int = 0

    def __post_init__(self):
        if not isinstance(self.action, Action):
            raise TypeError('operation action must be a semantic Action')
        _unsigned(self.pc, ADDRESS_BITS, 'operation PC')
        _unsigned(self.position, (POSITIONS-1).bit_length(), 'CFI position')

    @property
    def return_address(self):
        return ((self.pc // ALIGN_HALFWORDS) * ALIGN_HALFWORDS + self.position + 1) % (1 << ADDRESS_BITS)


@dataclass(frozen=True, slots=True)
class RasEvents:
    """One hardware-consumption boundary, independent of simulator phases.

    accept=None is no accepted prediction, distinct from accepting NEUTRAL.
    A pending correction replaces younger speculation; a retiring correction
    discards the entire younger window. Advance moves the pending operation
    to the older window, while retire releases an older operation without
    moving the younger one. Both may occur on the same boundary.
    """
    main_top: int = 0
    accept: Operation | None = None
    correct_pending: Operation | None = None
    correct_retiring: Operation | None = None
    advance: bool = False
    retire: bool = False
    redirect: bool = False
    reset: bool = False
    enabled: bool = True

    def __post_init__(self):
        _unsigned(self.main_top, ADDRESS_BITS, 'main-RAS top')
        for name in ('accept', 'correct_pending', 'correct_retiring'):
            value = getattr(self, name)
            if value is not None and not isinstance(value, Operation):
                raise TypeError(f'{name} must be an Operation or None')
        for name in ('advance', 'retire', 'redirect', 'reset', 'enabled'):
            if type(getattr(self, name)) is not bool:
                raise TypeError(f'{name} must be Boolean')


def _unsigned(value, width, name):
    if type(value) is not int or not 0 <= value < (1 << width):
        raise ValueError(f'{name} must fit {width} unsigned bits')


def stack_top(main_top, operations, *, trusted=True):
    """Reduce older→younger operations using push/pop, with unknown depth.

    No register flags, DUT targets or table of RTL branch combinations enter
    this calculation. A coroutine is a pop followed by a push, not a no-op.
    """
    stack = [main_top] if trusted else []
    for operation in operations:
        if operation is None:
            continue
        if operation.action in (Action.RETURN, Action.RETURN_AND_CALL) and stack:
            stack.pop()
        if operation.action in (Action.CALL, Action.RETURN_AND_CALL):
            stack.append(operation.return_address)
    return UrasResult(1, stack[-1]) if stack else UrasResult(0, 0)


class UrasReference:
    def __init__(self):
        self.reset()

    def reset(self):
        self.younger = None
        self.older = None
        self.main_trusted = True
        self.result = UrasResult(0, 0)

    def advance(self, events: RasEvents):
        if not isinstance(events, RasEvents):
            raise TypeError('reference input must be RasEvents')
        if events.reset:
            self.reset()
            return self.result

        # Corrections choose the authoritative operation window. The actual
        # prediction is then obtained by the same stack reduction for every
        # case, not by reproducing each RTL output priority branch.
        if events.redirect:
            self.result = UrasResult(0, 0)
        elif events.correct_retiring is not None:
            self.result = stack_top(events.main_top, (events.correct_retiring,))
        elif events.correct_pending is not None:
            self.result = stack_top(events.main_top, (self.older, events.correct_pending),
                                    trusted=self.main_trusted)
        elif events.accept is not None:
            self.result = stack_top(events.main_top, (self.older, self.younger, events.accept),
                                    trusted=self.main_trusted)

        if events.redirect or events.correct_retiring is not None:
            self.younger = self.older = None
        else:
            previous_younger = self.younger
            if events.advance:
                self.older = (events.correct_pending if events.correct_pending is not None
                              else previous_younger)
            elif events.retire:
                self.older = None
            if events.correct_pending is not None:
                self.younger = None if events.advance else events.correct_pending
            elif events.accept is not None:
                self.younger = events.accept
            elif events.advance:
                self.younger = None

        # After one consumption boundary the main RAS has recovered. Calls
        # can yield a known top during the bubble; an untrusted main top alone
        # cannot. A retiring correction supplies authoritative recovery data.
        self.main_trusted = not events.redirect
        # A disabled MicroRAS must not expose a usable return target. The
        # internal pending windows may still advance (that policy is separate),
        # but the public result is qualified by the current enable only.
        if not events.enabled:
            self.result = UrasResult(0, 0)
        return self.result

    def state(self):
        return dict(older=self.older, younger=self.younger,
                    main_trusted=self.main_trusted, result=self.result)
