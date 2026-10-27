"""Environment and independent model for StoreUnitS2.

S2 decides the memory type of the store from the TLB PBMT/PMP result and forms
the final access-fault / misalign exceptions:

    tlbHit          = pipeIn.valid && pipeIn.tlbHit
    pmpInaccessible = tlbHit && (pmp.st || pmp.ld && isCboNoZero)
    tlbInaccessible = exc[7] || exc[15] || exc[23]
    isNC            = tlbHit && !tlbInaccessible && pbmt == 1
    isMMIO          = tlbHit && !tlbInaccessible && (pbmt == 2 || (pbmt == 0 && pmp.mmio))
    af              = exc[7] || pmpInaccessible || (vector && isUncache)
                      || (isCbo && isUncache) || (isMMIO && !align)
    am              = !align && scalar && isNC && !pmpInaccessible
    memBackTypeMM   = !(pmp.mmio && !tlbInaccessible)

Contract: docs/contracts/store-s2.md
"""
from __future__ import annotations

import random

from lsuverify.common.robptr import rob_need_flush

PIPE_IN_FIELDS = {
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

PIPE_OUT_FIELDS = {
    "accessType_instrType": 3,
    "accessType_isCbo": 1,
    "uop_exceptionVec_23": 1,
    "uop_exceptionVec_19": 1,
    "uop_exceptionVec_15": 1,
    "uop_exceptionVec_7": 1,
    "uop_exceptionVec_6": 1,
    "uop_exceptionVec_3": 1,
    "uop_trigger": 4,
    "uop_robIdx_flag": 1,
    "uop_robIdx_value": 8,
    "uop_robIdx_isFormer": 1,
    "fullva": 64,
    "unalignHead": 1,
    "tlbException_vaNeedExt": 1,
    "tlbException_isHyper": 1,
    "isForVSnonLeafPTE": 1,
    "gpaddr": 64,
    "hasException": 1,
    "needRSReplay": 1,
    "nc": 1,
    "mmio": 1,
    "memBackTypeMM": 1,
}

PBMT_PMA = 0
PBMT_NC = 1
PBMT_IO = 2
PBMT_DEFAULT = 3


def mask_fields(values: dict, widths: dict) -> dict:
    return {name: int(values.get(name, 0)) & ((1 << width) - 1)
            for name, width in widths.items()}


class StoreS2Model:
    def __init__(self) -> None:
        self.valid = 0
        self.bits: dict[str, int] | None = None

    def comb(self, in_valid: int, pipe_in: dict, pmp: dict, redirect: dict) -> dict:
        pipe_in = mask_fields(pipe_in, PIPE_IN_FIELDS)
        instr_type = pipe_in["accessType_instrType"]
        is_scalar = instr_type & 0x1
        is_vector = (instr_type >> 1) & 1
        is_cbo = pipe_in["accessType_isCbo"]
        is_cbo_no_zero = pipe_in["accessType_isCboNoZero"]

        tlb_hit = bool(in_valid) and bool(pipe_in["tlbHit"])
        redirect_kill = rob_need_flush(pipe_in["uop_robIdx_flag"],
                                       pipe_in["uop_robIdx_value"],
                                       pipe_in["uop_robIdx_isFormer"], redirect)
        fire = bool(in_valid) and not redirect_kill

        pmp_inaccessible = tlb_hit and (
            bool(pmp["st"]) or (bool(pmp["ld"]) and bool(is_cbo_no_zero)))
        tlb_inaccessible = bool(pipe_in["uop_exceptionVec_7"] or
                                pipe_in["uop_exceptionVec_15"] or
                                pipe_in["uop_exceptionVec_23"])
        usable = tlb_hit and not tlb_inaccessible
        pbmt = pipe_in["pbmt"]
        is_nc = usable and pbmt == PBMT_NC
        is_mmio = usable and (pbmt == PBMT_IO or (pbmt == PBMT_PMA and bool(pmp["mmio"])))
        is_uncache = is_nc or is_mmio
        mem_back_type_mm = not (bool(pmp["mmio"]) and not tlb_inaccessible)

        af = bool(pipe_in["uop_exceptionVec_7"]) or pmp_inaccessible or\
            bool(is_vector and is_uncache) or bool(is_cbo and is_uncache) or\
            bool(is_mmio and not pipe_in["align"])
        am = bool(not pipe_in["align"] and is_scalar and is_nc and not pmp_inaccessible)
        has_exception = bool(pipe_in["hasException"]) or af or am

        out = {
            "accessType_instrType": instr_type,
            "accessType_isCbo": pipe_in["accessType_isCbo"],
            "uop_exceptionVec_23": pipe_in["uop_exceptionVec_23"],
            "uop_exceptionVec_19": pipe_in["uop_exceptionVec_19"],
            "uop_exceptionVec_15": pipe_in["uop_exceptionVec_15"],
            "uop_exceptionVec_7": int(af),
            "uop_exceptionVec_6": int(am),
            "uop_exceptionVec_3": pipe_in["uop_exceptionVec_3"],
            "uop_trigger": pipe_in["uop_trigger"],
            "uop_robIdx_flag": pipe_in["uop_robIdx_flag"],
            "uop_robIdx_value": pipe_in["uop_robIdx_value"],
            "uop_robIdx_isFormer": pipe_in["uop_robIdx_isFormer"],
            "fullva": pipe_in["fullva"],
            "unalignHead": pipe_in["unalignHead"],
            "tlbException_vaNeedExt": pipe_in["tlbException_vaNeedExt"],
            "tlbException_isHyper": pipe_in["tlbException_isHyper"],
            "isForVSnonLeafPTE": pipe_in["isForVSnonLeafPTE"],
            "gpaddr": pipe_in["gpaddr"],
            "hasException": int(has_exception),
            "needRSReplay": pipe_in["needRSReplay"],
            "nc": int(is_nc),
            "mmio": int(is_mmio),
            "memBackTypeMM": int(mem_back_type_mm),
        }
        return {
            "kill": redirect_kill, "fire": fire, "tlb_hit": tlb_hit,
            "pmp_inaccessible": pmp_inaccessible, "is_nc": is_nc,
            "is_mmio": is_mmio, "is_uncache": is_uncache, "af": af, "am": am,
            "out_valid": int(fire), "out_bits": out,
            "toSqAddrRe_nc": int(is_nc),
            "toSqAddrRe_mmio": int(is_mmio),
            "toSqAddrRe_memBackTypeMM": int(mem_back_type_mm),
            "toSqAddrRe_hasException": int(fire and has_exception),
            "toSqAddrRe_isLastRequest": 0 if pipe_in["unalignHead"] else 1,
            "unalignHeadTlbHit": int(fire and bool(pipe_in["unalignHead"]) and tlb_hit),
        }


class StoreS2Env:
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
        self.pmp = {"ld": dut.io_pmp_ld, "st": dut.io_pmp_st, "mmio": dut.io_pmp_mmio}
        self.sq_re_nc = dut.io_toSqAddrRe_nc
        self.sq_re_mmio = dut.io_toSqAddrRe_mmio
        self.sq_re_mem_back = dut.io_toSqAddrRe_memBackTypeMM
        self.sq_re_has_exc = dut.io_toSqAddrRe_hasException
        self.sq_re_last = dut.io_toSqAddrRe_isLastRequest
        self.head_tlb_hit = dut.io_unalignHeadTlbHit
        self.model = StoreS2Model()
        self.cycles = 0

    def reset(self, cycles: int = 4) -> None:
        self.dut.reset.Set(1)
        for _ in range(cycles):
            self.dut.Step(1)
        self.dut.reset.Set(0)
        self.model = StoreS2Model()
        self.drive(0, blank(PIPE_IN_FIELDS), {"ld": 0, "st": 0, "mmio": 0},
                   {"valid": 0, "level": 0, "flag": 0, "value": 0, "former": 0})
        self.dut.Step(1)

    def drive(self, in_valid: int, in_bits: dict, pmp: dict, redirect: dict) -> None:
        self.in_valid.Set(1 if in_valid else 0)
        for name, signal in self.in_bits.items():
            signal.Set(int(in_bits.get(name, 0)))
        self.pmp["ld"].Set(int(pmp.get("ld", 0)))
        self.pmp["st"].Set(int(pmp.get("st", 0)))
        self.pmp["mmio"].Set(int(pmp.get("mmio", 0)))
        self.redirect_valid.Set(1 if redirect["valid"] else 0)
        self.redirect_level.Set(int(redirect["level"]))
        self.redirect_flag.Set(int(redirect["flag"]))
        self.redirect_value.Set(int(redirect["value"]))
        self.redirect_former.Set(int(redirect["former"]))

    def cycle(self, in_valid: int, in_bits: dict, pmp: dict, redirect: dict,
              context: str = "cycle") -> dict:
        want = self.model.comb(in_valid, in_bits, pmp, redirect)
        self.drive(in_valid, in_bits, pmp, redirect)
        self.dut.Step(1)

        def expect(signal, value, name):
            got = int(signal.value)
            if got != value:
                raise AssertionError(
                    f"{context}: {name} {got:#x} != {value:#x} "
                    f"(in_valid={in_valid} pmp={pmp} redirect={redirect})")

        expect(self.sq_re_nc, want["toSqAddrRe_nc"], "toSqAddrRe.nc")
        expect(self.sq_re_mmio, want["toSqAddrRe_mmio"], "toSqAddrRe.mmio")
        expect(self.sq_re_mem_back, want["toSqAddrRe_memBackTypeMM"],
               "toSqAddrRe.memBackTypeMM")
        expect(self.sq_re_has_exc, want["toSqAddrRe_hasException"],
               "toSqAddrRe.hasException")
        expect(self.sq_re_last, want["toSqAddrRe_isLastRequest"],
               "toSqAddrRe.isLastRequest")
        expect(self.head_tlb_hit, want["unalignHeadTlbHit"], "unalignHeadTlbHit")
        expect(self.out_valid, want["out_valid"], "pipeOut.valid")
        if want["out_valid"]:
            for name, signal in self.out.items():
                expect(signal, want["out_bits"][name], f"pipeOut.bits.{name}")
        if self.coverage is not None:
            self.coverage.observe(want=want, pipe_in=in_bits, pmp=pmp)
        self.model.valid = want["out_valid"]
        self.model.bits = want["out_bits"] if want["out_valid"] else None
        self.cycles += 1
        return want


def blank(fields) -> dict[str, int]:
    return {name: 0 for name in fields}


def random_pipe_in(rng: random.Random, **overrides) -> dict:
    values = {name: rng.randrange(1 << width) for name, width in PIPE_IN_FIELDS.items()}
    values.update(overrides)
    return values
