"""Environment and independent model for StoreUnitS1.

S1 turns a virtual store address into a physical one and decides whether the
store may proceed. Everything except the output pipeline register is
combinational, which is why the TLB response, the SQ address write, the
STA nuke query, the unaligned tail injection and the RS feedback all appear in
the same cycle as the input beat.

Relations implemented here (see ``docs/contracts/store-s1.md``):

* ``kill = redirectKill | illegalIssue | youngCrossHead``
* ``fire = valid & ~kill``
* ``tlbHit = resp.valid & ~resp.miss``
* ``feedBackHit`` / ``feedBackValid`` with the unaligned-tail two-response rule
* ``toSqAddr`` CBO normalisation (16B aligned, size=4, wlineflag=1)
* ``unalignTail`` next-16B address and high-half mask
* ``updateLFST`` / ``staNukeQueryReq`` / ``toUnalignQueue`` gating
* exception bits 3/7/15/23 and ``needRSReplay`` in the output register
"""
from __future__ import annotations

import random

from suites.memblock.lsu.pointers import rob_need_flush
from suites.memblock.lsu.store_trigger.env import (
    ACTION_CODE_BREAKPOINT,
    ACTION_CODE_DEBUG,
    TRIGGER_NUM,
    TriggerConfig,
    reference_action,
)

PIPE_IN_FIELDS = {
    "entrance": 4,
    "accessType_instrType": 3,
    "accessType_isCbo": 1,
    "accessType_isCboNoZero": 1,
    "uop_exceptionVec_19": 1,
    "uop_isRVC": 1,
    "uop_ftqPtr_flag": 1,
    "uop_ftqPtr_value": 6,
    "uop_ftqOffset": 5,
    "uop_fuOpType": 12,
    "uop_robIdx_flag": 1,
    "uop_robIdx_value": 8,
    "uop_robIdx_isFormer": 1,
    "uop_sqIdx_first_flag": 1,
    "uop_sqIdx_second_flag": 1,
    "uop_sqIdx_value": 6,
    "vaddr": 50,
    "fullva": 64,
    "size": 3,
    "mask": 16,
    "illegalIssue": 1,
    "ssid": 6,
    "storeSetHit": 1,
    "align": 1,
    "unalignHead": 1,
    "cross4KPage": 1,
    "isAddrReadyHead": 1,
}

TLB_RESP_FIELDS = {
    "paddr_0": 48,
    "gpaddr_0": 64,
    "fullva": 64,
    "pbmt_0": 2,
    "miss": 1,
    "isForVSnonLeafPTE": 1,
    "excp_0_vaNeedExt": 1,
    "excp_0_isHyper": 1,
    "excp_0_gpf_ld": 1,
    "excp_0_gpf_st": 1,
    "excp_0_pf_ld": 1,
    "excp_0_pf_st": 1,
    "excp_0_af_ld": 1,
    "excp_0_af_st": 1,
}

PIPE_OUT_FIELDS = {
    "accessType_instrType": 3,
    "accessType_isCbo": 1,
    "accessType_isCboNoZero": 1,
    "uop_exceptionVec_23": 1,
    "uop_exceptionVec_19": 1,
    "uop_exceptionVec_15": 1,
    "uop_exceptionVec_7": 1,
    "uop_exceptionVec_3": 1,
    "uop_trigger": 4,
    "uop_robIdx_flag": 1,
    "uop_robIdx_value": 8,
    "uop_robIdx_isFormer": 1,
    "fullva": 64,
    "align": 1,
    "unalignHead": 1,
    "tlbHit": 1,
    "tlbException_vaNeedExt": 1,
    "tlbException_isHyper": 1,
    "pbmt": 2,
    "isForVSnonLeafPTE": 1,
    "gpaddr": 64,
    "hasException": 1,
    "needRSReplay": 1,
}

UPDATE_LFST_FIELDS = ("sqIdx_first_flag", "sqIdx_second_flag", "sqIdx_value",
                      "ssid", "storeSetHit")
NUKE_FIELDS = ("robIdx_flag", "robIdx_value", "robIdx_isFormer",
               "sqIdx_first_flag", "sqIdx_second_flag", "sqIdx_value",
               "paddr", "mask", "matchType")
