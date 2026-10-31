"""Public-port environment for TlbStorageWrapper (real TLBFA child + PLRU)."""
from __future__ import annotations

from dataclasses import dataclass

from toffee import RisingEdge

from ..tlbfa.env import CONTEXT_NAME, PAGE_NAME, RespSnap, PERM_KEYS, G_PERM_KEYS
from ..tlbfa.model import MASK, NO_S2, Context, ExpectedResponse, Refill, TlbfaModel
from .model import WrapperModel


@dataclass
class WrapperProbe:
    vpn: int
    s2xlate: int
    hit: int


class WrapperEnv:
    def __init__(self, dut, coverage=None) -> None:
        self.dut = dut
        self.coverage = coverage
        self.model = WrapperModel()
        self._req_outstanding = 0
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
        self.w_valid = d.io_w_valid
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
        for key, value in values.items():
            self._write(self.csr[key], value)
        self.dut.RefreshComb()

    def _drive_req(self, valid: int, vpn: int = 0, s2xlate: int = 0) -> None:
        self._write(self.req_valid, valid)
        self._write(self.req_vpn, vpn & MASK["vpn"])
        self._write(self.req_s2xlate, s2xlate)

    def _drive_sfence(self, valid: int, rs1: int = 0, rs2: int = 0, addr: int = 0,
                      sfence_id: int = 0, hv: int = 0, hg: int = 0) -> None:
        self._write(self.sfence["valid"], valid)
        self._write(self.sfence["rs1"], rs1)
        self._write(self.sfence["rs2"], rs2)
        self._write(self.sfence["addr"], addr & ((1 << 50) - 1))
        self._write(self.sfence["id"], sfence_id & MASK["asid"])
        self._write(self.sfence["hv"], hv)
        self._write(self.sfence["hg"], hg)

    def _drive_refill(self, data: Refill | None) -> None:
        if data is None:
            self._write(self.w_valid, 0)
            for signal in self._w_pins.values():
                self._write(signal, 0)
            return
        self._write(self.w_valid, 1)
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

    def read_response(self) -> RespSnap:
        perm = {key: self.read(self.resp[f"perm_{key}"]) for key in PERM_KEYS}
        g_perm = {key: self.read(self.resp[f"g_perm_{key}"]) for key in G_PERM_KEYS}
        return RespSnap(
            valid=1 if self._req_outstanding else 0,
            hit=self.read(self.resp["hit"]),
            ppn=self.read(self.resp["ppn"]),
            pbmt=self.read(self.resp["pbmt"]),
            g_pbmt=self.read(self.resp["g_pbmt"]),
            s2xlate=self.read(self.resp["s2xlate"]),
            perm=perm,
            g_perm=g_perm,
            access_valid=0,
            access_bits=0,
        )

    def _check(self, snap: RespSnap, expected: ExpectedResponse, note: str) -> None:
        assert snap.valid == expected.valid, f"{note}: valid"
        assert snap.hit == expected.hit, f"{note}: hit {snap.hit} != {expected.hit}"
        if expected.hit:
            assert snap.ppn == expected.ppn, f"{note}: ppn {snap.ppn:#x} != {expected.ppn:#x}"
            assert snap.pbmt == expected.pbmt, f"{note}: pbmt"
            assert snap.g_pbmt == expected.g_pbmt, f"{note}: g_pbmt"
            assert snap.s2xlate == expected.s2xlate, f"{note}: s2xlate"
            for key in PERM_KEYS:
                assert snap.perm[key] == expected.perm[key], f"{note}: perm.{key}"
            for key in G_PERM_KEYS:
                assert snap.g_perm[key] == expected.g_perm[key], f"{note}: g_perm.{key}"
        else:
            assert snap.ppn == 0 and snap.pbmt == 0 and snap.g_pbmt == 0
            assert snap.s2xlate == 0
            assert all(value == 0 for value in snap.perm.values())
            assert all(value == 0 for value in snap.g_perm.values())

    async def reset(self, context: str = "empty") -> None:
        self._drive_req(0)
        self._drive_sfence(0)
        self._drive_refill(None)
        self.model.tlbfa.context = Context()
        self._drive_context(self.model.context)
        self.dut.reset.Set(1)
        await self.edge()
        await self.edge()
        self.model.reset()
        self.dut.reset.Set(0)
        await self.edge()
        self._req_outstanding = 0
        if self.coverage is not None:
            self.coverage.sample_reset(context)

    async def refill(self, data: Refill, note: str = "") -> int:
        victim = self.model.victim()
        self._drive_refill(data)
        await self.edge()
        was_valid = self.model.tlbfa.valid[victim]
        self.model.refill(data)
        if self.coverage is not None:
            self.coverage.sample_refill(
                victim,
                "valid" if was_valid else "invalid",
                self.model.tlbfa.entries[victim],
            )
        self._drive_refill(None)
        await self.edge()
        return victim

    async def lookup(self, vpn: int, s2xlate: int, note: str = "") -> RespSnap:
        expected = self.model.tlbfa.lookup(vpn, s2xlate)
        self._drive_req(1, vpn, s2xlate)
        self._req_outstanding = 1
        await self.edge()
        snap = self.read_response()
        self._check(snap, expected, note)
        self.model.lookup(vpn, s2xlate)
        if self.coverage is not None:
            self.coverage.sample_lookup(
                CONTEXT_NAME[s2xlate], bool(expected.hit), expected.way
            )
        self._drive_req(0)
        await self.edge()
        self._req_outstanding = 0
        if self.coverage is not None:
            self.coverage.timing.sample({"response": "valid_drop"}, details=False)
        return snap

    async def refill_and_lookup(self, data: Refill, vpn: int, s2xlate: int, note: str = ""):
        victim = self.model.victim()
        expected = self.model.tlbfa.lookup(vpn, s2xlate, refill_way=victim)
        self._drive_refill(data)
        self._drive_req(1, vpn, s2xlate)
        self._req_outstanding = 1
        await self.edge()
        snap = self.read_response()
        self._check(snap, expected, note)
        self.model.refill(data)
        if self.coverage is not None:
            self.coverage.sample_same_cycle(victim)
        self._drive_refill(None)
        self._drive_req(0)
        await self.edge()
        self._req_outstanding = 0
        return snap

    async def fence(self, kind: str, rs1: int, rs2: int, addr: int, sfence_id: int,
                    hv: int = 0, hg: int = 0, note: str = "") -> None:
        self._drive_sfence(1, rs1, rs2, addr, sfence_id, hv, hg)
        await self.edge()
        self.model.tlbfa.apply_sfence(1, rs1, rs2, addr, sfence_id, hv, hg)
        self._drive_sfence(0)
        await self.edge()

    def sample_fence(self, kind: str, effects: list[str]) -> None:
        if self.coverage is not None:
            self.coverage.sample_fence(kind, effects)

    async def probe(self, pairs: list[tuple[int, int]]) -> list[WrapperProbe]:
        out = []
        for vpn, s2xlate in pairs:
            snap = await self.lookup(vpn, s2xlate, "probe")
            out.append(WrapperProbe(vpn, s2xlate, snap.hit))
        return out
