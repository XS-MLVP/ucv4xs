"""Bounded two-key retention reference, separate from same-key coalescing.

Two real counter-2 indirect hits target distinct sets in one physical bank and
way, during 24 sentinel reads. No full-miss, flush or stale-way claim is made.
"""
from suites.frontend.bpu.models.configuration import *
from copy import deepcopy
from dataclasses import replace

from suites.frontend.bpu.mbtb.model.entry import REGION_SPAN
from suites.frontend.bpu.mbtb.model.entry import mbtb_retarget_targets


def mbtb_entry_key_targets(pcs, original_targets, pair):
    """Choose each key's own partial-target region; a pair is not a rewrite."""
    if len(pcs) != 2 or len(original_targets) != 2 or any(not isinstance(value, int) for value in (*pcs, *original_targets)):
        raise ValueError("entry target pair requires two PCs and original targets")
    return tuple(mbtb_retarget_targets(pc, target, pair)[index]
                 for index, (pc, target) in enumerate(zip(pcs, original_targets, strict=True)))


def entry_key_coordinate(pc):
    """DefaultConfig MainBTB physical coordinates.

    ``AddrField`` starts at the halfword address bit: 16-byte align offset
    (3 bits), 1 align-bank bit, 2 internal-bank bits, 8 set bits, 16 tag bits.
    In byte-PC terms that is align=PC[4], bank=PC[6:5], set=PC[14:7].
    """
    if type(pc) is not int or pc < 0 or pc & 15:
        raise ValueError("MainBTB PC must be a nonnegative 16-byte aligned address")
    return (pc >> 4) & 1, (pc >> 5) & (MAIN_BANKS - 1), (pc >> 7) & (MAIN_ROWS - 1)


def entry_key_tag(pc):
    return (pc >> 15) & 0xFFFF


def mbtb_bank_coordinate(pc, position=0):
    """Coordinate of the align-bank start descriptor actually written.

    MainBTB rotates the two 32-byte start descriptors by the CFI position's
    alignment bit, so a branch at position 16..31 is written into align bank 1
    with ``startPc + ALIGN_HALFWORDS`` as its set/tag base.
    """
    position_align = (position // ALIGN_HALFWORDS) % 2
    start_align = (pc >> 4) & 1
    align = start_align ^ position_align
    start = pc + position_align * ALIGN_HALFWORDS
    return (align, (start >> 5) & (MAIN_BANKS - 1), (start >> 7) & (MAIN_ROWS - 1)), \
           (start >> 15) & 0xFFFF


def expected_mbtb_entry_keys_activity(pcs, position, way, targets, mode, *, reads=24,
                                      writeback_offsets=None):
    if len(pcs) != 2 or any(not isinstance(pc, int) or pc < 0 or pc & 15 for pc in pcs):
        raise ValueError("entry keys require two aligned fetch starts")
    first, second = entry_key_coordinate(pcs[0]), entry_key_coordinate(pcs[1])
    if first[1] != second[1] or first[2] == second[2]:
        raise ValueError("entry keys require two distinct sets in the same internal bank")
    if position % ALIGN_HALFWORDS != 1 or position // ALIGN_HALFWORDS not in (0, 1) \
            or way not in range(MAIN_WAYS):
        raise ValueError("entry keys require a 32-byte group position 1 and a physical way")
    if mode not in ("blocked", "flow") or not isinstance(reads, int) or reads < 4:
        raise ValueError("entry keys require blocked/flow and a sufficient read window")
    if len(targets) != 2 or any(not isinstance(target, int) for target in targets):
        raise ValueError("entry keys require one target for each key")
    requests = []
    for pc, target in zip(pcs, targets, strict=True):
        delta = target // REGION_SPAN - pc // REGION_SPAN
        if target < 0 or delta not in (-1, 0, 1):
            raise ValueError("partial target carry only reconstructs the same or adjacent PC region")
        (align, bank, set_idx), tag = mbtb_bank_coordinate(pc, position)
        requests.append(dict(align=align, bank=bank, way=way,
            set_idx=set_idx, tag=tag, branch_type=3, ras_action=0,
            position=position % ALIGN_HALFWORDS, carry={0: 0, 1: 1, -1: 2}[delta], lower=target % REGION_SPAN))
    blocked = mode == "blocked"
    return {"requests": tuple(requests), "writebacks": deepcopy(tuple(requests)),
            "input_to_request_ticks": (4, 4), "request_read_state": ((0, int(not blocked)), (1, int(not blocked))),
            "writeback_offsets": writeback_offsets if writeback_offsets is not None
                                 else (2, 4) if blocked else (6, 6),
            "read_overlap": True,
            "lookups": reads, "lookup_cadence_ok": True, "lookup_completion_ticks": (4,) * reads}


def expected_mbtb_entry_keys_states(prepared, align, way, targets):
    """Targets correspond to prepared key 0/1, regardless of submission order."""
    if len(prepared) != 4 or align not in (0, 1) or way not in range(MAIN_WAYS) or len(targets) != 2 or any(not isinstance(target, int) or target < 0 for target in targets):
        raise ValueError("entry key states require four residents and two targets in the supported geometry")
    active = align * (MAIN_WAYS + 1) + way
    for key in (0, 1):
        entry = prepared[key]["entries"][active]
        meta = prepared[key]["meta_entries"][align][way]
        if not entry.valid or entry.branch_type != 3 or not meta["rawHit"] or meta["counter_value"] != 2:
            raise ValueError("entry keys require two real indirect hits with initial counter 2")
    states = deepcopy(prepared)
    for key, target in enumerate(targets):
        states[key]["entries"] = tuple(replace(value, target=target) if index == active else value
                                       for index, value in enumerate(states[key]["entries"]))
    return states
