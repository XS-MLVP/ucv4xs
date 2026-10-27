"""High-level reference for the TLB (ITLB) parent on the verified storage stack."""
from __future__ import annotations

from dataclasses import dataclass

from ..tlbfa.model import MASK, NO_S2, Context, Refill, TlbfaModel, bits
from ..wrapper.model import WrapperModel


@dataclass
class TlbResponse:
    paddr: int
    miss: int
    pbmt: int
    is_fake_or_nonleaf: int
    pf: int
    af: int
    gpf: int


class TlbModel:
    def __init__(self) -> None:
        self.storage = WrapperModel()
        self.context = Context()
        self.satp_mode = 0
        self.satp_asid = 0
        self.imode = 0
        self.virt = 0
        self.vsatp_mode = 0
        self.hgatp_mode = 0
        self.hgatp_vmid = 0

    def reset(self) -> None:
        self.storage.reset()
        self.context = Context()

    def set_context(self, *, satp_mode: int = 0, satp_asid: int = 0,
                    imode: int = 0, virt: int = 0, vsatp_mode: int = 0,
                    hgatp_mode: int = 0, hgatp_vmid: int = 0) -> None:
        self.satp_mode = satp_mode
        self.satp_asid = satp_asid
        self.imode = imode
        self.virt = virt
        self.vsatp_mode = vsatp_mode
        self.hgatp_mode = hgatp_mode
        self.hgatp_vmid = hgatp_vmid
        self.context.satp_asid = satp_asid & MASK["asid"]
        self.context.vsatp_asid = satp_asid & MASK["asid"]
        self.context.hgatp_vmid = hgatp_vmid & MASK["vmid"]
        self.context.virt = virt
        self.storage.tlbfa.context = self.context

    def translation_enabled(self) -> bool:
        stage1 = self.satp_mode in (8, 9)
        stage2 = bool(self.virt and (self.vsatp_mode in (8, 9) or self.hgatp_mode in (8, 9)))
        return (stage1 or stage2) and self.imode < 3

    def stage_class(self) -> int:
        if not self.virt:
            return NO_S2
        if self.vsatp_mode and self.hgatp_mode:
            return 3
        if not self.vsatp_mode:
            return 2
        return 1

    def _expected_stage2_class(self) -> int:
        return self.stage_class()

    def ptw_request(self, vaddr: int) -> tuple[int, int, int]:
        return (
            (vaddr >> 12) & MASK["vpn"],
            self._expected_stage2_class(),
            0,
        )

    def refill(self, data: Refill) -> int:
        return self.storage.refill(data)

    def sfence(self, rs1: int, rs2: int, addr: int, sfence_id: int,
               hv: int = 0, hg: int = 0) -> None:
        self.storage.tlbfa.apply_sfence(
            1, rs1, rs2, addr, sfence_id, hv, hg, self.context
        )

    def translate(self, vaddr: int) -> TlbResponse:
        vaddr &= MASK["vpn"] << 12 | 0xFFF
        off = vaddr & 0xFFF
        if not self.translation_enabled():
            return TlbResponse(vaddr, 0, 0, 0, 0, 0, 0)
        vpn = vaddr >> 12
        stage = self.stage_class()
        expected = self.storage.tlbfa.lookup(vpn, stage)
        if not expected.hit:
            return TlbResponse(off, 1, 0, 1, 0, 0, 0)
        entry = self.storage.tlbfa.entries[expected.way]
        assert entry is not None
        ppn = TlbfaModel.gen_ppn(entry, vpn)
        if stage == 3 or stage == 2:
            # A clean two-stage leaf returns the merged/G-stage PPN and the
            # G-stage PBMT; fault composition is covered by the leaf tests.
            return TlbResponse(
                paddr=((ppn << 12) | off) & ((1 << 48) - 1),
                miss=0,
                pbmt=entry.g_pbmt,
                is_fake_or_nonleaf=0,
                pf=0,
                af=0,
                gpf=0,
            )
        mode_ok = (self.imode == 0 and entry.perm["u"] == 1) or (
            self.imode == 1 and entry.perm["u"] == 0
        )
        fake = (
            entry.perm["v"] == 0
            and entry.perm["pf"] == 0
            and entry.perm["af"] == 0
        )
        nonleaf = (
            not (entry.perm["r"] or entry.perm["w"] or entry.perm["x"])
            and entry.perm["v"] == 1
            and entry.perm["pf"] == 0
            and entry.perm["af"] == 0
        )
        af = int(entry.perm["af"])
        perm_fail = int(not (mode_ok and entry.perm["x"]))
        pf = int(
            bool(
                (entry.perm["pf"] or perm_fail or not entry.perm["a"])
                and not af
                and not fake
                and not nonleaf
            )
        )
        return TlbResponse(
            paddr=((ppn << 12) | off) & ((1 << 48) - 1),
            miss=0,
            pbmt=entry.pbmt,
            is_fake_or_nonleaf=int(fake or nonleaf),
            pf=pf,
            af=af,
            gpf=0,
        )
