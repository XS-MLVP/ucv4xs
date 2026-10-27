"""Semantic functional coverage for StdExeUnit."""
from __future__ import annotations

from toffee import Bin, CoverGroupDef, CoverPointDef

STD_CASES = (
    "valid.scalar_store_writes_back_to_rob",
    "valid.scalar_store_writes_sq_data",
    "valid.illegal_issue_blocks_rob_writeback",
    "valid.amo_goes_to_atomic_port_not_rob",
    "valid.amo_does_not_write_sq_data",
    "valid.no_rob_writeback_when_vector_std_wins",
    "valid.vstd_writes_sq_data_with_vector_payload",
    "valid.vstd_blocks_scalar_ready",
    "valid.vstd_does_not_write_rob",
    "valid.vstd_does_not_issue_atomic",
    "valid.idle_quiet",
    "rob.robidx_fields_pass_through",
    "sq.window_start_and_end",
    "sq.window_wrap_with_flag",
    "sq.flag_mismatch_is_illegal",
    "sq.vector_payload_uses_full_128_bits",
    "sq.scalar_payload_zero_extended_high_half",
    "feedback.valid_is_one_cycle_delayed",
    "feedback.hit_true_for_legal_scalar",
    "feedback.hit_false_for_illegal_scalar",
    "feedback.hit_true_for_amo",
    "feedback.hit_holds_when_invalid",
)
GROUP = CoverGroupDef(
    "std_case",
    (CoverPointDef("case", {name: Bin.values(name) for name in STD_CASES},
                   description="StdExeUnit 的可读语义情形：标量/向量写回与 SQ 数据、AMO 分流、"
                               "SQ 窗口合法性、载荷拼接与反馈寄存。"),),
    description="StdExeUnit 语义情形清单。",
)


class StdExeUnitCoverage:
    def __init__(self) -> None:
        self.cases = GROUP.instantiate("std_exe_unit.case")

    def sample_case(self, name: str) -> None:
        if name not in STD_CASES:
            raise KeyError(f"undeclared StdExeUnit cover case: {name}")
        self.cases.sample({"case": name}, details=False)

    def observe(self, **_) -> None:
        """Every bin is an explicitly asserted case."""
