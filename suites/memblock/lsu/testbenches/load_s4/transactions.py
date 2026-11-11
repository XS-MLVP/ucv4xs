"""LoadUnitS4 pass-through transaction and observation types.

``LoadUnitS4`` is a combinational head/tail merge payload: every contract
field, including each replay-cause bit, must arrive at ``unalignConcat``
unchanged.  Tests build an immutable :class:`S4HeadPayload` and compare the
monitor result with :class:`S4Observation`; no generated port name appears in
the test.

Contract: ``docs/spec/design/contracts/load-s4.md`` §2.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import random

# Widths and order come from the LoadUnitS4 payload contract.  This is a
# transaction schema, not a port map: the environment owns the RTL binding.
PAYLOAD_FIELDS = {
    "entrance": 8,
    "uop_exceptionVec_23": 1,
    "uop_exceptionVec_21": 1,
    "uop_exceptionVec_19": 1,
    "uop_exceptionVec_15": 1,
    "uop_exceptionVec_13": 1,
    "uop_exceptionVec_7": 1,
    "uop_exceptionVec_6": 1,
    "uop_exceptionVec_5": 1,
    "uop_exceptionVec_4": 1,
    "uop_exceptionVec_3": 1,
    "vaddr": 50,
    "fullva": 64,
    "mask": 16,
    "paddr": 48,
    "tlbException_vaNeedExt": 1,
    "gpaddr": 64,
    "isForVSnonLeafPTE": 1,
    "mshrId": 4,
    "cause_0": 1,
    "cause_1": 1,
    "cause_2": 1,
    "cause_3": 1,
    "cause_4": 1,
    "cause_5": 1,
    "cause_6": 1,
    "cause_8": 1,
    "cause_9": 1,
    "cause_10": 1,
    "cause_11": 1,
    "specialModeRequest": 1,
    "handledByMSHR": 1,
    "tlbId": 4,
    "tlbFull": 1,
    "causeOrR": 1,
    "matchInvalid": 1,
    "shouldWakeup": 1,
    "hasException": 1,
    "headAlwaysWriteback": 1,
    "writebackDependOnTail": 1,
    "shouldRarViolation": 1,
}


def payload_fields() -> tuple:
    """(field, width) pairs in contract order for walking-one coverage."""
    return tuple(PAYLOAD_FIELDS.items())


def payload_field_names() -> tuple:
    return tuple(PAYLOAD_FIELDS)


@dataclass(frozen=True)
class S4HeadPayload:
    entrance: int = 0
    uop_exceptionVec_23: int = 0
    uop_exceptionVec_21: int = 0
    uop_exceptionVec_19: int = 0
    uop_exceptionVec_15: int = 0
    uop_exceptionVec_13: int = 0
    uop_exceptionVec_7: int = 0
    uop_exceptionVec_6: int = 0
    uop_exceptionVec_5: int = 0
    uop_exceptionVec_4: int = 0
    uop_exceptionVec_3: int = 0
    vaddr: int = 0
    fullva: int = 0
    mask: int = 0
    paddr: int = 0
    tlbException_vaNeedExt: int = 0
    gpaddr: int = 0
    isForVSnonLeafPTE: int = 0
    mshrId: int = 0
    cause_0: int = 0
    cause_1: int = 0
    cause_2: int = 0
    cause_3: int = 0
    cause_4: int = 0
    cause_5: int = 0
    cause_6: int = 0
    cause_8: int = 0
    cause_9: int = 0
    cause_10: int = 0
    cause_11: int = 0
    specialModeRequest: int = 0
    handledByMSHR: int = 0
    tlbId: int = 0
    tlbFull: int = 0
    causeOrR: int = 0
    matchInvalid: int = 0
    shouldWakeup: int = 0
    hasException: int = 0
    headAlwaysWriteback: int = 0
    writebackDependOnTail: int = 0
    shouldRarViolation: int = 0

    def __post_init__(self) -> None:
        for name, width in PAYLOAD_FIELDS.items():
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"payload.{name} must be an integer")
            if not 0 <= value < (1 << width):
                raise ValueError(
                    f"payload.{name} does not fit {width} bits: {value!r}")

    def field(self, name: str) -> int:
        if name not in PAYLOAD_FIELDS:
            raise KeyError(f"unknown LoadUnitS4 payload field {name!r}")
        return getattr(self, name)

    def with_field(self, name: str, value: int) -> "S4HeadPayload":
        if name not in PAYLOAD_FIELDS:
            raise KeyError(f"unknown LoadUnitS4 payload field {name!r}")
        return replace(self, **{name: value})

    def values(self) -> dict:
        return {name: getattr(self, name) for name in PAYLOAD_FIELDS}


def blank_payload() -> S4HeadPayload:
    return S4HeadPayload()


def random_payload(rng: random.Random) -> S4HeadPayload:
    return S4HeadPayload(**{
        name: rng.randrange(1 << width) for name, width in PAYLOAD_FIELDS.items()})


@dataclass(frozen=True)
class S4Observation:
    """Observed ``unalignConcat`` beat at the sampling point."""

    valid: int
    payload: S4HeadPayload

    def unequal_fields(self, expected: S4HeadPayload) -> tuple:
        """Field names whose observed value differs from ``expected``."""
        return tuple(name for name in PAYLOAD_FIELDS
                     if getattr(self.payload, name) != getattr(expected, name))
