"""Standalone PTW environment with page-table memory, PMP, bitmap and HPTW responders."""
from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

from toffee import RisingEdge

from suites.memblock.mmu.testbenches.l2tlb.env.l2tlb import PageMemory
from suites.memblock.mmu.testbenches.l2tlb.env.l2tlb import pte
from suites.memblock.mmu.testbenches.shared.env.execution import sweep_inputs
from suites.memblock.mmu.testbenches.shared.env.interface import MXR_PIN
from suites.memblock.mmu.testbenches.shared.env.interface import MxrInputCapability
from suites.memblock.mmu.testbenches.shared.env.interface import signal_schema


TRIMMED_MXR_REASON = (
    "io_csr_priv_mxr is trimmed by the current DUT schema; RISC-V privileged "
    "v20260120 (hypervisor 14.1.5.1: a VS page-table access is checked as an "
    "implicit load; priv-preface: MXR affects only explicit memory accesses) "
    "requires R=1 for the implicit G-stage page-table read, so MXR does not "
    "apply and the field cannot be driven"
)


@dataclass
class MemReq:
    address: int


@dataclass(frozen=True)
class WalkRequest:
    """Caller identity, frozen at the actual PTW request acceptance edge."""
    sequence: int
    vpn: int
    source: int
    s2xlate: int
    accepted_tick: int = -1
    handoff_start: int = 0


@dataclass(frozen=True)
class WalkCompletion:
    request: WalkRequest
    kind: str
    tick: int


