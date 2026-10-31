"""Environment and independent reference for LoadUnitS0.

S0 is the request-synthesis + arbitration stage of ``NewLoadUnit``. Four
logical request lanes reach it:

======================  ==============  ============================================
lane                    entrance        payload origin
======================  ==============  ============================================
``unalignTail``         0x01 (fixed)    S1 tail injection, fields passed through
``replay`` hi prio      0x02 (fixed)    LRQ replay, ``entrance[1]`` set
``fastReplay``          ``ent | 0x04``  S3 fast replay, entrance low bits OR'ed
``replay`` lo prio      0x08 (fixed)    LRQ replay, *ordered after* the new ldin
``ldin`` (scalar)       0x40 (fixed)    ExuInput turned into a load request
======================  ==============  ============================================

The low-priority replay lane only exists when the replaying load is **older**
than the load being issued in the same cycle. "Older" is the ring comparison
``replay.lqIdx > ldin.lqIdx`` with the wrap bit XOR'ed in
(``replayIsLoPrio``); when the replaying load is younger it is simply dropped
this cycle (neither the hi nor the lo lane is valid).

Reference structure:

1. **Synthesize** the five lane payloads exactly as S0 wires them (including
   the constant entrance codes, the ``ldin`` address/size/mask derivation and
   ``noQuery = (fuOpType == 0x1)``).
2. **Arbitrate** with the standalone arbiter model (priority 0>1>2>3>5, ready
   gated by ``dcacheReq.ready``). This is the already-verified leaf contract.
3. **Derive** the alignment / cross-16B / 128-bit qualifiers, TLB request,
   DCache request, forward requests, wakeup and the two performance counters
   from the micro-architectural rules, not from the RTL ternary trees.
4. **Register** the S0 output stage: one entry, written only when
   ``arb.valid & dcacheReq.ready``, no flush/kill at this stage.

Contract: docs/contracts/load-s0.md
"""
from __future__ import annotations

import random

from suites.memblock.lsu.load_arbiter.env import (
    FIELD_RULES as STAGE_FIELDS,
    PAYLOAD,
    SOURCES,
    reference_action,
)

# ---------------------------------------------------------------- lane mapping
LANES = {"unalign": 0, "replay_hi": 1, "fast": 2, "replay_lo": 3, "ldin": 5}
LANE_NAMES = {value: key for key, value in LANES.items()}

UNALIGN_FIELDS = (
    "accessType_instrType", "accessType_pftType", "uop_exceptionVec_23",
    "uop_exceptionVec_19", "uop_exceptionVec_15", "uop_exceptionVec_7",
    "uop_exceptionVec_6", "uop_isRVC", "uop_ftqPtr_flag", "uop_ftqPtr_value",
    "uop_ftqOffset", "uop_fuOpType", "uop_rfWen", "uop_fpWen", "uop_vecWen",
    "uop_v0Wen", "uop_pdest", "uop_robIdx_flag", "uop_robIdx_value",
    "uop_robIdx_isFormer", "uop_perfDebugInfo_runahead_checkpoint_id",
    "uop_storeSetHit", "uop_waitSqIdx_first_flag", "uop_waitSqIdx_second_flag",
    "uop_waitSqIdx_value", "uop_loadWaitBit", "uop_loadWaitStrict",
    "uop_lqIdx_flag", "uop_lqIdx_value", "uop_sqIdx_first_flag",
    "uop_sqIdx_second_flag", "uop_sqIdx_value", "vaddr", "fullva", "mask",
    "paddr", "mshrId", "replayQueueIdx", "uncacheReplay", "ncReplay",
)
REPLAY_FIELDS = (
    "entrance", "accessType_instrType", "uop_exceptionVec_23",
    "uop_exceptionVec_19", "uop_exceptionVec_15", "uop_exceptionVec_7",
    "uop_exceptionVec_6", "uop_isRVC", "uop_ftqPtr_flag", "uop_ftqPtr_value",
    "uop_ftqOffset", "uop_fuOpType", "uop_rfWen", "uop_fpWen", "uop_vecWen",
    "uop_v0Wen", "uop_pdest", "uop_robIdx_flag", "uop_robIdx_value",
    "uop_robIdx_isFormer", "uop_perfDebugInfo_runahead_checkpoint_id",
    "uop_storeSetHit", "uop_waitSqIdx_first_flag", "uop_waitSqIdx_second_flag",
    "uop_waitSqIdx_value", "uop_loadWaitBit", "uop_loadWaitStrict",
    "uop_lqIdx_flag", "uop_lqIdx_value", "uop_sqIdx_first_flag",
    "uop_sqIdx_second_flag", "uop_sqIdx_value", "vaddr", "fullva", "size",
    "mask", "mshrId", "replayQueueIdx", "forwardDChannel", "uncacheReplay",
    "ncReplay",
)
FAST_FIELDS = (
    "entrance", "accessType_instrType", "accessType_pftType",
    "uop_exceptionVec_23", "uop_exceptionVec_19", "uop_exceptionVec_15",
    "uop_exceptionVec_7", "uop_exceptionVec_6", "uop_isRVC",
    "uop_ftqPtr_flag", "uop_ftqPtr_value", "uop_ftqOffset", "uop_fuOpType",
    "uop_rfWen", "uop_fpWen", "uop_vecWen", "uop_v0Wen", "uop_pdest",
    "uop_robIdx_flag", "uop_robIdx_value", "uop_robIdx_isFormer",
    "uop_perfDebugInfo_runahead_checkpoint_id", "uop_storeSetHit",
    "uop_waitSqIdx_first_flag", "uop_waitSqIdx_second_flag",
    "uop_waitSqIdx_value", "uop_loadWaitBit", "uop_loadWaitStrict",
    "uop_lqIdx_flag", "uop_lqIdx_value", "uop_sqIdx_first_flag",
    "uop_sqIdx_second_flag", "uop_sqIdx_value", "vaddr", "fullva", "size",
    "mask", "paddr", "mshrId", "replayQueueIdx", "uncacheReplay", "ncReplay",
)
LDIN_FIELDS = (
    "fuOpType", "src_0", "imm", "robIdx_flag", "robIdx_value",
    "robIdx_isFormer", "pdest", "rfWen", "fpWen", "vecWen", "v0Wen",
    "isRVC", "ftqIdx_flag", "ftqIdx_value", "ftqOffset", "loadWaitBit",
    "waitSqIdx_first_flag", "waitSqIdx_second_flag", "waitSqIdx_value",
    "storeSetHit", "loadWaitStrict", "lqIdx_flag", "lqIdx_value",
    "sqIdx_first_flag", "sqIdx_second_flag", "sqIdx_value",
)

