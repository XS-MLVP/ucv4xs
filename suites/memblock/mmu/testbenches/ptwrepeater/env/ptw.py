"""Env/models for PTWRepeaterNB and PTWFilter."""
from __future__ import annotations

from dataclasses import dataclass

from toffee import RisingEdge

from suites.memblock.mmu.testbenches.shared.env.execution import sweep_inputs

S1_KEYS = ("entry_tag", "entry_asid", "entry_vmid", "entry_n", "entry_pbmt",
           "entry_perm_a", "entry_perm_g", "entry_perm_u", "entry_perm_x",
           "entry_perm_w", "entry_perm_r", "entry_level", "entry_v", "entry_ppn",
           "addr_low")
S2_KEYS = ("entry_tag", "entry_vmid", "entry_n", "entry_pbmt", "entry_ppn",
           "entry_perm_a", "entry_perm_x", "entry_level", "gpf", "gaf")


def s1_pin(dut, key: str):
    return getattr(dut, f"io_ptw_resp_bits_s1_{key}")


def s2_pin(dut, key: str):
    return getattr(dut, f"io_ptw_resp_bits_s2_{key}")


@dataclass
class Req:
    vpn: int
    s2xlate: int = 0
    get_gpa: int = 0


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


class FilterEnv:
    def __init__(self, dut, coverage=None) -> None:
        self.dut = dut
        self.coverage = coverage
        self.tick = 0
        d = dut
        self.req_ready = d.io_tlb_req_0_ready
        self.req_valid = d.io_tlb_req_0_valid
        self.req_vpn = d.io_tlb_req_0_bits_vpn
        self.req_s2 = d.io_tlb_req_0_bits_s2xlate
        self.req_getgpa = d.io_tlb_req_0_bits_getGpa
        self.resp_valid = d.io_tlb_resp_valid
        self.resp_s2 = d.io_tlb_resp_bits_data_s2xlate
        self.resp_s1 = {key: s1_pin(d, key) for key in S1_KEYS}
        self.resp_s2_bits = {key: s2_pin(d, key) for key in S2_KEYS}
        self.resp_getgpa = d.io_tlb_resp_bits_data_getGpa
        self.resp_valididx = [getattr(d, f"io_tlb_resp_bits_data_s1_valididx_{i}") for i in range(8)]
        self.resp_pteidx = [getattr(d, f"io_tlb_resp_bits_data_s1_pteidx_{i}") for i in range(8)]
        self.resp_ppn_low = [getattr(d, f"io_tlb_resp_bits_data_s1_ppn_low_{i}") for i in range(8)]
        self.ptw_ready = d.io_ptw_req_0_ready
        self.ptw_valid = d.io_ptw_req_0_valid
        self.ptw_vpn = d.io_ptw_req_0_bits_vpn
        self.ptw_s2 = d.io_ptw_req_0_bits_s2xlate
        self.ptw_resp_valid = d.io_ptw_resp_valid
        self.ptw_resp_pins = {
            "s2xlate": d.io_ptw_resp_bits_s2xlate,
            **{f"s1_{key}": s1_pin(d, key) for key in S1_KEYS},
            **{f"s2_{key}": s2_pin(d, key) for key in S2_KEYS},
            **{f"s1_valididx_{i}": getattr(d, f"io_ptw_resp_bits_s1_valididx_{i}") for i in range(8)},
            **{f"s1_pteidx_{i}": getattr(d, f"io_ptw_resp_bits_s1_pteidx_{i}") for i in range(8)},
            **{f"s1_ppn_low_{i}": getattr(d, f"io_ptw_resp_bits_s1_ppn_low_{i}") for i in range(8)},
        }
        self.sfence = d.io_sfence_valid
        self.csr = dict(
            satp_asid=d.io_csr_satp_asid,
            satp_changed=d.io_csr_satp_changed,
            vsatp_asid=d.io_csr_vsatp_asid,
            vsatp_changed=d.io_csr_vsatp_changed,
            hgatp_vmid=d.io_csr_hgatp_vmid,
            hgatp_changed=d.io_csr_hgatp_changed,
            virt_changed=d.io_csr_priv_virt_changed,
        )

    async def edge(self) -> None:
        await RisingEdge(self.dut.clock)
        self.tick += 1

    def read(self, signal) -> int:
        return int(signal.value)

    def _settle_comb(self) -> None:
        refresh = getattr(getattr(self, "dut", None), "RefreshComb", None)
        if refresh is not None:
            refresh()

    async def reset(self) -> None:
        self.req_valid.Set(0)
        self.ptw_ready.Set(0)
        self.ptw_resp_valid.Set(0)
        self.sfence.Set(0)
        for signal in self.csr.values():
            signal.Set(0)
        self.dut.reset.Set(1)
        await self.edge()
        await self.edge()
        self.dut.reset.Set(0)
        await self.edge()
        assert self.read(self.req_ready) == 1
        assert self.read(self.resp_valid) == 0
        assert self.read(self.ptw_valid) == 0

    def set_asid(self, satp: int = 0, vsatp: int = 0, vmid: int = 0) -> None:
        self.csr["satp_asid"].Set(satp)
        self.csr["vsatp_asid"].Set(vsatp)
        self.csr["hgatp_vmid"].Set(vmid)
        self.dut.RefreshComb()

    def request_ready(self) -> int:
        return self.read(self.req_ready)

    def ptw_request_valid(self) -> int:
        return self.read(self.ptw_valid)

    def response_ready(self) -> int:
        return self.read(self.ptw_resp_ready)

    def set_ptw_ready(self, value: int) -> None:
        if value not in (0, 1):
            raise ValueError("PTW ready must be 0 or 1")
        self.ptw_ready.Set(value)
        self.dut.RefreshComb()

    async def accept_ptw(self) -> None:
        """Complete one PTW request handshake."""
        self.ptw_ready.Set(1)
        await self.edge()
        self.ptw_ready.Set(0)

    async def offer_request(self, req: Req, note: str = "") -> bool:
        """Offer one request and report this cycle's real handshake fire.

        Acceptance is the pre-edge ``valid && ready`` seen after the payload
        is driven and combinational logic settles; a later ready level is not
        evidence that this offer was accepted.
        """
        self.req_valid.Set(1)
        self.req_vpn.Set(req.vpn)
        self.req_s2.Set(req.s2xlate)
        self.req_getgpa.Set(req.get_gpa)
        self._settle_comb()
        fire = bool(self.read(self.req_valid) and self.read(self.req_ready))
        await self.edge()
        self.req_valid.Set(0)
        return fire

    def begin_request_stream(self) -> None:
        self.req_valid.Set(1)

    def stream_request(self, vpn: int, s2: int = 0, getgpa: int = 0) -> None:
        """Hold request valid and advance one payload in a stress stream."""
        self.req_vpn.Set(vpn)
        self.req_s2.Set(s2)
        self.req_getgpa.Set(getgpa)
        self.dut.RefreshComb()

    async def end_request_stream(self) -> None:
        self.req_valid.Set(0)
        await self.edge()

    def clear_flush_sources(self) -> None:
        for signal in self.csr.values():
            signal.Set(0)
        self.sfence.Set(0)
        self.ptw_resp_valid.Set(0)
        self.dut.RefreshComb()

    async def pulse_csr_change(self, key: str, *, hold: int = 1,
                               settle: int = 3) -> None:
        if key not in self.csr:
            raise KeyError(key)
        self.csr[key].Set(1)
        for _ in range(hold):
            await self.edge()
        self.csr[key].Set(0)
        for _ in range(settle):
            await self.edge()

    async def pulse_sfence(self, *, hold: int = 1, settle: int = 2) -> None:
        self.sfence.Set(1)
        for _ in range(hold):
            await self.edge()
        self.sfence.Set(0)
        for _ in range(settle):
            await self.edge()

    def drive_structural_ptw_response(self, *, s2xlate: int | None = None,
                                      s1_entry_tag: int | None = None,
                                      s1_entry_ppn: int | None = None,
                                      s2_entry_tag: int | None = None,
                                      s2_entry_ppn: int | None = None) -> None:
        """Drive named structural-stress payload fields on the PTW response.

        This is an explicit interface-stress channel operation, not a generic
        name-to-pin forwarder. Only the fields passed as arguments are written;
        every other response leaf keeps its current stress value, so filling
        selected payload bits never silently drops the rest of the stimulus.
        The caller owns ``ptw_resp_valid`` through ``drive_ptw_response_valid``.
        """
        fields = dict(s2xlate=s2xlate, s1_entry_tag=s1_entry_tag,
                      s1_entry_ppn=s1_entry_ppn, s2_entry_tag=s2_entry_tag,
                      s2_entry_ppn=s2_entry_ppn)
        for key, value in fields.items():
            if value is not None:
                self.ptw_resp_pins[key].Set(value)
        self.dut.RefreshComb()

    def drive_ptw_response_valid(self, valid: int) -> None:
        if valid not in (0, 1):
            raise ValueError("PTW response valid must be 0 or 1")
        self.ptw_resp_valid.Set(valid)
        self.dut.RefreshComb()

    def clear_ptw_response(self) -> None:
        """Release the PTW response valid level without touching its payload."""
        self.ptw_resp_valid.Set(0)
        self.dut.RefreshComb()

    def structural_input_sweep(self, value: int) -> None:
        excluded = [self.dut.clock, self.dut.reset, self.req_valid]
        sweep_inputs(self.dut, value, excluded)
        self.dut.RefreshComb()

    def _drive_ptw_resp(self, values: dict | None) -> None:
        for pin in self.ptw_resp_pins.values():
            pin.Set(0)
        if values:
            for key, value in values.items():
                self.ptw_resp_pins[key].Set(value)
        self.ptw_resp_valid.Set(1 if values is not None else 0)
        self.dut.RefreshComb()

    async def ptw_respond_same_cycle(self, values: dict, note: str = "") -> dict:
        """Drive a response in the current cycle and sample it on the edge."""
        self._drive_ptw_resp(values)
        await self.edge()
        snap = self.read_resp()
        self._drive_ptw_resp(None)
        return snap

    async def send(self, req: Req, note: str = "") -> None:
        """Send one request, asserting the same-cycle handshake actually fired."""
        self.req_valid.Set(1)
        self.req_vpn.Set(req.vpn)
        self.req_s2.Set(req.s2xlate)
        self.req_getgpa.Set(req.get_gpa)
        self._settle_comb()
        fire = bool(self.read(self.req_valid) and self.read(self.req_ready))
        if not fire:
            self.req_valid.Set(0)
            raise RuntimeError(f"{note}: filter request port did not accept the offer")
        await self.edge()
        self.req_valid.Set(0)
        await self.edge()

    async def wait_ptw_req(self, note: str = "", max_cycles: int = 8) -> tuple[int, int]:
        for _ in range(max_cycles):
            await self.edge()
            if self.read(self.ptw_valid):
                return self.read(self.ptw_vpn), self.read(self.ptw_s2)
        raise TimeoutError(f"{note}: no PTW request")

    async def ptw_respond(self, values: dict, note: str = "") -> dict:
        self._drive_ptw_resp(values)
        await self.edge()
        snap = self.read_resp()
        self._drive_ptw_resp(None)
        await self.edge()
        return snap

    def read_resp(self) -> dict:
        return {
            "valid": self.read(self.resp_valid),
            "s2xlate": self.read(self.resp_s2),
            **{f"s1_{key}": self.read(pin) for key, pin in self.resp_s1.items()},
            **{f"s2_{key}": self.read(pin) for key, pin in self.resp_s2_bits.items()},
            "getgpa": self.read(self.resp_getgpa),
            "valididx": [self.read(pin) for pin in self.resp_valididx],
            "pteidx": [self.read(pin) for pin in self.resp_pteidx],
            "ppn_low": [self.read(pin) for pin in self.resp_ppn_low],
        }

    async def flush(self) -> None:
        self.sfence.Set(1)
        await self.edge()
        self.sfence.Set(0)
        await self.edge()
        await self.edge()
        assert self.read(self.ptw_valid) == 0
