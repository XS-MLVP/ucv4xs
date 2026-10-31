"""Shared builders for TLBFA test vectors."""
from __future__ import annotations

from suites.memblock.mmu.tlbfa.model import ALL_STAGE, NO_S2, ONLY_S1, ONLY_S2, Refill


def make_refill(
    kind: int,
    level: int,
    tag: int,
    ppn: int,
    *,
    n: int = 0,
    asid: int = 0,
    vmid: int = 0,
    perm_g: int = 0,
    valididx=None,
    pteidx=None,
    ppn_low=None,
    s1_pf: int = 0,
    s1_af: int = 0,
    s2_gpf: int = 0,
    s2_gaf: int = 0,
    pbmt: int = 0,
    g_pbmt: int = 0,
    s2_tag: int | None = None,
    s2_ppn: int | None = None,
    s1_perm_r: int = 1,
    s1_perm_w: int = 0,
    s1_perm_x: int = 0,
    s2_perm_a: int = 1,
    s2_perm_x: int = 0,
    s1_perm_a: int = 1,
    s1_perm_d: int = 1,
    s2_perm_d: int = 1,
    s2_perm_r: int = 1,
    s2_perm_w: int = 1,
    s1_perm_u: int = 1,
    s1_v: int = 1,
) -> Refill:
    """Build a legal-ish PTW response for one translation-stage form.

    `tag` is the 35-bit sector VPN for no-S2/only-S1/two-stage forms. For
    onlyStage2 it is treated as the 38-bit GPA VPN; `s2_tag` can override it.
    """
    if valididx is None:
        valididx = (1,) * 8
    if pteidx is None:
        pteidx = (1, 0, 0, 0, 0, 0, 0, 0)
    if ppn_low is None:
        ppn_low = tuple(index & 0x7 for index in range(8))
    if s2_tag is None:
        s2_tag = ((tag & ((1 << 35) - 1)) << 3) if kind != ONLY_S2 else (tag & ((1 << 38) - 1))
    if s2_ppn is None:
        s2_ppn = ppn & ((1 << 38) - 1)
    return Refill(
        s2xlate=kind,
        s1_tag=tag & ((1 << 35) - 1),
        s1_asid=asid,
        s1_vmid=vmid,
        s1_n=n,
        s1_pbmt=pbmt,
        s1_level=level,
        s1_v=s1_v,
        s1_ppn=ppn & ((1 << 41) - 1),
        s1_ppn_low=tuple(ppn_low),
        s1_valididx=tuple(valididx),
        s1_pteidx=tuple(pteidx),
        s1_pf=s1_pf,
        s1_af=s1_af,
        s1_perm_a=s1_perm_a,
        s1_perm_d=s1_perm_d,
        s1_perm_g=perm_g,
        s1_perm_u=s1_perm_u,
        s1_perm_x=s1_perm_x,
        s1_perm_w=s1_perm_w,
        s1_perm_r=s1_perm_r,
        s2_tag=s2_tag & ((1 << 38) - 1),
        s2_vmid=vmid,
        s2_n=n,
        s2_pbmt=g_pbmt,
        s2_ppn=s2_ppn,
        s2_level=level,
        s2_gpf=s2_gpf,
        s2_gaf=s2_gaf,
        s2_perm_a=s2_perm_a,
        s2_perm_d=s2_perm_d,
        s2_perm_r=s2_perm_r,
        s2_perm_w=s2_perm_w,
        s2_perm_x=s2_perm_x,
    )


def lookup_vpn(kind: int, tag: int, low: int = 0) -> int:
    """VPN presented on the read port for a stored translation."""
    if kind == ONLY_S2:
        return tag & ((1 << 38) - 1)
    return ((tag & ((1 << 35) - 1)) << 3) | (low & 0x7)


def vpn_plus(vpn: int, delta: int) -> int:
    return (vpn + delta) & ((1 << 38) - 1)
