"""SbufferData commands and frozen observations, including invalid-payload controls."""
from dataclasses import dataclass

from suites.memblock.sbuffer.testbenches.sbuffer_data.model import WriteRequest


@dataclass(frozen=True)
class Op:
    writes: tuple[WriteRequest, ...] = ()
    flush: int | None = None
    ports: tuple[int, ...] | None = None

    def active(self):
        ports = self.ports if self.ports is not None else tuple(range(len(self.writes)))
        if len(ports) != len(self.writes):
            raise ValueError('ports and writes length differ')
        if ports != tuple(sorted(set(ports))) or any(port not in (0, 1) for port in ports):
            raise ValueError('write ports must be unique, increasing and in [0, 1]')
        return tuple(zip(ports, self.writes, strict=True))


@dataclass(frozen=True)
class Frame:
    op: Op = Op()
    reset: bool = False
    writes_valid: bool = True
    flush_valid: bool = True


@dataclass(frozen=True)
class Snapshot:
    masks: tuple[tuple[int, ...], ...]
    data: tuple[tuple[tuple[int, ...], ...], ...]
