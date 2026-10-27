"""Deterministic MicroRAS stage vectors."""

from __future__ import annotations

from dataclasses import dataclass

from bpuverify.uras.transaction.types import UrasCycle


MAIN_TOP = 0x4000_3456


@dataclass(frozen=True, slots=True)
class CallVector:
    start_pc: int
    position: int


CALL_A = CallVector(0x4000_0802, 3)
CALL_B = CallVector(0x4000_1000, 11)
BOUNDARIES = (
    CallVector(0x0000_0000, 0),
    CallVector(0x7FFF_FFFF, 15),
)


def pending_s3_pop_cycles() -> tuple[UrasCycle, ...]:
    """Advance a RETURN to S3, then observe both neutral S1 and S2 paths."""

    return (
        UrasCycle(s1_fire=1, full_ret_addr=MAIN_TOP),
        UrasCycle(s1_fire=1, spec_action=1, full_ret_addr=MAIN_TOP),
        UrasCycle(s2_fire=1, full_ret_addr=MAIN_TOP),
        UrasCycle(s1_fire=1, full_ret_addr=MAIN_TOP),
        UrasCycle(s2_valid=1, full_ret_addr=MAIN_TOP),
        UrasCycle(s3_fire=1, full_ret_addr=MAIN_TOP),
        UrasCycle(s1_fire=1, full_ret_addr=MAIN_TOP),
        UrasCycle(),
    )


def younger_s2_push_cycles() -> tuple[UrasCycle, ...]:
    """Place a CALL in S2 above an older pending S3 RETURN."""

    return (
        UrasCycle(s1_fire=1, spec_action=1, full_ret_addr=MAIN_TOP),
        UrasCycle(s2_fire=1, full_ret_addr=MAIN_TOP),
        UrasCycle(
            s1_fire=1,
            spec_start_pc=CALL_B.start_pc,
            spec_position=CALL_B.position,
            spec_action=2,
            full_ret_addr=MAIN_TOP,
        ),
        UrasCycle(s1_fire=1, full_ret_addr=MAIN_TOP),
        UrasCycle(s1_fire=1, full_ret_addr=MAIN_TOP),
        UrasCycle(s3_fire=1, full_ret_addr=MAIN_TOP),
        UrasCycle(s1_fire=1, full_ret_addr=MAIN_TOP),
        UrasCycle(),
    )
