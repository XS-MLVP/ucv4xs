"""Environment and independent reference for LoadUnitS1.

S1 turns an S0 request into a translated load: it merges the TLB response,
raises the load exceptions, decides the replay/kill conditions, extracts the
unaligned tail, feeds the data-path metadata and the trigger unit, and registers
the widened S1 beat.

Micro-architectural rules encoded here:

* **kill**: no valid input, or any of the redirect pipeline entries (current,
  1-cycle-delayed, 2-cycle-delayed) covers this load. The 2-cycle-delayed
  redirect only kills *tail injections* (``entrance[0]``), because a tail is
  injected into S0 one cycle after the head passed S1.
* **TLB merge**: ``tlbHit = resp.valid & ~miss & ~noQuery``,
  ``paddr = noQuery ? (bypass valid ? bypass.paddr : in.paddr) : resp.paddr_0``,
  ``dcachePAddr`` uses the second TLB port ``paddr_1``.
* **exception**: page/access/guest-page faults only when ``tlbHit``; the
  breakpoint comes from the independently verified ``MemTrigger`` child
  (``action == BREAKPOINT``).
* **killDCache** = kill | tlbMiss | tlbException | specialRequest; forward
  requests to SQ/Sbuffer use the same term, while the uncache forward and the
  TLB request only use kill | specialRequest.
* **unalign tail**: emitted whenever ``pipeIn.valid & unalignHead`` (even for a
  killed beat - the redirect pipeline re-kills it one cycle later), with the
  address advanced by one 16B line and the byte mask shifted into the next line.
* **shouldFastReplay** = tail injected, S0's tail lane not ready, and the head
  did not miss or fault.
* **output register**: payload captures on every ``pipeIn.valid`` beat, valid is
  ``~kill & pipeIn.valid``; there is no backpressure at this boundary.

Contract: docs/contracts/load-s1.md
"""
from __future__ import annotations

import random

from lsuverify.load_trigger.env import (
    ACTION_BREAKPOINT,
    reference_action,
)
from lsuverify.store_trigger.env import TriggerConfig

PIPEIN_FIELDS = {
    "entrance": 8, "accessType_instrType": 3, "accessType_pftType": 2,
    "uop_exceptionVec_23": 1, "uop_exceptionVec_19": 1, "uop_exceptionVec_15": 1,
    "uop_exceptionVec_7": 1, "uop_exceptionVec_6": 1, "uop_isRVC": 1,
    "uop_ftqPtr_flag": 1, "uop_ftqPtr_value": 6, "uop_ftqOffset": 5,
    "uop_fuOpType": 12, "uop_rfWen": 1, "uop_fpWen": 1, "uop_vecWen": 1,
    "uop_v0Wen": 1, "uop_pdest": 8, "uop_robIdx_flag": 1,
    "uop_robIdx_value": 8, "uop_robIdx_isFormer": 1,
    "uop_perfDebugInfo_runahead_checkpoint_id": 64, "uop_storeSetHit": 1,
    "uop_waitSqIdx_first_flag": 1, "uop_waitSqIdx_second_flag": 1,
    "uop_waitSqIdx_value": 6, "uop_loadWaitBit": 1, "uop_loadWaitStrict": 1,
    "uop_lqIdx_flag": 1, "uop_lqIdx_value": 7, "uop_sqIdx_first_flag": 1,
    "uop_sqIdx_second_flag": 1, "uop_sqIdx_value": 6, "vaddr": 50, "fullva": 64,
    "size": 3, "mask": 16, "paddr": 48, "noQuery": 1, "align": 1,
    "unalignHead": 1, "mshrId": 4, "replayQueueIdx": 7, "uncacheReplay": 1,
    "ncReplay": 1,
}
TLB_FIELDS = {
    "paddr_0": 48, "paddr_1": 48, "gpaddr_0": 64, "fullva": 64, "pbmt_0": 2,
    "miss": 1, "isForVSnonLeafPTE": 1, "excp_0_vaNeedExt": 1,
    "excp_0_isHyper": 1, "excp_0_gpf_ld": 1, "excp_0_pf_ld": 1,
    "excp_0_af_ld": 1,
}
REDIRECT_FIELDS = {"level": 1, "robIdx_flag": 1, "robIdx_value": 8,
                   "robIdx_isFormer": 1}
