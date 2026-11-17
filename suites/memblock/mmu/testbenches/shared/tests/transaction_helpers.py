"""Fake scalar signals shared by MMU offline transaction self-checks."""
from __future__ import annotations

from types import SimpleNamespace


READY_CASES = ((1, 1), (1, 0), (0, 1), (0, 0))


class Signal:
    def __init__(self, value: int = 0) -> None:
        self.value = value

    def Set(self, value: int) -> None:
        self.value = value


def _dut() -> SimpleNamespace:
    return SimpleNamespace(RefreshComb=lambda: None)


def _install_ready_cycle(env, signal, before: int, after: int,
                         fires: list[bool]) -> None:
    async def edge() -> None:
        fires.append(bool(signal.value and env.req_ready.value))
        signal.value = after

    env.edge = edge
    env.req_ready.value = before
