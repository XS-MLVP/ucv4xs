"""Bounded condition waits using Reactor triggers, with sampled diagnostics."""
from dataclasses import dataclass
from typing import Any

from toffee import AnyOf, PythonPredicateTrigger, RisingEdge, SimTimeout, XEventKind

RESET_TIMEOUT_CYCLES = 1024


@dataclass(frozen=True)
class ConditionResult:
    tick: int
    samples: int
    state: Any


async def wait_condition(clock, *, sample, satisfied, name, timeout_cycles):
    """Timeout is a failure budget, never a required settling delay.

    Always sample after registration: already-idle live signals must not let a
    pending rise-write launch escape observation. Return the sampled state,
    not a later live re-read. Trigger cancellation is owned by Reactor.
    """
    if type(timeout_cycles) is not int or timeout_cycles <= 0:
        raise ValueError('condition timeout_cycles must be a positive integer')
    state, samples, failure = None, 0, None

    def predicate():
        nonlocal state, samples, failure
        if failure is not None:
            return True
        try:
            state = sample()
            samples += 1
            return bool(satisfied(state))
        except Exception as error:
            # Predicate callbacks execute inside the simulation pump. Wake
            # the awaiting task and raise there, not out of backend.run_until.
            failure = error
            return True

    event = await AnyOf(
        PythonPredicateTrigger(name, predicate, sample=RisingEdge(clock), mode='each_sample'),
        SimTimeout(timeout_cycles, clock=clock),
    )
    if failure is not None:
        raise failure
    if event.kind is XEventKind.TIMEOUT:
        raise TimeoutError(f'{name}: no completion within {timeout_cycles} cycles; '
                           f'tick={event.tick}, samples={samples}, last_state={state!r}')
    return ConditionResult(event.tick, samples, state)


async def wait_reset_done(status, *, timeout_cycles=RESET_TIMEOUT_CYCLES):
    def sample():
        snapshot = status.bits.sample()
        return dict(reset_done=snapshot.reset_done.as_int(),
                    train_ready=snapshot.train_ready.as_int())
    return await wait_condition(status.clock, sample=sample,
        satisfied=lambda state: state['reset_done'] == 1,
        name=status.name + '.reset_done', timeout_cycles=timeout_cycles)