PIPEOUT_FIELDS = tuple(sorted(STAGE_FIELDS)) + ("align", "unalignHead")

LSU_DEFAULT = 0x06          # LD: size field 3, the most common load


# ------------------------------------------------------------ ldin synthesis
def sext(value: int, bits: int, width: int = 64) -> int:
    value &= (1 << bits) - 1
    if value & (1 << (bits - 1)):
        value -= 1 << bits
    return value & ((1 << width) - 1)


def gen_vwmask(size: int, vaddr: int) -> int:
    """Byte mask of a ``size``-coded access starting at ``vaddr``.

    ``size`` is the LSUOpType size (0:B, 1:H, 2:W, 3:D, >=4:16B). The mask is 16
    bits wide and is shifted by the byte offset inside the 16B word, dropping
    bits that leave the word - the same ``genVWmask`` the RTL instantiates.
    """
    base = 0xFFFF if (size >> 2) else ((1 << (1 << size)) - 1)
    return (base << (vaddr & 0xF)) & 0xFFFF


def ldin_payload(ldin: dict) -> dict:
    """Turn an ``ExuInput`` into the load-stage payload S0 builds for it."""
    ldin = dict({name: 0 for name in LDIN_FIELDS}, **ldin)
    fu = ldin["fuOpType"]
    size = (fu >> 1) & 0x7
    vaddr = (ldin["src_0"] + sext(ldin["imm"], 12)) & ((1 << 50) - 1)
    fullva = (ldin["src_0"] + sext(ldin["imm"], 12)) & ((1 << 64) - 1)
    no_query = 1 if fu == 0x1 else 0
    payload = {name: 0 for name in STAGE_FIELDS}
    payload.update({
        "accessType_instrType": 4 if (fu & 1) else 1,
        "accessType_pftType": 2 | no_query,
        "uop_isRVC": ldin["isRVC"],
        "uop_ftqPtr_flag": ldin["ftqIdx_flag"],
        "uop_ftqPtr_value": ldin["ftqIdx_value"],
        "uop_ftqOffset": ldin["ftqOffset"],
        "uop_fuOpType": fu,
        "uop_rfWen": ldin["rfWen"],
        "uop_fpWen": ldin["fpWen"],
        "uop_vecWen": ldin["vecWen"],
        "uop_v0Wen": ldin["v0Wen"],
        "uop_pdest": ldin["pdest"],
        "uop_robIdx_flag": ldin["robIdx_flag"],
        "uop_robIdx_value": ldin["robIdx_value"],
        "uop_robIdx_isFormer": ldin["robIdx_isFormer"],
        "uop_storeSetHit": ldin["storeSetHit"],
        "uop_waitSqIdx_first_flag": ldin["waitSqIdx_first_flag"],
        "uop_waitSqIdx_second_flag": ldin["waitSqIdx_second_flag"],
        "uop_waitSqIdx_value": ldin["waitSqIdx_value"],
        "uop_loadWaitBit": ldin["loadWaitBit"],
        "uop_loadWaitStrict": ldin["loadWaitStrict"],
        "uop_lqIdx_flag": ldin["lqIdx_flag"],
        "uop_lqIdx_value": ldin["lqIdx_value"],
        "uop_sqIdx_first_flag": ldin["sqIdx_first_flag"],
        "uop_sqIdx_second_flag": ldin["sqIdx_second_flag"],
        "uop_sqIdx_value": ldin["sqIdx_value"],
        "vaddr": vaddr,
        "fullva": fullva,
        "size": size,
        "mask": 0 if (fu & 1) else gen_vwmask(size, vaddr),
        "noQuery": no_query,
        "entrance": 0x40,
    })
    return payload


