"""FIL-02/FIL-06 response construction from request identity and stage.

These are the existing scenario models; no DUT observation supplies an expectation.
"""
from __future__ import annotations

from suites.memblock.mmu.testbenches.ptwfilter.transactions import Req


def s1_values(vpn: int, tag: int | None = None, asid: int = 0, level: int = 0,
              valididx=None) -> dict:
    if tag is None:
        tag = (vpn >> 3) & ((1 << 35) - 1)
    if valididx is None:
        valididx = [1] * 8
    values = {
        "s1_entry_tag": tag,
        "s1_entry_asid": asid,
        "s1_entry_vmid": 0,
        "s1_entry_n": 0,
        "s1_entry_pbmt": 0,
        "s1_entry_perm_a": 1,
        "s1_entry_perm_g": 0,
        "s1_entry_perm_u": 1,
        "s1_entry_perm_x": 1,
        "s1_entry_perm_w": 0,
        "s1_entry_perm_r": 1,
        "s1_entry_level": level,
        "s1_entry_v": 1,
        "s1_entry_ppn": 0x12345,
        "s1_addr_low": 0,
    }
    for index, value in enumerate(valididx):
        values[f"s1_valididx_{index}"] = value
    for index in range(8):
        values[f"s1_ppn_low_{index}"] = index
        values[f"s1_pteidx_{index}"] = 1 if index == 0 else 0
    return values


def staged_values(req: Req, satp: int = 0, vsatp: int = 0, vmid: int = 0) -> dict:
    """Build a PTW response that matches one pending request for any stage."""
    values = {
        "s2xlate": req.s2xlate,
        "s1_entry_asid": vsatp if req.s2xlate != 0 else satp,
        "s1_entry_vmid": vmid,
        "s1_entry_level": 0,
        "s1_entry_v": 1,
        "s1_entry_perm_a": 1,
        "s1_entry_perm_r": 1,
        "s1_entry_perm_x": 1,
    }
    for index in range(8):
        values[f"s1_valididx_{index}"] = 1
        values[f"s1_pteidx_{index}"] = 1 if index == 0 else 0
        values[f"s1_ppn_low_{index}"] = index
    if req.s2xlate == 2:
        values["s1_entry_tag"] = 0
        values["s2_entry_tag"] = req.vpn
        values["s2_entry_vmid"] = vmid
        values["s2_entry_level"] = 0
        values["s2_entry_perm_a"] = 1
        values["s2_entry_perm_x"] = 1
    else:
        values["s1_entry_tag"] = (req.vpn >> 3) & ((1 << 35) - 1)
        values["s2_entry_tag"] = req.vpn
        values["s2_entry_vmid"] = vmid
        values["s2_entry_level"] = 0
        values["s2_entry_perm_a"] = 1
        values["s2_entry_perm_x"] = 1
    return values
