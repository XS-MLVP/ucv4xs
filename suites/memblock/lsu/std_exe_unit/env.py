"""Environment and reference for StdExeUnit (store-data unit).

Semantics (all combinational except the feedback register):

    legalIssue      = sqIdx.withInPhysicalQueue(sqDeqPtr)          // [deq, deq+64)
    isAMO           = fuType[18]
    in.ready        = !vstdIn.valid
    out.toRob.valid = in.valid && !vstdIn.valid && !isAMO && legalIssue
    atomicData      = in.valid && !vstdIn.valid && isAMO
    sqData.valid    = out.toRob.valid || vstdIn.valid
    sqData.bits     = vstdIn.valid ? vstdIn : (fuOpType, {64'h0, src0}, sqIdx)
    feedBack.valid  = RegNext(in.valid)
    feedBack.hit    = RegEnable(legalIssue || isAMO, in.valid)

Contract: docs/contracts/std-exe-unit.md
"""
from __future__ import annotations

import random

from suites.memblock.lsu.pointers import sq_in_physical_queue

IN_FIELDS = {
    "fuType": 32,
    "fuOpType": 12,
    "src_0": 64,
    "robIdx_flag": 1,
    "robIdx_value": 8,
    "robIdx_isFormer": 1,
    "sqIdx_first_flag": 1,
    "sqIdx_second_flag": 1,
    "sqIdx_value": 6,
}
VSTD_FIELDS = {
    "fuOpType": 12,
    "data": 128,
    "sqIdx_first_flag": 1,
    "sqIdx_second_flag": 1,
    "sqIdx_value": 6,
}
SQ_DATA_FIELDS = dict(VSTD_FIELDS)

AMO_FU_TYPE_BIT = 18


def mask_fields(values: dict, widths: dict) -> dict:
    return {name: int(values.get(name, 0)) & ((1 << width) - 1)
            for name, width in widths.items()}


class StdExeUnitModel:
    def __init__(self) -> None:
        self.feedback_valid = None
        self.feedback_hit = None

    def comb(self, in_valid: int, in_bits: dict, vstd_valid: int, vstd: dict,
             deq: tuple) -> dict:
        in_bits = mask_fields(in_bits, IN_FIELDS)
        vstd = mask_fields(vstd, VSTD_FIELDS)
        sq = (in_bits["sqIdx_first_flag"], in_bits["sqIdx_second_flag"],
              in_bits["sqIdx_value"])
        legal = sq_in_physical_queue(*sq, *deq)
        is_amo = (in_bits["fuType"] >> AMO_FU_TYPE_BIT) & 1
        out_valid = int(bool(in_valid) and not vstd_valid and not is_amo and legal)
        scalar_sq = {
            "fuOpType": in_bits["fuOpType"],
            "data": in_bits["src_0"] & ((1 << 64) - 1),
            "sqIdx_first_flag": in_bits["sqIdx_first_flag"],
            "sqIdx_second_flag": in_bits["sqIdx_second_flag"],
            "sqIdx_value": in_bits["sqIdx_value"],
        }
        chosen = vstd if vstd_valid else scalar_sq
        return {
            "legal": legal,
            "is_amo": bool(is_amo),
            "in_ready": 0 if vstd_valid else 1,
            "toRob_valid": out_valid,
            "atomic_valid": int(bool(in_valid) and not vstd_valid and bool(is_amo)),
            "sqData_valid": int(bool(out_valid) or bool(vstd_valid)),
            "sqData_bits": chosen,
            "feedback_valid_next": int(bool(in_valid)),
            "feedback_hit_next": int(bool(legal) or bool(is_amo)),
        }


