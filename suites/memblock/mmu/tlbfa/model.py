"""Independent behavioural model of the generated TLBFA storage leaf.

The model is written from the microarchitectural contract in
docs/functional-points-tlbfa.md and the generated RTL's observable behaviour.
It does not import or reuse any RTL, DUT or sibling-project model.
"""
from __future__ import annotations

from dataclasses import dataclass, field

WAYS = 48
VPN_BITS = 38
PPN_BITS = 36
ASID_BITS = 16
VMID_BITS = 14
LEVELS = 3

NO_S2 = 0
ONLY_S1 = 1
ONLY_S2 = 2
ALL_STAGE = 3

MASK = {
    "vpn": (1 << VPN_BITS) - 1,
    "ppn": (1 << PPN_BITS) - 1,
    "pte_ppn": (1 << 41) - 1,
    "tag": (1 << 35) - 1,
    "gvpn_tag": (1 << 38) - 1,
    "asid": (1 << ASID_BITS) - 1,
    "vmid": (1 << VMID_BITS) - 1,
}


def bits(value: int, hi: int, lo: int) -> int:
    return (value >> lo) & ((1 << (hi - lo + 1)) - 1)


@dataclass
class Refill:
    """One PTW response as seen by the refill port.

    s1.* describes the VS-stage leaf/sector; s2.* describes the G-stage result.
    Fields not relevant for a particular s2xlate value are still carried so the
    model can represent the full port and expose illegal/irrelevant inputs.
    """

    s2xlate: int = NO_S2
    s1_tag: int = 0
    s1_asid: int = 0
    s1_vmid: int = 0
    s1_n: int = 0
    s1_pbmt: int = 0
    s1_level: int = 0
    s1_v: int = 1
    s1_ppn: int = 0
    s1_ppn_low: tuple[int, ...] = (0,) * 8
    s1_valididx: tuple[int, ...] = (1, 1, 1, 1, 1, 1, 1, 1)
    s1_pteidx: tuple[int, ...] = (1, 0, 0, 0, 0, 0, 0, 0)
    s1_pf: int = 0
    s1_af: int = 0
    s1_perm_a: int = 1
    s1_perm_d: int = 1
    s1_perm_g: int = 0
    s1_perm_u: int = 1
    s1_perm_x: int = 0
    s1_perm_w: int = 0
    s1_perm_r: int = 1
    s2_tag: int = 0
    s2_vmid: int = 0
    s2_n: int = 0
    s2_pbmt: int = 0
    s2_ppn: int = 0
    s2_level: int = 0
    s2_gpf: int = 0
    s2_gaf: int = 0
    s2_perm_a: int = 1
    s2_perm_d: int = 1
    s2_perm_r: int = 1
    s2_perm_w: int = 1
    s2_perm_x: int = 0


@dataclass
class StoredEntry:
    s2xlate: int
    tag: int
    asid: int
    level: int
    ppn: int
    n: int
    pbmt: int
    g_pbmt: int
    perm: dict[str, int]
    valididx: tuple[int, ...]
    pteidx: tuple[int, ...]
    ppn_low: tuple[int, ...]
    g_perm: dict[str, int]
    vmid: int


def _inner_level(data: Refill) -> int:
    if data.s2xlate != ALL_STAGE:
        return {
            NO_S2: data.s1_level,
            ONLY_S1: data.s1_level,
            ONLY_S2: data.s2_level,
        }[data.s2xlate]
    s1_fake = not data.s1_pf and not data.s1_v and not data.s1_af
    s1_exception = (data.s1_pf or data.s1_af) and not s1_fake
    s2_exception = data.s2_gpf or data.s2_gaf
    s1_leaf = bool((data.s1_perm_r or data.s1_perm_x or data.s1_perm_w) and data.s1_v)
    merge = min(data.s1_level, data.s2_level)
    if s1_exception or (s2_exception and not s1_leaf):
        return data.s1_level
    if s2_exception and s1_fake:
        return 3
    return merge