# --------------------------------------------------------------- alignment
def up_bound(size: int, vaddr: int) -> int:
    """Offset of the last byte of the access inside its 16B word (0..30)."""
    last = 15 if (size >> 2) else ((1 << size) - 1)
    return last + (vaddr & 0xF)


def is_aligned(size: int, vaddr: int) -> bool:
    if size == 0:
        return True
    if size == 1:
        return (vaddr & 0x1) == 0
    if size == 2:
        return (vaddr & 0x3) == 0
    if size == 3:
        return (vaddr & 0x7) == 0
    return (vaddr & 0xF) == 0


def crosses_bank(size: int, vaddr: int) -> bool:
    return bool((up_bound(size, vaddr) >> 4) & 1)


def needs_128(size: int, vaddr: int) -> bool:
    bound = up_bound(size, vaddr)
    return (not (bound >> 4)) and (not (vaddr >> 3) & 1) and bool((bound >> 3) & 1)


def ring_greater(flag_a: int, value_a: int, flag_b: int, value_b: int) -> bool:
    """``a`` is after ``b`` in a power-of-two ring indexed by (flag, value)."""
    return bool((flag_a ^ flag_b ^ (1 if value_a > value_b else 0)) & 1)


# ------------------------------------------------------------------ the model
class S0Model:
    def __init__(self) -> None:
        self.pipe_out_valid = 0
        self.pipe_out_bits: dict | None = None
        self.perf0 = [0, 0]
        self.perf1 = [0, 0]

    def reset(self) -> None:
        self.pipe_out_valid = 0
        self.pipe_out_bits = None
        self.perf0 = [0, 0]
        self.perf1 = [0, 0]

    # -- helpers ---------------------------------------------------------
    @staticmethod
    def replay_is_lo_prio(inputs: dict) -> bool:
        replay = inputs["replay"]
        ldin = inputs["ldin"]
        entrance = replay["bits"].get("entrance", 0)
        if (entrance >> 1) & 1:
            return False
        if not ldin["valid"]:
            return True
        lbits = dict({name: 0 for name in LDIN_FIELDS}, **ldin["bits"])
        return not ring_greater(
            replay["bits"].get("uop_lqIdx_flag", 0),
            replay["bits"].get("uop_lqIdx_value", 0),
            lbits["lqIdx_flag"], lbits["lqIdx_value"])

    @classmethod
    def lane_valid(cls, inputs: dict) -> dict:
        replay = inputs["replay"]
        ldin = inputs["ldin"]
        hi = bool(replay["valid"] and
                  ((replay["bits"].get("entrance", 0) >> 1) & 1))
        lo = bool(replay["valid"] and cls.replay_is_lo_prio(inputs))
        return {
            0: 1 if inputs["unalign"]["valid"] else 0,
            1: 1 if hi else 0,
            2: 1 if inputs["fast"]["valid"] else 0,
            3: 1 if lo else 0,
            5: 1 if ldin["valid"] else 0,
        }

    @staticmethod
    def lane_payloads(inputs: dict) -> dict:
        unalign = dict({name: 0 for name in UNALIGN_FIELDS},
                       **inputs["unalign"]["bits"])
        replay = dict({name: 0 for name in REPLAY_FIELDS},
                      **inputs["replay"]["bits"])
        fast = dict({name: 0 for name in FAST_FIELDS},
                    **inputs["fast"]["bits"])
        ldin = dict({name: 0 for name in LDIN_FIELDS},
                    **inputs["ldin"]["bits"])

        p0 = {name: unalign.get(name, 0) for name in STAGE_FIELDS}
        p1 = {name: replay.get(name, 0) for name in STAGE_FIELDS}
        p1["noQuery"] = replay["uncacheReplay"]
        p1["paddr"] = 0
        p1["accessType_pftType"] = 0
        p2 = {name: fast.get(name, 0) for name in STAGE_FIELDS}
        p2["entrance"] = ((fast["entrance"] & 0xF8) |
                          ((fast["entrance"] & 0x7) | 0x4))
        p2["noQuery"] = 1
        p3 = dict(p1)
        p5 = ldin_payload(ldin)
        return {0: p0, 1: p1, 2: p2, 3: p3, 5: p5}

    @staticmethod
    def scalar_qualifiers(inputs: dict) -> tuple[bool, bool, bool]:
        """(aligned, crosses_16B, needs_128) for the scalar lane's own payload."""
        payload = ldin_payload(inputs["ldin"]["bits"] or {})
        return (is_aligned(payload["size"], payload["vaddr"]),
                crosses_bank(payload["size"], payload["vaddr"]),
                needs_128(payload["size"], payload["vaddr"]))

    def comb(self, inputs: dict) -> dict:
        """Combinational half: everything except the pipeOut/perf registers."""
        valid = self.lane_valid(inputs)
        payloads = self.lane_payloads(inputs)
        dcache_ready = 1 if inputs["dcache_ready"] else 0
        arb = reference_action(valid, payloads, dcache_ready)
        bits = arb["bits"]
        ready = arb["ready"]

        unalign = dict({name: 0 for name in UNALIGN_FIELDS},
                       **inputs["unalign"]["bits"])
        replay = dict({name: 0 for name in REPLAY_FIELDS},
                      **inputs["replay"]["bits"])
        fast = dict({name: 0 for name in FAST_FIELDS},
                    **inputs["fast"]["bits"])
        ldin = dict({name: 0 for name in LDIN_FIELDS},
                    **inputs["ldin"]["bits"])
        ldin_stage = ldin_payload(ldin)

        always_unalign = bool(ready[0] and inputs["unalign"]["valid"])
        first_issue = bool(ready[5] and inputs["ldin"]["valid"])
        no_align_check = always_unalign or bool((bits["accessType_instrType"] >> 2) & 1)

        # Alignment / cross-bank / 128-bit chain: S0 recomputes these from the
        # lane payloads in the arbitration priority order (the tail lane is
        # covered by ``always_unalign``, hence excluded here).
        if (valid[1] or valid[2]):
            if valid[1]:
                aligned = is_aligned(replay["size"], replay["vaddr"])
                crossing = crosses_bank(replay["size"], replay["vaddr"])
                req128 = needs_128(replay["size"], replay["vaddr"])
            else:
                aligned = is_aligned(fast["size"], fast["vaddr"])
                crossing = crosses_bank(fast["size"], fast["vaddr"])
                req128 = needs_128(fast["size"], fast["vaddr"])
        elif valid[3]:
            aligned = is_aligned(replay["size"], replay["vaddr"])
            crossing = crosses_bank(replay["size"], replay["vaddr"])
            req128 = needs_128(replay["size"], replay["vaddr"])
        else:
            aligned = is_aligned(ldin_stage["size"], ldin_stage["vaddr"])
            crossing = crosses_bank(ldin_stage["size"], ldin_stage["vaddr"])
            req128 = needs_128(ldin_stage["size"], ldin_stage["vaddr"])

        align_out = 0 if always_unalign else int(no_align_check or aligned)
        cross_bank = 0 if no_align_check else int(crossing)
        is128 = 1 if inputs["unalign"]["valid"] else int(
            (not no_align_check) and req128)

        # TLB request. ``fastReplay`` is deliberately absent from both the
        # valid term and the address mux: a fast replay is a DCache data
        # replay, it never issues a new translation request.
        tlb_valid = int(bool(inputs["unalign"]["valid"] or valid[1] or valid[3]
                             or valid[5]) and bool(dcache_ready))
        if inputs["unalign"]["valid"] or valid[1]:
            tlb_vaddr = (unalign["vaddr"] if inputs["unalign"]["valid"]
                         else replay["vaddr"])
            tlb_fu = (unalign["uop_fuOpType"] if inputs["unalign"]["valid"]
                      else replay["uop_fuOpType"])
        elif valid[3]:
            tlb_vaddr, tlb_fu = replay["vaddr"], replay["uop_fuOpType"]
        else:
            tlb_vaddr, tlb_fu = ldin_stage["vaddr"], ldin["fuOpType"]
        tlb_fu &= 0x7F

        dcache_valid = int(arb["valid"] and not (
            ((bits["accessType_instrType"] >> 2) & 1 and (bits["accessType_pftType"] & 1))
            or bits["uncacheReplay"]))
        prefetch = (bits["accessType_instrType"] >> 2) & 1

        # Forward / bypass requests. Only the *high priority* replay lane can
        # ask for uncache / MSHR / TLD forwarding.
        hi_ready = bool(ready[1] and valid[1])
        uncache_fwd = int(hi_ready and replay["uncacheReplay"])
        dchannel_fwd = int(hi_ready and replay["forwardDChannel"])

        need0 = int(always_unalign and (unalign["accessType_instrType"] & 1))
        need1 = int(hi_ready and (replay["accessType_instrType"] & 1))
        need2 = int(ready[2] and valid[2] and (fast["accessType_instrType"] & 1))
        need3 = int(ready[3] and valid[3] and (replay["accessType_instrType"] & 1))
        need_scalar = int(first_issue and not (ldin["fuOpType"] & 1))
        wakeup_valid = int(bool(need0 or need1 or need2 or need3 or need_scalar)
                           and not cross_bank)

        if need0 or need1:
            wake_src = unalign if need0 else replay
        elif need2:
            wake_src = fast
        elif need3:
            wake_src = replay
        else:
            wake_src = ldin
        if wake_src is ldin:
            wake_rf, wake_fp = ldin["rfWen"], ldin["fpWen"]
            wake_pdest = ldin["pdest"]
        else:
            wake_rf = wake_src["uop_rfWen"]
            wake_fp = wake_src["uop_fpWen"]
            wake_pdest = wake_src["uop_pdest"]

        pipe_in_valid = int(bool(arb["valid"]) and bool(dcache_ready))
        new_bits = dict(bits)
        new_bits["align"] = align_out
        new_bits["unalignHead"] = cross_bank

        out = {
            "next_valid": pipe_in_valid,
            "next_bits": new_bits if pipe_in_valid else None,
            "perf0_next": pipe_in_valid,
            "perf1_next": int(bool(arb["valid"]) and not dcache_ready),
            "unalignTail_ready": ready[0],
            "replay_ready": int((((replay["entrance"] >> 1) & 1) and ready[1])
                                or (self.replay_is_lo_prio(inputs) and ready[3])),
            "fastReplay_ready": ready[2],
            "ldin_ready": ready[5],
            "tlbReq_valid": tlb_valid,
            "tlbReq_vaddr": tlb_vaddr,
            "tlbReq_fullva": bits["fullva"],
            "tlbReq_checkfullva": int(first_issue),
            "tlbReq_hyperinst": int(((tlb_fu >> 6) & 1) and not (tlb_fu & 1)),
            "tlbReq_hlvx": int(((tlb_fu >> 6) & 1) and ((tlb_fu >> 5) & 1)
                               and not (tlb_fu & 1)),
            "tlbReq_kill": bits["noQuery"],
            "tlbReq_isPrefetch": prefetch,
            "tlbReq_no_translate": bits["noQuery"],
            "tlbReq_debug_robIdx_flag": bits["uop_robIdx_flag"],
            "tlbReq_debug_robIdx_value": bits["uop_robIdx_value"],
            "tlbReq_debug_robIdx_isFormer": bits["uop_robIdx_isFormer"],
            "tlbReq_robIdx_flag": bits["uop_robIdx_flag"],
            "tlbReq_robIdx_value": bits["uop_robIdx_value"],
            "tlbReq_robIdx_isFormer": bits["uop_robIdx_isFormer"],
            "dcacheReq_valid": dcache_valid,
            "dcacheReq_cmd": (prefetch << 1) & 0x1F,
            "dcacheReq_vaddr": bits["vaddr"],
            "dcacheReq_vaddr_dup": bits["vaddr"],
            "dcacheReq_mask": bits["mask"],
            "dcacheReq_instrtype": prefetch * 3,
            "dcacheReq_lqIdx_flag": bits["uop_lqIdx_flag"],
            "dcacheReq_lqIdx_value": bits["uop_lqIdx_value"],
            "is128Req": is128,
            "sqSbForwardReq_valid": arb["valid"],
            "sqSbForwardReq_vaddr": bits["vaddr"],
            "sqSbForwardReq_sqIdx_first_flag": bits["uop_sqIdx_first_flag"],
            "sqSbForwardReq_sqIdx_second_flag": bits["uop_sqIdx_second_flag"],
            "sqSbForwardReq_sqIdx_value": bits["uop_sqIdx_value"],
            "sqSbForwardReq_size": bits["size"],
            "sqSbForwardReq_loadWaitBit": bits["uop_loadWaitBit"],
            "sqSbForwardReq_loadWaitStrict": bits["uop_loadWaitStrict"],
            "sqSbForwardReq_waitSqIdx_first_flag": bits["uop_waitSqIdx_first_flag"],
            "sqSbForwardReq_waitSqIdx_second_flag": bits["uop_waitSqIdx_second_flag"],
            "sqSbForwardReq_waitSqIdx_value": bits["uop_waitSqIdx_value"],
            "uncacheForwardReq_valid": uncache_fwd,
            "uncacheForwardReq_vaddr": bits["vaddr"],
            "mshrForwardReq_valid": dchannel_fwd,
            "mshrForwardReq_mshrId": bits["mshrId"],
            "tldForwardReq_valid": dchannel_fwd,
            "tldForwardReq_mshrId": bits["mshrId"],
            "uncacheBypassReq_valid": uncache_fwd,
            "uncacheBypassReq_lqIdx_flag": replay["uop_lqIdx_flag"],
            "uncacheBypassReq_lqIdx_value": replay["uop_lqIdx_value"],
            "uncacheBypassReq_isNCReplay": int(bool(replay["uncacheReplay"])
                                               and bool(replay["ncReplay"])),
            "uncacheBypassReq_isMMIOReplay": int(bool(replay["uncacheReplay"])
                                                 and not replay["ncReplay"]),
            "wakeup_valid": wakeup_valid,
            "wakeup_rfWen": wake_rf,
            "wakeup_fpWen": wake_fp,
            "wakeup_pdest": wake_pdest,
            "arb": arb,
            "lane_valid": valid,
            "pipeIn_valid": pipe_in_valid,
        }
        return out

    def advance(self, inputs: dict, comb: dict) -> None:
        if comb["next_valid"]:
            self.pipe_out_bits = comb["next_bits"]
        self.pipe_out_valid = comb["next_valid"]
        self.perf0 = [comb["perf0_next"], self.perf0[0]]
        self.perf1 = [comb["perf1_next"], self.perf1[0]]

    def cycle(self, inputs: dict) -> dict:
        comb = self.comb(inputs)
        self.advance(inputs, comb)
        out = dict(comb)
        out["pipeOut_valid"] = self.pipe_out_valid
        out["pipeOut_bits"] = self.pipe_out_bits
        out["perf0"] = self.perf0[1]
        out["perf1"] = self.perf1[1]
        return out


