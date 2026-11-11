"""Environment and independent reference for NewLoadUnit (the integrated load unit).

The parent DUT keeps the *real* S0..S4, the data path, the request arbiter and
the trigger unit. This reference composes the five independently verified stage
models and the data-path model in the same order as the RTL:

    ldin/replay ──> S0 ──> S1 ──> S2 ──> S3 ──> (S4 loopback) ──> S3.unalignConcat
                     ▲        │       │       │
                     │        │       │       └─> dataPath s1Meta ─> ldout/vldout data
                     │        │       └─────────> fastReplay? no: S3.fastReplay ─┐
                     │        └── unalignTail ───────────────────────────────────┤
                     └──────────────────── fast lane ◄───────────────────────────┘

Two timing rules drive the whole model, both measured on the real DUT by the
leaf tests:

* stage-to-stage data moves through a **one-entry register** (``pipeOut``); the
  parent model captures the pre-edge combinational value and exposes the
  post-edge register on the next cycle;
* Picker re-evaluates combinational logic after the edge, so the observed pins
  are functions of the **post-edge** registers. The model evaluates every
  stage's combinational half twice per cycle (capture and observe), which is
  what makes the cross-stage combinational paths (S1 tail -> S0 arbiter,
  S3 fast replay -> S0 arbiter, S2 unalignTailValid -> S3) land in the right
  cycle.

The parent also owns two extra registers: the prefetch-train beat (one cycle
after S2) and the eight performance counters (two cycles after the stage
counters, i.e. four cycles after the raw condition).

Functional tests describe loads and protocol responses as
:class:`~..transactions.CycleInput` transactions and read immutable
:class:`~..transactions.LoadPipelineSnapshot` stage observations.  Input
encoding lives in ``stimulus.py``, output decoding in ``monitor.py``; the full
273-pin reference comparison below remains the independent checker.

Contract: docs/spec/design/contracts/new-load-unit.md
"""
from __future__ import annotations

from suites.memblock.lsu.testbenches.load_datapath.env import LoadDataPathModel
from suites.memblock.lsu.testbenches.load_s0.env import LDIN_FIELDS
from suites.memblock.lsu.testbenches.load_s0.env import REPLAY_FIELDS
from suites.memblock.lsu.testbenches.load_s0.env import S0Model
from suites.memblock.lsu.testbenches.load_s0.env import _INPUT_WIDTHS as S0_INPUT_WIDTHS
from suites.memblock.lsu.testbenches.load_s1.env import S1Model
from suites.memblock.lsu.testbenches.load_s2.env import DCRESP_FIELDS
from suites.memblock.lsu.testbenches.load_s2.env import MSHR_FIELDS
from suites.memblock.lsu.testbenches.load_s2.env import S2Model
from suites.memblock.lsu.testbenches.load_s2.env import SQ_FIELDS
from suites.memblock.lsu.testbenches.load_s2.env import SB_FIELDS
from suites.memblock.lsu.testbenches.load_s2.env import UNC_FIELDS
from suites.memblock.lsu.testbenches.load_s2.env import TLD_FIELDS
from suites.memblock.lsu.testbenches.load_s3.env import S3Model
from suites.memblock.lsu.testbenches.load_datapath.env import S1_META_FIELDS

from suites.memblock.lsu.testbenches.new_load_unit.env.monitor import check_pin_inventory
from suites.memblock.lsu.testbenches.new_load_unit.env.monitor import decode_snapshot
from suites.memblock.lsu.testbenches.new_load_unit.env.stimulus import FORWARD_DATA_FIELDS
from suites.memblock.lsu.testbenches.new_load_unit.env.stimulus import NUKE_FIELDS
from suites.memblock.lsu.testbenches.new_load_unit.env.stimulus import REDIRECT_FIELDS
from suites.memblock.lsu.testbenches.new_load_unit.env.stimulus import TLB_RESP_FIELDS
from suites.memblock.lsu.testbenches.new_load_unit.env.stimulus import blank_inputs
from suites.memblock.lsu.testbenches.new_load_unit.env.stimulus import random_inputs
from suites.memblock.lsu.testbenches.new_load_unit.env.stimulus import to_inputs
from suites.memblock.lsu.testbenches.new_load_unit.env.stimulus import validate_input_keys
from suites.memblock.lsu.testbenches.new_load_unit.transactions import CycleInput
from suites.memblock.lsu.testbenches.new_load_unit.transactions import LoadIssue
from suites.memblock.lsu.testbenches.new_load_unit.transactions import RobTag
from suites.memblock.lsu.testbenches.new_load_unit.transactions import Translation