def _all_stage_n(data: Refill) -> int:
    return int(
        (data.s1_n != 0 and data.s2_level != 0)
        or (data.s2_n != 0 and data.s1_level != 0)
        or (data.s1_n != 0 and data.s2_n != 0)
    )


def _stored_ppn(data: Refill, level: int) -> int:
    if data.s2xlate in (NO_S2, ONLY_S1):
        return data.s1_ppn & ((1 << 33) - 1)
    # Generated RTL recombines the G-stage PPN with the GPA tag slice selected
    # by the G-stage level (not the merged stage-1/stage-2 level).
    tag = data.s2_tag
    ppn = data.s2_ppn
    level = data.s2_level
    if level == 3:
        return (bits(ppn, 35, 27) << 24) | bits(tag, 26, 3)
    if level == 2:
        return (bits(ppn, 35, 18) << 15) | bits(tag, 17, 3)
    if level == 1:
        return (bits(ppn, 35, 9) << 6) | bits(tag, 8, 3)
    if data.s2_n:
        return (bits(ppn, 35, 4) << 1) | bits(tag, 3, 3)
    return bits(ppn, 35, 3)


def _s2_low(data: Refill) -> int:
    if data.s2_level == 0 and data.s2_n == 0:
        return data.s2_ppn & 0x7
    return data.s2_tag & 0x7


def make_stored(data: Refill) -> StoredEntry:
    level = _inner_level(data)
    if data.s2xlate == ALL_STAGE:
        n = _all_stage_n(data)
    elif data.s2xlate == ONLY_S2:
        n = data.s2_n
    else:
        n = data.s1_n
    is_super = level != 0 or n != 0
    if data.s2xlate == ONLY_S2:
        onehot = 1 << (data.s2_tag & 0x7)
        valididx = tuple((onehot >> i) & 1 for i in range(8))
        pteidx = tuple((onehot >> i) & 1 for i in range(8))
    else:
        valididx = (1,) * 8 if is_super else tuple(data.s1_valididx)
        pteidx = tuple(data.s1_pteidx)
    if data.s2xlate in (NO_S2, ONLY_S1):
        ppn_low = tuple(data.s1_ppn_low)
    else:
        low = _s2_low(data)
        ppn_low = (low,) * 8
    perm = dict(
        pf=data.s1_pf,
        af=data.s1_af,
        v=data.s1_v,
        d=0,
        a=data.s1_perm_a,
        g=data.s1_perm_g,
        u=data.s1_perm_u,
        x=data.s1_perm_x,
        w=data.s1_perm_w,
        r=data.s1_perm_r,
    )
    g_perm = dict(
        pf=data.s2_gpf,
        af=data.s2_gaf,
        v=0,
        d=0,
        a=data.s2_perm_a,
        g=0,
        u=0,
        x=data.s2_perm_x,
        w=0,
        r=0,
    )
    return StoredEntry(
        s2xlate=data.s2xlate,
        tag=bits(data.s2_tag, 37, 3) if data.s2xlate == ONLY_S2 else data.s1_tag,
        asid=data.s1_asid,
        level=level,
        ppn=_stored_ppn(data, level),
        n=n,
        pbmt=data.s1_pbmt,
        g_pbmt=data.s2_pbmt,
        perm=perm,
        valididx=valididx,
        pteidx=pteidx,
        ppn_low=ppn_low,
        g_perm=g_perm,
        vmid=data.s2_vmid if data.s2xlate == ONLY_S2 else data.s1_vmid,
    )


@dataclass
class Context:
    satp_asid: int = 0
    vsatp_asid: int = 0
    hgatp_vmid: int = 0
    virt: int = 0
    bme: int = 0
    cmode: int = 0


@dataclass
class ExpectedResponse:
    valid: int
    hit: int
    ppn: int = 0
    pbmt: int = 0
    g_pbmt: int = 0
    s2xlate: int = 0
    perm: dict[str, int] = field(default_factory=dict)
    g_perm: dict[str, int] = field(default_factory=dict)
    way: int | None = None