# --------------------------------------------------------------- the environment
class LoadS0Env:
    def __init__(self, dut, coverage=None) -> None:
        self.dut = dut
        self.coverage = coverage
        self.valid = {
            "unalign": dut.io_unalignTail_valid,
            "replay": dut.io_replay_valid,
            "fast": dut.io_fastReplay_valid,
            "ldin": dut.io_ldin_valid,
        }
        self.dcache_ready = dut.io_dcacheReq_ready
        self.in_bits = {
            "unalign": {name: getattr(dut, f"io_unalignTail_bits_{name}")
                        for name in UNALIGN_FIELDS},
            "replay": {name: getattr(dut, f"io_replay_bits_{name}")
                       for name in REPLAY_FIELDS},
            "fast": {name: getattr(dut, f"io_fastReplay_bits_{name}")
                     for name in FAST_FIELDS},
            "ldin": {name: getattr(dut, f"io_ldin_bits_{name}")
                     for name in LDIN_FIELDS},
        }
        self.out = {name: getattr(dut, f"io_pipeOut_bits_{name}")
                    for name in PIPEOUT_FIELDS}
        self.out["valid"] = dut.io_pipeOut_valid
        self.ready = {
            "unalign": dut.io_unalignTail_ready,
            "replay": dut.io_replay_ready,
            "fast": dut.io_fastReplay_ready,
            "ldin": dut.io_ldin_ready,
        }
        self.tlb = {
            "valid": dut.io_tlbReq_valid,
            "vaddr": dut.io_tlbReq_bits_vaddr,
            "fullva": dut.io_tlbReq_bits_fullva,
            "checkfullva": dut.io_tlbReq_bits_checkfullva,
            "hyperinst": dut.io_tlbReq_bits_hyperinst,
            "hlvx": dut.io_tlbReq_bits_hlvx,
            "kill": dut.io_tlbReq_bits_kill,
            "isPrefetch": dut.io_tlbReq_bits_isPrefetch,
            "no_translate": dut.io_tlbReq_bits_no_translate,
            "robIdx_flag": dut.io_tlbReq_bits_debug_robIdx_flag,
            "robIdx_value": dut.io_tlbReq_bits_debug_robIdx_value,
            "robIdx_isFormer": dut.io_tlbReq_bits_debug_robIdx_isFormer,
        }
        self.dcache = {
            "valid": dut.io_dcacheReq_valid,
            "cmd": dut.io_dcacheReq_bits_cmd,
            "vaddr": dut.io_dcacheReq_bits_vaddr,
            "vaddr_dup": dut.io_dcacheReq_bits_vaddr_dup,
            "mask": dut.io_dcacheReq_bits_mask,
            "instrtype": dut.io_dcacheReq_bits_instrtype,
            "lqIdx_flag": dut.io_dcacheReq_bits_lqIdx_flag,
            "lqIdx_value": dut.io_dcacheReq_bits_lqIdx_value,
        }
        self.sqsb = {
            "valid": dut.io_sqSbForwardReq_valid,
            "vaddr": dut.io_sqSbForwardReq_bits_vaddr,
            "sqIdx_first_flag": dut.io_sqSbForwardReq_bits_sqIdx_first_flag,
            "sqIdx_second_flag": dut.io_sqSbForwardReq_bits_sqIdx_second_flag,
            "sqIdx_value": dut.io_sqSbForwardReq_bits_sqIdx_value,
            "size": dut.io_sqSbForwardReq_bits_size,
            "loadWaitBit": dut.io_sqSbForwardReq_bits_loadWaitBit,
            "loadWaitStrict": dut.io_sqSbForwardReq_bits_loadWaitStrict,
            "waitSqIdx_first_flag": dut.io_sqSbForwardReq_bits_waitSqIdx_first_flag,
            "waitSqIdx_second_flag": dut.io_sqSbForwardReq_bits_waitSqIdx_second_flag,
            "waitSqIdx_value": dut.io_sqSbForwardReq_bits_waitSqIdx_value,
        }
        self.uncache = {
            "valid": dut.io_uncacheForwardReq_valid,
            "vaddr": dut.io_uncacheForwardReq_bits_vaddr,
            "bypass_valid": dut.io_uncacheBypassReq_valid,
            "bypass_lqIdx_flag": dut.io_uncacheBypassReq_bits_lqIdx_flag,
            "bypass_lqIdx_value": dut.io_uncacheBypassReq_bits_lqIdx_value,
            "bypass_isNCReplay": dut.io_uncacheBypassReq_bits_isNCReplay,
            "bypass_isMMIOReplay": dut.io_uncacheBypassReq_bits_isMMIOReplay,
        }
        self.mshr = {"valid": dut.io_mshrForwardReq_valid,
                     "mshrId": dut.io_mshrForwardReq_bits_mshrId}
        self.tld = {"valid": dut.io_tldForwardReq_valid,
                    "mshrId": dut.io_tldForwardReq_bits_mshrId}
        self.wakeup = {
            "valid": dut.io_wakeup_valid,
            "rfWen": dut.io_wakeup_bits_rfWen,
            "fpWen": dut.io_wakeup_bits_fpWen,
            "pdest": dut.io_wakeup_bits_pdest,
        }
        self.is128 = dut.io_is128Req
        self.perf0 = dut.io_perf_0_value
        self.perf1 = dut.io_perf_1_value
        self.model = S0Model()
        self.cycles = 0

    # -- drive ------------------------------------------------------------
    def drive(self, inputs: dict) -> None:
        for lane, signal in self.valid.items():
            signal.Set(1 if inputs[lane]["valid"] else 0)
        for lane, fields in self.in_bits.items():
            for name, signal in fields.items():
                width = _input_width(lane, name)
                signal.Set(int(inputs[lane]["bits"].get(name, 0)) & ((1 << width) - 1))
        self.dcache_ready.Set(1 if inputs["dcache_ready"] else 0)

    def reset(self, cycles: int = 3) -> None:
        idle = blank_inputs()
        self.dut.reset.Set(1)
        for _ in range(cycles):
            self.drive(idle)
            self.dut.Step(1)
        self.dut.reset.Set(0)
        self.model.reset()
        self.cycles = 0

    # -- one checked cycle -------------------------------------------------
    def cycle(self, inputs: dict, context: str = "cycle") -> dict:
        want = self.model.cycle(inputs)
        self.drive(inputs)
        self.dut.Step(1)
        self.cycles += 1

        def fail(name, got, exp):
            raise AssertionError(f"{context}: {name} {got:#x} != {exp:#x} "
                                 f"(lane_valid={want['lane_valid']} "
                                 f"dcache_ready={inputs['dcache_ready']})")

        checks = {
            "pipeOut_valid": (int(self.out["valid"].value), want["pipeOut_valid"]),
            "unalignTail_ready": (int(self.ready["unalign"].value),
                                  want["unalignTail_ready"]),
            "replay_ready": (int(self.ready["replay"].value), want["replay_ready"]),
            "fastReplay_ready": (int(self.ready["fast"].value),
                                 want["fastReplay_ready"]),
            "ldin_ready": (int(self.ready["ldin"].value), want["ldin_ready"]),
            "is128Req": (int(self.is128.value), want["is128Req"]),
            "perf0": (int(self.perf0.value), want["perf0"]),
            "perf1": (int(self.perf1.value), want["perf1"]),
        }
        for key in ("valid", "vaddr", "fullva", "checkfullva", "hyperinst",
                    "hlvx", "kill", "isPrefetch", "no_translate"):
            checks[f"tlb.{key}"] = (int(self.tlb[key].value), want[f"tlbReq_{key}"])
        for key in ("flag", "value", "isFormer"):
            checks[f"tlb.robIdx_{key}"] = (int(self.tlb[f"robIdx_{key}"].value),
                                           want[f"tlbReq_debug_robIdx_{key}"])
        for key in ("valid", "cmd", "vaddr", "vaddr_dup", "mask", "instrtype",
                    "lqIdx_flag", "lqIdx_value"):
            checks[f"dcache.{key}"] = (int(self.dcache[key].value),
                                       want[f"dcacheReq_{key}"])
        for key in ("valid", "vaddr", "sqIdx_first_flag", "sqIdx_second_flag",
                    "sqIdx_value", "size", "loadWaitBit", "loadWaitStrict",
                    "waitSqIdx_first_flag", "waitSqIdx_second_flag",
                    "waitSqIdx_value"):
            checks[f"sqsb.{key}"] = (int(self.sqsb[key].value),
                                     want[f"sqSbForwardReq_{key}"])
        for key in ("valid", "vaddr"):
            checks[f"uncache.{key}"] = (int(self.uncache[key].value),
                                        want[f"uncacheForwardReq_{key}"])
        for key in ("valid", "lqIdx_flag", "lqIdx_value", "isNCReplay",
                    "isMMIOReplay"):
            checks[f"uncache.bypass_{key}"] = (
                int(self.uncache[f"bypass_{key}"].value),
                want[f"uncacheBypassReq_{key}"])
        checks["mshr.valid"] = (int(self.mshr["valid"].value),
                                want["mshrForwardReq_valid"])
        checks["mshr.mshrId"] = (int(self.mshr["mshrId"].value),
                                 want["mshrForwardReq_mshrId"])
        checks["tld.valid"] = (int(self.tld["valid"].value),
                               want["tldForwardReq_valid"])
        checks["tld.mshrId"] = (int(self.tld["mshrId"].value),
                                want["tldForwardReq_mshrId"])
        for key in ("valid", "rfWen", "fpWen", "pdest"):
            checks[f"wakeup.{key}"] = (int(self.wakeup[key].value),
                                       want[f"wakeup_{key}"])
        for name, (got, exp) in checks.items():
            if got != exp:
                fail(name, got, exp)

        if want["pipeOut_valid"]:
            for name in PIPEOUT_FIELDS:
                got = int(self.out[name].value)
                exp = want["pipeOut_bits"][name]
                if got != exp:
                    raise AssertionError(
                        f"{context}: pipeOut.{name} {got:#x} != {exp:#x} "
                        f"(lane_valid={want['lane_valid']} "
                        f"dcache_ready={inputs['dcache_ready']})")
        elif self.coverage is not None and self.model.pipe_out_bits is not None:
            # Empty beat: payload must hold its previous value.
            for name in PIPEOUT_FIELDS:
                got = int(self.out[name].value)
                exp = self.model.pipe_out_bits[name]
                if got != exp:
                    raise AssertionError(
                        f"{context}: pipeOut.{name} not held on an empty beat: "
                        f"{got:#x} != {exp:#x}")

        if self.coverage is not None:
            self.coverage.observe(want=want, inputs=inputs)
        return want


