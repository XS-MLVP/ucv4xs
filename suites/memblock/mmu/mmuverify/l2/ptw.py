"""Env/models for PTWRepeaterNB and PTWFilter."""
from __future__ import annotations

from dataclasses import dataclass

from toffee import RisingEdge

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

    def _drive_ptw_resp(self, values: dict | None) -> None:
        for pin in self.ptw_resp_pins.values():
            pin.Set(0)
        if values:
            for key, value in values.items():
                self.ptw_resp_pins[key].Set(value)
        self.ptw_resp_valid.Set(1 if values is not None else 0)
        self.dut.RefreshComb()

    async def send(self, req: Req, note: str = "") -> None:
        assert self.read(self.req_ready) == 1, f"{note}: not ready"
        self.req_valid.Set(1)
        self.req_vpn.Set(req.vpn)
        self.req_s2.Set(req.s2xlate)
        self.req_getgpa.Set(req.get_gpa)
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