def _merge_tld(first: dict, second: dict) -> tuple[int, dict]:
    """The parent OR-merges the two TLD forward ports into one response."""
    valid = int(bool(first["valid"]) or bool(second["valid"]))
    bits = {}
    for index in range(16):
        l0 = first["bits"].get(f"forwardData_{index}", 0) if first["valid"] else 0
        l1 = second["bits"].get(f"forwardData_{index}", 0) if second["valid"] else 0
        bits[f"forwardData_{index}"] = l0 | l1
    denied = int((bool(first["valid"]) and bool(first["bits"].get("denied", 0)))
                 or (bool(second["valid"]) and bool(second["bits"].get("denied", 0))))
    corrupt = int((bool(first["valid"]) and bool(first["bits"].get("corrupt", 0)))
                  or (bool(second["valid"]) and bool(second["bits"].get("corrupt", 0))))
    return valid, {"denied": denied, "corrupt": corrupt, **bits}


class NewLoadUnitModel:
    def __init__(self) -> None:
        self.s0 = S0Model()
        self.s1 = S1Model()
        self.s2 = S2Model()
        self.s3 = S3Model()
        self.dp = LoadDataPathModel()
        self.train_valid = 0
        self.train_bits: dict | None = None
        self.parent_perf = [[0, 0] for _ in range(8)]

    def reset(self) -> None:
        self.__init__()

    # ------------------------------------------------------------------ inputs
    @staticmethod
    def s0_inputs(inp: dict, tail_valid: int, tail_bits: dict,
                  fast_valid: int, fast_bits: dict) -> dict:
        return {
            "unalign": {"valid": int(tail_valid), "bits": tail_bits},
            "replay": inp["replay"],
            "fast": {"valid": int(fast_valid), "bits": fast_bits},
            "ldin": inp["ldin"],
            "dcache_ready": inp["dcache"]["ready"],
        }

    @staticmethod
    def s1_inputs(inp: dict, valid: int, bits: dict | None) -> dict:
        return {
            "pipeIn": {"valid": int(valid), "bits": bits or {}},
            "redirect": inp["redirect"],
            "specialMode": inp["specialMode"],
            "robHeadPtr": inp["robHeadPtr"],
            "tlbResp": inp["tlbResp"],
            "bypass": inp["bypass1"],
            "unalignTail_ready": inp["dcache"]["ready"],
            "nuke": inp["nuke"],
            "trigger": inp["trigger"],
        }

    @staticmethod
    def s2_inputs(inp: dict, valid: int, bits: dict | None) -> dict:
        tld_valid, tld_bits = _merge_tld(inp["tld0"], inp["tld1"])
        return {
            "pipeIn": {"valid": int(valid), "bits": bits or {}},
            "redirect": inp["redirect"],
            "pmp": inp["pmp"],
            "tlbHint": inp["tlbHint"],
            "dcacheResp": inp["dcache"]["resp"],
            "dcacheBankConflict": inp["dcache"]["bank"],
            "dcacheRRBankConflict": inp["dcache"]["rr"],
            "dcacheMSHRNack": inp["dcache"]["mq_nack"],
            "rrGrant": inp["rrGrant"],
            "sq": inp["sq"], "sb": inp["sb"], "unc": inp["unc"],
            "mshr": inp["mshr"],
            "tld": {"valid": tld_valid, "bits": tld_bits},
            "bypass": inp["bypass2"],
            "stdData": inp["std"],
            "nuke": inp["nuke"],
            "rarReady": inp["rarReady"], "rawReady": inp["rawReady"],
        }

    @staticmethod
    def s3_inputs(inp: dict, valid: int, bits: dict | None, concat_valid: int,
                  concat_bits: dict | None, unalign_tail_valid: int,
                  fast_ready: int) -> dict:
        return {
            "pipeIn": {"valid": int(valid), "bits": bits or {}},
            "redirect": inp["redirect"],
            "unalignTailValid": int(unalign_tail_valid),
            "concat": {"valid": int(concat_valid), "bits": concat_bits or {}},
            "fastReplayReady": int(fast_ready),
            "rarResp": inp["rarResp"],
            "ldldCheck": inp["ldld"],
        }

    @staticmethod
    def dp_forward(inp: dict) -> dict:
        forward = {}
        for key, name in (("sq", "sq"), ("sb", "sbuffer"), ("unc", "uncache"),
                          ("mshr", "mshr")):
            bits = inp[key]["bits"]
            forward[name] = {
                "mask": [bits.get(f"forwardMask_{i}", 0) for i in range(16)],
                "data": [bits.get(f"forwardData_{i}", 0) for i in range(16)],
            }
        return forward

    # ------------------------------------------------------------------ cycle
    def cycle(self, inp: dict) -> dict:
        pre_s0 = (self.s0.pipe_out_valid, self.s0.pipe_out_bits or {})
        pre_s1 = (self.s1.pipe_out_valid, self.s1.pipe_out_bits or {})
        pre_s2 = (self.s2.pipe_out_valid, self.s2.pipe_out_bits or {})
        pre_s3 = (self.s3.pipe_out_valid, self.s3.pipe_out_bits or {})
        pre_perf = [self.s0.perf0[1], self.s0.perf1[1],
                    self.s1.perf0[1], self.s1.perf1[1],
                    self.s2.perf[0][1], self.s2.perf[1][1],
                    self.s2.perf[2][1], self.s2.perf[3][1]]

        # ---- pre-edge combinational values (what the clock edge captures) ----
        c1_pre = self.s1.comb(self.s1_inputs(inp, *pre_s0))
        c2_pre = self.s2.compute(self.s2_inputs(inp, *pre_s1))
        c3_meta = self.s3.compute(self.s3_inputs(
            inp, *pre_s2, concat_valid=pre_s3[0], concat_bits=pre_s3[1],
            unalign_tail_valid=c2_pre["unalignTailValid"], fast_ready=0))
        c0_pre = self.s0.comb(self.s0_inputs(
            inp, c1_pre["unalignTail_valid"], _tail_bits(c1_pre),
            c3_meta["fast_replay_valid"], c3_meta["fast"]))
        c3_pre = self.s3.compute(self.s3_inputs(
            inp, *pre_s2, concat_valid=pre_s3[0], concat_bits=pre_s3[1],
            unalign_tail_valid=c2_pre["unalignTailValid"],
            fast_ready=c0_pre["fastReplay_ready"]))

        # ---- the data path captures the pre-edge S1 metadata ----------------
        tld_valid = int(bool(inp["tld0"]["valid"]) or bool(inp["tld1"]["valid"]))
        dp_out = self.dp.cycle(
            c1_pre["dataPathMeta_valid"],
            {name: c1_pre[f"dataPathMeta_{name}"] for name in S1_META_FIELDS},
            self.dp_forward(inp), tld_valid, _tld_bytes(inp),
            inp["bypass2"]["bits"].get("data", 0),
            inp["dcache"]["resp"]["bits"].get("data", 0))

        # ---- the clock edge --------------------------------------------------
        self.s0.advance(None, c0_pre)
        self.s1.advance(self.s1_inputs(inp, *pre_s0), c1_pre)
        self.s2.advance(c2_pre)
        self.s3.advance(self.s3_inputs(
            inp, *pre_s2, concat_valid=pre_s3[0], concat_bits=pre_s3[1],
            unalign_tail_valid=c2_pre["unalignTailValid"],
            fast_ready=c0_pre["fastReplay_ready"]), c3_pre)
        new_train_valid = c2_pre["prefetchTrain_valid"]
        new_train_bits = c2_pre["train"] if new_train_valid else None
        if new_train_valid:
            self.train_bits = new_train_bits
        self.train_valid = int(bool(new_train_valid))
        self.parent_perf = [[pre_perf[index], self.parent_perf[index][0]]
                            for index in range(8)]

        # ---- post-edge combinational values (what the pins show) -------------
        post_s0 = (self.s0.pipe_out_valid, self.s0.pipe_out_bits or {})
        post_s1 = (self.s1.pipe_out_valid, self.s1.pipe_out_bits or {})
        post_s2 = (self.s2.pipe_out_valid, self.s2.pipe_out_bits or {})
        post_s3 = (self.s3.pipe_out_valid, self.s3.pipe_out_bits or {})
        c1 = self.s1.comb(self.s1_inputs(inp, *post_s0))
        c2 = self.s2.compute(self.s2_inputs(inp, *post_s1))
        c3a = self.s3.compute(self.s3_inputs(
            inp, *post_s2, concat_valid=post_s3[0], concat_bits=post_s3[1],
            unalign_tail_valid=c2["unalignTailValid"], fast_ready=0))
        c0 = self.s0.comb(self.s0_inputs(
            inp, c1["unalignTail_valid"], _tail_bits(c1),
            c3a["fast_replay_valid"], c3a["fast"]))
        c3 = self.s3.compute(self.s3_inputs(
            inp, *post_s2, concat_valid=post_s3[0], concat_bits=post_s3[1],
            unalign_tail_valid=c2["unalignTailValid"],
            fast_ready=c0["fastReplay_ready"]))

        return self._outputs(inp, c0, c1, c2, c3, dp_out)

    # --------------------------------------------------------------- outputs
    def _outputs(self, inp, c0, c1, c2, c3, dp_out) -> dict:
        out = {}
        # -------- S0 combinational request/ready boundary ------------------
        out["io_ldin_ready"] = c0["ldin_ready"]
        out["io_replay_ready"] = c0["replay_ready"]
        for name, key in (("vaddr", "tlbReq_vaddr"),
                          ("fullva", "tlbReq_fullva"),
                          ("checkfullva", "tlbReq_checkfullva"),
                          ("hyperinst", "tlbReq_hyperinst"), ("hlvx", "tlbReq_hlvx"),
                          ("kill", "tlbReq_kill"),
                          ("isPrefetch", "tlbReq_isPrefetch"),
                          ("no_translate", "tlbReq_no_translate"),
                          ("debug_robIdx_flag", "tlbReq_debug_robIdx_flag"),
                          ("debug_robIdx_value", "tlbReq_debug_robIdx_value"),
                          ("debug_robIdx_isFormer", "tlbReq_debug_robIdx_isFormer")):
            out[f"io_tlb_req_bits_{name}"] = c0[key]
        out["io_tlb_req_valid"] = c0["tlbReq_valid"]
        out["io_tlb_req_bits_pmp_addr"] = c1["tlbPAddr"]
        out["io_tlb_req_kill"] = c1["tlbReqKill"]
        for name, key in (("cmd", "dcacheReq_cmd"),
                          ("vaddr", "dcacheReq_vaddr"),
                          ("vaddr_dup", "dcacheReq_vaddr_dup"),
                          ("mask", "dcacheReq_mask"),
                          ("instrtype", "dcacheReq_instrtype"),
                          ("lqIdx_flag", "dcacheReq_lqIdx_flag"),
                          ("lqIdx_value", "dcacheReq_lqIdx_value")):
            out[f"io_dcache_req_bits_{name}"] = c0[key]
        out["io_dcache_req_valid"] = c0["dcacheReq_valid"]
        out["io_dcache_is128Req"] = c0["is128Req"]
        out["io_dcache_s1_kill"] = c1["dcacheKill"]
        out["io_dcache_s2_kill"] = c2["dcache_kill"]
        out["io_dcache_s1_paddr_dup_lsu"] = c1["dcachePAddr"]
        out["io_dcache_s1_paddr_dup_dcache"] = c1["dcachePAddr"]
        for name, key in (("valid", "wakeup_valid"), ("bits_rfWen", "wakeup_rfWen"),
                          ("bits_fpWen", "wakeup_fpWen"),
                          ("bits_pdest", "wakeup_pdest")):
            out[f"io_wakeup_{name}"] = c0[key]
        out["io_sqForward_s0Req_valid"] = c0["sqSbForwardReq_valid"]
        out["io_sqForward_s0Req_bits_vaddr"] = c0["sqSbForwardReq_vaddr"]
        for name in ("sqIdx_first_flag", "sqIdx_second_flag", "sqIdx_value",
                     "size", "loadWaitBit", "loadWaitStrict",
                     "waitSqIdx_first_flag", "waitSqIdx_second_flag",
                     "waitSqIdx_value"):
            out[f"io_sqForward_s0Req_bits_{name}"] = c0[f"sqSbForwardReq_{name}"]
        out["io_sqForward_s1Req_paddr"] = c1["storeForwardReq_paddr"]
        out["io_sqForward_s1Kill"] = c1["sqForwardKill"]
        out["io_sbufferForward_s0Req_valid"] = c0["sqSbForwardReq_valid"]
        out["io_sbufferForward_s0Req_bits_vaddr"] = c0["sqSbForwardReq_vaddr"]
        out["io_sbufferForward_s1Req_paddr"] = c1["storeForwardReq_paddr"]
        out["io_sbufferForward_s1Kill"] = c1["sbufferForwardKill"]
        out["io_uncacheForward_s0Req_valid"] = c0["uncacheForwardReq_valid"]
        out["io_uncacheForward_s0Req_bits_vaddr"] = c0["uncacheForwardReq_vaddr"]
        out["io_uncacheForward_s1Req_paddr"] = c1["storeForwardReq_paddr"]
        out["io_uncacheForward_s1Kill"] = c1["uncacheForwardKill"]
        out["io_mshrForward_s0Req_valid"] = c0["mshrForwardReq_valid"]
        out["io_mshrForward_s0Req_bits_mshrId"] = c0["mshrForwardReq_mshrId"]
        out["io_mshrForward_s1Req_paddr"] = c1["mshrForwardReq_paddr"]
        for index in range(2):
            out[f"io_tldForward_{index}_s0Req_valid"] = c0["tldForwardReq_valid"]
            out[f"io_tldForward_{index}_s0Req_bits_mshrId"] = c0["tldForwardReq_mshrId"]
            out[f"io_tldForward_{index}_s1Req_paddr"] = c1["tldForwardReq_paddr"]
        out["io_uncacheBypass_s0Req_valid"] = c0["uncacheBypassReq_valid"]
        out["io_uncacheBypass_s0Req_bits_lqIdx_flag"] = c0["uncacheBypassReq_lqIdx_flag"]
        out["io_uncacheBypass_s0Req_bits_lqIdx_value"] = c0["uncacheBypassReq_lqIdx_value"]
        out["io_uncacheBypass_s0Req_bits_isNCReplay"] = c0["uncacheBypassReq_isNCReplay"]
        out["io_uncacheBypass_s0Req_bits_isMMIOReplay"] = c0["uncacheBypassReq_isMMIOReplay"]

        # -------- S1 combinational -----------------------------------------
        out["io_prefetchTrainHintS1"] = c1["prefetchTrainHint"]
        out["io_swInstrPrefetch_valid"] = c1["swInstrPrefetch_valid"]
        out["io_swInstrPrefetch_bits_vaddr"] = c1["swInstrPrefetch_vaddr"]

        # -------- S2 combinational -----------------------------------------
        out["io_prefetchTrainHintS2"] = c2["prefetchTrain_valid"]
        out["io_rrBankConflictFastReplay_candidate"] = c2["rrCandidate"]
        out["io_rarNukeQuery_req_valid"] = c2["rar_valid"]
        for name in ("robIdx_flag", "robIdx_value", "robIdx_isFormer", "paddr",
                     "lqIdx_flag", "lqIdx_value", "dataValid", "nc"):
            out[f"io_rarNukeQuery_req_bits_{name}"] = c2["rar"][name]
        out["io_rawNukeQuery_req_valid"] = c2["raw_valid"]
        for name in RAW_FIELDS_LOCAL:
            out[f"io_rawNukeQuery_req_bits_{name}"] = c2["raw"][name]

        # -------- S3 combinational -----------------------------------------
        out["io_ldout_toRob_valid"] = c3["ldout_valid"]
        for name, value in c3["ldout"].items():
            out[f"io_ldout_toRob_bits_{name}"] = value
        out["io_ldout_toIntRf_valid"] = c3["int_rf"]
        out["io_ldout_toIntRf_bits_pdest"] = c3["pipe"]["uop_pdest"]
        out["io_ldout_toIntRf_bits_data"] = dp_out["shift_and_ext"] & ((1 << 64) - 1)
        out["io_ldout_toFpRf_valid"] = c3["fp_rf"]
        out["io_ldout_toFpRf_bits_pdest"] = c3["pipe"]["uop_pdest"]
        out["io_ldout_toFpRf_bits_data"] = dp_out["shift_and_ext"] & ((1 << 64) - 1)
        out["io_vldout_toRob_valid"] = c3["vldout_valid"]
        for name, value in c3["vldout"].items():
            out[f"io_vldout_toRob_bits_{name}"] = value
        out["io_vldout_pdest"] = c3["vldout_pdest"]
        out["io_vldout_toVecRf_valid"] = c3["vld_wakeup"]
        out["io_vldout_toVecRf_bits"] = dp_out["shift_data"]
        out["io_vldout_toV0Rf_valid"] = c3["v0_rf"]
        out["io_vldout_toV0Rf_bits"] = dp_out["shift_data"] & ((1 << 64) - 1)
        out["io_vldS3WakeUp_wen"] = c3["vld_wakeup"]
        out["io_vldS3WakeUp_pdest"] = c3["pdest"]
        out["io_lqWrite_valid"] = c3["lq_write_valid"]
        for name, value in c3["lq"].items():
            out[f"io_lqWrite_bits_{name}"] = value
        out["io_rarNukeQuery_revokeLastCycle"] = c3["revoke_last"]
        out["io_rarNukeQuery_revokeLastLastCycle"] = c3["revoke_last_last"]
        out["io_rawNukeQuery_revokeLastCycle"] = c3["revoke_last"]
        out["io_rawNukeQuery_revokeLastLastCycle"] = c3["revoke_last_last"]
        out["io_rollback_valid"] = c3["rollback_valid"]
        for name, value in c3["rollback"].items():
            out[f"io_rollback_bits_{name}"] = value
        out["io_exceptionInfo_valid"] = c3["exception_info_valid"]
        for name, value in c3["excinfo"].items():
            out[f"io_exceptionInfo_bits_{name}"] = value
        out["io_cancel"] = c3["cancel_out"]

        # -------- parent-level registers -----------------------------------
        out["io_prefetchTrain_valid"] = self.train_valid
        train = self.train_bits or {name: 0 for name in PREFETCH_TRAIN_FIELDS_LOCAL}
        for name in PREFETCH_TRAIN_FIELDS_LOCAL:
            out[f"io_prefetchTrain_bits_{name}"] = train[name]
        for index in range(8):
            out[f"io_perf_{index}_value"] = self.parent_perf[index][1]
        return out