NUKE_FIELDS = {"robIdx_flag": 1, "robIdx_value": 8, "robIdx_isFormer": 1,
               "sqIdx_first_flag": 1, "sqIdx_second_flag": 1, "sqIdx_value": 6,
               "paddr": 48, "mask": 16, "matchType": 2}

# pipeOut field set = the S1 LoadStageIO widening: the S0 payload plus the TLB
# results and the replay bookkeeping.
PIPEOUT_FIELDS = tuple(name for name in PIPEIN_FIELDS
                       if name not in ("noQuery", "mshrId")) + (
    "uop_exceptionVec_21", "uop_exceptionVec_13", "uop_exceptionVec_5",
    "uop_exceptionVec_3", "uop_trigger", "tlbAccessResult",
    "tlbException_vaNeedExt", "tlbException_isHyper", "pbmt", "gpaddr",
    "isForVSnonLeafPTE", "cause_11", "specialModeRequest",
    "fastReplayNukeFirst", "shouldFastReplay",
)


def ring_greater(flag_a: int, value_a: int, flag_b: int, value_b: int) -> bool:
    return bool((flag_a ^ flag_b ^ (1 if value_a > value_b else 0)) & 1)


def same_index(a: dict, b: dict, prefix_a: str = "", prefix_b: str = "") -> bool:
    return (a[prefix_a + "flag"] == b[prefix_b + "flag"]
            and a[prefix_a + "value"] == b[prefix_b + "value"])


def redirect_kill(pipe: dict, red: dict) -> bool:
    """``Redirect.level`` widens the match to the whole ROB entry; the
    ``isFormer`` bits order two uops of the same ROB entry."""
    same = same_index(pipe, red, "uop_robIdx_", "robIdx_")
    level_same = bool(red["level"]) and same and (
        pipe["uop_robIdx_isFormer"] == red["robIdx_isFormer"])
    newer = ring_greater(pipe["uop_robIdx_flag"], pipe["uop_robIdx_value"],
                         red["robIdx_flag"], red["robIdx_value"])
    former = (same and not pipe["uop_robIdx_isFormer"]
              and bool(red["robIdx_isFormer"]))
    return bool(level_same or newer or former)


def gen_vwmask_16(size: int, vaddr: int) -> int:
    base = 0xFFFF if (size >> 2) else ((1 << (1 << size)) - 1)
    return (base << (vaddr & 0xF)) & 0xFFFF


def tail_mask(fu_op_type: int, vaddr: int) -> int:
    """Mask of the bytes that spilled into the *next* 16B line.

    The RTL decodes the size from ``fuOpType[3:1]`` (not from the ``size`` input
    port, which is only a payload copy), and uses ``fuOpType[3]`` to select the
    16B base mask.
    """
    size = (fu_op_type >> 1) & 0x7
    base = 0xFFFF if (fu_op_type & 0x8) else ((1 << (1 << size)) - 1)
    shifted = (base << (vaddr & 0xF)) & 0x7FFF_FFFF
    return (shifted >> 16) & 0x7FFF


