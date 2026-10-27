"""Environment and independent reference for DelayPipeline (store S3 writeback).

The model keeps ``(reg_valid, reg_bits)`` and applies, once per clock:

    prevFire   = in.valid and not needFlush(in.robIdx)
    next_valid = prevFire
    next_bits  = in.bits if prevFire else reg_bits

``next_valid = prevFire`` is not a simplification: ``io_out_ready`` is tied
high in the parent and was constant-propagated away (the generated DUT has no
ready port), so a registered beat is consumed in the very cycle it appears and
never persists. The RTL's additional ``curKill`` term on the registered beat is
therefore unobservable at this boundary; ``OutputKillProbe`` below measures
that equivalence instead of pretending to check it.

The ``needFlush`` predicate is written from the RobPtr relation, not from the
RTL bit expression.

Contract: docs/contracts/store-delay.md
"""
from __future__ import annotations

import random

from lsuverify.common.robptr import (  # noqa: E402
    LEVEL_FLUSH,
    LEVEL_FLUSH_AFTER,
    is_after_slot,
    is_same_entry,
    is_same_slot,
    rob_need_flush as need_flush,
)

PAYLOAD_FIELDS = {
    "accessType_instrType": 3,
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
    "tlbException_vaNeedExt": 1,
    "tlbException_isHyper": 1,
    "isForVSnonLeafPTE": 1,
    "gpaddr": 64,
    "nc": 1,
    "mmio": 1,
    "memBackTypeMM": 1,
}




class DelayReference:
    def __init__(self) -> None:
        self.valid = 0
        self.bits = {name: 0 for name in PAYLOAD_FIELDS}

    def push(self, in_valid: int, in_bits: dict[str, int], redirect: dict) -> None:
        prev_fire = bool(in_valid) and not need_flush(
            in_bits["uop_robIdx_flag"], in_bits["uop_robIdx_value"],
            in_bits["uop_robIdx_isFormer"], redirect)
        if prev_fire:
            self.bits = {name: in_bits[name] for name in PAYLOAD_FIELDS}
        self.valid = 1 if prev_fire else 0

    def snapshot(self) -> dict:
        return dict(valid=self.valid, bits=dict(self.bits))


def make_bits(rng: random.Random | None = None, **overrides) -> dict[str, int]:
    bits = {}
    for name, width in PAYLOAD_FIELDS.items():
        bits[name] = rng.randrange(1 << width) if rng is not None else 0
    bits.update(overrides)
    return bits


class StoreDelayEnv:
    def __init__(self, dut, coverage=None) -> None:
        self.dut = dut
        self.coverage = coverage
        self.in_valid = dut.io_in_valid
        self.in_bits = {name: getattr(dut, f"io_in_bits_{name}") for name in PAYLOAD_FIELDS}
        self.out_valid = dut.io_out_valid
        self.out_bits = {name: getattr(dut, f"io_out_bits_{name}") for name in PAYLOAD_FIELDS}
        self.redirect_valid = dut.io_redirect_valid
        self.redirect_level = dut.io_redirect_bits_level
        self.redirect_flag = dut.io_redirect_bits_robIdx_flag
        self.redirect_value = dut.io_redirect_bits_robIdx_value
        self.redirect_former = dut.io_redirect_bits_robIdx_isFormer
        self.model = DelayReference()
        self.cycles = 0

    # ------------------------------------------------------------------ reset
    def reset(self, cycles: int = 4) -> None:
        self.dut.reset.Set(1)
        for _ in range(cycles):
            self.dut.Step(1)
        self.dut.reset.Set(0)
        self.model = DelayReference()
        # One settle cycle with no input keeps the model and DUT aligned.
        self.drive(0, {name: 0 for name in PAYLOAD_FIELDS},
                   {"valid": 0, "level": 0, "flag": 0, "value": 0, "former": 0})
        self.dut.Step(1)
        self.model.push(0, {name: 0 for name in PAYLOAD_FIELDS},
                        {"valid": 0, "level": 0, "flag": 0, "value": 0, "former": 0})
        # Leave the DUT and model in the same pre-edge state for cycle 0.
        self.drive(0, {name: 0 for name in PAYLOAD_FIELDS},
                   {"valid": 0, "level": 0, "flag": 0, "value": 0, "former": 0})

    # ------------------------------------------------------------------ drive
    def drive(self, in_valid: int, in_bits: dict[str, int], redirect: dict) -> None:
        self.in_valid.Set(1 if in_valid else 0)
        for name, signal in self.in_bits.items():
            signal.Set(int(in_bits.get(name, 0)))
        self.redirect_valid.Set(1 if redirect["valid"] else 0)
        self.redirect_level.Set(int(redirect["level"]))
        self.redirect_flag.Set(int(redirect["flag"]))
        self.redirect_value.Set(int(redirect["value"]))
        self.redirect_former.Set(int(redirect["former"]))

    # -------------------------------------------------------------- one cycle
    def cycle(self, in_valid: int, in_bits: dict[str, int], redirect: dict,
              context: str = "cycle") -> dict:
        """Sample the outputs of the current cycle, then apply this cycle's inputs.

        The returned dict is the state *before* this cycle's clock edge, so a
        beat driven at T is returned by the call for T+1: the DUT latency is one
        cycle both in the model and in the returned data.
        """
        want = self.model.snapshot()
        got_valid = int(self.out_valid.value)
        got_bits = {name: int(signal.value) for name, signal in self.out_bits.items()}
        if got_valid != want["valid"]:
            raise AssertionError(
                f"{context}: out.valid {got_valid} != {want['valid']} "
                f"(redirect={redirect})")
        # Payload is only meaningful while out.valid is high; the register keeps
        # stale bytes when the beat has been consumed, and the contract declares
        # that don't-care explicitly.
        if want["valid"]:
            for name, got in got_bits.items():
                if got != want["bits"][name]:
                    raise AssertionError(
                        f"{context}: out.{name} {got:#x} != {want['bits'][name]:#x}")
        self.coverage and self.coverage.observe(
            out_valid=got_valid, in_valid=int(in_valid), redirect=redirect,
            in_bits=in_bits, out_bits=got_bits)
        self.drive(in_valid, in_bits, redirect)
        self.dut.Step(1)
        self.model.push(in_valid, in_bits, redirect)
        self.cycles += 1
        return {"valid": got_valid, "bits": got_bits}


def no_redirect() -> dict:
    return {"valid": 0, "level": 0, "flag": 0, "value": 0, "former": 0}


def redirect(flag=0, value=0, former=1, level=LEVEL_FLUSH, valid=1) -> dict:
    return {"valid": valid, "level": level, "flag": flag, "value": value,
            "former": former}