RAW_FIELDS_LOCAL = ("robIdx_flag", "robIdx_value", "robIdx_isFormer", "paddr",
                    "sqIdx_first_flag", "sqIdx_second_flag", "sqIdx_value",
                    "dataValid", "mask", "isRVC", "ftqPtr_flag", "ftqPtr_value",
                    "ftqOffset", "debugInfo_runahead_checkpoint_id")
PREFETCH_TRAIN_FIELDS_LOCAL = ("robIdx_flag", "robIdx_value", "robIdx_isFormer",
                               "vaddr", "paddr", "miss", "metaSource",
                               "isFirstIssue", "isHwPrefetch")


def _tail_bits(c1: dict) -> dict:
    """S1's unalignTail payload expressed as an S0 tail lane payload.

    Every uop/exception/address field of the S1 beat is forwarded; only the
    line-advanced vaddr/fullva and the shifted mask are recomputed. The arbiter
    forces the tail lane's size to a Q access, so ``size`` is not carried.
    """
    bits = dict(c1["unalignTail_payload"])
    bits["vaddr"] = c1["unalignTail_vaddr"]
    bits["fullva"] = c1["unalignTail_fullva"]
    bits["mask"] = c1["unalignTail_mask"]
    return bits


def _tld_bytes(inp: dict) -> list[int]:
    out = []
    for index in range(16):
        l0 = inp["tld0"]["bits"].get(f"forwardData_{index}", 0) if inp["tld0"]["valid"] else 0
        l1 = inp["tld1"]["bits"].get(f"forwardData_{index}", 0) if inp["tld1"]["valid"] else 0
        out.append(l0 | l1)
    return out