_INPUT_WIDTHS = {
    "unalign": {name: width for name, (width, _a, _d) in STAGE_FIELDS.items()},
    "replay": dict({name: width for name, (width, _a, _d) in STAGE_FIELDS.items()},
                   forwardDChannel=1),
    "fast": {name: width for name, (width, _a, _d) in STAGE_FIELDS.items()},
    "ldin": {"fuOpType": 12, "src_0": 64, "imm": 64, "robIdx_flag": 1,
             "robIdx_value": 8, "robIdx_isFormer": 1, "pdest": 8, "rfWen": 1,
             "fpWen": 1, "vecWen": 1, "v0Wen": 1, "isRVC": 1, "ftqIdx_flag": 1,
             "ftqIdx_value": 6, "ftqOffset": 5, "loadWaitBit": 1,
             "waitSqIdx_first_flag": 1, "waitSqIdx_second_flag": 1,
             "waitSqIdx_value": 6, "storeSetHit": 1, "loadWaitStrict": 1,
             "lqIdx_flag": 1, "lqIdx_value": 7, "sqIdx_first_flag": 1,
             "sqIdx_second_flag": 1, "sqIdx_value": 6},
}


def _input_width(lane: str, name: str) -> int:
    return _INPUT_WIDTHS[lane][name]


# ------------------------------------------------------------------ stimulus
def blank_lane() -> dict:
    return {name: 0 for name in PIPEOUT_FIELDS}


def blank_inputs() -> dict:
    inputs = {lane: {"valid": 0, "bits": {}} for lane in
              ("unalign", "replay", "fast", "ldin")}
    inputs["dcache_ready"] = 1
    return inputs


def random_unalign(rng: random.Random) -> dict:
    bits = {name: rng.randrange(1 << _INPUT_WIDTHS["unalign"][name])
            for name in UNALIGN_FIELDS}
    return bits


def random_replay(rng: random.Random) -> dict:
    bits = {name: rng.randrange(1 << _INPUT_WIDTHS["replay"][name])
            for name in REPLAY_FIELDS}
    return bits


def random_fast(rng: random.Random) -> dict:
    bits = {name: rng.randrange(1 << _INPUT_WIDTHS["fast"][name])
            for name in FAST_FIELDS}
    return bits


def random_ldin(rng: random.Random) -> dict:
    return {name: rng.randrange(1 << _INPUT_WIDTHS["ldin"][name])
            for name in LDIN_FIELDS}
