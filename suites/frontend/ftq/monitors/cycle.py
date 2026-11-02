"""Passive decoder views of the SDK's lossless complete-cycle stream.

Views own no clock subscription. Dut's two SamplingMonitors freeze every
channel first, then publish the checked snapshots to these non-consuming
caches. A bounded history is only a display window, not the lossless queue.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Mapping
from dataclasses import dataclass, fields, is_dataclass, replace
from types import MappingProxyType
from typing import Any
from typing import Callable
from typing import Generic
from typing import TypeVar

from typing import TYPE_CHECKING

from toffee import SamplingMonitor

if TYPE_CHECKING:
    from suites.frontend.ftq.harness import Dut

T = TypeVar("T")


def freeze(value):
    """Detach nested metadata/maps without retaining a signal or native view."""
    if is_dataclass(value) and not isinstance(value, type):
        if not value.__dataclass_params__.frozen:
            raise TypeError('FTQ decoder returned a mutable dataclass')
        return replace(value, **{field.name: freeze(getattr(value, field.name)) for field in fields(value)})
    if isinstance(value, Mapping):
        return MappingProxyType({key: freeze(item) for key, item in value.items()})
    if isinstance(value, (tuple, list)):
        return tuple(freeze(item) for item in value)
    if value is None or type(value) in (int, bool, str):
        return value
    raise TypeError(f'FTQ decoder returned a non-snapshot {type(value).__name__}')


@dataclass(frozen=True, slots=True)
class CycleSnapshot:
    inputs: tuple[tuple[str, int], ...]
    observations: tuple[tuple[str, Any], ...]


@dataclass(frozen=True, slots=True)
class SampledCycle:
    before: Any  # SDK Transfer retaining its event, not a reconstructed tick.
    after: Any


class CycleMonitor(SamplingMonitor):
    """SDK delivery plus explicit lifecycle state for environment guards.

    No private SDK queues/watchers are inspected or replaced. The public
    start/aclose boundary lets live legacy observations reject early closure.
    """
    def __init__(self, trigger, *, capture):
        self.active = False
        super().__init__(trigger, capture=capture, delivery='lossless', capacity=64)

    def start(self, execution):
        super().start(execution)
        self.active = True
        return self

    async def aclose(self):
        try:
            await super().aclose()
        finally:
            self.active = False


class ObservationView(Generic[T]):
    def __init__(self, name: str) -> None:
        if not name:
            raise ValueError("monitor needs a name")
        self.name = name

    def sample(self, dut: Dut) -> T | None:
        raise NotImplementedError

    def record(self, value, event):
        pass


class EdgeMonitor(ObservationView[T]):
    """Compatibility name for a decoder plus checked latest/history view."""

    def __init__(self, name: str, sample: Callable[[Dut], T | None], *, history: int = 256) -> None:
        super().__init__(name)
        self.sample_fn = sample
        self.history: deque[T] = deque(maxlen=history)
        self.latest: T | None = None
        self.last_event = None

    def sample(self, dut: Dut) -> T | None:
        dut.check_sampling()
        return freeze(self.sample_fn(dut))

    def record(self, value, event) -> None:
        self.latest = value
        self.last_event = event
        if value is not None:
            self.history.append(value)

    def take(self) -> T | None:
        value = self.latest
        self.latest = None
        return value

    def clear(self) -> None:
        self.latest = None
        self.history.clear()


class InvariantMonitor(ObservationView[None]):
    """Run a design-contract predicate every edge; never produce credit."""

    def __init__(self, name: str, check: Callable[[Dut], None]) -> None:
        super().__init__(name)
        self.check = check

    def sample(self, dut: Dut) -> None:
        self.check(dut)
