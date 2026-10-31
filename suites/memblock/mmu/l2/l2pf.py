"""Model and env for L2TlbPrefetch."""
from __future__ import annotations

from dataclasses import dataclass
from toffee import RisingEdge

HISTORY = 4


def next_line(vpn: int) -> int:
    return (((vpn >> 3) + 1) & ((1 << 35) - 1)) << 3


def s2_class(virt: int, vsatp_mode: int, hgatp_mode: int) -> int:
    if virt and vsatp_mode and hgatp_mode:
        return 3
    if virt and vsatp_mode:
        return 1
    return 2 if (virt and hgatp_mode) else 0


@dataclass
class PFOut:
    valid: int
    vpn: int
    s2xlate: int


class PFModel:
    def __init__(self) -> None:
        self.valid = 0
        self.next_req = 0
        self.history: list[int | None] = [None] * HISTORY
        self.old_index = 0

    def reset(self) -> None:
        self.valid = 0
        self.next_req = 0
        self.history = [None] * HISTORY
        self.old_index = 0

    def _suppressed(self, candidate: int) -> bool:
        return any(value is not None and value == candidate for value in self.history)

    def step(self, in_valid: int, in_vpn: int, out_ready: int, flush: bool) -> None:
        consume = bool(out_ready and self.valid)
        if flush:
            self.valid = 0
            self.history = [None] * HISTORY
            self.old_index = 0
            return
        incoming_suppressed = False
        if in_valid:
            incoming = next_line(in_vpn)
            incoming_suppressed = self._suppressed(incoming)
        if consume:
            self.history[self.old_index] = self.next_req
            self.old_index = (self.old_index + 1) % HISTORY
        if in_valid:
            self.next_req = next_line(in_vpn)
            if not incoming_suppressed:
                self.valid = 1
        if consume and not in_valid:
            self.valid = 0


class PFEnv:
    def __init__(self, dut, coverage=None) -> None:
        self.dut = dut
        self.coverage = coverage
        self.model = PFModel()
        self.tick = 0
        d = dut
        self.in_valid = d.io_in_valid
        self.in_vpn = d.io_in_bits_vpn
        self.out_ready = d.io_out_ready
        self.out_valid = d.io_out_valid
        self.out_vpn = d.io_out_bits_req_info_vpn
        self.out_s2 = d.io_out_bits_req_info_s2xlate
        self.sfence = d.io_sfence_valid
        self.csr = dict(
            satp_changed=d.io_csr_satp_changed,
            vsatp_mode=d.io_csr_vsatp_mode,
            vsatp_changed=d.io_csr_vsatp_changed,
            hgatp_mode=d.io_csr_hgatp_mode,
            hgatp_changed=d.io_csr_hgatp_changed,
            virt=d.io_csr_priv_virt,
            virt_changed=d.io_csr_priv_virt_changed,
        )

    async def edge(self) -> None:
        await RisingEdge(self.dut.clock)
        self.tick += 1

    def read(self, signal) -> int:
        return int(signal.value)

    def set_context(self, virt: int = 0, vsatp_mode: int = 0, hgatp_mode: int = 0) -> None:
        for signal in self.csr.values():
            signal.Set(0)
        self.csr["virt"].Set(virt)
        self.csr["vsatp_mode"].Set(vsatp_mode)
        self.csr["hgatp_mode"].Set(hgatp_mode)
        self.dut.RefreshComb()

    async def reset(self) -> None:
        self.in_valid.Set(0)
        self.out_ready.Set(1)
        self.sfence.Set(0)
        for signal in self.csr.values():
            signal.Set(0)
        self.dut.reset.Set(1)
        await self.edge()
        await self.edge()
        self.dut.reset.Set(0)
        self.model.reset()
        await self.edge()
        assert self.read(self.out_valid) == 0

    async def cycle(self, in_valid: int = 0, in_vpn: int = 0, out_ready: int = 1,
                    flush: int = 0) -> None:
        flush = int(flush or self.read(self.sfence))
        self.in_valid.Set(in_valid)
        self.in_vpn.Set(in_vpn)
        self.out_ready.Set(out_ready)
        self.sfence.Set(flush)
        self.dut.RefreshComb()
        consumed = bool(self.read(self.out_valid) and out_ready)
        candidate = next_line(in_vpn)
        suppressed = bool(in_valid and self.model._suppressed(candidate))
        self.model.step(in_valid, in_vpn, out_ready, bool(flush))
        await self.edge()
        assert self.read(self.out_valid) == self.model.valid
        if self.model.valid:
            assert self.read(self.out_vpn) == self.model.next_req
            assert self.read(self.out_s2) == s2_class(
                self.read(self.csr["virt"]),
                self.read(self.csr["vsatp_mode"]),
                self.read(self.csr["hgatp_mode"]),
            )
        if self.coverage is not None:
            stage = s2_class(self.read(self.csr["virt"]),
                             self.read(self.csr["vsatp_mode"]), self.read(self.csr["hgatp_mode"]))
            if flush:
                self.coverage.sample_event("flush", stage)
            else:
                if consumed:
                    self.coverage.sample_event("consume", stage)
                if in_valid:
                    self.coverage.sample_event("suppressed" if suppressed else "issue", stage,
                                               "wrap" if candidate == 0 else "normal")