class StdExeUnitEnv:
    def __init__(self, dut, coverage=None) -> None:
        self.dut = dut
        self.coverage = coverage
        self.in_valid = dut.io_in_valid
        self.in_bits = {name: getattr(dut, f"io_in_bits_{name}") for name in IN_FIELDS}
        self.vstd_valid = dut.io_vstdIn_valid
        self.vstd = {name: getattr(dut, f"io_vstdIn_bits_{name}") for name in VSTD_FIELDS}
        self.deq = (dut.io_sqDeqPtr_first_flag, dut.io_sqDeqPtr_second_flag,
                    dut.io_sqDeqPtr_value)
        self.in_ready = dut.io_in_ready
        self.to_rob_valid = dut.io_out_toRob_valid
        self.to_rob = {
            "robIdx_flag": dut.io_out_toRob_bits_robIdx_flag,
            "robIdx_value": dut.io_out_toRob_bits_robIdx_value,
            "robIdx_isFormer": dut.io_out_toRob_bits_robIdx_isFormer,
        }
        self.atomic_valid = dut.io_atomicData_valid
        self.atomic = {"fuOpType": dut.io_atomicData_bits_fuOpType,
                       "src_0": dut.io_atomicData_bits_src_0}
        self.sq_valid = dut.io_sqData_valid
        self.sq = {name: getattr(dut, f"io_sqData_bits_{name}")
                   for name in SQ_DATA_FIELDS}
        self.feedback_valid = dut.io_feedBack_valid
        self.feedback_hit = dut.io_feedBack_bits_hit
        self.model = StdExeUnitModel()
        self.cycles = 0
        self.primed = False

    def reset(self) -> None:
        """No reset port: the feedback registers start from a random value.

        One legal beat makes both bits deterministic from the next cycle on; the
        first observed cycle is therefore not compared.
        """
        self.model = StdExeUnitModel()
        self.primed = False

    def drive(self, in_valid: int, in_bits: dict, vstd_valid: int, vstd: dict,
              deq: tuple) -> None:
        self.in_valid.Set(1 if in_valid else 0)
        for name, signal in self.in_bits.items():
            signal.Set(int(in_bits.get(name, 0)))
        self.vstd_valid.Set(1 if vstd_valid else 0)
        for name, signal in self.vstd.items():
            signal.Set(int(vstd.get(name, 0)))
        for index, value in enumerate(deq):
            self.deq[index].Set(int(value))

    def cycle(self, in_valid: int, in_bits: dict, vstd_valid: int, vstd: dict,
              deq: tuple, context: str = "cycle") -> dict:
        """Drive one cycle, clock it, then compare.

        After ``Step`` the combinational pins reflect this cycle's inputs and
        the feedback register reflects the value captured at this edge, so both
        are compared against the same model evaluation.
        """
        want = self.model.comb(in_valid, in_bits, vstd_valid, vstd, deq)
        self.drive(in_valid, in_bits, vstd_valid, vstd, deq)
        self.dut.Step(1)

        def expect(signal, value, name):
            got = int(signal.value)
            if got != value:
                raise AssertionError(
                    f"{context}: {name} {got:#x} != {value:#x} "
                    f"(in_valid={in_valid} vstd={vstd_valid} deq={deq})")

        expect(self.in_ready, want["in_ready"], "in.ready")
        expect(self.to_rob_valid, want["toRob_valid"], "out.toRob.valid")
        if want["toRob_valid"]:
            expect(self.to_rob["robIdx_flag"], int(in_bits.get("robIdx_flag", 0)),
                   "toRob.robIdx_flag")
            expect(self.to_rob["robIdx_value"],
                   int(in_bits.get("robIdx_value", 0)) & 0xFF, "toRob.robIdx_value")
            expect(self.to_rob["robIdx_isFormer"],
                   int(in_bits.get("robIdx_isFormer", 0)), "toRob.robIdx_isFormer")
        expect(self.atomic_valid, want["atomic_valid"], "atomicData.valid")
        if want["atomic_valid"]:
            expect(self.atomic["fuOpType"], int(in_bits["fuOpType"]) & 0xFFF,
                   "atomicData.fuOpType")
            expect(self.atomic["src_0"], int(in_bits["src_0"]) & ((1 << 64) - 1),
                   "atomicData.src_0")
        expect(self.sq_valid, want["sqData_valid"], "sqData.valid")
        if want["sqData_valid"]:
            for name, signal in self.sq.items():
                expect(signal, want["sqData_bits"][name], f"sqData.{name}")
        # After the edge the feedback register holds this cycle's capture
        # (RegNext of in.valid). `hit` is RegEnable, so it holds its old value
        # when the new valid is low and is only compared when the capture is 1.
        expect(self.feedback_valid, want["feedback_valid_next"], "feedBack.valid")
        if want["feedback_valid_next"]:
            expect(self.feedback_hit, want["feedback_hit_next"], "feedBack.hit")
        self.model.feedback_valid = want["feedback_valid_next"]
        self.model.feedback_hit = want["feedback_hit_next"]

        self.cycles += 1
        if self.coverage is not None:
            self.coverage.observe(want=want, in_valid=in_valid, vstd_valid=vstd_valid)
        return want


def blank(fields) -> dict[str, int]:
    return {name: 0 for name in fields}


def random_in(rng: random.Random, **overrides) -> dict:
    values = {name: rng.randrange(1 << width) for name, width in IN_FIELDS.items()}
    values.update(overrides)
    return values


def random_vstd(rng: random.Random, **overrides) -> dict:
    values = {name: rng.randrange(1 << width) for name, width in VSTD_FIELDS.items()}
    values.update(overrides)
    return values