class PtwEnv:
    def __init__(self, dut, coverage=None, *, schema_path=None) -> None:
        self.dut = dut
        self.coverage = coverage
        self.memory = PageMemory()
        self.tick = 0
        self._monitor_enabled = False
        self._bitmap_queue = []
        self._hptw_responses = []
        self.requests: list[MemReq] = []
        self.llptw_requests: list[dict] = []
        self.hptw_requests: list[dict] = []
        self.bitmap_requests: list[dict] = []
        self._pending_mem: list[int] = []
        self.pmp_allow = True
        self.bitmap_cf = 0
        self.hptw_queue: list[dict] = []
        self.hptw_identity = False
        self._hptw_pending: dict | None = None
        self._bitmap_pending = False
        self._offered_request: WalkRequest | None = None
        self._active_request: WalkRequest | None = None
        self._next_sequence = 0
        self.walk_completions: list[WalkCompletion] = []
        d = dut
        self.csr = dict(
            satp_mode=d.io_csr_satp_mode,
            satp_asid=d.io_csr_satp_asid,
            satp_ppn=d.io_csr_satp_ppn,
            satp_changed=d.io_csr_satp_changed,
            vsatp_mode=d.io_csr_vsatp_mode,
            vsatp_asid=d.io_csr_vsatp_asid,
            vsatp_ppn=d.io_csr_vsatp_ppn,
            vsatp_changed=d.io_csr_vsatp_changed,
            hgatp_mode=d.io_csr_hgatp_mode,
            hgatp_vmid=d.io_csr_hgatp_vmid,
            hgatp_changed=d.io_csr_hgatp_changed,
            bme=d.io_csr_mbmc_BME,
            cmode=d.io_csr_mbmc_CMODE,
            virt_changed=d.io_csr_priv_virt_changed,
            mpbmte=d.io_csr_mPBMTE,
            hpbmte=d.io_csr_hPBMTE,
        )
        # The only accepted optional CSR leaf is MXR, and only when the
        # artifact schema and the bound handle agree. No generic pin proxy or
        # fake zero is created.
        self._trimmed_csrs: dict[str, str] = {}
        self._interface_schema: dict | None = None
        self._register_mxr(d, schema_path)
        self.sfence = d.io_sfence_valid
        self.req = dict(
            ready=d.io_req_ready,
            valid=d.io_req_valid,
            vpn=d.io_req_bits_req_info_vpn,
            s2xlate=d.io_req_bits_req_info_s2xlate,
            source=d.io_req_bits_req_info_source,
            l3hit=d.io_req_bits_l3Hit,
            l2hit=d.io_req_bits_l2Hit,
            ppn=d.io_req_bits_ppn,
            stage1hit=d.io_req_bits_stage1Hit,
            not_super=d.io_req_bits_stage1_not_super,
            jmp_bitmap=d.io_req_bits_bitmapCheck_jmp_bitmap_check,
            bitmap_pte=d.io_req_bits_bitmapCheck_pte,
            bitmap_splevel=d.io_req_bits_bitmapCheck_SPlevel,
        )
        self.stage1 = {}
        for index in range(8):
            for field in ("tag", "asid", "vmid", "n", "pbmt", "perm_d", "perm_a",
                          "perm_g", "perm_u", "perm_x", "perm_w", "perm_r",
                          "level", "v", "ppn", "ppn_low", "pf", "cf"):
                self.stage1[f"{index}_{field}"] = getattr(
                    d, f"io_req_bits_stage1_entry_{index}_{field}")
            self.stage1[f"pteidx_{index}"] = getattr(
                d, f"io_req_bits_stage1_pteidx_{index}")
        self.resp = dict(
            ready=d.io_resp_ready,
            valid=d.io_resp_valid,
            source=d.io_resp_bits_source,
            s2xlate=d.io_resp_bits_s2xlate,
        )
        for index in range(8):
            for field in ("tag", "asid", "vmid", "n", "pbmt", "perm_d", "perm_a",
                          "perm_g", "perm_u", "perm_x", "perm_w", "perm_r",
                          "level", "v", "ppn", "ppn_low", "af", "pf", "cf"):
                self.resp[f"{index}_{field}"] = getattr(
                    d, f"io_resp_bits_resp_entry_{index}_{field}")
        self.resp["pteidx"] = [getattr(d, f"io_resp_bits_resp_pteidx_{i}")
                               for i in range(8)]
        self.resp["not_super"] = d.io_resp_bits_resp_not_super
        self.hresp = dict(
            gpf=d.io_resp_bits_h_resp_gpf,
            gaf=d.io_resp_bits_h_resp_gaf,
            tag=d.io_resp_bits_h_resp_entry_tag,
            vmid=d.io_resp_bits_h_resp_entry_vmid,
            ppn=d.io_resp_bits_h_resp_entry_ppn,
            level=d.io_resp_bits_h_resp_entry_level,
            perm_r=d.io_resp_bits_h_resp_entry_perm_r,
            perm_w=d.io_resp_bits_h_resp_entry_perm_w,
            perm_x=d.io_resp_bits_h_resp_entry_perm_x,
            perm_a=d.io_resp_bits_h_resp_entry_perm_a,
            perm_d=d.io_resp_bits_h_resp_entry_perm_d,
        )
        self.mem_req = dict(
            valid=d.io_mem_req_valid,
            ready=d.io_mem_req_ready,
            addr=d.io_mem_req_bits_addr,
        )
        self.mem_resp = dict(valid=d.io_mem_resp_valid, bits=d.io_mem_resp_bits)
        self.mem_mask = d.io_mem_mask
        self.pmp = dict(req=d.io_pmp_req_bits_addr,
                        ld=d.io_pmp_resp_ld, mmio=d.io_pmp_resp_mmio)
        self.llptw = dict(
            valid=d.io_llptw_valid,
            ready=d.io_llptw_ready,
            vpn=d.io_llptw_bits_req_info_vpn,
            source=d.io_llptw_bits_req_info_source,
            s2xlate=d.io_llptw_bits_req_info_s2xlate,
        )
        self.hptw = dict(
            valid=d.io_hptw_req_valid,
            ready=d.io_hptw_req_ready,
            gvpn=d.io_hptw_req_bits_gvpn,
            source=d.io_hptw_req_bits_source,
            resp_valid=d.io_hptw_resp_valid,
            resp_gpf=d.io_hptw_resp_bits_h_resp_gpf,
            resp_gaf=d.io_hptw_resp_bits_h_resp_gaf,
            resp_tag=d.io_hptw_resp_bits_h_resp_entry_tag,
            resp_vmid=d.io_hptw_resp_bits_h_resp_entry_vmid,
            resp_ppn=d.io_hptw_resp_bits_h_resp_entry_ppn,
            resp_level=d.io_hptw_resp_bits_h_resp_entry_level,
            resp_n=d.io_hptw_resp_bits_h_resp_entry_n,
            resp_pbmt=d.io_hptw_resp_bits_h_resp_entry_pbmt,
            resp_perm_r=d.io_hptw_resp_bits_h_resp_entry_perm_r,
            resp_perm_w=d.io_hptw_resp_bits_h_resp_entry_perm_w,
            resp_perm_x=d.io_hptw_resp_bits_h_resp_entry_perm_x,
            resp_perm_a=d.io_hptw_resp_bits_h_resp_entry_perm_a,
            resp_perm_d=d.io_hptw_resp_bits_h_resp_entry_perm_d,
        )
        self.bitmap = dict(
            valid=d.io_bitmap_req_valid,
            ready=d.io_bitmap_req_ready,
            bmppn=d.io_bitmap_req_bits_bmppn,
            vpn=d.io_bitmap_req_bits_vpn,
            level=d.io_bitmap_req_bits_level,
            n=d.io_bitmap_req_bits_n,
            s2xlate=d.io_bitmap_req_bits_s2xlate,
            resp_valid=d.io_bitmap_resp_valid,
            resp_ready=d.io_bitmap_resp_ready,
            resp_cf=d.io_bitmap_resp_bits_cf,
        )
        self.refill = dict(
            vpn=d.io_refill_req_info_vpn,
            source=d.io_refill_req_info_source,
            s2xlate=d.io_refill_req_info_s2xlate,
            level=d.io_refill_level,
        )

    async def edge(self) -> None:
        self.dut.RefreshComb()
        accepted = None
        if self._monitor_enabled:
            flushing = self.read(self.sfence) or any(self.read(self.csr[key]) for key in (
                "satp_changed", "vsatp_changed", "hgatp_changed", "virt_changed"))
            if flushing and self._active_request is not None:
                self.walk_completions.append(WalkCompletion(self._active_request, "flush", self.tick+1))
                self._active_request = None
            if (not flushing and self._offered_request is not None
                    and self.read(self.req["valid"]) and self.read(self.req["ready"])):
                accepted = replace(self._offered_request, accepted_tick=self.tick+1,
                                   handoff_start=len(self.llptw_requests))
            if self.read(self.mem_req["valid"]) and self.read(self.mem_req["ready"]):
                address = self.read(self.mem_req["addr"])
                self.requests.append(MemReq(address))
                self._pending_mem.append(self.memory.read(address & ~7, 8))
            if self.read(self.llptw["valid"]) and self.read(self.llptw["ready"]):
                self.llptw_requests.append({key: self.read(self.llptw[key])
                                            for key in ("vpn", "source", "s2xlate")})
            if self.read(self.bitmap["valid"]) and self.read(self.bitmap["ready"]):
                item = {key: self.read(self.bitmap[key])
                        for key in ("bmppn", "vpn", "level", "n", "s2xlate")}
                self.bitmap_requests.append(item)
                self._bitmap_queue.append(item)
            if self.read(self.hptw["valid"]) and self.read(self.hptw["ready"]):
                gvpn = self.read(self.hptw["gvpn"])
                self.hptw_requests.append({"gvpn": gvpn, "source": self.read(self.hptw["source"])})
                if self.hptw_queue:
                    self._hptw_responses.append(self.hptw_queue.pop(0))
                elif self.hptw_identity:
                    self._hptw_responses.append(dict(
                        resp_gpf=0, resp_gaf=0, resp_tag=gvpn, resp_vmid=7,
                        resp_ppn=gvpn, resp_level=0, resp_n=0, resp_pbmt=0,
                        resp_perm_r=1, resp_perm_w=1, resp_perm_x=1,
                        resp_perm_a=1, resp_perm_d=1))
        await RisingEdge(self.dut.clock)
        self.tick += 1
        if accepted is not None:
            self._active_request = accepted
            self._offered_request = None

    def read(self, signal) -> int:
        return int(signal.value)

    def set_csr(self, **values) -> None:
        unknown = [key for key in values
                   if key not in self.csr and key not in self._trimmed_csrs]
        if unknown:
            raise KeyError(unknown[0])
        trimmed = [key for key in values if key in self._trimmed_csrs]
        if trimmed:
            key = trimmed[0]
            raise ValueError(
                f"{key}: {self._trimmed_csrs[key]}; explicit value "
                f"{values[key]!r} is rejected instead of being silently ignored")
        for key, value in values.items():
            self.csr[key].Set(value)
        self.dut.RefreshComb()

    def _register_mxr(self, dut, schema_path) -> None:
        """Bind MXR only when the artifact schema and handle agree.

        The schema is the generated artifact's own ``signals.json``; a Python
        attribute alone is not evidence that a build declares the pin.
        """
        if schema_path is None:
            raise RuntimeError(
                "MXR schema is unavailable: pass the bound artifact signals "
                "schema from the loader; absence of a handle attribute cannot "
                "be generalized into a trimmed-field decision")
        leaves, digest = signal_schema(schema_path)
        declared = MXR_PIN in leaves
        present = hasattr(dut, MXR_PIN)
        self._interface_schema = {
            "path": str(Path(schema_path).resolve()),
            "sha256": digest,
            "mxr_declared": declared,
            "mxr_handle": present,
        }
        if declared and not present:
            raise RuntimeError(
                f"interface binding failure: schema declares {MXR_PIN} but "
                f"the bound handle does not expose it ({schema_path})")
        if present and not declared:
            raise RuntimeError(
                f"interface binding mismatch: handle exposes {MXR_PIN} but "
                f"the artifact schema does not declare it ({schema_path}); "
                "refusing to infer a baseline from the handle")
        if declared:
            self.csr["mxr"] = getattr(dut, MXR_PIN)
            self._mxr_capability = MxrInputCapability(driveable=True)
        else:
            self._trimmed_csrs["mxr"] = TRIMMED_MXR_REASON
            self._mxr_capability = MxrInputCapability(
                driveable=False, reason=TRIMMED_MXR_REASON)

    @property
    def mxr_input_capability(self) -> MxrInputCapability:
        """Fresh immutable capability; never exposes a pin or the CSR dict."""
        current = self._mxr_capability
        return MxrInputCapability(current.driveable, current.reason)

    @property
    def has_mxr_input(self) -> bool:
        return self._mxr_capability.driveable

    async def pulse_csr_change(self, name: str, *, hold: int = 1,
                               settle: int = 0) -> None:
        if name in self._trimmed_csrs:
            raise ValueError(
                f"{name}: {self._trimmed_csrs[name]}; no pulse can be driven")
        if name not in self.csr:
            raise KeyError(name)
        self.csr[name].Set(1)
        for _ in range(hold):
            await self.edge()
        self.csr[name].Set(0)
        for _ in range(settle):
            await self.edge()

    def preload_stage1_hit(self, *, index: int = 0, tag: int | None = None,
                           asid: int | None = None, vmid: int | None = None,
                           n: int | None = None, level: int | None = None,
                           v: int | None = None, ppn: int | None = None,
                           ppn_low: int | None = None, pteidx: int | None = None,
                           perm_r: int | None = None, perm_w: int | None = None,
                           perm_x: int | None = None, perm_u: int | None = None,
                           perm_a: int | None = None, perm_d: int | None = None) -> None:
        """Preload one stage-1 hit entry; every field remains caller-owned."""
        fields = dict(tag=tag, asid=asid, vmid=vmid, n=n, level=level, v=v,
                      ppn=ppn, ppn_low=ppn_low, perm_r=perm_r, perm_w=perm_w,
                      perm_x=perm_x, perm_u=perm_u, perm_a=perm_a, perm_d=perm_d)
        for name, value in fields.items():
            if value is not None:
                key = f"{index}_{name}"
                if key not in self.stage1:
                    raise KeyError(key)
                self.stage1[key].Set(value)
        if pteidx is not None:
            key = f"pteidx_{index}"
            if key not in self.stage1:
                raise KeyError(key)
            self.stage1[key].Set(pteidx)
        self.dut.RefreshComb()

    def set_pmp(self, *, ld: int | None = None, mmio: int | None = None) -> None:
        if ld is not None:
            self.pmp["ld"].Set(ld)
        if mmio is not None:
            self.pmp["mmio"].Set(mmio)
        self.dut.RefreshComb()

    def set_mem_mask(self, value: int) -> None:
        self.mem_mask.Set(value)
        self.dut.RefreshComb()

    def drive_sfence(self, value: int) -> None:
        if value not in (0, 1):
            raise ValueError("sfence valid must be 0 or 1")
        self.sfence.Set(value)
        self.dut.RefreshComb()

    async def pulse_sfence(self, *, hold: int = 1, settle: int = 1,
                            service: bool = False) -> None:
        self.drive_sfence(1)
        for _ in range(hold):
            if service:
                await self.service(1)
            else:
                await self.edge()
        self.drive_sfence(0)
        for _ in range(settle):
            if service:
                await self.service(1)
            else:
                await self.edge()

    def set_llptw_ready(self, value: int) -> None:
        if value not in (0, 1):
            raise ValueError("LLPTW ready must be 0 or 1")
        self.llptw["ready"].Set(value)
        self.dut.RefreshComb()

    def llptw_valid(self) -> int:
        return self.read(self.llptw["valid"])

    def llptw_snapshot(self) -> dict:
        """Fresh scalar handoff snapshot; no live signal is returned."""
        return {key: self.read(signal) for key, signal in self.llptw.items()}

    def queue_hptw_response(self, *, resp_gpf: int = 0, resp_gaf: int = 0,
                            resp_tag: int = 0, resp_vmid: int = 0,
                            resp_ppn: int = 0, resp_level: int = 0,
                            resp_n: int = 0, resp_pbmt: int = 0,
                            resp_perm_r: int = 0, resp_perm_w: int = 0,
                            resp_perm_x: int = 0, resp_perm_a: int = 0,
                            resp_perm_d: int = 0) -> None:
        """Queue one explicit G-stage response for the next HPTW handshake."""
        self.hptw_queue.append(dict(
            resp_gpf=resp_gpf, resp_gaf=resp_gaf, resp_tag=resp_tag,
            resp_vmid=resp_vmid, resp_ppn=resp_ppn, resp_level=resp_level,
            resp_n=resp_n, resp_pbmt=resp_pbmt, resp_perm_r=resp_perm_r,
            resp_perm_w=resp_perm_w, resp_perm_x=resp_perm_x,
            resp_perm_a=resp_perm_a, resp_perm_d=resp_perm_d))

    def set_hptw_identity(self, enabled: bool) -> None:
        self.hptw_identity = bool(enabled)

    def set_bitmap_cf(self, value: int) -> None:
        if value not in (0, 1):
            raise ValueError("bitmap cf must be 0 or 1")
        self.bitmap_cf = value

    def set_resp_ready(self, value: int) -> None:
        if value not in (0, 1):
            raise ValueError("response ready must be 0 or 1")
        self.resp["ready"].Set(value)
        self.dut.RefreshComb()

    def request_ready(self) -> int:
        return self.read(self.req["ready"])

    def response_valid(self) -> int:
        return self.read(self.resp["valid"])

    def response_snapshot(self) -> dict:
        """Fresh nested snapshot: scalar fields plus copied pteidx and h_resp."""
        snap = {key: self.read(sig) for key, sig in self.resp.items()
                if not isinstance(sig, list)}
        snap["pteidx"] = [self.read(sig) for sig in self.resp["pteidx"]]
        for key, sig in self.hresp.items():
            snap[f"h_{key}"] = self.read(sig)
        return snap

    def clear_requests(self) -> None:
        self.requests.clear()

    def clear_llptw_requests(self) -> None:
        self.llptw_requests.clear()

    def clear_pending_memory(self) -> None:
        self._pending_mem.clear()

    def drive_structural_hptw_resp(self, valid: int) -> None:
        """Structural-stress drive of the HPTW response valid level."""
        self.hptw["resp_valid"].Set(valid)
        self.dut.RefreshComb()

    def drive_structural_bitmap_resp(self, valid: int,
                                     cf: int | None = None) -> None:
        """Structural-stress drive of the bitmap response channel.

        Only the fields that are actually arguments are written; ``cf`` is
        left at its current stress level when omitted so clearing ``valid``
        does not silently drop the other payload stimulus. Both declared
        levels are validated before any pin is written, so a rejected call
        leaves the current stimulus untouched.
        """
        if valid not in (0, 1):
            raise ValueError("bitmap resp valid must be 0 or 1")
        if cf is not None and cf not in (0, 1):
            raise ValueError("bitmap resp cf must be 0 or 1")
        self.bitmap["resp_valid"].Set(valid)
        if cf is not None:
            self.bitmap["resp_cf"].Set(cf)
        self.dut.RefreshComb()

    def structural_input_sweep(self, value: int) -> None:
        excluded = [self.dut.clock, self.dut.reset, self.req["valid"],
                    self.resp["ready"], self.mem_req["ready"],
                    self.mem_resp["valid"], self.mem_mask, self.pmp["ld"],
                    self.pmp["mmio"], self.llptw["ready"], self.hptw["ready"],
                    self.hptw["resp_valid"], self.bitmap["ready"],
                    self.bitmap["resp_valid"], self.bitmap["resp_cf"],
                    self.sfence, self.csr["satp_changed"],
                    self.csr["vsatp_changed"], self.csr["hgatp_changed"],
                    self.csr["virt_changed"]]
        sweep_inputs(self.dut, value, excluded)
        self.dut.RefreshComb()


    async def reset(self) -> None:
        self._monitor_enabled = False
        self._pending_mem.clear()
        self._hptw_responses.clear()
        self._bitmap_queue.clear()
        self.requests.clear()
        self.hptw_requests.clear()
        self.llptw_requests.clear()
        self.bitmap_requests.clear()
        self._hptw_pending = None
        self._bitmap_pending = False
        self._offered_request = None
        self._active_request = None
        self._next_sequence = 0
        self.walk_completions.clear()
        for name, signal in self.req.items():
            if name != "ready":
                signal.Set(0)
        for signal in self.stage1.values():
            signal.Set(0)
        for signal in self.csr.values():
            signal.Set(0)
        self.sfence.Set(0)
        self.resp["ready"].Set(0)
        self.mem_req["ready"].Set(1)
        self.mem_resp["valid"].Set(0)
        self.mem_resp["bits"].Set(0)
        self.mem_mask.Set(0)
        self.pmp["ld"].Set(0)
        self.pmp["mmio"].Set(0)
        self.llptw["ready"].Set(1)
        self.hptw["ready"].Set(1)
        self.hptw["resp_valid"].Set(0)
        for key in ("resp_gpf", "resp_gaf", "resp_tag", "resp_vmid", "resp_ppn",
                    "resp_level", "resp_n", "resp_pbmt", "resp_perm_r", "resp_perm_w",
                    "resp_perm_x", "resp_perm_a", "resp_perm_d"):
            self.hptw[key].Set(0)
        self.bitmap["ready"].Set(1)
        self.bitmap["resp_valid"].Set(0)
        self.bitmap["resp_cf"].Set(0)
        self.dut.reset.Set(1)
        await self.edge()
        await self.edge()
        self.dut.reset.Set(0)
        self.sfence.Set(1)
        await self.edge()
        await self.edge()
        self.sfence.Set(0)
        await self.edge()
        assert self.read(self.req["ready"]) == 1
        self._monitor_enabled = True

    async def issue(self, vpn: int, *, s2xlate: int = 0, source: int = 0,
                    l3hit: int = 0, l2hit: int = 0, ppn: int = 0,
                    stage1hit: int = 0, not_super: int = 0,
                    jmp_bitmap: int = 0, bitmap_pte: int = 0,
                    bitmap_splevel: int = 0) -> None:
        if self._active_request is not None or self._offered_request is not None:
            raise RuntimeError("PTW: previous request has no consumed response/handoff or flush")
        values=dict(vpn=vpn,s2xlate=s2xlate,source=source,l3hit=l3hit,l2hit=l2hit,
                    ppn=ppn,stage1hit=stage1hit,not_super=not_super,
                    jmp_bitmap=jmp_bitmap,bitmap_pte=bitmap_pte,bitmap_splevel=bitmap_splevel)
        # Reject truncation before touching any signal; widths come from this DUT.
        for key,value in values.items():
            # xcomm width=0 denotes scalar SV logic, not a zero-bit field.
            # Its 2/3 encodings are Z/X, not legal boolean request values.
            width=max(1,int(self.req[key].mWidth))
            if not isinstance(value,int) or not 0<=value<(1<<width):
                raise ValueError(f"PTW request {key} does not fit {width} bits: {value!r}")
        self._offered_request=WalkRequest(self._next_sequence,vpn,source,s2xlate)
        self._next_sequence+=1
        for key,value in values.items():
            self.req[key].Set(value)
        self.req["valid"].Set(1)
        try:
            for _ in range(2000):
                # service() can change ready combinationally. Only edge()'s
                # pre-edge valid&&ready snapshot establishes acceptance.
                await self.service(1)
                if self._offered_request is None:
                    return
            raise TimeoutError("PTW: input ready timeout")
        finally:
            self._offered_request=None
            self.req["valid"].Set(0)
            for key in values:
                self.req[key].Set(0)

    def _drive_hptw_resp(self, values: dict | None) -> None:
        self.hptw["resp_valid"].Set(1 if values is not None else 0)
        for key in ("resp_gpf", "resp_gaf", "resp_tag", "resp_vmid", "resp_ppn",
                    "resp_level", "resp_n", "resp_pbmt", "resp_perm_r", "resp_perm_w",
                    "resp_perm_x", "resp_perm_a", "resp_perm_d"):
            self.hptw[key].Set(values.get(key, 0) if values else 0)

    async def service(self, cycles: int) -> int:
        before = len(self.requests)
        for _ in range(cycles):
            self.mem_resp["valid"].Set(0)
            self.bitmap["resp_valid"].Set(0)
            self._drive_hptw_resp(None)
            if self._pending_mem:
                self.mem_resp["valid"].Set(1)
                self.mem_resp["bits"].Set(self._pending_mem.pop(0))
            if self._hptw_responses:
                self._drive_hptw_resp(self._hptw_responses.pop(0))
            if self._bitmap_queue:
                self.bitmap["resp_valid"].Set(1)
                self.bitmap["resp_cf"].Set(self.bitmap_cf)
                self.dut.RefreshComb()
                if self.read(self.bitmap["resp_ready"]):
                    self._bitmap_queue.pop(0)
            await self.edge()
            self.mem_resp["valid"].Set(0)
            self.bitmap["resp_valid"].Set(0)
            self._drive_hptw_resp(None)
        return len(self.requests) - before

    async def wait_response(self, max_cycles: int = 2000, note: str = "") -> dict | None:
        request=self._active_request
        if request is None:
            raise RuntimeError(f"{note}: no accepted PTW request awaiting completion")
        # Hold the response to avoid losing it inside the two-edge service helper.
        self.resp["ready"].Set(0)
        for _ in range(max_cycles):
            await self.service(1)
            if self._active_request!=request:
                raise RuntimeError(f"{note}: PTW request was cancelled while awaiting completion")
            if self.read(self.resp["valid"]):
                snap = {key: self.read(sig) for key, sig in self.resp.items()
                        if not isinstance(sig, list)}
                snap["pteidx"] = [self.read(sig) for sig in self.resp["pteidx"]]
                for key, sig in self.hresp.items():
                    snap[f"h_{key}"] = self.read(sig)
                assert (snap["source"],snap["s2xlate"])==(request.source,request.s2xlate), (
                    "PTW response identity mismatch",request,snap)
                if self.coverage is not None:
                    self.sample_response(snap)
                self.resp["ready"].Set(1)
                await self.edge()
                self.resp["ready"].Set(0)
                self.walk_completions.append(WalkCompletion(request,"response",self.tick))
                self._active_request=None
                return snap
            handoffs=self.llptw_requests[request.handoff_start:]
            if handoffs and self.read(self.req["ready"]):
                # A 4KB walk legitimately ends at LLPTW without a PTW response.
                assert len(handoffs)==1, ("duplicate PTW handoff",request,handoffs)
                handoff=handoffs[0]
                assert (handoff["vpn"],handoff["source"],handoff["s2xlate"])==(
                    request.vpn,request.source,request.s2xlate), ("PTW handoff identity mismatch",request,handoff)
                self.walk_completions.append(WalkCompletion(request,"llptw",self.tick))
                self._active_request=None
                return None
        raise TimeoutError(f"{note}: no PTW response; mem={[hex(r.address) for r in self.requests]} "
                           f"llptw={self.llptw_requests}")

    def sample_response(self, snap: dict) -> None:
        if snap.get("0_pf") or snap.get("0_af"):
            self.coverage.sample("fault", page="fault")
        else:
            page = {2: "1g", 1: "2m", 0: "4k"}.get(snap.get("0_level"), "4k")
            self.coverage.sample("walk", page=page)
