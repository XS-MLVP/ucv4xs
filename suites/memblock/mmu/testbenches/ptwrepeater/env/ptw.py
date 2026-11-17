"""Standalone ptwrepeater environment and port adaptation."""
from __future__ import annotations

from toffee import RisingEdge

from suites.memblock.mmu.testbenches.shared.env.execution import sweep_inputs


class RepeaterEnv:
    def __init__(self, dut, coverage=None) -> None:
        self.dut = dut
        self.coverage = coverage
        self.tick = 0
        d = dut
        self.req_ready = d.io_tlb_req_0_ready
        self.req_valid = d.io_tlb_req_0_valid
        self.req_vpn = d.io_tlb_req_0_bits_vpn
        self.req_s2 = d.io_tlb_req_0_bits_s2xlate
        self.resp_ready = d.io_tlb_resp_ready
        self.resp_valid = d.io_tlb_resp_valid
        self.resp_s2 = d.io_tlb_resp_bits_s2xlate
        self.resp_tag = d.io_tlb_resp_bits_s1_entry_tag
        self.resp_ppn = d.io_tlb_resp_bits_s1_entry_ppn
        self.ptw_ready = d.io_ptw_req_0_ready
        self.ptw_valid = d.io_ptw_req_0_valid
        self.ptw_vpn = d.io_ptw_req_0_bits_vpn
        self.ptw_s2 = d.io_ptw_req_0_bits_s2xlate
        self.ptw_resp_ready = d.io_ptw_resp_ready
        self.ptw_resp_valid = d.io_ptw_resp_valid
        self.ptw_resp_s2 = d.io_ptw_resp_bits_s2xlate
        self.ptw_resp_tag = d.io_ptw_resp_bits_s1_entry_tag
        self.ptw_resp_ppn = d.io_ptw_resp_bits_s1_entry_ppn
        self.sfence = d.io_sfence_valid
        self.csr_changed = [d.io_csr_satp_changed, d.io_csr_vsatp_changed,
                            d.io_csr_hgatp_changed, d.io_csr_priv_virt_changed]

    async def edge(self) -> None:
        await RisingEdge(self.dut.clock)
        self.tick += 1

    def read(self, signal) -> int:
        return int(signal.value)

    async def reset(self) -> None:
        self.req_valid.Set(0)
        self.resp_ready.Set(0)
        self.ptw_ready.Set(0)
        self.ptw_resp_valid.Set(0)
        self.sfence.Set(0)
        for signal in self.csr_changed:
            signal.Set(0)
        self.dut.reset.Set(1)
        await self.edge()
        await self.edge()
        self.dut.reset.Set(0)
        await self.edge()
        assert self.read(self.req_ready) == 1
        assert self.read(self.resp_valid) == 0
        assert self.read(self.ptw_valid) == 0
        assert self.read(self.ptw_resp_ready) == 1

    def request_ready(self) -> int:
        return self.read(self.req_ready)

    def ptw_request_valid(self) -> int:
        return self.read(self.ptw_valid)

    def ptw_request(self) -> tuple[int, int]:
        return self.read(self.ptw_vpn), self.read(self.ptw_s2)

    def response_valid(self) -> int:
        return self.read(self.resp_valid)

    def response_snapshot(self) -> dict:
        return dict(tag=self.read(self.resp_tag), ppn=self.read(self.resp_ppn),
                    s2xlate=self.read(self.resp_s2))

    def response_ready(self) -> int:
        return self.read(self.ptw_resp_ready)

    def _settle_comb(self) -> None:
        refresh = getattr(getattr(self, "dut", None), "RefreshComb", None)
        if refresh is not None:
            refresh()

    async def send_request(self, vpn: int, s2: int = 0) -> None:
        """Send one request, asserting the same-cycle handshake actually fired."""
        self.req_valid.Set(1)
        self.req_vpn.Set(vpn)
        self.req_s2.Set(s2)
        self._settle_comb()
        fire = bool(self.read(self.req_valid) and self.read(self.req_ready))
        if not fire:
            self.req_valid.Set(0)
            raise RuntimeError("PTW repeater request port did not accept the offer")
        await self.edge()
        self.req_valid.Set(0)

    async def offer_second_request(self, vpn: int, s2: int = 0) -> bool:
        """Offer a second request and report this cycle's real handshake fire."""
        self.req_valid.Set(1)
        self.req_vpn.Set(vpn)
        self.req_s2.Set(s2)
        self._settle_comb()
        fire = bool(self.read(self.req_valid) and self.read(self.req_ready))
        await self.edge()
        self.req_valid.Set(0)
        return fire

    async def accept_ptw(self) -> None:
        self.ptw_ready.Set(1)
        await self.edge()
        self.ptw_ready.Set(0)

    async def ptw_respond(self, tag: int, ppn: int, s2: int = 0) -> None:
        self.ptw_resp_valid.Set(1)
        self.ptw_resp_tag.Set(tag)
        self.ptw_resp_ppn.Set(ppn)
        self.ptw_resp_s2.Set(s2)
        await self.edge()
        self.ptw_resp_valid.Set(0)

    async def accept_response(self) -> None:
        self.resp_ready.Set(1)
        await self.edge()
        self.resp_ready.Set(0)

    async def pulse_sfence(self, *, hold: int = 1, settle: int = 2) -> None:
        self.sfence.Set(1)
        for _ in range(hold):
            await self.edge()
        self.sfence.Set(0)
        for _ in range(settle):
            await self.edge()

    async def pulse_csr_change(self, index: int) -> None:
        if not 0 <= index < len(self.csr_changed):
            raise IndexError(index)
        signal = self.csr_changed[index]
        signal.Set(1)
        await self.edge()
        signal.Set(0)
        await self.edge()
        await self.edge()

    def set_resp_ready(self, value: int) -> None:
        if value not in (0, 1):
            raise ValueError("response ready must be 0 or 1")
        self.resp_ready.Set(value)
        self.dut.RefreshComb()

    def set_ptw_ready(self, value: int) -> None:
        """Drive the PTW request-side ready level of the repeater channel."""
        if value not in (0, 1):
            raise ValueError("PTW ready must be 0 or 1")
        self.ptw_ready.Set(value)
        self._settle_comb()

    def begin_request_stream(self) -> None:
        """Hold the TLB-side request valid while a stress payload is driven."""
        self.req_valid.Set(1)

    def stream_request(self, vpn: int, s2: int = 0) -> None:
        """Drive one request payload while the stream valid is held."""
        self.req_vpn.Set(vpn)
        self.req_s2.Set(s2)
        self._settle_comb()

    async def end_request_stream(self) -> None:
        """Release the held request valid on this edge."""
        self.req_valid.Set(0)
        await self.edge()

    def structural_input_sweep(self, value: int) -> None:
        """Sweep every input except clock/reset, matching the frozen probe.

        The original stress case used a cross-DUT exclusion tuple whose leaf
        names did not exist on this DUT, so only clock and reset were actually
        excluded; the handshake inputs were part of the swept stimulus. Keep
        that effective behavior so per-edge input levels match.
        """
        excluded = [self.dut.clock, self.dut.reset]
        sweep_inputs(self.dut, value, excluded)
        self.dut.RefreshComb()
