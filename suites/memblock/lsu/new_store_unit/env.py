"""Environment and reference for NewStoreUnit (the integrated store-address unit).

The reference is built by composing the five independently verified stage
models in ``suites.memblock.lsu.store_s*`` in the same order as the RTL:

    S0 register -> S1 comb/register -> S2 comb/register -> S3 comb/register
    S1.unalignTail  -> S0 arbitration input (the head/tail loopback)
    S2.unalignHeadTlbHit -> S1 (tail feedback)
    S3.pipeOut -> S4 -> S3.unalignConcat (head/tail merge)

Picker evaluates combinational logic again after the clock edge, so the pins
observed after ``Step`` are functions of the *post-edge* registers, while the
registers themselves were captured from the *pre-edge* combinational values.
The model reproduces both halves, which is why the writeback appears three
cycles after ``stin`` while the SQ address write appears in the same cycle.

Contract: docs/contracts/new-store-unit.md
"""
from __future__ import annotations

import random

from suites.memblock.lsu.store_s0.env import (
    PIPE_FIELDS as S0_PIPE_FIELDS,
    STIN_FIELDS,
    StoreS0Model,
    scalar_stage_fields,
    derive_stage_flags,
    derive_tlb_request,
    mask_fields as s0_mask,
    TAIL_FIELDS,
)
from suites.memblock.lsu.store_s1.env import (
    PIPE_IN_FIELDS as S1_IN_FIELDS,
    UPDATE_LFST_FIELDS,
    NUKE_FIELDS,
    SQ_ADDR_FIELDS,
    UNALIGN_QUEUE_FIELDS,
    StoreS1Model,
    mask_fields as s1_mask,
)
from suites.memblock.lsu.store_s2.env import (
    PIPE_IN_FIELDS as S2_IN_FIELDS,
    StoreS2Model,
    mask_fields as s2_mask,
)
from suites.memblock.lsu.store_s3.env import (
    PIPE_IN_FIELDS as S3_IN_FIELDS,
    CONCAT_FIELDS,
    MIXED_FIELDS,
    StoreS3Model,
    mask_fields as s3_mask,
)
from suites.memblock.lsu.store_trigger.env import TRIGGER_NUM, TriggerConfig

# Parent-visible outputs driven by S1's combinational logic.
S1_COMB_OUTPUTS = {
    "updateLFST": UPDATE_LFST_FIELDS,
    "staNukeQueryReq": NUKE_FIELDS,
    "toSqAddr": tuple(SQ_ADDR_FIELDS),
    "toUnalignQueue": UNALIGN_QUEUE_FIELDS,
}

STOUT_FIELDS = (
    "robIdx_flag", "robIdx_value", "robIdx_isFormer", "exceptionVec_23",
    "exceptionVec_19", "exceptionVec_15", "exceptionVec_7", "exceptionVec_6",
    "exceptionVec_3", "trigger", "debugInfo_isMMIO", "debugInfo_isNCIO",
)
EXC_FIELDS = (
    "robIdx_flag", "robIdx_value", "robIdx_isFormer", "exceptionVec_23",
    "exceptionVec_19", "exceptionVec_15", "exceptionVec_7", "exceptionVec_6",
    "exceptionVec_3", "vaddr", "vaNeedExt", "isHyper", "isForVSnonLeafPTE",
    "gpaddr",
)


class StageState:
    """One stage's output register."""

    __slots__ = ("valid", "bits")

    def __init__(self) -> None:
        self.valid = 0
        self.bits: dict | None = None

    def load(self, valid: int, bits: dict | None) -> None:
        self.valid = valid
        self.bits = bits


