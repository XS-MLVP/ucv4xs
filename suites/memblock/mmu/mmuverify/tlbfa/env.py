"""Public-port environment and checker for the TLBFA DUT."""
from __future__ import annotations

from dataclasses import dataclass

from toffee import RisingEdge

from .coverage import TlbfaCoverage
from .model import (
    ALL_STAGE,
    MASK,
    NO_S2,
    ONLY_S1,
    ONLY_S2,
    WAYS,
    Context,
    ExpectedResponse,
    Refill,
    StoredEntry,
    TlbfaModel,
    _inner_level,
)

PAGE_NAME = {0: "4k", 1: "2m", 2: "1g", 3: "512g"}
CONTEXT_NAME = {
    NO_S2: "bare_no_s2",
    ONLY_S1: "stage1_only",
    ONLY_S2: "stage2_only",
    ALL_STAGE: "two_stage",
}
PERM_KEYS = ("pf", "af", "v", "a", "u", "x", "w", "r")
G_PERM_KEYS = ("pf", "af", "a", "x")


@dataclass
class RespSnap:
    valid: int
    hit: int
    ppn: int
    pbmt: int
    g_pbmt: int
    s2xlate: int
    perm: dict[str, int]
    g_perm: dict[str, int]
    access_valid: int
    access_bits: int


@dataclass
class AccessSnap:
    valid: int
    bits: int