SQ_ADDR_FIELDS = {
    "uop_sqIdx_value": 6,
    "uop_fuOpType": 12,
    "uop_robIdx_flag": 1,
    "uop_robIdx_value": 8,
    "uop_robIdx_isFormer": 1,
    "uop_ftqPtr_flag": 1,
    "uop_ftqPtr_value": 6,
    "uop_ftqOffset": 5,
    "uop_isRVC": 1,
    "tlbMiss": 1,
    "vaddr": 50,
    "paddr": 48,
    "mask": 16,
    "size": 3,
    "isHyper": 1,
    "wlineflag": 1,
    "isUnalign": 1,
    "cross16Byte": 1,
    "isLastRequest": 1,
}
TAIL_OUT_FIELDS = {
    "accessType_instrType": 3,
    "accessType_isCbo": 1,
    "accessType_isCboNoZero": 1,
    "uop_exceptionVec_19": 1,
    "uop_isRVC": 1,
    "uop_ftqPtr_flag": 1,
    "uop_ftqPtr_value": 6,
    "uop_ftqOffset": 5,
    "uop_fuOpType": 12,
    "uop_robIdx_flag": 1,
    "uop_robIdx_value": 8,
    "uop_robIdx_isFormer": 1,
    "uop_sqIdx_first_flag": 1,
    "uop_sqIdx_second_flag": 1,
    "uop_sqIdx_value": 6,
    "vaddr": 50,
    "fullva": 64,
    "size": 3,
    "mask": 16,
    "cross4KPage": 1,
}
UNALIGN_QUEUE_FIELDS = ("sqIdx_first_flag", "sqIdx_second_flag", "sqIdx_value",
                        "paddr")

MASK_SMALL_BASE = {0: 0x1, 1: 0x3, 2: 0xF, 3: 0xFF}


def mask_fields(values: dict, widths: dict) -> dict:
    return {name: int(values.get(name, 0)) & ((1 << width) - 1)
            for name, width in widths.items()}


def trigger_is_vector_stride(pipe_in: dict) -> int:
    return 1 if ((pipe_in["accessType_instrType"] >> 1) & 1) and\
        (((pipe_in["uop_fuOpType"] >> 5) & 0x3) == 0) else 0


def tail_mask(vaddr: int, fu_op_type: int) -> int:
    """``genVWmask(vaddr, size) >> 16``: the high 16B half of the byte mask.

    ``genVWmask`` takes ``size.take(2)``, i.e. ``fuOpType[2:1]``, and only knows
    B/H/W/D, so a 16B store produces a 0xFF base here. The shifted value is
    truncated to the low 7 bits of the high half by the generated width.
    """
    base = MASK_SMALL_BASE[(fu_op_type >> 1) & 0x3]
    return ((base << (vaddr & 0xF)) >> 16) & 0x7F