class NewStoreUnitModel:
    """Composition of the five verified stage models."""

    def __init__(self) -> None:
        self.s0 = StageState()   # S0 pipeOut register
        self.s1 = StageState()
        self.s2 = StageState()
        self.s3 = StageState()
        self.feedback = (0, 0)   # parent-level RegNext of s1.feedBackSlow
        self.m_s0 = StoreS0Model()
        self.m_s1 = StoreS1Model()
        self.m_s2 = StoreS2Model()
        self.m_s3 = StoreS3Model()

    # ------------------------------------------------------------------ reset
    def reset(self) -> None:
        self.__init__()

    # ------------------------------------------------------------- one cycle
    def cycle(self, stin_valid: int, stin: dict, tlb: dict, tlb_valid: int,
              pmp: dict, redirect: dict, trigger_cfg, trigger_enables,
              trigger_debug, trigger_bp_exp, deq, addr_ready, queue_ready) -> dict:
        """Returns the expected pin values after this cycle's clock edge."""
        # Pre-edge validity of every stage register (the capture conditions).
        pre_s0_valid = self.s0.valid
        pre_s1_valid = self.s1.valid
        pre_s2_valid = self.s2.valid
        pre_s3_valid = self.s3.valid

        # ---- pre-edge combinational values (what the edge captures) ----------
        # S2's head-hit flag feeds S1, so S2's comb must be evaluated first.
        s2c = self.m_s2.comb(pre_s1_valid, self.s1.bits or {}, pmp, redirect)
        s1c = self.m_s1.comb(pre_s0_valid, self.s0.bits or {},
                             tlb, tlb_valid, redirect, trigger_cfg,
                             trigger_enables, trigger_debug, trigger_bp_exp,
                             s2c["unalignHeadTlbHit"], queue_ready)
        s4c = _s4(self.s3)
        s3c = self.m_s3.comb(pre_s2_valid, self.s2.bits or {}, s4c["valid"],
                             s4c["bits"] or {}, redirect)
        # The tail's page-crossing verdict is carried by S1's unalignTail output.
        s0c = self.m_s0.arb(stin_valid, stin, s1c["unalignTail_valid"],
                            s1c["unalignTail_bits"] or {},
                            s1c["unalignTail_bits"]["cross4KPage"]
                            if s1c["unalignTail_valid"] else 0,
                            deq, addr_ready)
        s0_next_valid, s0_next_bits = _s0_next(s0c, redirect)

        # ---- the edge --------------------------------------------------------
        # Payload registers are written only while the stage input is valid; a
        # killed beat still writes the payload (only `valid` is gated).
        new_feedback = (s1c["feedBackSlow_valid"], s1c["feedBackSlow_hit"])
        if s0c["arb_valid"]:
            self.s0.load(s0_next_valid, s0_next_bits)
        else:
            self.s0.valid = 0            # payload keeps its previous value
        if pre_s0_valid:
            self.s1.load(s1c["out_valid"], s1c["out_bits"])
        else:
            self.s1.valid = 0
        if pre_s1_valid:
            self.s2.load(s2c["out_valid"], s2c["out_bits"])
        else:
            self.s2.valid = 0
        if pre_s2_valid:
            self.s3.load(s3c["pipe_out_valid"], s3c["pipe_out_bits"])
        else:
            self.s3.valid = 0
        delay_beat = s3c  # the delay register captures the pre-edge S3 beat
        feedback_seen = new_feedback

        # ---- post-edge combinational values (what the pins show) -------------
        s2 = self.m_s2.comb(self.s1.valid, self.s1.bits or {}, pmp, redirect)
        s1 = self.m_s1.comb(self.s0.valid, self.s0.bits or {}, tlb, tlb_valid,
                            redirect, trigger_cfg, trigger_enables,
                            trigger_debug, trigger_bp_exp,
                            s2["unalignHeadTlbHit"], queue_ready)
        s3 = self.m_s3.comb(self.s2.valid, self.s2.bits or {},
                            _s4(self.s3)["valid"], _s4(self.s3)["bits"] or {},
                            redirect)
        s0 = self.m_s0.arb(stin_valid, stin, s1["unalignTail_valid"],
                           s1["unalignTail_bits"] or {},
                           s1["unalignTail_bits"]["cross4KPage"]
                           if s1["unalignTail_valid"] else 0,
                           deq, addr_ready)
        wb = self.m_s3.writeback(delay_beat) if delay_beat["delay_in_valid"] else\
            {"valid": 0, "bits": None, "exception_bits": None}
        self.feedback = new_feedback

        return {
            "stin_ready": s0["stin_ready"],
            "tlb_req_valid": s0["arb_valid"],
            "tlb_req_bits": derive_tlb_request(s0["fields"]) if s0["arb_valid"] else None,
            "tlb_req_kill": s1["tlbReqKill"],
            "updateLFST_valid": s1["updateLFST_valid"],
            "updateLFST_bits": s1["updateLFST_bits"],
            "staNukeQueryReq_valid": s1["staNukeQueryReq_valid"],
            "staNukeQueryReq_bits": s1["staNukeQueryReq_bits"],
            "toSqAddr_valid": s1["toSqAddr_valid"],
            "toSqAddr_bits": s1["toSqAddr_bits"],
            "toUnalignQueue_valid": s1["toUnalignQueue_valid"],
            "toUnalignQueue_bits": s1["toUnalignQueue_bits"],
            "toSqAddrRe_nc": s2["toSqAddrRe_nc"],
            "toSqAddrRe_mmio": s2["toSqAddrRe_mmio"],
            "toSqAddrRe_memBackTypeMM": s2["toSqAddrRe_memBackTypeMM"],
            "toSqAddrRe_hasException": s2["toSqAddrRe_hasException"],
            "toSqAddrRe_isLastRequest": s2["toSqAddrRe_isLastRequest"],
            "feedBackSlow_valid": feedback_seen[0],
            "feedBackSlow_hit": feedback_seen[1],
            "stout_valid": wb["valid"],
            "stout_bits": wb["bits"],
            "exceptionInfo_valid": wb["valid"],
            "exceptionInfo_bits": wb.get("exception_bits"),
            "internal": {
                "s0_next_valid": s0_next_valid, "s1c_out_valid": s1c["out_valid"],
                "s2c_out_valid": s2c["out_valid"],
                "s3c_pipe_out_valid": s3c["pipe_out_valid"],
                "delay_in_valid": delay_beat["delay_in_valid"],
                "fire_s0": s0["arb_valid"] and s0["stin_ready"] == 1,
            },
        }


