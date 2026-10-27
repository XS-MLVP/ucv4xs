"""Port-level environment and independent reference for Arbiter3_StoreStageIO.

The reference is a two-source fixed-priority selector plus an explicit table of
documented bubble defaults. It never reuses the RTL ternaries: selection is
expressed as "pick the first valid source, else bubble", and every payload
field is looked up from that decision.

Contract: docs/contracts/store-arbiter.md
"""
from __future__ import annotations

import random

# One-hot StoreEntrance encodings (package.scala:190-210).
ENTRANCE_UNALIGN_TAIL = 0x1
ENTRANCE_PREFETCH = 0x2
ENTRANCE_SCALAR_ISSUE = 0x8

INSTR_TYPE_PREFETCH = 4
INSTR_TYPE_SCALAR = 1
SIZE_QB = 4
MASK_FULL = 0xFFFF

# Fields present on the unalign-tail source (in_0).
IN0_FIELDS = {
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
}

# Fields only present on the scalar source (in_1).
IN1_EXTRA_FIELDS = {
    "ssid": 6,
    "storeSetHit": 1,
}

IN1_FIELDS = dict(IN0_FIELDS)
IN1_FIELDS.pop("accessType_instrType", None)
IN1_FIELDS.pop("uop_exceptionVec_19", None)
IN1_FIELDS.update(IN1_EXTRA_FIELDS)

OUT_FIELDS = dict(IN1_FIELDS)
OUT_FIELDS["accessType_instrType"] = 3
OUT_FIELDS["uop_exceptionVec_19"] = 1

# Fields that the generated RTL gates with the source's own valid bit.
VALID_GATED = (
    "accessType_isCbo",
    "accessType_isCboNoZero",
    "uop_isRVC",
    "uop_ftqPtr_flag",
    "uop_robIdx_flag",
    "uop_robIdx_isFormer",
    "uop_sqIdx_first_flag",
    "uop_sqIdx_second_flag",
    "storeSetHit",
)

BUBBLE = {
    "entrance": ENTRANCE_PREFETCH,
    "accessType_instrType": INSTR_TYPE_PREFETCH,
    "accessType_isCbo": 0,
    "accessType_isCboNoZero": 0,
    "uop_exceptionVec_19": 0,
    "uop_isRVC": 0,
    "uop_ftqPtr_flag": 0,
    "uop_ftqPtr_value": 0,
    "uop_ftqOffset": 0,
    "uop_fuOpType": 0,
    "uop_robIdx_flag": 0,
    "uop_robIdx_value": 0,
    "uop_robIdx_isFormer": 0,
    "uop_sqIdx_first_flag": 0,
    "uop_sqIdx_second_flag": 0,
    "uop_sqIdx_value": 0,
    "vaddr": 0,
    "fullva": 0,
    "size": SIZE_QB,
    "mask": MASK_FULL,
    "ssid": 0,
    "storeSetHit": 0,
}


def reference(in0_valid: bool, in0: dict, in1_valid: bool, in1: dict) -> dict:
    """Independent priority model: unalign tail wins, else scalar, else bubble."""
    if in0_valid:
        want = {name: in0[name] for name in IN0_FIELDS}
        want["entrance"] = ENTRANCE_UNALIGN_TAIL
        # Fields absent on source 0 are structurally zero on the output.
        want["ssid"] = 0
        want["storeSetHit"] = 0
        return want
    if in1_valid:
        want = {name: in1[name] for name in IN1_FIELDS}
        want["entrance"] = ENTRANCE_SCALAR_ISSUE
        want["accessType_instrType"] = INSTR_TYPE_SCALAR
        # exceptionVec[19] has no scalar-source port at this boundary.
        want["uop_exceptionVec_19"] = 0
        return want
    return dict(BUBBLE)


class StoreArbiterEnv:
    def __init__(self, dut, coverage=None) -> None:
        self.dut = dut
        self.coverage = coverage
        self.in0_valid = dut.io_in_0_valid
        self.in1_valid = dut.io_in_1_valid
        self.in1_ready = dut.io_in_1_ready
        self.out_valid = dut.io_out_valid
        self.out_entrance = dut.io_out_bits_entrance
        self.in0 = {name: getattr(dut, f"io_in_0_bits_{name}") for name in IN0_FIELDS}
        self.in1 = {name: getattr(dut, f"io_in_1_bits_{name}") for name in IN1_FIELDS}
        self.out = {name: getattr(dut, f"io_out_bits_{name}") for name in OUT_FIELDS}
        self.out["entrance"] = self.out_entrance
        self.vectors = 0

    # ------------------------------------------------------------------ drive
    def drive(self, in0_valid: bool, in0: dict | None = None,
              in1_valid: bool = False, in1: dict | None = None) -> None:
        self.in0_valid.Set(1 if in0_valid else 0)
        self.in1_valid.Set(1 if in1_valid else 0)
        for name, signal in self.in0.items():
            signal.Set((in0 or {}).get(name, 0))
        for name, signal in self.in1.items():
            signal.Set((in1 or {}).get(name, 0))

    def eval(self) -> None:
        """Pure combinational DUT: one evaluation settles the outputs."""
        self.dut.Step(1)

    # ------------------------------------------------------------------ check
    def check(self, context: str) -> dict:
        in0_valid = int(self.in0_valid.value)
        in1_valid = int(self.in1_valid.value)
        in0 = {name: int(signal.value) for name, signal in self.in0.items()}
        in1 = {name: int(signal.value) for name, signal in self.in1.items()}
        want = reference(bool(in0_valid), in0, bool(in1_valid), in1)

        got_valid = int(self.out_valid.value)
        want_valid = in0_valid or in1_valid
        if got_valid != want_valid:
            raise AssertionError(f"{context}: out.valid {got_valid} != {want_valid}")
        got_ready = int(self.in1_ready.value)
        want_ready = 0 if in0_valid else 1
        if got_ready != want_ready:
            raise AssertionError(
                f"{context}: in_1.ready {got_ready} != {want_ready} "
                f"(in_0_valid={in0_valid})")
        for name, signal in self.out.items():
            got = int(signal.value)
            if got != want[name]:
                raise AssertionError(
                    f"{context}: out.{name} {got:#x} != {want[name]:#x} "
                    f"(in0_valid={in0_valid} in1_valid={in1_valid})")
        self.vectors += 1
        if self.coverage is not None:
            self.coverage.sample(
                in0_valid=in0_valid,
                in1_valid=in1_valid,
                entrance=int(self.out_entrance.value),
                in0=in0,
                in1=in1,
                ready=got_ready,
            )
        return {"valid": got_valid, "ready": got_ready,
                "entrance": int(self.out_entrance.value)}


def random_payload(rng: random.Random, fields: dict[str, int]) -> dict[str, int]:
    return {name: rng.randrange(1 << width) for name, width in fields.items()}