class S1Model:
    def __init__(self) -> None:
        self.redirect_next_valid = 0
        self.redirect_next_bits: dict | None = None
        self.redirect_nextnext_valid = 0
        self.redirect_nextnext_bits: dict | None = None
        self.pipe_out_valid = 0
        self.pipe_out_bits: dict | None = None
        self.perf0 = [0, 0]
        self.perf1 = [0, 0]

    def reset(self) -> None:
        self.redirect_next_valid = 0
        self.redirect_next_bits = None
        self.redirect_nextnext_valid = 0
        self.redirect_nextnext_bits = None
        self.pipe_out_valid = 0
        self.pipe_out_bits = None
        self.perf0 = [0, 0]
        self.perf1 = [0, 0]

    def _state_kill(self, inputs: dict) -> bool:
        """Redirect kill evaluated against the *current* redirect pipeline."""
        pipe = dict({name: 0 for name in PIPEIN_FIELDS},
                    **inputs["pipeIn"]["bits"])
        redirect = inputs["redirect"]
        if not inputs["pipeIn"]["valid"]:
            return True
        return bool(
            (redirect["valid"] and redirect_kill(pipe, redirect["bits"]))
            or (self.redirect_next_valid
                and redirect_kill(pipe, self.redirect_next_bits))
            or (self.redirect_nextnext_valid and (pipe["entrance"] & 1)
                and redirect_kill(pipe, self.redirect_nextnext_bits)))

    def comb(self, inputs: dict) -> dict:
        """Combinational half: kill uses the *current* redirect pipeline."""
        pipe = dict({name: 0 for name in PIPEIN_FIELDS},
                    **inputs["pipeIn"]["bits"])
        pipe_valid = 1 if inputs["pipeIn"]["valid"] else 0
        redirect = inputs["redirect"]
        tlb = inputs["tlbResp"]
        tlb_bits = dict({name: 0 for name in TLB_FIELDS}, **tlb["bits"])
        bypass = inputs["bypass"]
        nukes = inputs["nuke"]
        trigger = inputs["trigger"]

        # The flops sample the combinational kill of the *pre-edge* state.
        kill_reg = self._state_kill(inputs)

        # -------------------------------------------------------------- trigger
        is_vector_stride = int(bool(pipe["accessType_instrType"] & 0x2)
                               and ((pipe["uop_fuOpType"] >> 5) & 0x3) == 0)
        is_prf = (pipe["accessType_instrType"] >> 2) & 1
        action = reference_action(
            trigger["configs"], pipe["vaddr"], pipe["mask"], is_vector_stride,
            is_prf, trigger["debugMode"], trigger["enables"],
            trigger["canRaiseBpExp"])
        bp = int(action == ACTION_BREAKPOINT)

        # ------------------------------------------------------------ TLB merge
        tlb_hit = int(bool(tlb["valid"]) and not tlb_bits["miss"]
                      and not pipe["noQuery"])
        tlb_miss = int(bool(tlb["valid"]) and bool(tlb_bits["miss"]))
        special_request = int(bool(inputs["specialMode"])
                              and not (same_index(pipe, inputs["robHeadPtr"],
                                                  "uop_robIdx_", "")))
        no_query_paddr = (bypass["bits"].get("paddr", 0)
                          if bypass["valid"] else pipe["paddr"])
        paddr = no_query_paddr if pipe["noQuery"] else tlb_bits["paddr_0"]
        pf = int(tlb_hit and tlb_bits["excp_0_pf_ld"])
        af = int(tlb_hit and tlb_bits["excp_0_af_ld"])
        gpf = int(tlb_hit and tlb_bits["excp_0_gpf_ld"])
        tlb_exception = pf or af or gpf
        tail_inject = int(bool(pipe_valid) and bool(pipe["unalignHead"]))

        # ------------------------------------------------------ nuke / replay
        def nuke_match(req: dict) -> int:
            if not req["valid"]:
                return 0
            bits = req["bits"]
            if bits["matchType"] == 2:
                addr_match = (paddr >> 6) == (bits["paddr"] >> 6)
            else:
                addr_match = (paddr >> 4) == (bits["paddr"] >> 4)
            order = (ring_greater(pipe["uop_robIdx_flag"],
                                  pipe["uop_robIdx_value"],
                                  bits["robIdx_flag"], bits["robIdx_value"])
                     or (same_index({"flag": pipe["uop_robIdx_flag"],
                                     "value": pipe["uop_robIdx_value"]},
                                    bits, "", "robIdx_")
                         and not pipe["uop_robIdx_isFormer"]
                         and bool(bits["robIdx_isFormer"])))
            overlap = bool(bits["mask"] & pipe["mask"])
            return int(addr_match and order and overlap)

        nuke0 = nuke_match(nukes[0])
        nuke1 = nuke_match(nukes[1])
        cause_11 = int(bool(nuke0 or nuke1) and bool(tlb_hit or pipe["noQuery"]))

        wait_sq = ((pipe["uop_waitSqIdx_first_flag"] << 7)
                   | (pipe["uop_waitSqIdx_second_flag"] << 6)
                   | pipe["uop_waitSqIdx_value"])
        sq0 = ((nukes[0]["bits"]["sqIdx_first_flag"] << 7)
               | (nukes[0]["bits"]["sqIdx_second_flag"] << 6)
               | nukes[0]["bits"]["sqIdx_value"]) if nukes[0]["valid"] else None
        sq1 = ((nukes[1]["bits"]["sqIdx_first_flag"] << 7)
               | (nukes[1]["bits"]["sqIdx_second_flag"] << 6)
               | nukes[1]["bits"]["sqIdx_value"]) if nukes[1]["valid"] else None
        fast_replay_nuke_first = int(
            bool(pipe["uop_storeSetHit"])
            and ((sq0 == wait_sq and nukes[0]["valid"])
                 or (sq1 == wait_sq and nukes[1]["valid"])))

        should_fast_replay = int(
            bool(tail_inject) and not inputs["unalignTail_ready"]
            and not tlb_miss and not (tlb_exception or bp))

        is_sw_prefetch = int(bool((pipe["accessType_instrType"] >> 2) & 1)
                             and (pipe["accessType_pftType"] & 0x3) == 3)

        # -------------------------------------------------------- pipeOut regs
        new_bits = {name: pipe.get(name, 0) for name in PIPEOUT_FIELDS}
        new_bits.update({
            "uop_exceptionVec_21": gpf,
            "uop_exceptionVec_13": pf,
            "uop_exceptionVec_5": af,
            "uop_exceptionVec_3": bp,
            "uop_trigger": action,
            "fullva": tlb_bits["fullva"],
            "paddr": paddr,
            "tlbAccessResult": (1 if pipe["noQuery"] else (2 if tlb_hit else 4)),
            "tlbException_vaNeedExt": tlb_bits["excp_0_vaNeedExt"],
            "tlbException_isHyper": tlb_bits["excp_0_isHyper"],
            "pbmt": tlb_bits["pbmt_0"] if tlb_hit else 0,
            "gpaddr": tlb_bits["gpaddr_0"],
            "isForVSnonLeafPTE": tlb_bits["isForVSnonLeafPTE"],
            "cause_11": cause_11,
            "specialModeRequest": special_request,
            "fastReplayNukeFirst": fast_replay_nuke_first,
            "shouldFastReplay": should_fast_replay,
        })
        kill = self._state_kill(inputs)
        kill_dcache = int(bool(kill) or bool(tlb_miss) or bool(tlb_exception)
                          or bool(special_request))
        out = self._finalize(inputs, pipe, pipe_valid, kill, tlb, tlb_bits,
                             tlb_hit, tlb_miss, special_request, paddr,
                             no_query_paddr, tlb_exception, kill_dcache,
                             tail_inject, action, is_sw_prefetch, bypass,
                             new_bits)
        out.update({
            "next_valid": int(not kill_reg and bool(pipe_valid)),
            "next_bits": new_bits if pipe_valid else None,
            "perf0_next": pipe_valid,
            "perf1_next": int(bool(pipe_valid) and bool(tlb_bits["miss"])),
        })
        return out

    def advance(self, inputs: dict, comb: dict) -> None:
        redirect = inputs["redirect"]
        if inputs["pipeIn"]["valid"]:
            self.pipe_out_bits = comb["next_bits"]
        self.pipe_out_valid = comb["next_valid"]
        self.perf0 = [comb["perf0_next"], self.perf0[0]]
        self.perf1 = [comb["perf1_next"], self.perf1[0]]
        old_next_valid = self.redirect_next_valid
        old_next_bits = self.redirect_next_bits
        if redirect["valid"]:
            self.redirect_next_bits = dict(redirect["bits"])
        self.redirect_next_valid = 1 if redirect["valid"] else 0
        if old_next_valid:
            self.redirect_nextnext_bits = dict(old_next_bits)
        self.redirect_nextnext_valid = 1 if old_next_valid else 0

    def cycle(self, inputs: dict) -> dict:
        comb = self.comb(inputs)
        self.advance(inputs, comb)
        # Picker re-evaluates the combinational logic after the edge, so the
        # observed pins use the advanced redirect pipeline.
        out = self.comb(inputs)
        out["pipeOut_valid"] = self.pipe_out_valid
        out["pipeOut_bits"] = self.pipe_out_bits
        out["perf0"] = self.perf0[1]
        out["perf1"] = self.perf1[1]
        return out

    def _finalize(self, inputs, pipe, pipe_valid, kill, tlb, tlb_bits,
                  tlb_hit, tlb_miss, special_request, paddr, no_query_paddr,
                  tlb_exception, kill_dcache, tail_inject, action,
                  is_sw_prefetch, bypass, new_bits):
        tail_vaddr = (((pipe["vaddr"] >> 4) + 1) & ((1 << 46) - 1)) << 4
        tail_fullva = (((pipe["fullva"] >> 4) + 1) & ((1 << 60) - 1)) << 4
        return {
            "pipeOut_valid": self.pipe_out_valid,
            "pipeOut_bits": self.pipe_out_bits,
            "tlbReqKill": int(bool(kill) or bool(special_request)),
            "tlbPAddr": no_query_paddr,
            "dcachePAddr": (no_query_paddr if pipe["noQuery"]
                            else tlb_bits["paddr_1"]),
            "dcacheKill": kill_dcache,
            "storeForwardReq_paddr": paddr,
            "mshrForwardReq_paddr": paddr,
            "tldForwardReq_paddr": paddr,
            "sqForwardKill": kill_dcache,
            "sbufferForwardKill": kill_dcache,
            "uncacheForwardKill": int(bool(kill)),
            "dataPathMeta_valid": int(bool(pipe_valid) and not kill),
            "dataPathMeta_bankOffset": paddr & 0xF,
            "dataPathMeta_fuOpType": pipe["uop_fuOpType"],
            "dataPathMeta_fpWen": pipe["uop_fpWen"],
            "dataPathMeta_isNCReplay": int(bool(pipe["uncacheReplay"])
                                           and bool(pipe["ncReplay"])),
            "dataPathMeta_isMMIOReplay": int(bool(pipe["uncacheReplay"])
                                             and not pipe["ncReplay"]),
            "dataPathMeta_isUnalignHead": pipe["unalignHead"],
            "unalignTail_valid": tail_inject,
            "unalignTail_payload": {name: pipe[name] for name in PIPEIN_FIELDS},
            "unalignTail_vaddr": tail_vaddr,
            "unalignTail_fullva": tail_fullva,
            "unalignTail_mask": tail_mask(pipe["uop_fuOpType"], pipe["vaddr"]),
            "prefetchTrainHint": int(
                bool(pipe_valid) and not kill
                and bool(pipe["entrance"] & 0x60) and not is_sw_prefetch),
            "swInstrPrefetch_valid": int(bool(pipe_valid) and bool(is_sw_prefetch)),
            "swInstrPrefetch_vaddr": pipe["vaddr"],
            "kill": int(kill),
            "kill_reg": int(int(not kill and pipe_valid) == 0 and pipe_valid),
            "tlbHit": tlb_hit,
            "tlbMiss": tlb_miss,
            "tlbException": tlb_exception,
            "tail_inject": tail_inject,
            "bp": int(action == ACTION_BREAKPOINT),
            "action": action,
            "specialRequest": special_request,
        }


