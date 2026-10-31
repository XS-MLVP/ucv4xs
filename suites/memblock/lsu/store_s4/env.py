"""Environment and independent model for StoreUnitS4.

Despite the name, the generated S4 contains no state: it forwards the head/tail
merge result to the unaligned-concat consumer. The model is therefore an
identity map, but the test still checks every field and the valid bit so the
absence of store address/data side effects is explicit.

Contract: docs/contracts/store-s4.md
"""
from __future__ import annotations

import random

FIELDS = {
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


class StoreS4Env:
    def __init__(self, dut, coverage=None) -> None:
        self.dut = dut
        self.coverage = coverage
        self.in_valid = dut.io_pipeIn_valid
        self.in_bits = {name: getattr(dut, f"io_pipeIn_bits_{name}") for name in FIELDS}
        self.out_valid = dut.io_unalignConcat_valid
        self.out = {name: getattr(dut, f"io_unalignConcat_bits_{name}")
                    for name in FIELDS}
        self.vectors = 0

    def drive(self, in_valid: int, in_bits: dict) -> None:
        self.in_valid.Set(1 if in_valid else 0)
        for name, signal in self.in_bits.items():
            signal.Set(int(in_bits.get(name, 0)))

    def check(self, in_valid: int, in_bits: dict, context: str = "vector") -> dict:
        got_valid = int(self.out_valid.value)
        want_valid = 1 if in_valid else 0
        if got_valid != want_valid:
            raise AssertionError(f"{context}: valid {got_valid} != {want_valid}")
        got = {}
        for name, signal in self.out.items():
            got[name] = int(signal.value)
            if got_valid and got[name] != int(in_bits.get(name, 0)):
                raise AssertionError(
                    f"{context}: {name} {got[name]:#x} != {int(in_bits[name]):#x}")
        self.vectors += 1
        if self.coverage is not None:
            self.coverage.observe(in_valid=in_valid, out=got)
        return got

    def evaluate(self, in_valid: int, in_bits: dict, context: str = "vector") -> dict:
        self.drive(in_valid, in_bits)
        self.dut.Step(1)
        return self.check(in_valid, in_bits, context)


def random_payload(rng: random.Random) -> dict[str, int]:
    return {name: rng.randrange(1 << width) for name, width in FIELDS.items()}
