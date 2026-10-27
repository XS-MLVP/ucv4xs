"""Bounded two-key retention reference, separate from same-key coalescing.

Two real counter-2 indirect hits target distinct sets in one physical bank and
way, during 24 sentinel reads. No full-miss, flush or stale-way claim is made.
"""
from copy import deepcopy
from dataclasses import replace

from bpuverify.mbtb.model.entry import REGION_SPAN
from bpuverify.mbtb.model.entry import mbtb_retarget_targets


def mbtb_entry_key_targets(pcs, original_targets, pair):
    """Choose each key's own partial-target region; a pair is not a rewrite."""
    if len(pcs) != 2 or len(original_targets) != 2 or any(not isinstance(value, int) for value in (*pcs, *original_targets)):
        raise ValueError("entry target pair requires two PCs and original targets")
    return tuple(mbtb_retarget_targets(pc, target, pair)[index]
                 for index, (pc, target) in enumerate(zip(pcs, original_targets, strict=True)))


def expected_mbtb_entry_keys_activity(pcs, position, way, targets, mode, *, reads=24):
    if len(pcs) != 2 or any(not isinstance(pc, int) or pc < 0 or pc & 15 for pc in pcs):
        raise ValueError("entry keys require two aligned fetch starts")
    if ((pcs[0] >> 4) & 1) != ((pcs[1] >> 4) & 1) or ((pcs[0] >> 5) & 63) == ((pcs[1] >> 5) & 63):
        raise ValueError("entry keys require two distinct sets in the same internal bank")
    if position not in (1, 9) or way not in (0, 1):
        raise ValueError("entry keys require position 1/9 and way 0/1")
    if mode not in ("blocked", "flow") or not isinstance(reads, int) or reads < 4:
        raise ValueError("entry keys require blocked/flow and a sufficient read window")
    if len(targets) != 2 or any(not isinstance(target, int) for target in targets):
        raise ValueError("entry keys require one target for each key")
    requests = []
    for pc, target in zip(pcs, targets, strict=True):
        delta = target // REGION_SPAN - pc // REGION_SPAN
        if target < 0 or delta not in (-1, 0, 1):
            raise ValueError("partial target carry only reconstructs the same or adjacent PC region")
        requests.append(dict(align=position // 8, bank=(pc >> 4) & 1, way=way,
            set_idx=(pc >> 5) & 63, tag=(pc >> 11) & 65535, branch_type=3, ras_action=0,
            position=position % 8, carry={0: 0, 1: 1, -1: 2}[delta], lower=target % REGION_SPAN))
    blocked = mode == "blocked"
    return {"requests": tuple(requests), "writebacks": deepcopy(tuple(requests)),
            "input_to_request_ticks": (4, 4), "request_read_state": ((0, int(not blocked)), (1, int(not blocked))),
            "writeback_offsets": (2, 4) if blocked else (6, 6), "read_overlap": True,
            "lookups": reads, "lookup_cadence_ok": True, "lookup_completion_ticks": (4,) * reads}


def expected_mbtb_entry_keys_states(prepared, align, way, targets):
    """Targets correspond to prepared key 0/1, regardless of submission order."""
    if len(prepared) != 4 or align not in (0, 1) or way not in (0, 1) or len(targets) != 2 or any(not isinstance(target, int) or target < 0 for target in targets):
        raise ValueError("entry key states require four residents and two targets in the supported geometry")
    active = align * 2 + way
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