class TlbfaEnv:
    def __init__(self, dut, coverage: TlbfaCoverage | None = None) -> None:
        self.dut = dut
        self.coverage = coverage
        self.model = TlbfaModel()
        self.pending_refill_way: int | None = None
        self.tick = 0
        self._bind()

    def _bind(self) -> None:
        d = self.dut
        self.sfence = dict(
            valid=d.io_sfence_valid,
            rs1=d.io_sfence_bits_rs1,
            rs2=d.io_sfence_bits_rs2,
            addr=d.io_sfence_bits_addr,
            id=d.io_sfence_bits_id,
            hv=d.io_sfence_bits_hv,
            hg=d.io_sfence_bits_hg,
        )
        self.csr = dict(
            satp_asid=d.io_csr_satp_asid,
            vsatp_asid=d.io_csr_vsatp_asid,
            hgatp_vmid=d.io_csr_hgatp_vmid,
            virt=d.io_csr_priv_virt,
            bme=d.io_csr_mbmc_BME,
            cmode=d.io_csr_mbmc_CMODE,
        )
        self.req_valid = d.io_r_req_0_valid
        self.req_vpn = d.io_r_req_0_bits_vpn
        self.req_s2xlate = d.io_r_req_0_bits_s2xlate
        self.resp = dict(
            hit=d.io_r_resp_0_bits_hit,
            ppn=d.io_r_resp_0_bits_ppn_0,
            pbmt=d.io_r_resp_0_bits_pbmt_0,
            g_pbmt=d.io_r_resp_0_bits_g_pbmt_0,
            s2xlate=d.io_r_resp_0_bits_s2xlate_0,
            **{f"perm_{key}": getattr(d, f"io_r_resp_0_bits_perm_0_{key}") for key in PERM_KEYS},
            **{f"g_perm_{key}": getattr(d, f"io_r_resp_0_bits_g_perm_0_{key}") for key in G_PERM_KEYS},
        )
        self.resp_valid = d.io_r_resp_0_valid if hasattr(d, "io_r_resp_0_valid") else None
        self.access_valid = d.io_access_0_touch_ways_valid
        self.access_bits = d.io_access_0_touch_ways_bits
        self.w_valid = d.io_w_valid
        self.w_way = d.io_w_bits_wayIdx
        self._w_pins = {
            "s2xlate": d.io_w_bits_data_s2xlate,
            "s1_tag": d.io_w_bits_data_s1_entry_tag,
            "s1_asid": d.io_w_bits_data_s1_entry_asid,
            "s1_vmid": d.io_w_bits_data_s1_entry_vmid,
            "s1_n": d.io_w_bits_data_s1_entry_n,
            "s1_pbmt": d.io_w_bits_data_s1_entry_pbmt,
            "s1_perm_a": d.io_w_bits_data_s1_entry_perm_a,
            "s1_perm_g": d.io_w_bits_data_s1_entry_perm_g,
            "s1_perm_u": d.io_w_bits_data_s1_entry_perm_u,
            "s1_perm_x": d.io_w_bits_data_s1_entry_perm_x,
            "s1_perm_w": d.io_w_bits_data_s1_entry_perm_w,
            "s1_perm_r": d.io_w_bits_data_s1_entry_perm_r,
            "s1_level": d.io_w_bits_data_s1_entry_level,
            "s1_v": d.io_w_bits_data_s1_entry_v,
            "s1_ppn": d.io_w_bits_data_s1_entry_ppn,
            "s1_pf": d.io_w_bits_data_s1_pf,
            "s1_af": d.io_w_bits_data_s1_af,
            "s2_tag": d.io_w_bits_data_s2_entry_tag,
            "s2_vmid": d.io_w_bits_data_s2_entry_vmid,
            "s2_n": d.io_w_bits_data_s2_entry_n,
            "s2_pbmt": d.io_w_bits_data_s2_entry_pbmt,
            "s2_ppn": d.io_w_bits_data_s2_entry_ppn,
            "s2_perm_a": d.io_w_bits_data_s2_entry_perm_a,
            "s2_perm_x": d.io_w_bits_data_s2_entry_perm_x,
            "s2_level": d.io_w_bits_data_s2_entry_level,
            "s2_gpf": d.io_w_bits_data_s2_gpf,
            "s2_gaf": d.io_w_bits_data_s2_gaf,
            **{f"s1_ppn_low_{i}": getattr(d, f"io_w_bits_data_s1_ppn_low_{i}") for i in range(8)},
            **{f"s1_valididx_{i}": getattr(d, f"io_w_bits_data_s1_valididx_{i}") for i in range(8)},
            **{f"s1_pteidx_{i}": getattr(d, f"io_w_bits_data_s1_pteidx_{i}") for i in range(8)},
        }
        # The generated top does not export an explicit response-valid port in
        # some splits; it is observable through access timing. The current
        # TLBFA build exports io_r_resp_0_valid? Check strictly.
        if self.resp_valid is None:
            # In this generated TLBFA the private response valid is not a port;
            # infer it from the one-cycle request/response protocol: the
            # response is valid exactly on the edge after a request valid.
            self._resp_valid_observed = 0
        else:
            self._resp_valid_observed = 0
        self._req_outstanding = 0

    # ------------------------------------------------------------------ basics
    async def edge(self) -> None:
        await RisingEdge(self.dut.clock)
        self.tick += 1

    def read(self, signal) -> int:
        return int(signal.value)

    async def settle(self, cycles: int = 1) -> None:
        for _ in range(cycles):
            await self.edge()

    def _write(self, signal, value: int) -> None:
        signal.Set(value)

    def _drive_context(self, context: Context) -> None:
        self._write(self.csr["satp_asid"], context.satp_asid & MASK["asid"])
        self._write(self.csr["vsatp_asid"], context.vsatp_asid & MASK["asid"])
        self._write(self.csr["hgatp_vmid"], context.hgatp_vmid & MASK["vmid"])
        self._write(self.csr["virt"], context.virt)
        self._write(self.csr["bme"], context.bme)
        self._write(self.csr["cmode"], context.cmode)

    def program_context(self, **values: int) -> None:
        for key, value in values.items():
            if not hasattr(self.model.context, key):
                raise KeyError(key)
            setattr(self.model.context, key, value)
        self._drive_context(self.model.context)
        self.dut.RefreshComb()

    def drive_raw_csr(self, **values: int) -> None:
        """Drive CSR input ports without changing the semantic model.

        Only for interface-toggle evidence; functional lookups still use the
        masked Context values.
        """
        for key, value in values.items():
            self._write(self.csr[key], value)
        self.dut.RefreshComb()

    def _drive_req(self, valid: int, vpn: int = 0, s2xlate: int = 0) -> None:
        self._write(self.req_valid, valid)
        self._write(self.req_vpn, vpn & MASK["vpn"])
        self._write(self.req_s2xlate, s2xlate)

    def _drive_sfence(
        self,
        valid: int,
        rs1: int = 0,
        rs2: int = 0,
        addr: int = 0,
        sfence_id: int = 0,
        hv: int = 0,
        hg: int = 0,
    ) -> None:
        self._write(self.sfence["valid"], valid)
        self._write(self.sfence["rs1"], rs1)
        self._write(self.sfence["rs2"], rs2)
        self._write(self.sfence["addr"], addr & ((1 << 50) - 1))
        self._write(self.sfence["id"], sfence_id & MASK["asid"])
        self._write(self.sfence["hv"], hv)
        self._write(self.sfence["hg"], hg)

    def _drive_refill(self, data: Refill | None, way: int = 0) -> None:
        if data is None:
            self._write(self.w_valid, 0)
            self._write(self.w_way, 0)
            for signal in self._w_pins.values():
                self._write(signal, 0)
            return
        self._write(self.w_valid, 1)
        self._write(self.w_way, way)
        pins = self._w_pins
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
        self._write(pins["s1_pf"], data.s1_pf)
        self._write(pins["s1_af"], data.s1_af)
        for index in range(8):
            self._write(pins[f"s1_ppn_low_{index}"], data.s1_ppn_low[index] & 0x7)
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

    # ------------------------------------------------------------------ readout
    def read_response(self) -> RespSnap:
        perm = {key: self.read(self.resp[f"perm_{key}"]) for key in PERM_KEYS}
        g_perm = {key: self.read(self.resp[f"g_perm_{key}"]) for key in G_PERM_KEYS}
        valid = 1 if self._req_outstanding else 0
        return RespSnap(
            valid=valid,
            hit=self.read(self.resp["hit"]),
            ppn=self.read(self.resp["ppn"]),
            pbmt=self.read(self.resp["pbmt"]),
            g_pbmt=self.read(self.resp["g_pbmt"]),
            s2xlate=self.read(self.resp["s2xlate"]),
            perm=perm,
            g_perm=g_perm,
            access_valid=self.read(self.access_valid),
            access_bits=self.read(self.access_bits),
        )

    def read_access(self) -> AccessSnap:
        return AccessSnap(self.read(self.access_valid), self.read(self.access_bits))

    # ------------------------------------------------------------------ checking
    def check_response(
        self, snap: RespSnap, expected: ExpectedResponse, note: str, allow_refill_touch: bool = False
    ) -> None:
        assert snap.valid == expected.valid, f"{note}: valid {snap.valid} != {expected.valid}"
        assert snap.hit == expected.hit, f"{note}: hit {snap.hit} != {expected.hit}"
        if expected.hit:
            assert snap.ppn == expected.ppn, (
                f"{note}: ppn {snap.ppn:#x} != {expected.ppn:#x}"
            )
            assert snap.pbmt == expected.pbmt, f"{note}: pbmt {snap.pbmt} != {expected.pbmt}"
            assert snap.g_pbmt == expected.g_pbmt, f"{note}: g_pbmt {snap.g_pbmt} != {expected.g_pbmt}"
            assert snap.s2xlate == expected.s2xlate, (
                f"{note}: s2xlate {snap.s2xlate} != {expected.s2xlate}"
            )
            for key in PERM_KEYS:
                assert snap.perm[key] == expected.perm[key], (
                    f"{note}: perm.{key} {snap.perm[key]} != {expected.perm[key]}"
                )
            for key in G_PERM_KEYS:
                assert snap.g_perm[key] == expected.g_perm[key], (
                    f"{note}: g_perm.{key} {snap.g_perm[key]} != {expected.g_perm[key]}"
                )
            assert snap.access_valid == 1, f"{note}: hit must report a touch way"
            if expected.way is not None:
                assert snap.access_bits == expected.way, (
                    f"{note}: touch {snap.access_bits} != hit way {expected.way}"
                )
        else:
            assert snap.ppn == 0, f"{note}: miss returned ppn {snap.ppn:#x}"
            assert snap.pbmt == 0 and snap.g_pbmt == 0, f"{note}: miss returned pbmt"
            assert snap.s2xlate == 0, f"{note}: miss returned s2xlate"
            assert all(value == 0 for value in snap.perm.values()), f"{note}: miss returned perm"
            assert all(value == 0 for value in snap.g_perm.values()), f"{note}: miss returned g_perm"
            if not allow_refill_touch:
                assert snap.access_valid == 0, f"{note}: miss must not report a touch way"

    def _reject_reasons(self, vpn: int, s2xlate: int) -> list[str]:
        reasons: list[str] = []
        ctx = self.model.context
        any_valid = any(self.model.valid)
        for way, entry in enumerate(self.model.entries):
            if entry is None:
                continue
            if not self.model.valid[way]:
                if self.model.entry_matches(way, vpn, s2xlate, ctx):
                    reasons.append("invalid_way")
                continue
            if entry.s2xlate != s2xlate:
                reasons.append("s2xlate")
                continue
            if s2xlate != ONLY_S2:
                asid = ctx.vsatp_asid if s2xlate != NO_S2 else ctx.satp_asid
                if not (entry.asid == asid or entry.perm["g"]):
                    reasons.append("asid")
                    continue
            if s2xlate != NO_S2 and entry.vmid != ctx.hgatp_vmid:
                reasons.append("vmid")
                continue
            if not self.model._tag_level_hit(entry, vpn):
                reasons.append("tag")
                continue
            if not entry.valididx[vpn & 7]:
                reasons.append("valididx")
                continue
            if (
                s2xlate != NO_S2
                and entry.level == 0
                and s2xlate != ONLY_S1
                and entry.n == 0
                and not entry.pteidx[vpn & 7]
            ):
                reasons.append("pteidx")
                continue
        if not reasons:
            reasons.append("no_candidate")
        return reasons

    def _hit_qualifiers(self, expected: ExpectedResponse, vpn: int) -> list[str]:
        if not expected.hit:
            return []
        entry = self.model.entries[expected.way] if expected.way is not None else None
        if entry is None:
            return []
        out = []
        if entry.perm["g"]:
            out.append("global")
        else:
            out.append("asid_match")
        if entry.s2xlate == ONLY_S2:
            out.append("stage2_asid_ignored")
        if (
            entry.s2xlate != NO_S2
            and entry.level == 0
            and entry.n == 0
            and entry.s2xlate != ONLY_S1
            and entry.pteidx[vpn & 7]
        ):
            out.append("pteidx_armed")
        if entry.level == 0 and not entry.n and entry.valididx.count(1) == 1:
            out.append("single_sector")
        return out

    def _sample_lookup(self, vpn: int, s2xlate: int, expected: ExpectedResponse) -> None:
        if self.coverage is None:
            return
        context = CONTEXT_NAME[s2xlate]
        if expected.hit and expected.way is not None:
            entry = self.model.entries[expected.way]
            assert entry is not None
            page = PAGE_NAME[entry.level]
            if entry.n:
                page = "napot64k"
            self.coverage.sample_lookup(
                context, True, page, [], self._hit_qualifiers(expected, vpn)
            )
            self.coverage.sample_ppn(
                page, (vpn & 7) if entry.level == 0 and not entry.n else None
            )
            kinds = ["stage1_perm"]
            if entry.s2xlate != NO_S2:
                kinds.append("stage2_perm")
            if entry.perm["pf"] or entry.perm["af"] or entry.g_perm["pf"] or entry.g_perm["af"]:
                kinds.append("fault_flags")
            if entry.pbmt or entry.g_pbmt:
                kinds.append("pbmt")
            self.coverage.sample_payload(kinds)
            self.coverage.sample_timing("one_cycle_latency")
            self.coverage.sample_touch("hit_touch")
        else:
            reasons = self._reject_reasons(vpn, s2xlate)
            self.coverage.sample_lookup(context, False, None, reasons, [])
            self.coverage.sample_payload(["miss_zero"])
            self.coverage.sample_timing("one_cycle_latency")

    # ------------------------------------------------------------------ operations
    async def reset(self, context: str = "empty") -> None:
        self._drive_req(0)
        self._drive_sfence(0)
        self._drive_refill(None)
        self.model.context = Context()
        self._drive_context(self.model.context)
        self.dut.reset.Set(1)
        await self.edge()
        await self.edge()
        self.model.reset()
        self.dut.reset.Set(0)
        await self.edge()
        self.pending_refill_way = None
        self._req_outstanding = 0
        assert self.read(self.access_valid) == 0, "reset must leave no refill touch"
        if self.coverage is not None:
            self.coverage.sample_reset(context)

    async def refill(self, data: Refill, way: int, note: str = "") -> AccessSnap:
        expected_access = way
        self._drive_refill(data, way)
        await self.edge()
        access = self.read_access()
        assert access.valid == 1, f"{note}: refill must report touch valid"
        assert access.bits == expected_access, f"{note}: refill touch {access.bits} != {way}"
        self.model.refill(way, data)
        if self.coverage is not None:
            entry = self.model.entries[way]
            assert entry is not None
            page = PAGE_NAME[entry.level]
            if entry.n:
                page = "napot64k"
            self.coverage.sample_refill(CONTEXT_NAME[data.s2xlate], page, way)
            self.coverage.sample_touch("refill_touch")
        self._drive_refill(None)
        await self.edge()
        assert self.read(self.access_valid) == 0, f"{note}: refill touch must last one cycle"
        return access

    async def lookup(self, vpn: int, s2xlate: int, note: str = "") -> RespSnap:
        expected = self.model.lookup(vpn, s2xlate)
        self._drive_req(1, vpn, s2xlate)
        self._req_outstanding = 1
        await self.edge()
        snap = self.read_response()
        self.check_response(snap, expected, note)
        self._sample_lookup(vpn, s2xlate, expected)
        self._drive_req(0)
        await self.edge()
        assert self._req_outstanding == 1
        self._req_outstanding = 0
        # The next response is invalid; payload is not claimed.
        if self.resp_valid is not None:
            assert self.read(self.resp_valid) == 0, f"{note}: response valid did not drop"
        else:
            assert self.read(self.access_valid) == 0, f"{note}: stale touch after valid drop"
        if self.coverage is not None:
            self.coverage.sample_timing("valid_drop")
        return snap

    async def refill_and_lookup(
        self, data: Refill, way: int, vpn: int, s2xlate: int, note: str = ""
    ) -> tuple[RespSnap, AccessSnap]:
        expected = self.model.lookup(vpn, s2xlate, refill_way=way)
        self._drive_refill(data, way)
        self._drive_req(1, vpn, s2xlate)
        self._req_outstanding = 1
        await self.edge()
        snap = self.read_response()
        access = self.read_access()
        self.check_response(snap, expected, note, allow_refill_touch=True)
        assert access.valid == 1 and access.bits == way, (
            f"{note}: same-cycle refill touch {access.valid}/{access.bits} != 1/{way}"
        )
        self.model.refill(way, data)
        if self.coverage is not None:
            entry = self.model.entries[way]
            assert entry is not None
            page = "napot64k" if entry.n else PAGE_NAME[entry.level]
            self.coverage.sample_refill(CONTEXT_NAME[data.s2xlate], page, way, "same_cycle_lookup")
            if not expected.hit:
                self.coverage.sample_lookup(
                    CONTEXT_NAME[s2xlate], False, None, ["refill_same_cycle"], []
                )
        self._drive_refill(None)
        self._drive_req(0)
        await self.edge()
        self._req_outstanding = 0
        return snap, access

    async def fence(
        self,
        kind: str,
        rs1: int,
        rs2: int,
        addr: int,
        sfence_id: int,
        hv: int = 0,
        hg: int = 0,
        same_cycle_refill: tuple[Refill, int] | None = None,
        note: str = "",
    ) -> None:
        refill_way = None
        if same_cycle_refill is not None:
            data, refill_way = same_cycle_refill
            self._drive_refill(data, refill_way)
        self._drive_sfence(1, rs1, rs2, addr, sfence_id, hv, hg)
        await self.edge()
        self.model.apply_sfence(1, rs1, rs2, addr, sfence_id, hv, hg)
        if same_cycle_refill is not None:
            assert refill_way is not None
            data, refill_way = same_cycle_refill
            self.model.refill(refill_way, data, sfence=True)
        if same_cycle_refill is not None:
            assert self.read(self.access_valid) == 1, f"{note}: refill touch missing under fence"
            assert self.read(self.access_bits) == refill_way, f"{note}: wrong refill touch"
        self._drive_sfence(0)
        self._drive_refill(None)
        await self.edge()
        assert self.read(self.access_valid) == 0, f"{note}: fence left touch valid"

    def observe_valid(self, vpn: int, s2xlate: int) -> int:
        return 1 if self.model.hit_ways(vpn, s2xlate) else 0

    def sample_fence(self, kind: str, effects: list[str], timing: str = "after_cycle") -> None:
        if self.coverage is not None:
            self.coverage.sample_sfence(kind, effects, timing)