class TlbfaModel:
    def __init__(self) -> None:
        self.valid = [0] * WAYS
        self.entries: list[StoredEntry | None] = [None] * WAYS
        self.context = Context()

    # ------------------------------------------------------------------ state
    def reset(self) -> None:
        self.valid = [0] * WAYS
        self.entries = [None] * WAYS

    def program_context(self, **values: int) -> None:
        for key, value in values.items():
            if not hasattr(self.context, key):
                raise KeyError(key)
            setattr(self.context, key, value)

    def refill(self, way: int, data: Refill, sfence: bool = False) -> None:
        if 0 <= way < WAYS:
            self.entries[way] = make_stored(data)
            # The generated validity update gives an active sfence priority
            # over the refill write of the same cycle.
            if not sfence:
                self.valid[way] = 1

    # ------------------------------------------------------------------ match
    def _tag_level_hit(self, entry: StoredEntry, vpn: int) -> bool:
        tag = entry.tag
        n = entry.n
        level = entry.level
        t0 = (
            bits(tag, 5, 1) == bits(vpn, 8, 4)
            if n
            else bits(tag, 5, 0) == bits(vpn, 8, 3)
        )
        t1 = bits(tag, 14, 6) == bits(vpn, 17, 9)
        t2 = bits(tag, 23, 15) == bits(vpn, 26, 18)
        t3 = bits(tag, 34, 24) == bits(vpn, 37, 27)
        return (
            (t0 or level >= 1)
            and (t1 or level >= 2)
            and (t2 or level >= 3)
            and t3
        )

    def entry_matches(
        self, way: int, vpn: int, s2xlate: int, context: Context | None = None
    ) -> bool:
        """CAM match ignoring the way's valid bit (used for gap analysis)."""
        ctx = context or self.context
        entry = self.entries[way]
        if entry is None:
            return False
        if entry.s2xlate != s2xlate:
            return False
        if s2xlate == ONLY_S2:
            asid_hit = True
        else:
            asid = ctx.vsatp_asid if s2xlate != NO_S2 else ctx.satp_asid
            asid_hit = entry.asid == asid or entry.perm["g"] != 0
        vmid_hit = entry.vmid == ctx.hgatp_vmid if s2xlate != NO_S2 else True
        pteidx_hit = True
        if s2xlate != NO_S2 and entry.level == 0 and s2xlate != ONLY_S1 and entry.n == 0:
            pteidx_hit = bool(entry.pteidx[bits(vpn, 2, 0)])
        valididx_hit = bool(entry.valididx[bits(vpn, 2, 0)])
        return bool(
            asid_hit
            and vmid_hit
            and pteidx_hit
            and valididx_hit
            and self._tag_level_hit(entry, vpn)
        )

    def entry_hits(
        self, way: int, vpn: int, s2xlate: int, context: Context | None = None
    ) -> bool:
        if not self.valid[way] or self.entries[way] is None:
            return False
        return self.entry_matches(way, vpn, s2xlate, context)

    def lookup(
        self,
        vpn: int,
        s2xlate: int,
        refill_way: int | None = None,
        context: Context | None = None,
    ) -> ExpectedResponse:
        hits = [
            way
            for way in range(WAYS)
            if way != refill_way
            and self.entry_hits(way, vpn & MASK["vpn"], s2xlate, context)
        ]
        if not hits:
            return ExpectedResponse(valid=1, hit=0)
        # Multiple simultaneous hits are outside the parent's legal contract.
        # Keep the first way for reporting but flag via hit set size in tests.
        way = hits[0]
        entry = self.entries[way]
        assert entry is not None
        return ExpectedResponse(
            valid=1,
            hit=1,
            ppn=self.gen_ppn(entry, vpn),
            pbmt=entry.pbmt,
            g_pbmt=entry.g_pbmt,
            s2xlate=entry.s2xlate,
            perm=dict(entry.perm),
            g_perm=dict(entry.g_perm),
            way=way if len(hits) == 1 else None,
        )

    def hit_ways(self, vpn: int, s2xlate: int) -> list[int]:
        return [
            way
            for way in range(WAYS)
            if self.entry_hits(way, vpn & MASK["vpn"], s2xlate)
        ]

    @staticmethod
    def gen_ppn(entry: StoredEntry, vpn: int) -> int:
        vpn &= MASK["vpn"]
        p = entry.ppn
        seg2 = bits(vpn, 26, 18) if entry.level == 3 else bits(p, 23, 15)
        seg1 = bits(vpn, 17, 9) if entry.level >= 2 else bits(p, 14, 6)
        if entry.level >= 1:
            seg0 = bits(vpn, 8, 0)
        elif entry.n:
            seg0 = (bits(p, 5, 1) << 4) | bits(vpn, 3, 0)
        else:
            seg0 = (bits(p, 5, 0) << 3) | entry.ppn_low[bits(vpn, 2, 0)]
        return (bits(p, 32, 24) << 27) | (seg2 << 18) | (seg1 << 9) | seg0

    # ------------------------------------------------------------------ sfence
    def apply_sfence(
        self,
        valid: int,
        rs1: int,
        rs2: int,
        addr: int,
        sfence_id: int,
        hv: int,
        hg: int,
        context: Context | None = None,
    ) -> None:
        if not valid:
            return
        ctx = context or self.context
        if hg:
            for way in range(WAYS):
                entry = self.entries[way]
                if entry is None or entry.s2xlate == NO_S2:
                    continue
                if rs2 or entry.vmid == (sfence_id & MASK["vmid"]):
                    self.valid[way] = 0
            return
        if hv:
            for way in range(WAYS):
                entry = self.entries[way]
                if entry is None or entry.s2xlate == NO_S2:
                    continue
                if rs2:
                    if entry.vmid == ctx.hgatp_vmid:
                        self.valid[way] = 0
                elif (
                    not entry.perm["g"]
                    and entry.asid == (sfence_id & MASK["asid"])
                    and entry.vmid == ctx.hgatp_vmid
                ):
                    self.valid[way] = 0
            return
        all_addr = bool(rs1 or ctx.virt or (ctx.bme and not ctx.cmode))
        if all_addr:
            for way in range(WAYS):
                entry = self.entries[way]
                if entry is None:
                    continue
                if rs2:
                    remove = (
                        (not ctx.virt and entry.s2xlate == NO_S2)
                        or (
                            ctx.virt
                            and entry.s2xlate != NO_S2
                            and entry.vmid == ctx.hgatp_vmid
                        )
                    )
                else:
                    remove = (
                        not entry.perm["g"]
                        and (
                            (
                                not ctx.virt
                                and entry.s2xlate == NO_S2
                                and entry.asid == (sfence_id & MASK["asid"])
                            )
                            or (
                                ctx.virt
                                and entry.s2xlate != NO_S2
                                and entry.asid == (sfence_id & MASK["asid"])
                                and entry.vmid == ctx.hgatp_vmid
                            )
                        )
                    )
                if remove:
                    self.valid[way] = 0
            return
        # Address-specific path. With virt=0 the generated RTL still evaluates
        # the stage-2 pteidx gate as a constant true, so it does not filter by
        # s2xlate class; the tag/valididx conditions are common.
        vpn = bits(addr, 49, 12)
        for way in range(WAYS):
            entry = self.entries[way]
            if entry is None:
                continue
            tag_hit = self._tag_level_hit(entry, vpn)
            valididx_hit = bool(entry.valididx[bits(vpn, 2, 0)])
            if not (tag_hit and valididx_hit):
                continue
            if rs2:
                # Address-specific + all-ASID is an address-only match: the
                # generated RTL does not compare ASID, global or stage here.
                self.valid[way] = 0
            elif (
                entry.asid == (sfence_id & MASK["asid"]) and not entry.perm["g"]
            ):
                self.valid[way] = 0
