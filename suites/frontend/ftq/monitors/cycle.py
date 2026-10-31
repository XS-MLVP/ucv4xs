"""Passive monitors: decode public output pins at every rising edge."""

from __future__ import annotations

from collections import deque
from typing import Any
from typing import Callable
from typing import Generic
from typing import TypeVar

from suites.frontend.ftq.harness import Dut

T = TypeVar("T")


class Monitor(Generic[T]):
    def __init__(self, name: str) -> None:
        if not name:
            raise ValueError("monitor needs a name")
        self.name = name

    def observe(self, dut: Dut) -> None:
        raise NotImplementedError


class EdgeMonitor(Monitor[T]):
    """Sample once per edge; keep the latest and a bounded history."""

    def __init__(self, name: str, sample: Callable[[Dut], T | None], *, history: int = 256) -> None:
        super().__init__(name)
        self.sample_fn = sample
        self.history: deque[T] = deque(maxlen=history)
        self.latest: T | None = None

    def sample(self, dut: Dut) -> T | None:
        return self.sample_fn(dut)

    def observe(self, dut: Dut) -> None:
        value = self.sample(dut)
        if value is None:
            return
        self.latest = value
        self.history.append(value)

    def take(self) -> T | None:
        value = self.latest
        self.latest = None
        return value

    def clear(self) -> None:
        self.latest = None
        self.history.clear()


class InvariantMonitor(Monitor[None]):
    """Run a design-contract predicate every edge; never produce credit."""

    def __init__(self, name: str, check: Callable[[Dut], None]) -> None:
        super().__init__(name)
        self.check = check

    def observe(self, dut: Dut) -> None:
        self.check(dut)
