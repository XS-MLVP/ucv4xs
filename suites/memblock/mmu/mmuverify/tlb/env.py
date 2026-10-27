"""Public-port environment for the TLB (ITLB) parent."""
from __future__ import annotations

from dataclasses import dataclass

from toffee import RisingEdge

from ..tlbfa.model import MASK, Refill
from .model import TlbModel, TlbResponse


@dataclass
class PtwSnap:
    valid: int
    vpn: int
    s2xlate: int
    get_gpa: int


@dataclass
class TlbSnap:
    paddr: int
    gpaddr: int
    pbmt: int
    miss: int
    fake_or_nonleaf: int
    gpf: int
    pf: int
    af: int
    ptw: PtwSnap


class TlbEnv:
    def __init__(self, dut, coverage=None) -> None:
        self.dut = dut
        self.coverage = coverage
        self.model = TlbModel()
        self.tick = 0
        self._bind()

    def _bind(self) -> None:
        d = self.dut
        self.req_valid = d.io_requestor_0_req_valid
        self.req_vaddr = d.io_requestor_0_req_bits_vaddr
        self.req_fullva = d.io_requestor_0_req_bits_fullva
        self.resp = dict(
            paddr=d.io_requestor_0_resp_bits_paddr_0,
            gpaddr=d.io_requestor_0_resp_bits_gpaddr_0,
            pbmt=d.io_requestor_0_resp_bits_pbmt_0,
            miss=d.io_requestor_0_resp_bits_miss,
            fake_or_nonleaf=d.io_requestor_0_resp_bits_isForVSnonLeafPTE,
            gpf=d.io_requestor_0_resp_bits_excp_0_gpf_instr,
            pf=d.io_requestor_0_resp_bits_excp_0_pf_instr,
            af=d.io_requestor_0_resp_bits_excp_0_af_instr,
        )
        self.ptw_req = dict(
            valid=d.io_ptw_req_0_valid,
            vpn=d.io_ptw_req_0_bits_vpn,
            s2xlate=d.io_ptw_req_0_bits_s2xlate,
            get_gpa=d.io_ptw_req_0_bits_getGpa,
            ready=d.io_ptw_req_0_ready,
        )
        self.sfence_pins = dict(
            valid=d.io_sfence_valid,
            rs1=d.io_sfence_bits_rs1,
            rs2=d.io_sfence_bits_rs2,
            addr=d.io_sfence_bits_addr,
            id=d.io_sfence_bits_id,
            hv=d.io_sfence_bits_hv,
            hg=d.io_sfence_bits_hg,
        )
        self.csr = dict(
            satp_mode=d.io_csr_satp_mode,
            satp_asid=d.io_csr_satp_asid,
            satp_changed=d.io_csr_satp_changed,
            vsatp_mode=d.io_csr_vsatp_mode,
            vsatp_asid=d.io_csr_vsatp_asid,
            vsatp_changed=d.io_csr_vsatp_changed,
            hgatp_mode=d.io_csr_hgatp_mode,
            hgatp_vmid=d.io_csr_hgatp_vmid,
            hgatp_changed=d.io_csr_hgatp_changed,
            imode=d.io_csr_priv_imode,
            virt=d.io_csr_priv_virt,
            virt_changed=d.io_csr_priv_virt_changed,
            mxr=d.io_csr_priv_mxr,
            sum=d.io_csr_priv_sum,
            bme=d.io_csr_mbmc_BME,
            cmode=d.io_csr_mbmc_CMODE,
        )
        self.flush_pipe = d.io_flushPipe_0
        self._ptw_pins = {
            "valid": d.io_ptw_resp_valid,
            "s2xlate": d.io_ptw_resp_bits_s2xlate,
            "s1_tag": d.io_ptw_resp_bits_s1_entry_tag,
            "s1_asid": d.io_ptw_resp_bits_s1_entry_asid,
            "s1_vmid": d.io_ptw_resp_bits_s1_entry_vmid,
            "s1_n": d.io_ptw_resp_bits_s1_entry_n,
            "s1_pbmt": d.io_ptw_resp_bits_s1_entry_pbmt,
            "s1_perm_a": d.io_ptw_resp_bits_s1_entry_perm_a,
            "s1_perm_g": d.io_ptw_resp_bits_s1_entry_perm_g,
            "s1_perm_u": d.io_ptw_resp_bits_s1_entry_perm_u,
            "s1_perm_x": d.io_ptw_resp_bits_s1_entry_perm_x,
            "s1_perm_w": d.io_ptw_resp_bits_s1_entry_perm_w,
            "s1_perm_r": d.io_ptw_resp_bits_s1_entry_perm_r,
            "s1_level": d.io_ptw_resp_bits_s1_entry_level,
            "s1_v": d.io_ptw_resp_bits_s1_entry_v,
            "s1_ppn": d.io_ptw_resp_bits_s1_entry_ppn,
            "s1_addr_low": d.io_ptw_resp_bits_s1_addr_low,
            "s1_pf": d.io_ptw_resp_bits_s1_pf,
            "s1_af": d.io_ptw_resp_bits_s1_af,
            "s2_tag": d.io_ptw_resp_bits_s2_entry_tag,
            "s2_vmid": d.io_ptw_resp_bits_s2_entry_vmid,
            "s2_n": d.io_ptw_resp_bits_s2_entry_n,
            "s2_pbmt": d.io_ptw_resp_bits_s2_entry_pbmt,
            "s2_ppn": d.io_ptw_resp_bits_s2_entry_ppn,
            "s2_perm_a": d.io_ptw_resp_bits_s2_entry_perm_a,
            "s2_perm_x": d.io_ptw_resp_bits_s2_entry_perm_x,
            "s2_level": d.io_ptw_resp_bits_s2_entry_level,
            "s2_gpf": d.io_ptw_resp_bits_s2_gpf,
            "s2_gaf": d.io_ptw_resp_bits_s2_gaf,
            "get_gpa": d.io_ptw_resp_bits_getGpa,
            **{f"s1_ppn_low_{i}": getattr(d, f"io_ptw_resp_bits_s1_ppn_low_{i}") for i in range(8)},
            **{f"s1_valididx_{i}": getattr(d, f"io_ptw_resp_bits_s1_valididx_{i}") for i in range(8)},
            **{f"s1_pteidx_{i}": getattr(d, f"io_ptw_resp_bits_s1_pteidx_{i}") for i in range(8)},
        }

    async def edge(self) -> None:
        await RisingEdge(self.dut.clock)
        self.tick += 1

    async def settle(self, cycles: int = 1) -> None:
        for _ in range(cycles):
            await self.edge()

    def read(self, signal) -> int:
        return int(signal.value)

    def _write(self, signal, value: int) -> None:
        signal.Set(value)

    def _drive_context(self) -> None:
        m = self.model
        c = self.csr
        self._write(c["satp_mode"], m.satp_mode)
        self._write(c["satp_asid"], m.satp_asid & MASK["asid"])
        self._write(c["satp_changed"], 0)
        self._write(c["vsatp_mode"], m.vsatp_mode)
        self._write(c["vsatp_asid"], m.satp_asid & MASK["asid"])
        self._write(c["vsatp_changed"], 0)
        self._write(c["hgatp_mode"], m.hgatp_mode)
        self._write(c["hgatp_vmid"], m.hgatp_vmid & MASK["vmid"])
        self._write(c["hgatp_changed"], 0)
        self._write(c["imode"], m.imode)
        self._write(c["virt"], m.virt)
        self._write(c["virt_changed"], 0)
        self._write(c["mxr"], 0)
        self._write(c["sum"], 0)
        self._write(c["bme"], 0)
        self._write(c["cmode"], 0)

    def set_context(self, **values) -> None:
        self.model.set_context(**values)
        self._drive_context()
        self.dut.RefreshComb()

    async def reset(self, context: str = "empty") -> None:
        self._write(self.req_valid, 0)
        self._write(self.ptw_req["ready"], 1)
        self._write(self._ptw_pins["valid"], 0)
        self._write(self.flush_pipe, 0)
        self.dut.reset.Set(1)
        await self.edge()
        await self.edge()
        self.model.reset()
        self.model.set_context()
        self._drive_context()
        self.dut.reset.Set(0)
        await self.edge()
        if self.coverage is not None:
            self.coverage.sample_reset(context)

    def read_ptw(self) -> PtwSnap:
        return PtwSnap(
            valid=self.read(self.ptw_req["valid"]),
            vpn=self.read(self.ptw_req["vpn"]),
            s2xlate=self.read(self.ptw_req["s2xlate"]),
            get_gpa=self.read(self.ptw_req["get_gpa"]),
        )

    def read_response(self) -> TlbSnap:
        return TlbSnap(
            paddr=self.read(self.resp["paddr"]),
            gpaddr=self.read(self.resp["gpaddr"]),
            pbmt=self.read(self.resp["pbmt"]),
            miss=self.read(self.resp["miss"]),
            fake_or_nonleaf=self.read(self.resp["fake_or_nonleaf"]),
            gpf=self.read(self.resp["gpf"]),
            pf=self.read(self.resp["pf"]),
            af=self.read(self.resp["af"]),
            ptw=self.read_ptw(),
        )

    async def issue(self, vaddr: int, fullva: int | None = None, note: str = "") -> TlbSnap:
        if fullva is None:
            fullva = vaddr
        expected = self.model.translate(vaddr)
        self._write(self.req_valid, 1)
        self._write(self.req_vaddr, vaddr & ((1 << 50) - 1))
        self._write(self.req_fullva, fullva & ((1 << 64) - 1))
        await self.edge()
        snap = self.read_response()
        self._check(snap, expected, vaddr, note)
        self._write(self.req_valid, 0)
        await self.edge()
        if self.coverage is not None:
            mode = "bare" if not self.model.translation_enabled() else (
                "sv48" if self.model.satp_mode == 9 else "sv39"
            )
            if expected.miss:
                self.coverage.sample_lookup(mode, False, None)
                self.coverage.sample_ptw_request(snap.ptw.s2xlate)
            else:
                if expected.is_fake_or_nonleaf:
                    kind = "fake_or_nonleaf"
                elif expected.pf:
                    kind = "pf"
                elif expected.af:
                    kind = "af"
                else:
                    kind = "none"
                self.coverage.sample_lookup(mode, True, kind)
                self.coverage.sample_no_ptw()
        return snap

    def _check(self, snap: TlbSnap, expected: TlbResponse, vaddr: int, note: str) -> None:
        assert snap.miss == expected.miss, f"{note}: miss {snap.miss} != {expected.miss}"
        if expected.miss:
            assert snap.paddr == (vaddr & 0xFFF), (
                f"{note}: miss paddr {snap.paddr:#x} != low offset"
            )
            assert snap.ptw.valid == 1, f"{note}: miss must request PTW"
            want_vpn, want_s2, want_gpa = self.model.ptw_request(vaddr)
            assert snap.ptw.vpn == want_vpn, f"{note}: PTW vpn {snap.ptw.vpn:#x} != {want_vpn:#x}"
            assert snap.ptw.s2xlate == want_s2, f"{note}: PTW s2xlate {snap.ptw.s2xlate} != {want_s2}"
            assert snap.ptw.get_gpa == want_gpa, f"{note}: PTW getGpa"
        else:
            assert snap.ptw.valid == 0, f"{note}: hit must not request PTW"
            if self.model.translation_enabled():
                assert snap.paddr == expected.paddr, (
                    f"{note}: paddr {snap.paddr:#x} != {expected.paddr:#x}"
                )
                assert snap.pf == expected.pf, f"{note}: pf {snap.pf} != {expected.pf}"
                assert snap.af == expected.af, f"{note}: af {snap.af} != {expected.af}"
                assert snap.gpf == expected.gpf, f"{note}: gpf"
                # In this no-S2 scope the fake/non-leaf flag is meaningful only
                # for a hit; the miss path leaks a stale value and is not checked.
                assert snap.fake_or_nonleaf == expected.is_fake_or_nonleaf, (
                    f"{note}: fake/nonleaf {snap.fake_or_nonleaf} != {expected.is_fake_or_nonleaf}"
                )
            else:
                assert snap.paddr == vaddr & ((1 << 48) - 1), f"{note}: bare paddr"
                assert snap.pf == 0 and snap.af == 0 and snap.gpf == 0, f"{note}: bare excp"

    def _drive_ptw(self, data: Refill | None, addr_low: int = 0,
                   get_gpa: int = 0) -> None:
        pins = self._ptw_pins
        if data is None:
            self._write(pins["valid"], 0)
            for key in pins:
                if key != "valid":
                    self._write(pins[key], 0)
            return
        self._write(pins["valid"], 1)
        self._write(pins["s2xlate"], data.s2xlate)
        self._write(pins["s1_tag"], data.s1_tag & MASK["tag"])
        self._write(pins["s1_asid"], data.s1_asid & MASK["asid"])
        self._write(pins["s1_vmid"], data.s1_vmid & MASK["vmid"])
        self._write(pins["s1_n"], data.s1_n)
        self._write(pins["s1_pbmt"], data.s1_pbmt)
        for key in ("s1_perm_a", "s1_perm_g", "s1_perm_u", "s1_perm_x", "s1_perm_w", "s1_perm_r"):
            self._write(pins[key], getattr(data, key))
        self._write(pins["s1_level"], data.s1_level)
        self._write(pins["s1_v"], data.s1_v)
        self._write(pins["s1_ppn"], data.s1_ppn & MASK["pte_ppn"])
        self._write(pins["s1_addr_low"], addr_low & 7)
        self._write(pins["s1_pf"], data.s1_pf)
        self._write(pins["s1_af"], data.s1_af)
        for index in range(8):
            self._write(pins[f"s1_ppn_low_{index}"], data.s1_ppn_low[index] & 7)
            self._write(pins[f"s1_valididx_{index}"], data.s1_valididx[index])
            self._write(pins[f"s1_pteidx_{index}"], data.s1_pteidx[index])
        self._write(pins["s2_tag"], data.s2_tag & MASK["gvpn_tag"])
        self._write(pins["s2_vmid"], data.s2_vmid & MASK["vmid"])
        self._write(pins["s2_n"], data.s2_n)
        self._write(pins["s2_pbmt"], data.s2_pbmt)
        self._write(pins["s2_ppn"], data.s2_ppn & ((1 << 38) - 1))
        self._write(pins["s2_perm_a"], data.s2_perm_a)
        self._write(pins["s2_perm_x"], data.s2_perm_x)
        self._write(pins["s2_level"], data.s2_level)
        self._write(pins["s2_gpf"], data.s2_gpf)
        self._write(pins["s2_gaf"], data.s2_gaf)
        self._write(pins["get_gpa"], get_gpa)

    async def ptw_respond(self, data: Refill, addr_low: int = 0,
                          wait: int = 2, get_gpa: int = 0) -> int:
        self._drive_ptw(data, addr_low, get_gpa)
        await self.edge()
        way = self.model.refill(data)
        self._drive_ptw(None)
        await self.settle(wait)
        if self.coverage is not None:
            self.coverage.sample_ptw_refill(data)
        return way

    async def sfence(self, rs1: int, rs2: int, addr: int, sfence_id: int,
                     hv: int = 0, hg: int = 0, note: str = "") -> None:
        for _ in range(3):
            self._write(self.sfence_pins["valid"], 1)
            self._write(self.sfence_pins["rs1"], rs1)
            self._write(self.sfence_pins["rs2"], rs2)
            self._write(self.sfence_pins["addr"], addr & ((1 << 50) - 1))
            self._write(self.sfence_pins["id"], sfence_id & MASK["asid"])
            self._write(self.sfence_pins["hv"], hv)
            self._write(self.sfence_pins["hg"], hg)
            await self.edge()
        self._write(self.sfence_pins["valid"], 0)
        await self.edge()
        self.model.sfence(rs1, rs2, addr, sfence_id, hv, hg)
        if self.coverage is not None:
            self.coverage.sample_sfence(rs1, rs2, hv, hg)

    def sample_fence(self, rs1: int, rs2: int, hv: int, hg: int,
                     effects: tuple[str, ...]) -> None:
        if self.coverage is not None:
            self.coverage.sample_sfence(rs1, rs2, hv, hg, effects)
