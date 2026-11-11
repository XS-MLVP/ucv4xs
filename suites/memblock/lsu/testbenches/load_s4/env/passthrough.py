"""Environment for LoadUnitS4 (a combinational identity pass-through).

Every contract field is checked against the expected transaction payload after
the clock edge, and the observed payload is returned as an immutable
:class:`S4Observation`.  Only this module spells the generated port names.

Contract: docs/spec/design/contracts/load-s4.md
"""
from __future__ import annotations

from suites.memblock.lsu.testbenches.load_s4.transactions import PAYLOAD_FIELDS
from suites.memblock.lsu.testbenches.load_s4.transactions import S4HeadPayload
from suites.memblock.lsu.testbenches.load_s4.transactions import S4Observation


class LoadS4Env:
    """Drive the head beat and check the forwarded merge payload."""

    def __init__(self, dut, coverage=None) -> None:
        self.dut = dut
        self.coverage = coverage
        self.in_valid = dut.io_pipeIn_valid
        self.in_bits = {
            name: getattr(dut, f"io_pipeIn_bits_{name}") for name in PAYLOAD_FIELDS}
        self.out_valid = dut.io_unalignConcat_valid
        self.out_bits = {
            name: getattr(dut, f"io_unalignConcat_bits_{name}")
            for name in PAYLOAD_FIELDS}
        self.vectors = 0

    @staticmethod
    def _flag(valid, context: str) -> int:
        if isinstance(valid, bool):
            return int(valid)
        if not isinstance(valid, int) or valid not in (0, 1):
            raise ValueError(
                f"{context}: valid must be 0 or 1, got {valid!r}")
        return valid

    def drive(self, valid: int, payload: S4HeadPayload) -> None:
        if not isinstance(payload, S4HeadPayload):
            raise TypeError("LoadS4Env.drive expects an S4HeadPayload")
        self.in_valid.Set(self._flag(valid, "LoadS4Env.drive"))
        for name, signal in self.in_bits.items():
            signal.Set(payload.field(name))

    def _observed(self) -> S4HeadPayload:
        return S4HeadPayload(**{name: int(signal.value)
                                for name, signal in self.out_bits.items()})

    def check(self, valid: int, payload: S4HeadPayload,
              context: str = "vector") -> S4Observation:
        if not isinstance(payload, S4HeadPayload):
            raise TypeError("LoadS4Env.check expects an S4HeadPayload")
        expected_valid = self._flag(valid, context)
        got_valid = int(self.out_valid.value)
        if got_valid != expected_valid:
            raise AssertionError(
                f"{context}: valid {got_valid} != {expected_valid}")
        observation = S4Observation(valid=got_valid, payload=self._observed())
        if got_valid:
            mismatched = observation.unequal_fields(payload)
            if mismatched:
                details = ", ".join(
                    f"{name} {observation.payload.field(name):#x} != "
                    f"{payload.field(name):#x}" for name in mismatched)
                raise AssertionError(f"{context}: {details}")
        self.vectors += 1
        if self.coverage is not None:
            self.coverage.observe(valid=got_valid, out=observation.payload)
        return observation

    def evaluate(self, valid: int, payload: S4HeadPayload,
                 context: str = "vector") -> S4Observation:
        self.drive(valid, payload)
        self.dut.Step(1)
        return self.check(valid, payload, context)

    def observe(self) -> S4Observation:
        """Read the current forwarded beat without advancing the clock."""
        return S4Observation(valid=int(self.out_valid.value), payload=self._observed())
