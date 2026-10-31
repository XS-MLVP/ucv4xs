"""Model and env for L2TlbMissQueue (40-entry queue with flush)."""
from __future__ import annotations

from dataclasses import dataclass
from toffee import RisingEdge

CAPACITY = 40


@dataclass
class MQEntry:
    vpn: int
    s2xlate: int
    source: int
    is_llptw: int


class MQModel:
    def __init__(self) -> None:
        self.queue: list[MQEntry] = []

    def reset(self) -> None:
        self.queue.clear()

    @property
    def full(self) -> bool:
        return len(self.queue) == CAPACITY

    @property
    def empty(self) -> bool:
        return not self.queue

    def enqueue(self, entry: MQEntry) -> None:
        if not self.full:
            self.queue.append(entry)

    def dequeue(self) -> MQEntry | None:
        return self.queue.pop(0) if self.queue else None

    def flush(self) -> None:
        self.queue.clear()


class MQEnv:
    def __init__(self, dut, coverage=None) -> None:
        self.dut = dut
        self.coverage = coverage
        self.model = MQModel()
        self.tick = 0
        d = dut
        self.in_ready = d.io_in_ready
        self.in_valid = d.io_in_valid
        self.in_vpn = d.io_in_bits_req_info_vpn
        self.in_s2 = d.io_in_bits_req_info_s2xlate
        self.in_source = d.io_in_bits_req_info_source
        self.in_llptw = d.io_in_bits_isLLptw
        self.out_ready = d.io_out_ready
        self.out_valid = d.io_out_valid
        self.out_vpn = d.io_out_bits_req_info_vpn
        self.out_s2 = d.io_out_bits_req_info_s2xlate
        self.out_source = d.io_out_bits_req_info_source
        self.out_hptw = d.io_out_bits_isHptwReq
        self.out_llptw = d.io_out_bits_isLLptw
        self.out_hptwid = d.io_out_bits_hptwId
        self.sfence = d.io_sfence_valid
        self.csr_changed = [d.io_csr_satp_changed, d.io_csr_vsatp_changed,
                            d.io_csr_hgatp_changed, d.io_csr_priv_virt_changed]

    async def edge(self) -> None:
        await RisingEdge(self.dut.clock)
        self.tick += 1

    def read(self, signal) -> int:
        return int(signal.value)

    def _drive_in(self, valid: int, entry: MQEntry | None = None) -> None:
        self.in_valid.Set(valid)
        if entry is not None:
            self.in_vpn.Set(entry.vpn)
            self.in_s2.Set(entry.s2xlate)
            self.in_source.Set(entry.source)
            self.in_llptw.Set(entry.is_llptw)
        self.dut.RefreshComb()

    def _drive_flush(self, value: int) -> None:
        self.sfence.Set(value)
        for signal in self.csr_changed:
            signal.Set(0)
        self.dut.RefreshComb()

    async def reset(self) -> None:
        self._drive_in(0)
        self.out_ready.Set(0)
        self._drive_flush(0)
        self.dut.reset.Set(1)
        await self.edge()
        await self.edge()
        self.dut.reset.Set(0)
        self.model.reset()
        await self.edge()
        assert self.read(self.in_ready) == 1
        assert self.read(self.out_valid) == 0

    async def enqueue(self, entry: MQEntry, note: str = "") -> None:
        assert self.read(self.in_ready) == 1, f"{note}: queue must be ready"
        self._drive_in(1, entry)
        await self.edge()
        self._drive_in(0)
        self.model.enqueue(entry)
        if self.coverage is not None:
            self.coverage.sample_enqueue(entry, len(self.model.queue))
        await self.edge()

    async def dequeue(self, note: str = "", expect=None) -> MQEntry:
        assert self.read(self.out_valid) == 1, f"{note}: queue must not be empty"
        entry = MQEntry(
            self.read(self.out_vpn), self.read(self.out_s2),
            self.read(self.out_source), self.read(self.out_llptw),
        )
        assert self.read(self.out_hptw) == 0
        assert self.read(self.out_hptwid) == 0
        if expect is not None:
            assert entry == expect, f"{note}: {entry} != {expect}"
        self.out_ready.Set(1)
        await self.edge()
        self.out_ready.Set(0)
        self.model.dequeue()
        if self.coverage is not None:
            self.coverage.sample_dequeue(entry)
        return entry

    async def flush(self) -> None:
        self._drive_flush(1)
        await self.edge()
        self.model.flush()
        self._drive_flush(0)
        if self.coverage is not None:
            self.coverage.sample_flush()
        await self.edge()
        assert self.read(self.out_valid) == 0