class LoadS1Env:
    def __init__(self, dut, coverage=None) -> None:
        self.dut = dut
        self.coverage = coverage
        self.pipe_valid = dut.io_pipeIn_valid
        self.pipe_bits = {name: getattr(dut, f"io_pipeIn_bits_{name}")
                          for name in PIPEIN_FIELDS}
        self.redirect_valid = dut.io_redirect_valid
        self.redirect_bits = {name: getattr(dut, f"io_redirect_bits_{name}")
                              for name in REDIRECT_FIELDS}
        self.special_mode = dut.io_specialMode
        self.rob_head = {name: getattr(dut, f"io_robHeadPtr_{name}")
                         for name in ("flag", "value", "isFormer")}
        self.tlb_valid = dut.io_tlbResp_valid
        self.tlb_bits = {name: getattr(dut, f"io_tlbResp_bits_{name}")
                         for name in TLB_FIELDS}
        self.bypass_valid = dut.io_uncacheBypassResp_valid
        self.bypass_paddr = dut.io_uncacheBypassResp_bits_paddr
        self.tail_ready = dut.io_unalignTail_ready
        self.nuke_valid = [dut.io_staNukeQueryReq_0_valid,
                           dut.io_staNukeQueryReq_1_valid]
        self.nuke_bits = [
            {name: getattr(dut, f"io_staNukeQueryReq_{index}_bits_{name}")
             for name in NUKE_FIELDS}
            for index in range(2)
        ]
        self.trigger_cfg = []
        for index in range(4):
            self.trigger_cfg.append({
                "match_type": getattr(dut, f"io_csrTrigger_tdataVec_{index}_matchType"),
                "select": getattr(dut, f"io_csrTrigger_tdataVec_{index}_select"),
                "timing": getattr(dut, f"io_csrTrigger_tdataVec_{index}_timing"),
                "action": getattr(dut, f"io_csrTrigger_tdataVec_{index}_action"),
                "chain": getattr(dut, f"io_csrTrigger_tdataVec_{index}_chain"),
                "load": getattr(dut, f"io_csrTrigger_tdataVec_{index}_load"),
                "tdata2": getattr(dut, f"io_csrTrigger_tdataVec_{index}_tdata2"),
            })
        self.trigger_enable = [getattr(dut, f"io_csrTrigger_tEnableVec_{index}")
                               for index in range(4)]
        self.trigger_debug = dut.io_csrTrigger_debugMode
        self.trigger_bp_exp = dut.io_csrTrigger_triggerCanRaiseBpExp

        self.out_valid = dut.io_pipeOut_valid
        self.out = {name: getattr(dut, f"io_pipeOut_bits_{name}")
                    for name in PIPEOUT_FIELDS}
        self.misc = {name: getattr(dut, f"io_{name}")
                     for name in ("tlbReqKill", "tlbPAddr", "dcachePAddr",
                                  "dcacheKill", "storeForwardReq_paddr",
                                  "mshrForwardReq_paddr", "tldForwardReq_paddr",
                                  "sqForwardKill", "sbufferForwardKill",
                                  "uncacheForwardKill", "prefetchTrainHint")}
        self.meta = {name: getattr(dut, f"io_dataPathMeta_bits_{name}")
                     for name in ("bankOffset", "fuOpType", "fpWen",
                                  "isNCReplay", "isMMIOReplay", "isUnalignHead")}
        self.meta_valid = dut.io_dataPathMeta_valid
        self.tail = {
            "valid": dut.io_unalignTail_valid,
            "vaddr": dut.io_unalignTail_bits_vaddr,
            "fullva": dut.io_unalignTail_bits_fullva,
            "mask": dut.io_unalignTail_bits_mask,
        }
        prefix = "io_unalignTail_bits_"
        self.tail_all = {name[len(prefix):]: getattr(dut, name)
                         for name in dut.xport.GetKeys()
                         if name.startswith(prefix)}
        self.sw_prefetch_valid = dut.io_swInstrPrefetch_valid
        self.sw_prefetch_vaddr = dut.io_swInstrPrefetch_bits_vaddr
        self.perf0 = dut.io_perf_0_value
        self.perf1 = dut.io_perf_1_value
        self.model = S1Model()
        self.cycles = 0

    # -- drive --------------------------------------------------------------
    def drive(self, inputs: dict) -> None:
        self.pipe_valid.Set(1 if inputs["pipeIn"]["valid"] else 0)
        for name, signal in self.pipe_bits.items():
            signal.Set(int(inputs["pipeIn"]["bits"].get(name, 0))
                       & ((1 << PIPEIN_FIELDS[name]) - 1))
        self.redirect_valid.Set(1 if inputs["redirect"]["valid"] else 0)
        for name, signal in self.redirect_bits.items():
            signal.Set(int(inputs["redirect"]["bits"].get(name, 0)))
        self.special_mode.Set(1 if inputs["specialMode"] else 0)
        for name, signal in self.rob_head.items():
            signal.Set(int(inputs["robHeadPtr"].get(name, 0)))
        self.tlb_valid.Set(1 if inputs["tlbResp"]["valid"] else 0)
        for name, signal in self.tlb_bits.items():
            signal.Set(int(inputs["tlbResp"]["bits"].get(name, 0))
                       & ((1 << TLB_FIELDS[name]) - 1))
        self.bypass_valid.Set(1 if inputs["bypass"]["valid"] else 0)
        self.bypass_paddr.Set(int(inputs["bypass"]["bits"].get("paddr", 0)))
        self.tail_ready.Set(1 if inputs["unalignTail_ready"] else 0)
        for index in range(2):
            nuke = inputs["nuke"][index]
            self.nuke_valid[index].Set(1 if nuke["valid"] else 0)
            for name, signal in self.nuke_bits[index].items():
                signal.Set(int(nuke["bits"].get(name, 0))
                           & ((1 << NUKE_FIELDS[name]) - 1))
        trigger = inputs["trigger"]
        for index, cfg in enumerate(trigger["configs"]):
            signals = self.trigger_cfg[index]
            signals["match_type"].Set(cfg.match_type)
            signals["select"].Set(cfg.select)
            signals["timing"].Set(cfg.timing)
            signals["action"].Set(cfg.action)
            signals["chain"].Set(cfg.chain)
            signals["load"].Set(cfg.store)
            signals["tdata2"].Set(cfg.tdata2 & ((1 << 64) - 1))
            self.trigger_enable[index].Set(1 if trigger["enables"][index] else 0)
        self.trigger_debug.Set(1 if trigger["debugMode"] else 0)
        self.trigger_bp_exp.Set(1 if trigger["canRaiseBpExp"] else 0)

    def reset(self, cycles: int = 3) -> None:
        idle = blank_inputs()
        self.dut.reset.Set(1)
        for _ in range(cycles):
            self.drive(idle)
            self.dut.Step(1)
        self.dut.reset.Set(0)
        self.model.reset()
        self.cycles = 0

    # -- one checked cycle --------------------------------------------------
    def cycle(self, inputs: dict, context: str = "cycle") -> dict:
        want = self.model.cycle(inputs)
        self.drive(inputs)
        self.dut.Step(1)
        self.cycles += 1

        checks = {
            "pipeOut.valid": (int(self.out_valid.value), want["pipeOut_valid"]),
            "tlbReqKill": (int(self.misc["tlbReqKill"].value), want["tlbReqKill"]),
            "tlbPAddr": (int(self.misc["tlbPAddr"].value), want["tlbPAddr"]),
            "dcachePAddr": (int(self.misc["dcachePAddr"].value), want["dcachePAddr"]),
            "dcacheKill": (int(self.misc["dcacheKill"].value), want["dcacheKill"]),
            "storeForwardReq.paddr": (int(self.misc["storeForwardReq_paddr"].value),
                                      want["storeForwardReq_paddr"]),
            "mshrForwardReq.paddr": (int(self.misc["mshrForwardReq_paddr"].value),
                                     want["mshrForwardReq_paddr"]),
            "tldForwardReq.paddr": (int(self.misc["tldForwardReq_paddr"].value),
                                    want["tldForwardReq_paddr"]),
            "sqForwardKill": (int(self.misc["sqForwardKill"].value),
                              want["sqForwardKill"]),
            "sbufferForwardKill": (int(self.misc["sbufferForwardKill"].value),
                                   want["sbufferForwardKill"]),
            "uncacheForwardKill": (int(self.misc["uncacheForwardKill"].value),
                                   want["uncacheForwardKill"]),
            "dataPathMeta.valid": (int(self.meta_valid.value),
                                   want["dataPathMeta_valid"]),
            "tail.valid": (int(self.tail["valid"].value), want["unalignTail_valid"]),
            "tail.vaddr": (int(self.tail["vaddr"].value), want["unalignTail_vaddr"]),
            "tail.fullva": (int(self.tail["fullva"].value), want["unalignTail_fullva"]),
            "tail.mask": (int(self.tail["mask"].value), want["unalignTail_mask"]),
            "prefetchTrainHint": (int(self.misc["prefetchTrainHint"].value),
                                  want["prefetchTrainHint"]),
            "swInstrPrefetch.valid": (int(self.sw_prefetch_valid.value),
                                      want["swInstrPrefetch_valid"]),
            "swInstrPrefetch.vaddr": (int(self.sw_prefetch_vaddr.value),
                                      want["swInstrPrefetch_vaddr"]),
            "perf0": (int(self.perf0.value), want["perf0"]),
            "perf1": (int(self.perf1.value), want["perf1"]),
        }
        for name, signal in self.meta.items():
            checks[f"dataPathMeta.{name}"] = (int(signal.value),
                                              want[f"dataPathMeta_{name}"])
        # All remaining tail fields are forwarded from this S1 input beat.
        # Do not let checking only address/mask hide a lost ROB/SQ identity.
        tail_payload = want["unalignTail_payload"]
        for name, signal in self.tail_all.items():
            if name in ("vaddr", "fullva", "mask"):
                expected = want[f"unalignTail_{name}"]
            else:
                expected = tail_payload[name]
            checks[f"tail.{name}"] = (int(signal.value), expected)
        for name, (got, exp) in checks.items():
            if got != exp:
                raise AssertionError(
                    f"{context}: {name} {got:#x} != {exp:#x} "
                    f"(pipeIn_valid={inputs['pipeIn']['valid']} "
                    f"kill={want['kill']} tlbHit={want['tlbHit']} "
                    f"tlbMiss={want['tlbMiss']} sp={want['specialRequest']})")
        if want["pipeOut_valid"]:
            for name in PIPEOUT_FIELDS:
                got = int(self.out[name].value)
                exp = want["pipeOut_bits"][name]
                if got != exp:
                    raise AssertionError(
                        f"{context}: pipeOut.{name} {got:#x} != {exp:#x} "
                        f"(kill={want['kill']} tlbHit={want['tlbHit']} "
                        f"entrance={want['pipeOut_bits'].get('entrance', 0):#x})")
        elif self.coverage is not None and self.model.pipe_out_bits is not None:
            for name in PIPEOUT_FIELDS:
                got = int(self.out[name].value)
                exp = self.model.pipe_out_bits[name]
                if got != exp:
                    raise AssertionError(
                        f"{context}: pipeOut.{name} not held on a killed/empty beat: "
                        f"{got:#x} != {exp:#x}")
        if self.coverage is not None:
            self.coverage.observe(want=want, inputs=inputs)
        return want


