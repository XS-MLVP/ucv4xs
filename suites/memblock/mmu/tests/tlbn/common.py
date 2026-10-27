"""Reference helpers for the TLBNonBlock DTLB tests."""
from __future__ import annotations

from mmuverify.tlbfa.model import (ALL_STAGE, NO_S2, ONLY_S1, ONLY_S2, Refill,
                                   TlbfaModel, bits)
from tests.tlbfa.common import make_refill

READ = 0
WRITE = 1
EXEC = 2
ATOM_WRITE = 5


def dtlb_refill(vaddr: int, ppn: int, kind: int = NO_S2, level: int = 0,
                **overrides) -> Refill:
    """Build a PTW response whose sector lane matches the tested VPN."""
    vpn = (vaddr >> 12) & ((1 << 38) - 1)
    lane = vpn & 7
    defaults = dict(
        kind=kind,
        level=level,
        tag=vpn if kind == ONLY_S2 else (vpn >> 3),
        ppn=ppn >> 3,
        s2_ppn=ppn,
        pteidx=tuple(1 if index == lane else 0 for index in range(8)),
        ppn_low=tuple(ppn & 7 for _ in range(8)),
        s1_perm_r=1,
        s1_perm_w=1,
        s1_perm_x=1,
        s1_perm_u=1,
        s1_perm_a=1,
        s1_perm_d=1,
        s2_perm_a=1,
        s2_perm_d=1,
    )
    defaults.update(overrides)
    return make_refill(**defaults)


def gen_ppn_s1(data: Refill, vpn: int) -> int:
    """Reconstruct the PPN from the sector PPN and the response lane."""
    lane = vpn & 7
    p = (data.s1_ppn & ((1 << 41) - 1)) << 3
    if data.s1_level == 0:
        return (p & ~0x7) | (data.s1_ppn_low[lane] & 7)
    mask = (1 << (9 * data.s1_level)) - 1
    return (p & ~mask) | (vpn & mask)


def gen_ppn_s2(data: Refill, gvpn: int) -> int:
    p = data.s2_ppn
    level = data.s2_level
    if level == 0:
        if data.s2_n:
            return ((p >> 4) << 4) | (gvpn & 0xF)
        return p
    if level == 1:
        return ((p >> 9) << 9) | (gvpn & 0x1FF)
    if level == 2:
        return ((p >> 18) << 18) | (gvpn & 0x3FFFF)
    return ((p >> 27) << 27) | (gvpn & 0x7FFFFFF)


def expected_paddr(data: Refill, vaddr: int) -> int:
    vpn = (vaddr >> 12) & ((1 << 38) - 1)
    off = vaddr & 0xFFF
    s1_ppn = gen_ppn_s1(data, vpn)
    if data.s2xlate in (ONLY_S2, ALL_STAGE):
        gvpn = vpn if data.s2xlate == ONLY_S2 else s1_ppn
        return (gen_ppn_s2(data, gvpn) << 12) | off
    return (s1_ppn << 12) | off


def expected_gpaddr(data: Refill, vaddr: int) -> int:
    """GPA replay address for a leaf response (only stage-2 forms)."""
    vpn = (vaddr >> 12) & ((1 << 38) - 1)
    off = vaddr & 0xFFF
    if data.s2xlate == ONLY_S2:
        return vaddr
    return (gen_ppn_s1(data, vpn) << 12) | off


def expected_pbmt(data: Refill) -> int:
    if data.s2xlate in (NO_S2, ONLY_S1):
        return data.s1_pbmt & 3
    if data.s2xlate == ONLY_S2:
        return data.s2_pbmt & 3
    return (data.s1_pbmt & 3) if (data.s1_pbmt & 3) else (data.s2_pbmt & 3)


def perm_expectations(data: Refill, cmd: int, *, dmode: int = 0, sum_: int = 0,
                      mxr: int = 0) -> dict:
    """Replicate TLB.perm_check for load/store/exec commands."""
    p = data
    stage2 = p.s2xlate in (ONLY_S2, ALL_STAGE)
    s1_valid = p.s2xlate != ONLY_S2
    s2_valid = stage2
    is_ld = cmd == READ
    is_st = cmd in (WRITE, ATOM_WRITE)
    is_inst = cmd == EXEC
    mode_s = dmode == 1
    mode_u = dmode == 0
    mode_ok = not (mode_u and not p.s1_perm_u or
                   mode_s and p.s1_perm_u and not sum_)
    af = bool((p.s2xlate != ONLY_S2 and p.s1_af) or
              (stage2 and p.s2_gaf))
    pf = bool(p.s1_pf)
    ld_update = (not p.s1_perm_a) and is_ld
    st_update = (not p.s1_perm_a or not p.s1_perm_d) and is_st
    ld_fail = not (mode_ok and (p.s1_perm_r or (mxr and p.s1_perm_x)))
    st_fail = not (mode_ok and p.s1_perm_w)
    gpf = bool(p.s2_gpf)
    has_pf = bool((ld_fail or ld_update or st_fail or st_update) and s1_valid
                  and not af)
    g_ld_fail = not (p.s2_perm_r or (mxr and p.s2_perm_x))
    g_st_fail = not p.s2_perm_w
    ld_gpf = bool((g_ld_fail or gpf) and is_ld)
    st_gpf = bool((g_st_fail or gpf) and is_st)
    is_fake = (not p.s1_v) and (not p.s1_pf) and (not p.s1_af) and p.s2xlate != ONLY_S2
    is_nonleaf = (not (p.s1_perm_r or p.s1_perm_w or p.s1_perm_x)) and p.s1_v\
        and (not p.s1_pf) and (not p.s1_af)
    pf_ld = bool((ld_fail or pf or ld_update) and is_ld and s1_valid and not af
                 and not is_fake and not is_nonleaf)
    pf_st = bool((st_fail or pf or st_update) and is_st and s1_valid and not af
                 and not is_fake and not is_nonleaf)
    gpf_ld = bool(ld_gpf and s2_valid and not af and not has_pf)
    gpf_st = bool(st_gpf and s2_valid and not af and not has_pf)
    af_ld = bool(af and is_ld and (s1_valid or s2_valid))
    af_st = bool(af and is_st and (s1_valid or s2_valid))
    return dict(pf_ld=pf_ld, pf_st=pf_st, gpf_ld=gpf_ld, gpf_st=gpf_st,
                af_ld=af_ld, af_st=af_st)
