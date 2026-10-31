"""Generic environment for a purely combinational identity module.

Several generated LSU leaves are nothing but a bundle of continuous assigns
(``StoreUnitS4``, ``LoadUnitS4``). They still deserve a UT: the point is to prove
that *no* field is delayed, renamed, gated or dropped, which the head/tail merge
downstream depends on. This helper keeps that check in one place.
"""
from __future__ import annotations

import random


class PassthroughEnv:
    def __init__(self, dut, fields: dict[str, int], prefix_in: str,
                 prefix_out: str, coverage=None) -> None:
        self.dut = dut
        self.coverage = coverage
        self.fields = dict(fields)
        self.in_valid = getattr(dut, f"{prefix_in}_valid")
        self.in_bits = {name: getattr(dut, f"{prefix_in}_bits_{name}") for name in fields}
        self.out_valid = getattr(dut, f"{prefix_out}_valid")
        self.out_bits = {name: getattr(dut, f"{prefix_out}_bits_{name}") for name in fields}
        self.vectors = 0

    def drive(self, valid: int, payload: dict[str, int]) -> None:
        self.in_valid.Set(1 if valid else 0)
        for name, signal in self.in_bits.items():
            signal.Set(int(payload.get(name, 0)))

    def check(self, valid: int, payload: dict[str, int], context: str = "vector") -> dict:
        got_valid = int(self.out_valid.value)
        if got_valid != (1 if valid else 0):
            raise AssertionError(
                f"{context}: valid {got_valid} != {1 if valid else 0}")
        got = {}
        for name, signal in self.out_bits.items():
            got[name] = int(signal.value)
            if got_valid and got[name] != int(payload.get(name, 0)):
                raise AssertionError(
                    f"{context}: {name} {got[name]:#x} != {int(payload[name]):#x}")
        self.vectors += 1
        if self.coverage is not None:
            self.coverage.observe(valid=got_valid, out=got)
        return got

    def evaluate(self, valid: int, payload: dict[str, int],
                 context: str = "vector") -> dict:
        self.drive(valid, payload)
        self.dut.Step(1)
        return self.check(valid, payload, context)


def random_payload(rng: random.Random, fields: dict[str, int]) -> dict[str, int]:
    return {name: rng.randrange(1 << width) for name, width in fields.items()}


def blank(fields: dict[str, int]) -> dict[str, int]:
    return {name: 0 for name in fields}