def _s0_next(s0c: dict, redirect: dict) -> tuple[int, dict | None]:
    """S0 keeps the payload even when the beat is killed (only `valid` is gated),
    which matters because S1's redirect-kill term reads the payload without a
    valid gate."""
    from suites.memblock.lsu.pointers import rob_need_flush
    if not s0c["arb_valid"]:
        return 0, None
    fields = s0c["fields"]
    killed = rob_need_flush(fields["uop_robIdx_flag"], fields["uop_robIdx_value"],
                            fields["uop_robIdx_isFormer"], redirect)
    return (0 if killed else 1), fields


def _s4(state: StageState) -> dict:
    """S4 is a pure pass-through of S3's head register."""
    return {"valid": state.valid, "bits": state.bits}


class NewStoreUnitEnv:
    def __init__(self, dut, coverage=None) -> None:
        self.dut = dut
        self.coverage = coverage
        self.stin_valid = dut.io_stin_valid
        self.stin = {name: getattr(dut, f"io_stin_bits_{name}") for name in STIN_FIELDS}
        self.stin_ready = dut.io_stin_ready
        self.tlb_valid_sig = dut.io_tlb_resp_valid
        self.tlb = {name: getattr(dut, f"io_tlb_resp_bits_{name}")
                    for name in _tlb_field_names(dut)}
        self.pmp = {"ld": dut.io_pmp_ld, "st": dut.io_pmp_st, "mmio": dut.io_pmp_mmio}
        self.redirect = {
            "valid": dut.io_redirect_valid, "level": dut.io_redirect_bits_level,
            "flag": dut.io_redirect_bits_robIdx_flag,
            "value": dut.io_redirect_bits_robIdx_value,
            "former": dut.io_redirect_bits_robIdx_isFormer,
        }
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
        self.trigger_enable = [getattr(dut, f"io_csrTrigger_tEnableVec_{i}")
                               for i in range(TRIGGER_NUM)]
        self.trigger_debug = dut.io_csrTrigger_debugMode
        self.trigger_bp_exp = dut.io_csrTrigger_triggerCanRaiseBpExp
        self.deq = (dut.io_sqDeqPtr_first_flag, dut.io_sqDeqPtr_second_flag,
                    dut.io_sqDeqPtr_value)
        self.addr_ready = (dut.io_sqAddrReadyPtr_first_flag,
                           dut.io_sqAddrReadyPtr_second_flag,
                           dut.io_sqAddrReadyPtr_value)
        self.queue_ready = dut.io_toUnalignQueue_ready
        self.out = {
            "tlb_req_valid": dut.io_tlb_req_valid,
            "tlb_req_kill": dut.io_tlb_req_kill,
            "updateLFST_valid": dut.io_updateLFST_valid,
            "staNukeQueryReq_valid": dut.io_staNukeQueryReq_valid,
            "toSqAddr_valid": dut.io_toSqAddr_valid,
            "toUnalignQueue_valid": dut.io_toUnalignQueue_valid,
            "toSqAddrRe_nc": dut.io_toSqAddrRe_nc,
            "toSqAddrRe_mmio": dut.io_toSqAddrRe_mmio,
            "toSqAddrRe_memBackTypeMM": dut.io_toSqAddrRe_memBackTypeMM,
            "toSqAddrRe_hasException": dut.io_toSqAddrRe_hasException,
            "toSqAddrRe_isLastRequest": dut.io_toSqAddrRe_isLastRequest,
            "feedBackSlow_valid": dut.io_feedBackSlow_valid,
            "feedBackSlow_hit": dut.io_feedBackSlow_bits_hit,
            "stout_valid": dut.io_stout_toRob_valid,
            "exceptionInfo_valid": dut.io_exceptionInfo_valid,
        }
        self.tlb_req_bits = {name: getattr(dut, f"io_tlb_req_bits_{name}")
                             for name in ("vaddr", "fullva", "checkfullva", "cmd",
                                          "hyperinst", "isPrefetch",
                                          "debug_robIdx_flag",
                                          "debug_robIdx_value",
                                          "debug_robIdx_isFormer")}
        self.update_lfst = {name: getattr(dut, f"io_updateLFST_bits_{name}")
                            for name in UPDATE_LFST_FIELDS}
        self.nuke = {name: getattr(dut, f"io_staNukeQueryReq_bits_{name}")
                     for name in NUKE_FIELDS}
        self.sq = {name: getattr(dut, f"io_toSqAddr_bits_{name}")
                   for name in SQ_ADDR_FIELDS}
        self.queue = {name: getattr(dut, f"io_toUnalignQueue_bits_{name}")
                      for name in UNALIGN_QUEUE_FIELDS}
        self.stout = {name: getattr(dut, f"io_stout_toRob_bits_{name}")
                      for name in STOUT_FIELDS}
        self.exc = {name: getattr(dut, f"io_exceptionInfo_bits_{name}")
                    for name in EXC_FIELDS}
        self.model = NewStoreUnitModel()
        self.cycles = 0

    def prime(self, cycles: int = 4) -> None:
        """Fill every stage register with a known beat.

        The generated payload registers are random-initialized (only their valid
        bit is reset), so before the first real beat the idle-cycle combinational
        outputs that read a stale payload are not predictable. Priming with
        ``cycles`` distinct stores makes them deterministic without hiding any
        behaviour: from here on the model and the DUT see the same stale data.
        """
        for index in range(cycles):
            stin_bits = dict(fuOpType=0, src_0=0x1000 + index * 0x10, imm=0,
                             robIdx_flag=0, robIdx_value=200 + index,
                             robIdx_isFormer=1, isRVC=0, ftqIdx_flag=0,
                             ftqIdx_value=0, ftqOffset=0, storeSetHit=0, ssid=0,
                             sqIdx_first_flag=0, sqIdx_second_flag=0,
                             sqIdx_value=index)
            tlb_bits = dict(paddr_0=0x8000, gpaddr_0=0, fullva=0, pbmt_0=3, miss=0,
                            isForVSnonLeafPTE=0, excp_0_vaNeedExt=0,
                            excp_0_isHyper=0, excp_0_gpf_ld=0, excp_0_gpf_st=0,
                            excp_0_pf_ld=0, excp_0_pf_st=0, excp_0_af_ld=0,
                            excp_0_af_st=0)
            self.model.cycle(1, stin_bits, tlb_bits, 1, blank_pmp(),
                             blank_redirect(), blank_trigger(), [0] * TRIGGER_NUM,
                             0, 0, (0, 0, 0), (0, 0, index), 1)
            self.drive(1, stin_bits, tlb_bits, 1, blank_pmp(), blank_redirect(),
                       blank_trigger(), [0] * TRIGGER_NUM, 0, 0, (0, 0, 0),
                       (0, 0, index), 1)
            self.dut.Step(1)
        # Drain the primed beats so the tests start from an idle pipeline.
        for _ in range(4):
            self.model.cycle(0, blank(STIN_FIELDS), blank_tlb(), 0, blank_pmp(),
                             blank_redirect(), blank_trigger(), [0] * TRIGGER_NUM,
                             0, 0, (0, 0, 0), (0, 0, 0), 1)
            self.drive(0, blank(STIN_FIELDS), blank_tlb(), 0, blank_pmp(),
                       blank_redirect(), blank_trigger(), [0] * TRIGGER_NUM, 0, 0,
                       (0, 0, 0), (0, 0, 0), 1)
            self.dut.Step(1)

    def reset(self, cycles: int = 4) -> None:
        self.dut.reset.Set(1)
        for _ in range(cycles):
            self.dut.Step(1)
        self.dut.reset.Set(0)
        self.model.reset()
        self.drive(0, blank(STIN_FIELDS), blank_tlb(), 0, blank_pmp(),
                   blank_redirect(), blank_trigger(), [0] * TRIGGER_NUM, 0, 1,
                   (0, 0, 0), (0, 0, 0), 1)
        self.dut.Step(1)
        self.prime()

    def drive(self, stin_valid, stin, tlb, tlb_valid, pmp, redirect, cfg,
              enables, debug, bp, deq, addr_ready, queue_ready) -> None:
        self.stin_valid.Set(1 if stin_valid else 0)
        for name, signal in self.stin.items():
            signal.Set(int(stin.get(name, 0)))
        self.tlb_valid_sig.Set(1 if tlb_valid else 0)
        for name, signal in self.tlb.items():
            signal.Set(int(tlb.get(name, 0)))
        for name, signal in self.pmp.items():
            signal.Set(int(pmp.get(name, 0)))
        self.redirect["valid"].Set(1 if redirect["valid"] else 0)
        self.redirect["level"].Set(int(redirect["level"]))
        self.redirect["flag"].Set(int(redirect["flag"]))
        self.redirect["value"].Set(int(redirect["value"]))
        self.redirect["former"].Set(int(redirect["former"]))
        for index, config in enumerate(cfg):
            signals = self.trigger_signals[index]
            signals["match_type"].Set(config.match_type)
            signals["select"].Set(config.select)
            signals["timing"].Set(config.timing)
            signals["action"].Set(config.action)
            signals["chain"].Set(config.chain)
            signals["store"].Set(config.store)
            signals["tdata2"].Set(config.tdata2 & ((1 << 64) - 1))
            self.trigger_enable[index].Set(1 if enables[index] else 0)
        self.trigger_debug.Set(1 if debug else 0)
        self.trigger_bp_exp.Set(1 if bp else 0)
        for index, value in enumerate(deq):
            self.deq[index].Set(int(value))
        for index, value in enumerate(addr_ready):
            self.addr_ready[index].Set(int(value))
        self.queue_ready.Set(1 if queue_ready else 0)

    def cycle(self, stin_valid, stin, tlb, tlb_valid, pmp, redirect, cfg,
              enables, debug, bp, deq, addr_ready, queue_ready,
              context="cycle") -> dict:
        want = self.model.cycle(stin_valid, stin, tlb, tlb_valid, pmp, redirect,
                               cfg, enables, debug, bp, deq, addr_ready, queue_ready)
        self.drive(stin_valid, stin, tlb, tlb_valid, pmp, redirect, cfg, enables,
                   debug, bp, deq, addr_ready, queue_ready)
        self.dut.Step(1)

        def expect(signal, value, name):
            got = int(signal.value)
            if got != value:
                raise AssertionError(
                    f"{context}: {name} {got:#x} != {value:#x} "
                    f"(stin_valid={stin_valid} redirect={redirect} pmp={pmp})")

        for name in ("tlb_req_valid", "tlb_req_kill", "updateLFST_valid",
                     "staNukeQueryReq_valid", "toSqAddr_valid",
                     "toUnalignQueue_valid", "toSqAddrRe_nc", "toSqAddrRe_mmio",
                     "toSqAddrRe_memBackTypeMM", "toSqAddrRe_hasException",
                     "toSqAddrRe_isLastRequest", "feedBackSlow_valid",
                     "stout_valid", "exceptionInfo_valid"):
            expect(self.out[name], want[name], name)
        # The parent registers the feedback with RegEnable, so `hit` holds its
        # previous value while `valid` is low; it is only meaningful when valid.
        if want["feedBackSlow_valid"]:
            expect(self.out["feedBackSlow_hit"], want["feedBackSlow_hit"],
                   "feedBackSlow_hit")
        expect(self.stin_ready, want["stin_ready"], "stin_ready")
        if want["tlb_req_valid"]:
            for name, signal in self.tlb_req_bits.items():
                expect(signal, want["tlb_req_bits"][name], f"tlb_req_bits.{name}")
        if want["updateLFST_valid"]:
            for name, signal in self.update_lfst.items():
                expect(signal, want["updateLFST_bits"][name], f"updateLFST.{name}")
        if want["staNukeQueryReq_valid"]:
            for name, signal in self.nuke.items():
                expect(signal, want["staNukeQueryReq_bits"][name],
                       f"staNukeQueryReq.{name}")
        if want["toSqAddr_valid"]:
            for name, signal in self.sq.items():
                expect(signal, want["toSqAddr_bits"][name], f"toSqAddr.{name}")
        if want["toUnalignQueue_valid"]:
            for name, signal in self.queue.items():
                expect(signal, want["toUnalignQueue_bits"][name],
                       f"toUnalignQueue.{name}")
        if want["stout_valid"]:
            for name, signal in self.stout.items():
                expect(signal, want["stout_bits"][name], f"stout.{name}")
        if want["exceptionInfo_valid"]:
            for name, signal in self.exc.items():
                expect(signal, want["exceptionInfo_bits"][name], f"exceptionInfo.{name}")

        if self.coverage is not None:
            self.coverage.observe(want=want, stin=stin, tlb=tlb, pmp=pmp,
                                  redirect=redirect)
        self.cycles += 1
        return want


def _tlb_field_names(dut) -> tuple[str, ...]:
    return ("paddr_0", "gpaddr_0", "fullva", "pbmt_0", "miss",
            "isForVSnonLeafPTE", "excp_0_vaNeedExt", "excp_0_isHyper",
            "excp_0_gpf_ld", "excp_0_gpf_st", "excp_0_pf_ld", "excp_0_pf_st",
            "excp_0_af_ld", "excp_0_af_st")


def blank(fields) -> dict[str, int]:
    return {name: 0 for name in fields}


def blank_tlb() -> dict[str, int]:
    return {name: 0 for name in _tlb_field_names(None)}


def blank_pmp() -> dict:
    return {"ld": 0, "st": 0, "mmio": 0}


def blank_redirect() -> dict:
    return {"valid": 0, "level": 0, "flag": 0, "value": 0, "former": 0}


def blank_trigger() -> list[TriggerConfig]:
    return [TriggerConfig(action=15, tdata2=0, store=1) for _ in range(TRIGGER_NUM)]


def random_stin(rng: random.Random, **overrides) -> dict:
    values = {name: rng.randrange(1 << width) for name, width in STIN_FIELDS.items()}
    values.update(overrides)
    return values
