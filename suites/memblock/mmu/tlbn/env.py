"""Public-port environment for the multi-port TLBNonBlock (MemBlock DTLB)."""
from __future__ import annotations

from dataclasses import dataclass

from toffee import RisingEdge

from ..tlbfa.model import MASK, Refill


@dataclass
class PtwSnap:
    valid: int
    vpn: int
    s2xlate: int
    get_gpa: int


@dataclass
class PortSnap:
    valid: int
    paddr_0: int
    paddr_1: int
    gpaddr: int
    fullva: int
    pbmt: int
    miss: int
    is_for_vs_nonleaf: int
    pf_ld: int
    pf_st: int
    af_ld: int
    af_st: int
    gpf_ld: int
    gpf_st: int
    isHyper: int
    vaNeedExt: int
    ptw: PtwSnap
    pmp: dict
    replay: int


class TlbNonBlockEnv:
    """Drive the four DTLB requestor ports through public pins only."""

    def __init__(self, dut, coverage=None) -> None:
        self.dut = dut
        self.coverage = coverage
        self.tick = 0
        self.ports = []
        d = dut
        for index in range(4):
            prefix = f"io_requestor_{index}"
            def opt(name, default=0):
                optional = {0: set(), 1: {'resp_bits_excp_0_pf_st', 'resp_bits_excp_0_gpf_st', 'resp_bits_excp_0_af_st'}, 2: {'resp_bits_excp_0_pf_st', 'resp_bits_excp_0_gpf_st', 'resp_bits_excp_0_af_st'}, 3: {'resp_bits_excp_0_pf_st', 'resp_bits_paddr_1', 'resp_bits_excp_0_gpf_st', 'resp_bits_excp_0_vaNeedExt', 'resp_bits_gpaddr_0', 'resp_bits_isForVSnonLeafPTE', 'resp_bits_excp_0_isHyper', 'resp_bits_excp_0_af_st', 'resp_bits_fullva', 'req_kill'}}
                suffix = name[len(prefix) + 1:]
                return getattr(d, name, None) if suffix in optional[index] else getattr(d, name)

            req = dict(
                valid=getattr(d, f"{prefix}_req_valid"),
                vaddr=getattr(d, f"{prefix}_req_bits_vaddr"),
                fullva=getattr(d, f"{prefix}_req_bits_fullva"),
                checkfullva=getattr(d, f"{prefix}_req_bits_checkfullva"),
                hyperinst=getattr(d, f"{prefix}_req_bits_hyperinst"),
                hlvx=getattr(d, f"{prefix}_req_bits_hlvx"),
                kill=getattr(d, f"{prefix}_req_bits_kill"),
                is_prefetch=getattr(d, f"{prefix}_req_bits_isPrefetch"),
                no_translate=getattr(d, f"{prefix}_req_bits_no_translate"),
                pmp_addr=getattr(d, f"{prefix}_req_bits_pmp_addr"),
                rob_flag=getattr(d, f"{prefix}_req_bits_debug_robIdx_flag"),
                rob_value=getattr(d, f"{prefix}_req_bits_debug_robIdx_value"),
                rob_is_former=getattr(d, f"{prefix}_req_bits_debug_robIdx_isFormer"),
                req_kill=opt(f"{prefix}_req_kill"),
            )
            if hasattr(d, f"{prefix}_req_bits_cmd"):
                req["cmd"] = getattr(d, f"{prefix}_req_bits_cmd")
            resp = dict(
                valid=opt(f"{prefix}_resp_valid"),
                paddr_0=opt(f"{prefix}_resp_bits_paddr_0"),
                paddr_1=opt(f"{prefix}_resp_bits_paddr_1"),
                gpaddr=opt(f"{prefix}_resp_bits_gpaddr_0"),
                fullva=opt(f"{prefix}_resp_bits_fullva"),
                pbmt=opt(f"{prefix}_resp_bits_pbmt_0"),
                miss=opt(f"{prefix}_resp_bits_miss"),
                is_for_vs_nonleaf=opt(f"{prefix}_resp_bits_isForVSnonLeafPTE"),
            )
            for field in ("pf_ld", "pf_st", "af_ld", "af_st",
                          "gpf_ld", "gpf_st"):
                resp[field] = opt(f"{prefix}_resp_bits_excp_0_{field}")
            for field in ("isHyper", "vaNeedExt"):
                resp[field] = opt(f"{prefix}_resp_bits_excp_0_{field}")
            ptw = dict(
                valid=getattr(d, f"io_ptw_req_{index}_valid"),
                vpn=getattr(d, f"io_ptw_req_{index}_bits_vpn"),
                s2xlate=getattr(d, f"io_ptw_req_{index}_bits_s2xlate"),
                get_gpa=getattr(d, f"io_ptw_req_{index}_bits_getGpa"),
            )
            pmp = dict(
                valid=getattr(d, f"io_pmp_{index}_valid"),
                addr=getattr(d, f"io_pmp_{index}_bits_addr"),
            )
            if hasattr(d, f"io_pmp_{index}_bits_cmd"):
                pmp["cmd"] = getattr(d, f"io_pmp_{index}_bits_cmd")
            self.ports.append(dict(req=req, resp=resp, ptw=ptw, pmp=pmp,
                                   replay=getattr(d, f"io_tlbreplay_{index}")))
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
            dmode=d.io_csr_priv_dmode,
            virt=d.io_csr_priv_virt,
            virt_changed=d.io_csr_priv_virt_changed,
            mxr=d.io_csr_priv_mxr,
            sum=d.io_csr_priv_sum,
            vmxr=d.io_csr_priv_vmxr,
            vsum=d.io_csr_priv_vsum,
            spvp=d.io_csr_priv_spvp,
            bme=d.io_csr_mbmc_BME,
            cmode=d.io_csr_mbmc_CMODE,
            pmm_seccfg=d.io_csr_pmm_mseccfg,
            pmm_menvcfg=d.io_csr_pmm_menvcfg,
            pmm_henvcfg=d.io_csr_pmm_henvcfg,
            pmm_hstatus=d.io_csr_pmm_hstatus,
            pmm_senvcfg=d.io_csr_pmm_senvcfg,
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
        self.redirect = dict(
            valid=d.io_redirect_valid,
            level=d.io_redirect_bits_level,
            flag=d.io_redirect_bits_robIdx_flag,
            value=d.io_redirect_bits_robIdx_value,
            is_former=d.io_redirect_bits_robIdx_isFormer,
        )
        self.ptw_resp = {
            "valid": d.io_ptw_resp_valid,
            "s2xlate": d.io_ptw_resp_bits_s2xlate,
            "s1_tag": d.io_ptw_resp_bits_s1_entry_tag,
            "s1_asid": d.io_ptw_resp_bits_s1_entry_asid,
            "s1_vmid": d.io_ptw_resp_bits_s1_entry_vmid,
            "s1_n": d.io_ptw_resp_bits_s1_entry_n,
            "s1_pbmt": d.io_ptw_resp_bits_s1_entry_pbmt,
            "s1_perm_a": d.io_ptw_resp_bits_s1_entry_perm_a,
            "s1_perm_d": d.io_ptw_resp_bits_s1_entry_perm_d,
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
            "s2_perm_d": d.io_ptw_resp_bits_s2_entry_perm_d,
            "s2_perm_x": d.io_ptw_resp_bits_s2_entry_perm_x,
            "s2_perm_w": d.io_ptw_resp_bits_s2_entry_perm_w,
            "s2_perm_r": d.io_ptw_resp_bits_s2_entry_perm_r,
            "s2_level": d.io_ptw_resp_bits_s2_entry_level,
            "s2_gpf": d.io_ptw_resp_bits_s2_gpf,
            "s2_gaf": d.io_ptw_resp_bits_s2_gaf,
            "get_gpa": d.io_ptw_resp_bits_getGpa,
        }
        for index in range(8):
            for field, name in (
                ("s1_ppn_low", f"io_ptw_resp_bits_s1_ppn_low_{index}"),
                ("s1_valididx", f"io_ptw_resp_bits_s1_valididx_{index}"),
                ("s1_pteidx", f"io_ptw_resp_bits_s1_pteidx_{index}"),
            ):
                self.ptw_resp[f"{field}_{index}"] = getattr(d, name)
        self.perf = [d.io_perf_0_value, d.io_perf_1_value]

    async def edge(self) -> None:
        await RisingEdge(self.dut.clock)
        self.tick += 1

    def read(self, signal) -> int:
        return int(signal.value)

    def _set(self, signal, value) -> None:
        signal.Set(value)

    def set_csr(self, **values) -> None:
        for key, value in values.items():
            self.csr[key].Set(value)
        self.dut.RefreshComb()

    async def reset(self) -> None:
        for entry in self.ports:
            self._set(entry["req"]["valid"], 0)
            for field in ("kill", "req_kill", "is_prefetch", "no_translate",
                          "checkfullva", "hyperinst", "hlvx"):
                if entry["req"][field] is not None:
                    self._set(entry["req"][field], 0)
            self._set(entry["req"]["vaddr"], 0)
            self._set(entry["req"]["fullva"], 0)
            self._set(entry["req"]["pmp_addr"], 0)
            self._set(entry["req"]["rob_flag"], 0)
            self._set(entry["req"]["rob_value"], 0)
            self._set(entry["req"]["rob_is_former"], 0)
            if "cmd" in entry["req"]:
                self._set(entry["req"]["cmd"], 0)
        for signal in self.csr.values():
            signal.Set(0)
        for signal in self.sfence_pins.values():
            signal.Set(0)
        for signal in self.redirect.values():
            signal.Set(0)
        self._set(self.ptw_resp["valid"], 0)
        for key, signal in self.ptw_resp.items():
            if key != "valid":
                signal.Set(0)
        self.dut.reset.Set(1)
        await self.edge()
        await self.edge()
        self.dut.reset.Set(0)
        await self.edge()
        self.set_csr(satp_mode=0, satp_asid=0, vsatp_mode=0, hgatp_mode=0,
                     hgatp_vmid=0, imode=0, dmode=0, virt=0, mxr=0, sum=0,
                     spvp=0, bme=0, cmode=0)
        await self.edge()

    def _request_snap(self, port: int) -> tuple[dict, dict, dict]:
        self.dut.RefreshComb()
        entry = self.ports[port]
        ptw = PtwSnap(
            valid=self.read(entry["ptw"]["valid"]),
            vpn=self.read(entry["ptw"]["vpn"]),
            s2xlate=self.read(entry["ptw"]["s2xlate"]),
            get_gpa=self.read(entry["ptw"]["get_gpa"]),
        )
        resp = {}
        for field in ("valid", "paddr_0", "paddr_1", "gpaddr", "fullva",
                      "pbmt", "miss", "is_for_vs_nonleaf"):
            signal = entry["resp"][field]
            resp[field] = self.read(signal) if signal is not None else 0
        for field in ("pf_ld", "pf_st", "af_ld", "af_st", "gpf_ld", "gpf_st",
                      "isHyper", "vaNeedExt"):
            signal = entry["resp"][field]
            resp[field] = self.read(signal) if signal is not None else 0
        pmp = dict(
            valid=self.read(entry["pmp"]["valid"]),
            addr=self.read(entry["pmp"]["addr"]),
            cmd=(self.read(entry["pmp"]["cmd"])
                 if "cmd" in entry["pmp"] else 0),
        )
        replay = self.read(entry["replay"])
        return resp, ptw, dict(pmp=pmp, replay=replay)

    async def issue(self, port: int, vaddr: int, *, cmd: int = 0,
                    fullva: int | None = None, hyperinst: int = 0,
                    hlvx: int = 0, kill: int = 0, req_kill: int = 0,
                    is_prefetch: int = 0, no_translate: int = 0,
                    pmp_addr: int = 0, checkfullva: int = 0,
                    rob_value: int = 0, rob_flag: int = 0,
                    rob_is_former: int = 0) -> PortSnap:
        entry = self.ports[port]
        req = entry["req"]
        if fullva is None:
            fullva = vaddr
        self._set(req["valid"], 1)
        self._set(req["vaddr"], vaddr & ((1 << 50) - 1))
        self._set(req["fullva"], fullva & ((1 << 64) - 1))
        self._set(req["checkfullva"], checkfullva)
        self._set(req["hyperinst"], hyperinst)
        self._set(req["hlvx"], hlvx)
        self._set(req["kill"], kill)
        self._set(req["is_prefetch"], is_prefetch)
        self._set(req["no_translate"], no_translate)
        self._set(req["pmp_addr"], pmp_addr & ((1 << 48) - 1))
        self._set(req["rob_flag"], rob_flag)
        self._set(req["rob_value"], rob_value & 0xFF)
        self._set(req["rob_is_former"], rob_is_former)
        if req["req_kill"] is not None:
            self._set(req["req_kill"], req_kill)
        if "cmd" in req:
            self._set(req["cmd"], cmd)
        self.dut.RefreshComb()
        await self.edge()
        resp, ptw, extra = self._request_snap(port)
        self._set(req["valid"], 0)
        self._set(req["kill"], 0)
        if req["req_kill"] is not None:
            self._set(req["req_kill"], 0)
        await self.edge()
        snap = PortSnap(**resp, ptw=ptw, **extra)
        if self.coverage is not None:
            if resp["miss"]:
                self.coverage.sample("miss", port, ptw.s2xlate, "miss")
            elif resp["pf_ld"] or resp["pf_st"]:
                self.coverage.sample("fault", port, ptw.s2xlate, "pf")
            elif resp["af_ld"] or resp["af_st"]:
                self.coverage.sample("fault", port, ptw.s2xlate, "af")
            elif resp["gpf_ld"] or resp["gpf_st"]:
                self.coverage.sample("fault", port, ptw.s2xlate, "gpf")
            else:
                self.coverage.sample("hit", port, ptw.s2xlate, "clean")
        return snap

    def _drive_ptw(self, data: Refill | None, addr_low: int = 0,
                   get_gpa: int = 0) -> None:
        pins = self.ptw_resp
        if data is None:
            for key, signal in pins.items():
                signal.Set(0)
            return
        self._set(pins["valid"], 1)
        self._set(pins["s2xlate"], data.s2xlate)
        self._set(pins["s1_tag"], data.s1_tag & MASK["tag"])
        self._set(pins["s1_asid"], data.s1_asid & MASK["asid"])
        self._set(pins["s1_vmid"], data.s1_vmid & MASK["vmid"])
        self._set(pins["s1_n"], data.s1_n)
        self._set(pins["s1_pbmt"], data.s1_pbmt)
        for key in ("s1_perm_a", "s1_perm_d", "s1_perm_g", "s1_perm_u",
                    "s1_perm_x", "s1_perm_w", "s1_perm_r"):
            self._set(pins[key], getattr(data, key, 1))
        self._set(pins["s1_level"], data.s1_level)
        self._set(pins["s1_v"], data.s1_v)
        self._set(pins["s1_ppn"], data.s1_ppn & MASK["pte_ppn"])
        self._set(pins["s1_addr_low"], addr_low & 7)
        self._set(pins["s1_pf"], data.s1_pf)
        self._set(pins["s1_af"], data.s1_af)
        for index in range(8):
            self._set(pins[f"s1_ppn_low_{index}"], data.s1_ppn_low[index] & 7)
            self._set(pins[f"s1_valididx_{index}"], data.s1_valididx[index])
            self._set(pins[f"s1_pteidx_{index}"], data.s1_pteidx[index])
        self._set(pins["s2_tag"], data.s2_tag & MASK["gvpn_tag"])
        self._set(pins["s2_vmid"], data.s2_vmid & MASK["vmid"])
        self._set(pins["s2_n"], data.s2_n)
        self._set(pins["s2_pbmt"], data.s2_pbmt)
        self._set(pins["s2_ppn"], data.s2_ppn & ((1 << 38) - 1))
        for key in ("s2_perm_a", "s2_perm_d", "s2_perm_x", "s2_perm_w",
                    "s2_perm_r"):
            signal = pins.get(key)
            if signal is not None:
                self._set(signal, getattr(data, key, 1))
        self._set(pins["s2_level"], data.s2_level)
        self._set(pins["s2_gpf"], data.s2_gpf)
        self._set(pins["s2_gaf"], data.s2_gaf)
        self._set(pins["get_gpa"], get_gpa)

    async def ptw_respond(self, data: Refill, addr_low: int = 0,
                          get_gpa: int = 0, wait: int = 2) -> None:
        self._drive_ptw(data, addr_low, get_gpa)
        self.dut.RefreshComb()
        await self.edge()
        self._drive_ptw(None)
        for _ in range(wait):
            await self.edge()

    async def sfence(self, rs1: int, rs2: int, addr: int, sfence_id: int,
                     hv: int = 0, hg: int = 0) -> None:
        for _ in range(3):
            self._set(self.sfence_pins["valid"], 1)
            self._set(self.sfence_pins["rs1"], rs1)
            self._set(self.sfence_pins["rs2"], rs2)
            self._set(self.sfence_pins["addr"], addr & ((1 << 50) - 1))
            self._set(self.sfence_pins["id"], sfence_id & MASK["asid"])
            self._set(self.sfence_pins["hv"], hv)
            self._set(self.sfence_pins["hg"], hg)
            await self.edge()
        self._set(self.sfence_pins["valid"], 0)
        for _ in range(6):
            await self.edge()

    async def redirect_now(self, value: int = 0, flag: int = 0,
                           is_former: int = 0) -> None:
        self._set(self.redirect["valid"], 1)
        self._set(self.redirect["level"], 0)
        self._set(self.redirect["flag"], flag)
        self._set(self.redirect["value"], value & 0xFF)
        self._set(self.redirect["is_former"], is_former)
        self.dut.RefreshComb()
        await self.edge()
        self._set(self.redirect["valid"], 0)
        await self.edge()

    def perf_values(self) -> list[int]:
        self.dut.RefreshComb()
        return [self.read(signal) for signal in self.perf]