class StoreS1Model:
    def __init__(self) -> None:
        self.valid = 0
        self.bits: dict[str, int] | None = None

    def comb(self, pipe_in_valid: int, pipe_in: dict, tlb: dict,
             tlb_valid: int, redirect: dict, trigger_cfg: list[TriggerConfig],
             trigger_enables: list[int], trigger_debug: int, trigger_bp_exp: int,
             unalign_head_tlb_hit: int, unalign_queue_ready: int) -> dict:
        pipe_in = mask_fields(pipe_in, PIPE_IN_FIELDS)
        tlb = mask_fields(tlb, TLB_RESP_FIELDS)
        instr_type = pipe_in["accessType_instrType"]
        is_scalar = instr_type & 0x1
        is_vector = (instr_type >> 1) & 0x1
        is_prefetch = (instr_type >> 2) & 1
        is_cbo = pipe_in["accessType_isCbo"]

        illegal_issue = bool(pipe_in_valid) and bool(pipe_in["illegalIssue"])
        young_cross_head = bool(pipe_in_valid) and bool(is_scalar) and\
            bool(pipe_in["unalignHead"]) and bool(pipe_in["cross4KPage"]) and\
            not bool(pipe_in["isAddrReadyHead"])
        # ``RobPtr.needFlush`` has no ``pipeIn.valid`` gate in the RTL, so a
        # redirect can raise kill (and therefore tlbReqKill) on an idle cycle
        # whose stale payload happens to be younger than the redirect target.
        redirect_kill = rob_need_flush(
            pipe_in["uop_robIdx_flag"], pipe_in["uop_robIdx_value"],
            pipe_in["uop_robIdx_isFormer"], redirect)
        killed = redirect_kill or illegal_issue or young_cross_head
        fire = bool(pipe_in_valid) and not killed

        tlb_hit = bool(tlb_valid) and not bool(tlb["miss"])
        both_hit = tlb_hit and bool(unalign_head_tlb_hit)
        force_replay = bool(is_scalar) and (illegal_issue or young_cross_head)
        feedback_valid = (fire and bool(is_scalar) and not bool(pipe_in["unalignHead"]))\
            or force_replay
        feedback_hit_inner = (both_hit and (not bool(pipe_in["cross4KPage"]) or
                                            bool(unalign_queue_ready)))\
            if pipe_in["entrance"] & 0x1 else tlb_hit
        feedback_hit = bool(feedback_hit_inner) and not force_replay

        trigger_action = reference_action(
            trigger_cfg, pipe_in["vaddr"], pipe_in["mask"], bool(is_cbo),
            bool(trigger_is_vector_stride(pipe_in)), trigger_debug,
            trigger_enables, trigger_bp_exp)

        pf = tlb_hit and (bool(tlb["excp_0_pf_st"]) or bool(tlb["excp_0_pf_ld"]))
        af = tlb_hit and (bool(tlb["excp_0_af_st"]) or bool(tlb["excp_0_af_ld"]))
        gpf = tlb_hit and (bool(tlb["excp_0_gpf_st"]) or bool(tlb["excp_0_gpf_ld"]))
        is_breakpoint = trigger_action == ACTION_CODE_BREAKPOINT

        update_lfst_valid = fire and tlb_hit and bool(is_scalar) and\
            not bool(pipe_in["entrance"] & 0x1)
        nuke_valid = fire and tlb_hit and not bool(is_prefetch)
        sq_addr_valid = fire and not bool(is_prefetch)
        tail_valid = fire and bool(pipe_in["unalignHead"])
        queue_valid = fire and bool(pipe_in["entrance"] & 0x1) and\
            bool(pipe_in["cross4KPage"]) and both_hit

        sq_vaddr = (pipe_in["vaddr"] & ~0xF) | 0 if is_cbo else pipe_in["vaddr"]
        sq_paddr = (tlb["paddr_0"] & ~0xF) | 0 if is_cbo else tlb["paddr_0"]
        sq_size = 4 if is_cbo else pipe_in["size"]

        tail_vaddr = (((pipe_in["vaddr"] >> 4) + 1) << 4) & ((1 << 50) - 1)
        tail_fullva = (((tlb["fullva"] >> 4) + 1) << 4) & ((1 << 64) - 1)
        tail = {
            "accessType_instrType": instr_type,
            "accessType_isCbo": pipe_in["accessType_isCbo"],
            "accessType_isCboNoZero": pipe_in["accessType_isCboNoZero"],
            "uop_exceptionVec_19": pipe_in["uop_exceptionVec_19"],
            "uop_isRVC": pipe_in["uop_isRVC"],
            "uop_ftqPtr_flag": pipe_in["uop_ftqPtr_flag"],
            "uop_ftqPtr_value": pipe_in["uop_ftqPtr_value"],
            "uop_ftqOffset": pipe_in["uop_ftqOffset"],
            "uop_fuOpType": pipe_in["uop_fuOpType"],
            "uop_robIdx_flag": pipe_in["uop_robIdx_flag"],
            "uop_robIdx_value": pipe_in["uop_robIdx_value"],
            "uop_robIdx_isFormer": pipe_in["uop_robIdx_isFormer"],
            "uop_sqIdx_first_flag": pipe_in["uop_sqIdx_first_flag"],
            "uop_sqIdx_second_flag": pipe_in["uop_sqIdx_second_flag"],
            "uop_sqIdx_value": pipe_in["uop_sqIdx_value"],
            "vaddr": tail_vaddr,
            "fullva": tail_fullva,
            "size": pipe_in["size"],
            "mask": tail_mask(pipe_in["vaddr"], pipe_in["uop_fuOpType"]),
            "cross4KPage": pipe_in["cross4KPage"],
        }

        next_bits = {
            "accessType_instrType": instr_type,
            "accessType_isCbo": pipe_in["accessType_isCbo"],
            "accessType_isCboNoZero": pipe_in["accessType_isCboNoZero"],
            "uop_exceptionVec_23": int(gpf),
            "uop_exceptionVec_19": pipe_in["uop_exceptionVec_19"],
            "uop_exceptionVec_15": int(pf),
            "uop_exceptionVec_7": int(af),
            "uop_exceptionVec_3": int(is_breakpoint),
            "uop_trigger": trigger_action,
            "uop_robIdx_flag": pipe_in["uop_robIdx_flag"],
            "uop_robIdx_value": pipe_in["uop_robIdx_value"],
            "uop_robIdx_isFormer": pipe_in["uop_robIdx_isFormer"],
            "fullva": pipe_in["fullva"],
            "align": pipe_in["align"],
            "unalignHead": pipe_in["unalignHead"],
            "tlbHit": int(tlb_hit),
            "tlbException_vaNeedExt": tlb["excp_0_vaNeedExt"],
            "tlbException_isHyper": tlb["excp_0_isHyper"],
            "pbmt": tlb["pbmt_0"] if tlb_hit else 0,
            "isForVSnonLeafPTE": tlb["isForVSnonLeafPTE"],
            "gpaddr": tlb["gpaddr_0"],
            "hasException": int(pf or af or gpf or
                                trigger_action == ACTION_CODE_DEBUG or is_breakpoint),
            "needRSReplay": int(feedback_valid and not feedback_hit),
        }
        return {
            "kill": killed,
            "redirect_kill": redirect_kill,
            "illegal_issue": illegal_issue,
            "young_cross_head": young_cross_head,
            "fire": fire,
            "tlb_hit": tlb_hit,
            "both_hit": both_hit,
            "force_replay": force_replay,
            "feedback_valid": feedback_valid,
            "feedback_hit": feedback_hit,
            "trigger_action": trigger_action,
            "out_valid": int(bool(pipe_in_valid) and not killed),
            "out_bits": next_bits,
            "tlbReqKill": int(killed),
            "updateLFST_valid": int(update_lfst_valid),
            "updateLFST_bits": {
                "sqIdx_first_flag": pipe_in["uop_sqIdx_first_flag"],
                "sqIdx_second_flag": pipe_in["uop_sqIdx_second_flag"],
                "sqIdx_value": pipe_in["uop_sqIdx_value"],
                "ssid": pipe_in["ssid"],
                "storeSetHit": pipe_in["storeSetHit"],
            },
            "staNukeQueryReq_valid": int(nuke_valid),
            "staNukeQueryReq_bits": {
                "robIdx_flag": pipe_in["uop_robIdx_flag"],
                "robIdx_value": pipe_in["uop_robIdx_value"],
                "robIdx_isFormer": pipe_in["uop_robIdx_isFormer"],
                "sqIdx_first_flag": pipe_in["uop_sqIdx_first_flag"],
                "sqIdx_second_flag": pipe_in["uop_sqIdx_second_flag"],
                "sqIdx_value": pipe_in["uop_sqIdx_value"],
                "paddr": tlb["paddr_0"],
                "mask": pipe_in["mask"],
                "matchType": ((1 if is_cbo else 0) << 1),
            },
            "toSqAddr_valid": int(sq_addr_valid),
            "toSqAddr_bits": {
                "uop_sqIdx_value": pipe_in["uop_sqIdx_value"],
                "uop_fuOpType": pipe_in["uop_fuOpType"],
                "uop_robIdx_flag": pipe_in["uop_robIdx_flag"],
                "uop_robIdx_value": pipe_in["uop_robIdx_value"],
                "uop_robIdx_isFormer": pipe_in["uop_robIdx_isFormer"],
                "uop_ftqPtr_flag": pipe_in["uop_ftqPtr_flag"],
                "uop_ftqPtr_value": pipe_in["uop_ftqPtr_value"],
                "uop_ftqOffset": pipe_in["uop_ftqOffset"],
                "uop_isRVC": pipe_in["uop_isRVC"],
                "tlbMiss": 0 if feedback_hit else 1,
                "vaddr": sq_vaddr,
                "paddr": sq_paddr,
                "mask": pipe_in["mask"],
                "size": sq_size,
                "isHyper": tlb["excp_0_isHyper"],
                "wlineflag": pipe_in["accessType_isCbo"],
                "isUnalign": 0 if pipe_in["align"] else 1,
                "cross16Byte": 1 if ((pipe_in["entrance"] & 0x1) or
                                     pipe_in["unalignHead"]) else 0,
                "isLastRequest": 0 if pipe_in["unalignHead"] else 1,
            },
            "unalignTail_valid": int(tail_valid),
            "unalignTail_bits": tail,
            "toUnalignQueue_valid": int(queue_valid),
            "toUnalignQueue_bits": {
                "sqIdx_first_flag": pipe_in["uop_sqIdx_first_flag"],
                "sqIdx_second_flag": pipe_in["uop_sqIdx_second_flag"],
                "sqIdx_value": pipe_in["uop_sqIdx_value"],
                "paddr": tlb["paddr_0"],
            },
            "feedBackSlow_valid": int(feedback_valid),
            "feedBackSlow_hit": int(feedback_hit),
        }