# ------------------------------------------------------------------ stimulus
def blank_pipe_bits() -> dict:
    return {name: 0 for name in PIPEIN_FIELDS}


def blank_inputs() -> dict:
    return {
        "pipeIn": {"valid": 0, "bits": blank_pipe_bits()},
        "redirect": {"valid": 0, "bits": {name: 0 for name in REDIRECT_FIELDS}},
        "specialMode": 0,
        "robHeadPtr": {"flag": 0, "value": 0, "isFormer": 0},
        "tlbResp": {"valid": 0, "bits": {name: 0 for name in TLB_FIELDS}},
        "bypass": {"valid": 0, "bits": {"paddr": 0}},
        "unalignTail_ready": 1,
        "nuke": [{"valid": 0, "bits": {name: 0 for name in NUKE_FIELDS}}
                 for _ in range(2)],
        "trigger": {"configs": [TriggerConfig() for _ in range(4)],
                    "enables": [0, 0, 0, 0], "debugMode": 0,
                    "canRaiseBpExp": 1},
    }


def random_pipe_bits(rng: random.Random) -> dict:
    bits = {name: rng.randrange(1 << width)
            for name, width in PIPEIN_FIELDS.items()}
    bits["accessType_instrType"] = rng.randrange(8)
    bits["unalignHead"] = 1 if rng.random() < 0.3 else 0
    return bits


def random_tlb_bits(rng: random.Random) -> dict:
    return {name: rng.randrange(1 << width) for name, width in TLB_FIELDS.items()}


def random_nuke(rng: random.Random) -> dict:
    return {"valid": 1 if rng.random() < 0.5 else 0,
            "bits": {name: rng.randrange(1 << width)
                     for name, width in NUKE_FIELDS.items()}}
