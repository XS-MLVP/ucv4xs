"""Environment and independent model for StoreUnitS3.

S3 has two independent paths:

1. a head-only pipeline register feeding ``io_pipeOut`` (the tail merge value
   consumed by S4);
2. a one-cycle writeback delay pipe feeding ``stout`` and ``exceptionInfo``,
   filtered by the same redirect on both sides.

The delay-pipe input is a *mixed* payload: when the unaligned head carries an
exception, the exception/trigger/fullva/gpaddr fields come from the concat path
and the rest from the normal pipe. The writeback is suppressed for vector
stores and for MMIO/CBO beats without an exception, and it is dropped when the
beat needs an RS replay.

Contract: docs/contracts/store-s3.md
"""
from __future__ import annotations

import random

from lsuverify.common.robptr import rob_need_flush

PIPE_IN_FIELDS = {
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

# The fields that the head/tail merge can override.
MIXED_FIELDS = ("uop_exceptionVec_23", "uop_exceptionVec_19", "uop_exceptionVec_15",
                "uop_exceptionVec_7", "uop_exceptionVec_6", "uop_exceptionVec_3",
                "uop_trigger", "fullva", "tlbException_vaNeedExt",
                "tlbException_isHyper", "isForVSnonLeafPTE", "gpaddr")

CONCAT_FIELDS = MIXED_FIELDS + ("hasException",)

PIPE_OUT_FIELDS = {
    "uop_exceptionVec_23": 1,
    "uop_exceptionVec_19": 1,
    "uop_exceptionVec_15": 1,
    "uop_exceptionVec_7": 1,
    "uop_exceptionVec_6": 1,
    "uop_exceptionVec_3": 1,
    "uop_trigger": 4,
    "fullva": 64,
    "tlbException_vaNeedExt": 1,
    "tlbException_isHyper": 1,
    "isForVSnonLeafPTE": 1,
    "gpaddr": 64,
    "hasException": 1,
}

STOUT_FIELDS = {
    "robIdx_flag": 1,
    "robIdx_value": 8,
    "robIdx_isFormer": 1,
    "exceptionVec_23": 1,
    "exceptionVec_19": 1,
    "exceptionVec_15": 1,
    "exceptionVec_7": 1,
    "exceptionVec_6": 1,
    "exceptionVec_3": 1,
    "trigger": 4,
    "debugInfo_isMMIO": 1,
    "debugInfo_isNCIO": 1,
}

EXC_INFO_FIELDS = {
    "robIdx_flag": 1,
    "robIdx_value": 8,
    "robIdx_isFormer": 1,
    "exceptionVec_23": 1,
    "exceptionVec_19": 1,
    "exceptionVec_15": 1,
    "exceptionVec_7": 1,
    "exceptionVec_6": 1,
    "exceptionVec_3": 1,
    "vaddr": 64,
    "vaNeedExt": 1,
    "isHyper": 1,
    "isForVSnonLeafPTE": 1,
    "gpaddr": 50,
}


def mask_fields(values: dict, widths: dict) -> dict:
    return {name: int(values.get(name, 0)) & ((1 << width) - 1)
            for name, width in widths.items()}


class StoreS3Model:
    def __init__(self) -> None:
        self.pipe_out_valid = 0
        self.pipe_out_bits: dict[str, int] | None = None
        # Delay-pipe state: the beat that will be visible on the next cycle.
        self.prev_delay_valid = 0
        self.prev_delay_bits: dict[str, int] | None = None

    def comb(self, in_valid: int, pipe_in: dict, concat_valid: int, concat: dict,
             redirect: dict) -> dict:
        pipe_in = mask_fields(pipe_in, PIPE_IN_FIELDS)
        concat = mask_fields(concat, {name: PIPE_IN_FIELDS[name]
                                      for name in CONCAT_FIELDS})
        instr_type = pipe_in["accessType_instrType"]
        is_vector = (instr_type >> 1) & 1
        is_prefetch = (instr_type >> 2) & 1

        redirect_kill = rob_need_flush(pipe_in["uop_robIdx_flag"],
                                       pipe_in["uop_robIdx_value"],
                                       pipe_in["uop_robIdx_isFormer"], redirect)
        head_has_exception = bool(concat_valid) and bool(concat["hasException"])

        # Mixed payload for the delay pipe.
        mixed = {name: (concat[name] if head_has_exception else pipe_in[name])
                 for name in MIXED_FIELDS}
        mixed["robIdx_flag"] = pipe_in["uop_robIdx_flag"]
        mixed["robIdx_value"] = pipe_in["uop_robIdx_value"]
        mixed["robIdx_isFormer"] = pipe_in["uop_robIdx_isFormer"]
        mixed["nc"] = pipe_in["nc"]
        mixed["mmio"] = pipe_in["mmio"]
        mixed["memBackTypeMM"] = pipe_in["memBackTypeMM"]
        mixed["instrType"] = instr_type

        delay_in_valid = bool(in_valid) and not redirect_kill and\
            (not pipe_in["mmio"] and not pipe_in["accessType_isCbo"] or
             bool(pipe_in["hasException"])) and\
            not pipe_in["unalignHead"] and not is_prefetch and\
            not pipe_in["needRSReplay"]

        return {
            "kill": redirect_kill,
            "head_has_exception": head_has_exception,
            "delay_in_valid": int(delay_in_valid),
            "delay_in_bits": mixed,
            "pipe_out_valid": int(bool(in_valid) and not redirect_kill and
                                  bool(pipe_in["unalignHead"])),
            "pipe_out_bits": {name: pipe_in[name] for name in PIPE_OUT_FIELDS},
            "is_vector": is_vector,
        }

    def writeback(self, comb: dict) -> dict:
        """Compute the writeback outputs for the beat that enters this cycle.

        The delay pipe's output register is loaded from the input when
        ``out.ready`` is high, and the parent ties ``out.ready`` to ``true``
        (NewStoreUnit.scala:782). After the clock edge the register therefore
        already holds this cycle's beat, so the writeback is visible in the same
        ``cycle()`` call. The input-side redirect filter is applied once, on the
        entry cycle; a later redirect can no longer remove a consumed beat.
        """
        if not comb["delay_in_valid"]:
            return {"valid": 0, "bits": None, "is_vector": 0}
        bits = comb["delay_in_bits"]
        is_vector = (bits["instrType"] >> 1) & 1
        return {
            "valid": 0 if is_vector else 1,
            "bits": {
                "robIdx_flag": bits["robIdx_flag"],
                "robIdx_value": bits["robIdx_value"],
                "robIdx_isFormer": bits["robIdx_isFormer"],
                "exceptionVec_23": bits["uop_exceptionVec_23"],
                "exceptionVec_19": bits["uop_exceptionVec_19"],
                "exceptionVec_15": bits["uop_exceptionVec_15"],
                "exceptionVec_7": bits["uop_exceptionVec_7"],
                "exceptionVec_6": bits["uop_exceptionVec_6"],
                "exceptionVec_3": bits["uop_exceptionVec_3"],
                "trigger": bits["uop_trigger"],
                "debugInfo_isMMIO": bits["mmio"],
                "debugInfo_isNCIO": 1 if (bits["nc"] and not bits["memBackTypeMM"]) else 0,
            },
            "exception_bits": {
                "robIdx_flag": bits["robIdx_flag"],
                "robIdx_value": bits["robIdx_value"],
                "robIdx_isFormer": bits["robIdx_isFormer"],
                "exceptionVec_23": bits["uop_exceptionVec_23"],
                "exceptionVec_19": bits["uop_exceptionVec_19"],
                "exceptionVec_15": bits["uop_exceptionVec_15"],
                "exceptionVec_7": bits["uop_exceptionVec_7"],
                "exceptionVec_6": bits["uop_exceptionVec_6"],
                "exceptionVec_3": bits["uop_exceptionVec_3"],
                "vaddr": bits["fullva"],
                "vaNeedExt": bits["tlbException_vaNeedExt"],
                "isHyper": bits["tlbException_isHyper"],
                "isForVSnonLeafPTE": bits["isForVSnonLeafPTE"],
                "gpaddr": bits["gpaddr"] & ((1 << 50) - 1),
            },
            "is_vector": is_vector,
        }


class StoreS3Env:
    def __init__(self, dut, coverage=None) -> None:
        self.dut = dut
        self.coverage = coverage
        self.in_valid = dut.io_pipeIn_valid
        self.in_bits = {name: getattr(dut, f"io_pipeIn_bits_{name}")
                        for name in PIPE_IN_FIELDS}
        self.concat_valid = dut.io_unalignConcat_valid
        self.concat = {name: getattr(dut, f"io_unalignConcat_bits_{name}")
                       for name in CONCAT_FIELDS}
        self.out_valid = dut.io_pipeOut_valid
        self.out = {name: getattr(dut, f"io_pipeOut_bits_{name}")
                    for name in PIPE_OUT_FIELDS}
        self.redirect_valid = dut.io_redirect_valid
        self.redirect_level = dut.io_redirect_bits_level
        self.redirect_flag = dut.io_redirect_bits_robIdx_flag
        self.redirect_value = dut.io_redirect_bits_robIdx_value
        self.redirect_former = dut.io_redirect_bits_robIdx_isFormer
        self.stout_valid = dut.io_stout_toRob_valid
        self.stout = {name: getattr(dut, f"io_stout_toRob_bits_{name}")
                      for name in STOUT_FIELDS}
        self.exc_valid = dut.io_exceptionInfo_valid
        self.exc = {name: getattr(dut, f"io_exceptionInfo_bits_{name}")
                    for name in EXC_INFO_FIELDS}
        self.model = StoreS3Model()
        self.cycles = 0

    def reset(self, cycles: int = 4) -> None:
        self.dut.reset.Set(1)
        for _ in range(cycles):
            self.dut.Step(1)
        self.dut.reset.Set(0)
        self.model = StoreS3Model()
        self.drive(0, blank(PIPE_IN_FIELDS), 0, blank(CONCAT_FIELDS), blank_redirect())
        self.dut.Step(1)

    def drive(self, in_valid: int, in_bits: dict, concat_valid: int, concat: dict,
              redirect: dict) -> None:
        self.in_valid.Set(1 if in_valid else 0)
        for name, signal in self.in_bits.items():
            signal.Set(int(in_bits.get(name, 0)))
        self.concat_valid.Set(1 if concat_valid else 0)
        for name, signal in self.concat.items():
            signal.Set(int(concat.get(name, 0)))
        self.redirect_valid.Set(1 if redirect["valid"] else 0)
        self.redirect_level.Set(int(redirect["level"]))
        self.redirect_flag.Set(int(redirect["flag"]))
        self.redirect_value.Set(int(redirect["value"]))
        self.redirect_former.Set(int(redirect["former"]))

    def cycle(self, in_valid: int, in_bits: dict, concat_valid: int, concat: dict,
              redirect: dict, context: str = "cycle") -> dict:
        comb = self.model.comb(in_valid, in_bits, concat_valid, concat, redirect)
        wb = self.model.writeback(comb)
        self.drive(in_valid, in_bits, concat_valid, concat, redirect)
        self.dut.Step(1)

        def expect(signal, value, name):
            got = int(signal.value)
            if got != value:
                raise AssertionError(
                    f"{context}: {name} {got:#x} != {value:#x} "
                    f"(in_valid={in_valid} concat_valid={concat_valid} "
                    f"redirect={redirect})")

        # Head-only pipeOut register.
        expect(self.out_valid, comb["pipe_out_valid"], "pipeOut.valid")
        if comb["pipe_out_valid"]:
            for name, signal in self.out.items():
                expect(signal, comb["pipe_out_bits"][name], f"pipeOut.bits.{name}")
        # Delay-pipe writeback (previous beat, current redirect).
        expect(self.stout_valid, wb["valid"], "stout.toRob.valid")
        if wb["valid"]:
            for name, signal in self.stout.items():
                expect(signal, wb["bits"][name], f"stout.toRob.bits.{name}")
        expect(self.exc_valid, wb["valid"], "exceptionInfo.valid")
        if wb["valid"]:
            for name, signal in self.exc.items():
                expect(signal, wb["exception_bits"][name],
                       f"exceptionInfo.bits.{name}")

        if self.coverage is not None:
            self.coverage.observe(comb=comb, wb=wb, concat_valid=concat_valid)
        self.model.pipe_out_valid = comb["pipe_out_valid"]
        self.model.pipe_out_bits = comb["pipe_out_bits"]
        self.cycles += 1
        return {"pipe_out_valid": comb["pipe_out_valid"],
                "pipe_out_bits": comb["pipe_out_bits"],
                "stout_valid": wb["valid"],
                "stout_bits": wb["bits"],
                "exception_valid": wb["valid"],
                "exception_bits": wb.get("exception_bits"),
                "delay_in_valid": comb["delay_in_valid"],
                "head_has_exception": comb["head_has_exception"]}


def blank(fields) -> dict[str, int]:
    return {name: 0 for name in fields}


def blank_redirect() -> dict:
    return {"valid": 0, "level": 0, "flag": 0, "value": 0, "former": 0}


def random_pipe_in(rng: random.Random, **overrides) -> dict:
    values = {name: rng.randrange(1 << width) for name, width in PIPE_IN_FIELDS.items()}
    values.update(overrides)
    return values


def random_concat(rng: random.Random, **overrides) -> dict:
    values = {name: rng.randrange(1 << PIPE_IN_FIELDS[name])
              for name in CONCAT_FIELDS}
    values.update(overrides)
    return values
