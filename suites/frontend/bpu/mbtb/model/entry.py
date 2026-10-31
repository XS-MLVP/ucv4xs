"""Bounded same-key indirect retargeting, including partial-target carry changes.

This MiniConfig model covers two counter-2 hit feedback beats and a 24-read
sentinel window. It is not a full allocator, overflow, flush or stale-way model.
"""
from suites.frontend.bpu.models.configuration import *
from copy import deepcopy
from dataclasses import replace

from suites.frontend.bpu.mbtb.monitor.entry import ENTRY_FIELDS


REGION_SPAN = 1 << 20  # picker Pc.addr/target_addr are halfword addresses.
CARRY_PATTERNS = {"fit_overflow": (0, 1), "overflow_underflow": (1, -1), "underflow_fit": (-1, 0)}


def mbtb_retarget_targets(pc, original_target, pattern):
    if pattern not in CARRY_PATTERNS:
        raise ValueError("unsupported MainBTB carry transition")
    if pc < REGION_SPAN or original_target // REGION_SPAN != pc // REGION_SPAN:
        raise ValueError("retarget preparation requires a same-region original target and a nonzero PC region")
    lower = original_target % REGION_SPAN
    if lower + 0x2000 >= REGION_SPAN:
        raise ValueError("retarget preparation lower bits are too close to a region boundary")
    region = pc // REGION_SPAN
    return tuple((region + delta) * REGION_SPAN + lower + offset
                 for delta, offset in zip(CARRY_PATTERNS[pattern], (0x1000, 0x2000), strict=True))


def expected_mbtb_entry_activity(pc, position, way, targets, mode, *, reads=24):
    if (pc < 0 or pc & 7 or position % ALIGN_HALFWORDS != 1
            or position // ALIGN_HALFWORDS not in (0, 1) or way not in range(MAIN_WAYS)):
        raise ValueError("entry scenario requires a 32-byte group position 1 and a physical way")
    if mode not in ("blocked", "flow") or not isinstance(reads, int) or reads < 4:
        raise ValueError("entry scenario requires blocked/flow and a sufficient read window")
    if len(targets) != 2 or targets[0] == targets[1]:
        raise ValueError("entry scenario requires two distinct target rewrites")
    requests = []
    for target in targets:
        delta = target // REGION_SPAN - pc // REGION_SPAN
        if target < 0 or delta not in (-1, 0, 1):
            raise ValueError("partial target carry only reconstructs the same or adjacent PC region")
        position_align = (position // ALIGN_HALFWORDS) % 2
        start = pc + position_align * ALIGN_HALFWORDS
        align = ((pc >> 4) & 1) ^ position_align
        requests.append(dict(align=align, bank=(start >> 5) & (MAIN_BANKS - 1), way=way,
            set_idx=(start >> 7) & (MAIN_ROWS - 1), tag=(start >> 15) & 65535, branch_type=3, ras_action=0,
            position=position % ALIGN_HALFWORDS, carry={0: 0, 1: 1, -1: 2}[delta], lower=target % REGION_SPAN))
    blocked = mode == "blocked"
    return {"requests": tuple(requests), "writebacks": deepcopy(tuple(requests[1:] if blocked else requests)),
            "input_to_request_ticks": (4, 4), "request_read_state": ((0, int(not blocked)), (1, int(not blocked))),
            "writeback_offsets": (2,) if blocked else (6, 6), "read_overlap": True,
            "lookups": reads, "lookup_cadence_ok": True, "lookup_completion_ticks": (4,) * reads}


def expected_mbtb_entry_states(prepared, align, way, latest_target):
    if len(prepared) != 4 or align not in (0, 1) or way not in range(MAIN_WAYS) or latest_target < 0:
        raise ValueError("entry states require four residents and the supported physical geometry")
    active = align * (MAIN_WAYS + 1) + way
    entry = prepared[0]["entries"][active]
    meta = prepared[0]["meta_entries"][align][way]
    if not entry.valid or entry.branch_type != 3 or not meta["rawHit"] or meta["counter_value"] != 2:
        raise ValueError("retarget requires a real indirect hit with initial counter 2")
    states = deepcopy(prepared)
    states[0]["entries"] = tuple(replace(value, target=latest_target) if index == active else value
                                 for index, value in enumerate(states[0]["entries"]))
    return states


def summarize_mbtb_entry_activity(frames, feedback, lookups, mode):
    """Normalize observations only; never evaluate the independent reference."""
    if mode not in ("blocked", "flow"):
        raise ValueError("entry activity mode must be blocked or flow")
    requests, writebacks = [], []

    def payload(align, bank, way, port, direction):
        return dict(align=align, bank=bank, way=way,
                    **{key: port[f"{direction}_{key}"] for key, _ in ENTRY_FIELDS})

    for frame in frames:
        for align, row in enumerate(frame.value["banks"]):
            for bank, ports in enumerate(row):
                for way, port in enumerate(ports):
                    if port["write_valid"]:
                        requests.append((frame.event.tick, payload(align, bank, way, port, "write"),
                                         (port["read_valid"], port["read_ready"])))
                    if port["read_valid"] and port["read_ready"]:
                        writebacks.append((frame.event.tick, payload(align, bank, way, port, "read")))
    inputs = tuple(frame.event.tick for frame in feedback)
    accepted = tuple(transfer.accepted_event.tick for transfer in lookups)
    completed = tuple(transfer.completed_event.tick for transfer in lookups)
    return {"requests": tuple(value for _, value, _ in requests),
            "writebacks": tuple(value for _, value in writebacks),
            "input_to_request_ticks": tuple(tick - inputs[index] if index < len(inputs) else None
                                            for index, (tick, _, _) in enumerate(requests)),
            "request_read_state": tuple(state for _, _, state in requests),
            "writeback_offsets": tuple(tick - accepted[-1] if mode == "blocked" and accepted else
                                       tick - inputs[index] if mode == "flow" and index < len(inputs) else None
                                       for index, (tick, _) in enumerate(writebacks)),
            "read_overlap": bool(accepted) and all(accepted[0] <= tick <= accepted[-1] for tick, _, _ in requests),
            "lookups": len(lookups),
            "lookup_cadence_ok": bool(accepted) and accepted == tuple(range(accepted[0], accepted[0] + 2 * len(accepted), 2)),
            "lookup_completion_ticks": tuple(done - start for start, done in zip(accepted, completed, strict=True))}