def _drive_bits(signals, fields, values):
    for name, signal in signals.items():
        signal.Set(int(values.get(name, 0)) & ((1 << fields[name]) - 1))


class LoadParentEnv:
    """Drives the parent DUT pins and checks every output against the model."""

    def __init__(self, dut, coverage=None) -> None:
        from toffee import as_xdata
        self.dut = dut
        self.coverage = coverage

        self.redirect_valid = dut.io_redirect_valid
        self.redirect_bits = {name: getattr(dut, f"io_redirect_bits_{name}")
                              for name in REDIRECT_FIELDS}
        self.special_mode = dut.io_specialMode
        self.rob_head = {name: getattr(dut, f"io_robHeadPtr_{name}")
                         for name in ("flag", "value", "isFormer")}
        self.ldin_valid = dut.io_ldin_valid
        self.ldin_bits = {name: getattr(dut, f"io_ldin_bits_{name}")
                          for name in LDIN_FIELDS}
        self.replay_valid = dut.io_replay_valid
        self.replay_bits = {name: getattr(dut, f"io_replay_bits_{name}")
                            for name in REPLAY_FIELDS}
        self.ldin_ready = dut.io_ldin_ready
        self.replay_ready = dut.io_replay_ready

        self.tlb_resp_valid = dut.io_tlb_resp_valid
        self.tlb_resp_bits = {name: getattr(dut, f"io_tlb_resp_bits_{name}")
                              for name in TLB_RESP_FIELDS}
        self.tlb_hint = {"id": dut.io_tlbHint_id, "full": dut.io_tlbHint_full}
        self.pmp = {"ld": dut.io_pmp_ld, "mmio": dut.io_pmp_mmio}
        self.dcache_ready = dut.io_dcache_req_ready
        self.dcache_resp_bits = {name: getattr(dut, f"io_dcache_resp_bits_{name}")
                                 for name in DCRESP_FIELDS}
        # The S2 stage only consumes the control bits; the data path also needs
        # the 128-bit data word.
        self.dcache_data = dut.io_dcache_resp_bits_data
        self.dcache_bank = dut.io_dcache_s2_bank_conflict
        self.dcache_rr = dut.io_dcache_s2_rr_bank_conflict
        self.dcache_nack = dut.io_dcache_s2_mq_nack
        self.rr_grant = dut.io_rrBankConflictFastReplay_grant

        self.resp = {}
        for key, field_dict, port in (
            ("sq", SQ_FIELDS, "io_sqForward_s2Resp"),
            ("sb", SB_FIELDS, "io_sbufferForward_s2Resp"),
            ("unc", UNC_FIELDS, "io_uncacheForward_s2Resp"),
            ("mshr", MSHR_FIELDS, "io_mshrForward_s2Resp"),
            ("tld0", TLD_FIELDS, "io_tldForward_0_s2Resp"),
            ("tld1", TLD_FIELDS, "io_tldForward_1_s2Resp"),
        ):
            self.resp[key] = {
                "valid": getattr(dut, f"{port}_valid"),
                "bits": {name: getattr(dut, f"{port}_bits_{name}")
                         for name in field_dict},
                "bits_data": {name: getattr(dut, f"{port}_bits_{name}")
                              for name in FORWARD_DATA_FIELDS},
            }
        self.bypass1 = {"valid": dut.io_uncacheBypass_s1Resp_valid,
                        "bits": {"paddr": dut.io_uncacheBypass_s1Resp_bits_paddr}}
        self.bypass2 = {"valid": dut.io_uncacheBypass_s2Resp_valid,
                        "bits": {"data": dut.io_uncacheBypass_s2Resp_bits_data,
                                 "nderr": dut.io_uncacheBypass_s2Resp_bits_nderr,
                                 "derr": dut.io_uncacheBypass_s2Resp_bits_derr}}
        self.nuke_valid = [dut.io_staNukeQueryReq_0_valid,
                           dut.io_staNukeQueryReq_1_valid]
        self.nuke_bits = [{name: getattr(dut, f"io_staNukeQueryReq_{i}_bits_{name}")
                           for name in NUKE_FIELDS} for i in range(2)]
        self.rar_ready = dut.io_rarNukeQuery_req_ready
        self.raw_ready = dut.io_rawNukeQuery_req_ready
        self.rar_resp_valid = dut.io_rarNukeQuery_resp_valid
        self.rar_resp_nuke = dut.io_rarNukeQuery_resp_bits_nuke
        self.ldld = dut.io_csrCtrl_ldld_vio_check_enable
        self.trigger_cfg = []
        for index in range(4):
            prefix = f"io_csrTrigger_tdataVec_{index}_"
            self.trigger_cfg.append({
                "match_type": getattr(dut, prefix + "matchType"),
                "select": getattr(dut, prefix + "select"),
                "timing": getattr(dut, prefix + "timing"),
                "action": getattr(dut, prefix + "action"),
                "chain": getattr(dut, prefix + "chain"),
                "load": getattr(dut, prefix + "load"),
                "tdata2": getattr(dut, prefix + "tdata2"),
            })
        self.trigger_enable = [getattr(dut, f"io_csrTrigger_tEnableVec_{i}")
                               for i in range(4)]
        self.trigger_debug = dut.io_csrTrigger_debugMode
        self.trigger_bp_exp = dut.io_csrTrigger_triggerCanRaiseBpExp
        self.std = {}
        for group in ("current", "previous"):
            self.std[group] = []
            for index in range(2):
                prefix = f"io_stdDataWrite_{group}_{index}"
                self.std[group].append({
                    "valid": getattr(dut, prefix + "_valid"),
                    "bits": {name: getattr(dut, prefix + "_bits_" + name)
                             for name in ("first_flag", "second_flag", "value")},
                })

        # Collect every output pin so the checker can prove full coverage.
        self.output_pins = []
        for name in dir(dut):
            if not name.startswith("io_"):
                continue
            try:
                data = as_xdata(getattr(dut, name))
            except TypeError:
                continue
            if hasattr(data, "IsOutIO") and data.IsOutIO():
                self.output_pins.append(name)
        check_pin_inventory(self.output_pins)
        self._model = NewLoadUnitModel()
        self.cycles = 0

    # -------------------------------------------------------------- driving
    def drive(self, inp: dict) -> None:
        self.redirect_valid.Set(1 if inp["redirect"]["valid"] else 0)
        _drive_bits(self.redirect_bits, REDIRECT_FIELDS, inp["redirect"]["bits"])
        self.special_mode.Set(1 if inp["specialMode"] else 0)
        for name, signal in self.rob_head.items():
            signal.Set(int(inp["robHeadPtr"].get(name, 0)))
        self.ldin_valid.Set(1 if inp["ldin"]["valid"] else 0)
        _drive_bits(self.ldin_bits, S0_INPUT_WIDTHS["ldin"], inp["ldin"]["bits"])
        self.replay_valid.Set(1 if inp["replay"]["valid"] else 0)
        _drive_bits(self.replay_bits, S0_INPUT_WIDTHS["replay"], inp["replay"]["bits"])
        self.tlb_resp_valid.Set(1 if inp["tlbResp"]["valid"] else 0)
        _drive_bits(self.tlb_resp_bits, TLB_RESP_FIELDS, inp["tlbResp"]["bits"])
        self.tlb_hint["id"].Set(int(inp["tlbHint"]["id"]) & 0xF)
        self.tlb_hint["full"].Set(1 if inp["tlbHint"]["full"] else 0)
        self.pmp["ld"].Set(1 if inp["pmp"]["ld"] else 0)
        self.pmp["mmio"].Set(1 if inp["pmp"]["mmio"] else 0)
        self.dcache_ready.Set(1 if inp["dcache"]["ready"] else 0)
        _drive_bits(self.dcache_resp_bits, DCRESP_FIELDS,
                    inp["dcache"]["resp"]["bits"])
        self.dcache_data.Set(int(inp["dcache"]["resp"]["bits"].get("data", 0))
                             & ((1 << 128) - 1))
        self.dcache_bank.Set(1 if inp["dcache"]["bank"] else 0)
        self.dcache_rr.Set(1 if inp["dcache"]["rr"] else 0)
        self.dcache_nack.Set(1 if inp["dcache"]["mq_nack"] else 0)
        self.rr_grant.Set(1 if inp["rrGrant"] else 0)
        resp_fields = {"sq": SQ_FIELDS, "sb": SB_FIELDS, "unc": UNC_FIELDS,
                       "mshr": MSHR_FIELDS, "tld0": TLD_FIELDS,
                       "tld1": TLD_FIELDS}
        for key in ("sq", "sb", "unc", "mshr", "tld0", "tld1"):
            port = self.resp[key]
            port["valid"].Set(1 if inp[key]["valid"] else 0)
            _drive_bits(port["bits"], resp_fields[key], inp[key]["bits"])
            _drive_bits(port["bits_data"], FORWARD_DATA_FIELDS, inp[key]["bits"])
        self.bypass1["valid"].Set(1 if inp["bypass1"]["valid"] else 0)
        self.bypass1["bits"]["paddr"].Set(int(inp["bypass1"]["bits"].get("paddr", 0)))
        self.bypass2["valid"].Set(1 if inp["bypass2"]["valid"] else 0)
        for name, signal in self.bypass2["bits"].items():
            signal.Set(int(inp["bypass2"]["bits"].get(name, 0)))
        for index in range(2):
            self.nuke_valid[index].Set(1 if inp["nuke"][index]["valid"] else 0)
            _drive_bits(self.nuke_bits[index], NUKE_FIELDS,
                        inp["nuke"][index]["bits"])
        self.rar_ready.Set(1 if inp["rarReady"] else 0)
        self.raw_ready.Set(1 if inp["rawReady"] else 0)
        self.rar_resp_valid.Set(1 if inp["rarResp"]["valid"] else 0)
        self.rar_resp_nuke.Set(1 if inp["rarResp"]["nuke"] else 0)
        self.ldld.Set(1 if inp["ldld"] else 0)
        for index, cfg in enumerate(inp["trigger"]["configs"]):
            signals = self.trigger_cfg[index]
            signals["match_type"].Set(cfg.match_type)
            signals["select"].Set(cfg.select)
            signals["timing"].Set(cfg.timing)
            signals["action"].Set(cfg.action)
            signals["chain"].Set(cfg.chain)
            signals["load"].Set(cfg.store)
            signals["tdata2"].Set(cfg.tdata2 & ((1 << 64) - 1))
        for index in range(4):
            self.trigger_enable[index].Set(
                1 if inp["trigger"]["enables"][index] else 0)
        self.trigger_debug.Set(1 if inp["trigger"]["debugMode"] else 0)
        self.trigger_bp_exp.Set(1 if inp["trigger"]["canRaiseBpExp"] else 0)
        for group in ("current", "previous"):
            for index in range(2):
                entry = inp["std"][group][index]
                self.std[group][index]["valid"].Set(1 if entry["valid"] else 0)
                for name, signal in self.std[group][index]["bits"].items():
                    signal.Set(int(entry["bits"].get(name, 0)) & 0x7F)

    # ---------------------------------------------------------------- reset
    def reset(self, cycles: int = 4) -> None:
        idle = to_inputs(CycleInput.idle())
        self.dut.reset.Set(1)
        for _ in range(cycles):
            self.drive(idle)
            self.dut.Step(1)
        self.dut.reset.Set(0)
        self._model.reset()
        self.cycles = 0

    def prime(self, beats: int = 10) -> None:
        """Fill every pipeline payload register with a known value.

        The generated RTL random-initialises the payload registers while reset
        only clears the valids, so the parent boundary is not deterministic
        until every stage has captured at least one beat. The prime beats use a
        clean scalar load so nothing is killed or replayed.
        """
        for index in range(beats):
            address = 0x8000_1000 + 0x40 * index
            plan = CycleInput.idle().issue(LoadIssue(
                address=address,
                rob=RobTag(value=index & 0xFF),
                pdest=index & 0xFF,
                lq_idx=index & 0x7F,
                sq_idx=index & 0x3F,
            )).translated(Translation(
                paddr=0x1234_5000 + 0x40 * index,
                paddr_1=0x1234_5800 + 0x40 * index,
                fullva=address,
            ))
            self.cycle(plan, f"prime {index}", compare=False)
        # Drain the pipeline. The TLB response is held valid so the last beats
        # in S1 hit instead of turning into replays, and six idle cycles push
        # everything past S3 and let the parent counters settle.
        drain = CycleInput.idle().translated(Translation(
            paddr=0x1234_5000, paddr_1=0x1234_5800, fullva=0x8000_1000))
        for index in range(6):
            self.cycle(drain, f"drain {index}", compare=False)
        assert self._model.s0.pipe_out_valid == 0
        assert self._model.s1.pipe_out_valid == 0
        assert self._model.s2.pipe_out_valid == 0
        assert self._model.s3.pipe_out_valid == 0

    # ---------------------------------------------------------------- cycle
    def _observe(self) -> dict:
        return {name: int(getattr(self.dut, name).value)
                for name in self.output_pins}

    def observe(self):
        """Sample the current public outputs without advancing the clock."""
        return decode_snapshot(self._observe(), self.cycles)

    def random_cycle(self, rng, context: str = "random"):
        """One frozen port-level random stimulus, decoded like any transaction."""
        inp = random_inputs(rng)
        return self._cycle_encoded(inp, context, compare=True)

    def cycle(self, plan: CycleInput, context: str = "cycle", compare: bool = True):
        if not isinstance(plan, CycleInput):
            raise TypeError("LoadParentEnv.cycle expects a CycleInput transaction")
        return self._cycle_encoded(to_inputs(plan), context, compare=compare)

    def _cycle_encoded(self, inp: dict, context: str, *, compare: bool):
        validate_input_keys(inp, blank_inputs())
        want = self._model.cycle(inp)
        self.drive(inp)
        self.dut.Step(1)
        self.cycles += 1
        observed = self._observe()
        if compare:
            for name, expected in want.items():
                got = observed[name]
                if got != expected:
                    raise AssertionError(
                        f"{context}: {name} {got:#x} != {expected:#x} "
                        f"(ldin.valid={inp['ldin']['valid']} "
                        f"replay.valid={inp['replay']['valid']} "
                        f"dcache.ready={inp['dcache']['ready']} "
                        f"redirect={inp['redirect']['valid']})")
            missing = set(self.output_pins) - set(want)
            if missing:
                raise AssertionError(
                    f"{context}: unchecked parent outputs: {sorted(missing)}")
            unexpected = set(want) - set(self.output_pins)
            if unexpected:
                raise AssertionError(
                    f"{context}: reference outputs absent from the DUT: "
                    f"{sorted(unexpected)}")
        if self.coverage is not None:
            self.coverage.observe(want=want, inputs=inp)
        return decode_snapshot(observed, self.cycles)