class StoreS1Env:
    def __init__(self, dut, coverage=None) -> None:
        self.dut = dut
        self.coverage = coverage
        self.in_valid = dut.io_pipeIn_valid
        self.in_bits = {name: getattr(dut, f"io_pipeIn_bits_{name}")
                        for name in PIPE_IN_FIELDS}
        self.out_valid = dut.io_pipeOut_valid
        self.out = {name: getattr(dut, f"io_pipeOut_bits_{name}")
                    for name in PIPE_OUT_FIELDS}
        self.redirect_valid = dut.io_redirect_valid
        self.redirect_level = dut.io_redirect_bits_level
        self.redirect_flag = dut.io_redirect_bits_robIdx_flag
        self.redirect_value = dut.io_redirect_bits_robIdx_value
        self.redirect_former = dut.io_redirect_bits_robIdx_isFormer
        self.tlb_valid_sig = dut.io_tlbResp_valid
        self.tlb = {name: getattr(dut, f"io_tlbResp_bits_{name}")
                    for name in TLB_RESP_FIELDS}
        self.tlb_req_kill = dut.io_tlbReqKill
        self.update_lfst_valid = dut.io_updateLFST_valid
        self.update_lfst = {name: getattr(dut, f"io_updateLFST_bits_{name}")
                            for name in UPDATE_LFST_FIELDS}
        self.nuke_valid = dut.io_staNukeQueryReq_valid
        self.nuke = {name: getattr(dut, f"io_staNukeQueryReq_bits_{name}")
                     for name in NUKE_FIELDS}
        self.sq_valid = dut.io_toSqAddr_valid
        self.sq = {name: getattr(dut, f"io_toSqAddr_bits_{name}")
                   for name in SQ_ADDR_FIELDS}
        self.tail_valid = dut.io_unalignTail_valid
        self.tail = {name: getattr(dut, f"io_unalignTail_bits_{name}")
                     for name in TAIL_OUT_FIELDS}
        self.queue_valid = dut.io_toUnalignQueue_valid
        self.queue = {name: getattr(dut, f"io_toUnalignQueue_bits_{name}")
                      for name in UNALIGN_QUEUE_FIELDS}
        self.queue_ready = dut.io_toUnalignQueue_ready
        self.feedback_valid = dut.io_feedBackSlow_valid
        self.feedback_hit = dut.io_feedBackSlow_bits_hit
        self.unalign_head_tlb_hit = dut.io_unalignHeadTlbHit
        self.trigger_signals = []
        for index in range(TRIGGER_NUM):
            prefix = f"io_csrTrigger_tdataVec_{index}_"
            self.trigger_signals.append({
                "match_type": getattr(dut, prefix + "matchType"),
                "select": getattr(dut, prefix + "select"),
                "timing": getattr(dut, prefix + "timing"),
                "action": getattr(dut, prefix + "action"),
                "chain": getattr(dut, prefix + "chain"),
                "store": getattr(dut, prefix + "store"),
                "tdata2": getattr(dut, prefix + "tdata2"),
            })
        self.trigger_enable = [getattr(dut, f"io_csrTrigger_tEnableVec_{index}")
                               for index in range(TRIGGER_NUM)]
        self.trigger_debug = dut.io_csrTrigger_debugMode
        self.trigger_bp_exp = dut.io_csrTrigger_triggerCanRaiseBpExp
        self.model = StoreS1Model()
        self.cycles = 0

    # ------------------------------------------------------------------ reset
    def reset(self, cycles: int = 4) -> None:
        self.dut.reset.Set(1)
        for _ in range(cycles):
            self.dut.Step(1)
        self.dut.reset.Set(0)
        self.model = StoreS1Model()
        self.drive(0, blank(PIPE_IN_FIELDS), blank(TLB_RESP_FIELDS), 0,
                   blank_redirect(), blank_trigger(), [0] * TRIGGER_NUM, 0, 1, 0, 1)
        self.dut.Step(1)

    # ------------------------------------------------------------------ drive
    def drive(self, in_valid: int, in_bits: dict, tlb: dict, tlb_valid: int,
              redirect: dict, trigger_cfg: list[TriggerConfig],
              trigger_enables: list[int], trigger_debug: int, trigger_bp_exp: int,
              unalign_head_tlb_hit: int, queue_ready: int) -> None:
        self.in_valid.Set(1 if in_valid else 0)
        for name, signal in self.in_bits.items():
            signal.Set(int(in_bits.get(name, 0)))
        self.tlb_valid_sig.Set(1 if tlb_valid else 0)
        for name, signal in self.tlb.items():
            signal.Set(int(tlb.get(name, 0)))
        self.redirect_valid.Set(1 if redirect["valid"] else 0)
        self.redirect_level.Set(int(redirect["level"]))
        self.redirect_flag.Set(int(redirect["flag"]))
        self.redirect_value.Set(int(redirect["value"]))
        self.redirect_former.Set(int(redirect["former"]))
        for index, cfg in enumerate(trigger_cfg):
            signals = self.trigger_signals[index]
            signals["match_type"].Set(cfg.match_type)
            signals["select"].Set(cfg.select)
            signals["timing"].Set(cfg.timing)
            signals["action"].Set(cfg.action)
            signals["chain"].Set(cfg.chain)
            signals["store"].Set(cfg.store)
            signals["tdata2"].Set(cfg.tdata2 & ((1 << 64) - 1))
            self.trigger_enable[index].Set(1 if trigger_enables[index] else 0)
        self.trigger_debug.Set(1 if trigger_debug else 0)
        self.trigger_bp_exp.Set(1 if trigger_bp_exp else 0)
        self.unalign_head_tlb_hit.Set(1 if unalign_head_tlb_hit else 0)
        self.queue_ready.Set(1 if queue_ready else 0)

    # -------------------------------------------------------------- one cycle
    def cycle(self, in_valid: int, in_bits: dict, tlb: dict, tlb_valid: int,
              redirect: dict, trigger_cfg: list[TriggerConfig],
              trigger_enables: list[int], trigger_debug: int, trigger_bp_exp: int,
              unalign_head_tlb_hit: int, queue_ready: int,
              context: str = "cycle") -> dict:
        want = self.model.comb(in_valid, in_bits, tlb, tlb_valid, redirect,
                               trigger_cfg, trigger_enables, trigger_debug,
                               trigger_bp_exp, unalign_head_tlb_hit, queue_ready)
        self.drive(in_valid, in_bits, tlb, tlb_valid, redirect, trigger_cfg,
                   trigger_enables, trigger_debug, trigger_bp_exp,
                   unalign_head_tlb_hit, queue_ready)
        self.dut.Step(1)

        debug = {
            "in_valid": in_valid, "instr": in_bits.get("accessType_instrType"),
            "entrance": in_bits.get("entrance"), "illegal": in_bits.get("illegalIssue"),
            "unalign_head": in_bits.get("unalignHead"),
            "cross4k": in_bits.get("cross4KPage"),
            "addr_ready": in_bits.get("isAddrReadyHead"),
            "tlb_valid": tlb_valid, "tlb_miss": tlb.get("miss"),
            "redirect": redirect, "head_hit": unalign_head_tlb_hit,
            "queue_ready": queue_ready,
            "fire": want["fire"], "redirect_kill": want["redirect_kill"],
            "illegal_issue": want["illegal_issue"],
            "young_cross_head": want["young_cross_head"],
        }

        def expect(signal, value, name):
            got = int(signal.value)
            if got != value:
                raise AssertionError(
                    f"{context}: {name} {got:#x} != {value:#x}; inputs={debug}")

        expect(self.tlb_req_kill, want["tlbReqKill"], "tlbReqKill")
        expect(self.update_lfst_valid, want["updateLFST_valid"], "updateLFST.valid")
        if want["updateLFST_valid"]:
            for name, signal in self.update_lfst.items():
                expect(signal, want["updateLFST_bits"][name], f"updateLFST.{name}")
        expect(self.nuke_valid, want["staNukeQueryReq_valid"], "staNukeQueryReq.valid")
        if want["staNukeQueryReq_valid"]:
            for name, signal in self.nuke.items():
                expect(signal, want["staNukeQueryReq_bits"][name],
                       f"staNukeQueryReq.{name}")
        expect(self.sq_valid, want["toSqAddr_valid"], "toSqAddr.valid")
        if want["toSqAddr_valid"]:
            for name, signal in self.sq.items():
                expect(signal, want["toSqAddr_bits"][name], f"toSqAddr.{name}")
        expect(self.tail_valid, want["unalignTail_valid"], "unalignTail.valid")
        if want["unalignTail_valid"]:
            for name, signal in self.tail.items():
                expect(signal, want["unalignTail_bits"][name], f"unalignTail.{name}")
        expect(self.queue_valid, want["toUnalignQueue_valid"], "toUnalignQueue.valid")
        if want["toUnalignQueue_valid"]:
            for name, signal in self.queue.items():
                expect(signal, want["toUnalignQueue_bits"][name],
                       f"toUnalignQueue.{name}")
        expect(self.feedback_valid, want["feedBackSlow_valid"], "feedBackSlow.valid")
        if want["feedBackSlow_valid"]:
            expect(self.feedback_hit, want["feedBackSlow_hit"], "feedBackSlow.hit")

        expect(self.out_valid, want["out_valid"], "pipeOut.valid")
        got_bits = {name: int(signal.value) for name, signal in self.out.items()}
        if want["out_valid"]:
            for name, got in got_bits.items():
                if got != want["out_bits"][name]:
                    raise AssertionError(
                        f"{context}: pipeOut.bits.{name} {got:#x} != "
                        f"{want['out_bits'][name]:#x}")

        if self.coverage is not None:
            self.coverage.observe(want=want, pipe_in=in_bits, tlb=tlb,
                                  redirect=redirect, trigger_action=want["trigger_action"])
        self.model.valid = want["out_valid"]
        self.model.bits = want["out_bits"] if want["out_valid"] else None
        self.cycles += 1
        return want


def blank(fields) -> dict[str, int]:
    return {name: 0 for name in fields}


def blank_redirect() -> dict:
    return {"valid": 0, "level": 0, "flag": 0, "value": 0, "former": 0}


def blank_trigger() -> list[TriggerConfig]:
    return [TriggerConfig(action=ACTION_CODE_DEBUG, tdata2=0, store=1)
            for _ in range(TRIGGER_NUM)]


def random_pipe_in(rng: random.Random, **overrides) -> dict:
    values = {name: rng.randrange(1 << width) for name, width in PIPE_IN_FIELDS.items()}
    values.update(overrides)
    return values


def random_tlb(rng: random.Random, **overrides) -> dict:
    values = {name: rng.randrange(1 << width) for name, width in TLB_RESP_FIELDS.items()}
    values.update(overrides)
    return values
