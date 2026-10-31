"""Semantic functional coverage for LoadUnitS3."""
from __future__ import annotations

from toffee import Bin, CoverGroupDef, CoverPointDef

CASES = (
    "kill.current_redirect",
    "cancel.head_cancelled_by_tail",
    "cancel.no_tail_no_cancel",
    "concat.head_always_writeback",
    "concat.writeback_depends_on_tail",
    "concat.tail_exception_replaces_head",
    "concat.tail_only_uses_tail_payload",
    "exc.s3_exception_from_any_bit",
    "exc.trigger_breakpoint",
    "wb.scalar_writeback",
    "wb.vector_writeback",
    "wb.suppressed_by_mismatch",
    "rfw.int_rf_write_on_wakeup",
    "rfw.fp_rf_write_on_wakeup",
    "rfw.v0_rf_write_on_wakeup",
    "rfw.vec_wakeup",
    "rfw.no_write_without_wakeup",
    "lq.write_valid_normal",
    "lq.suppressed_by_accepted_fast_replay",
    "lq.nc_from_replay",
    "lq.mem_back_type",
    "lq.is_vec_and_aligned_type",
    "lq.is_load_replay_entrance",
    "lq.rep_info_cause_one_hot",
    "lq.rep_info_last_beat",
    "lq.rep_info_tlb_hint",
    "lq.rep_info_mshr",
    "lq.special_mode_eligible",
    "lq.rep_from_unalign_head",
    "replay.fast_replay_valid",
    "replay.rr_grant_required",
    "replay.revoke_last_cycle",
    "replay.revoke_last_last_cycle",
    "rollback.rar_violation",
    "rollback.match_invalid",
    "rollback.level_follows_match_invalid",
    "excinfo.scalar_only_and_not_mmio",
    "excinfo.payload_fields",
    "cancel.output_when_misaligned_and_no_wakeup",
    "reg.payload_holds",
)
GROUP = CoverGroupDef(
    "ls3_case",
    (CoverPointDef("case", {name: Bin.values(name) for name in CASES},
                   description="LoadUnitS3 的可读语义情形：redirect kill、head/tail 取消与合并、"
                               "写回/唤醒、RF 写、LQ 写入与 replay 记录、fast replay/revoke、"
                               "rollback、exceptionInfo 与输出寄存器。"),),
    description="LoadUnitS3 语义情形清单。",
)


class LoadS3Coverage:
    def __init__(self) -> None:
        self.cases = GROUP.instantiate("load_s3.case")

    def sample_case(self, name: str) -> None:
        if name not in CASES:
            raise KeyError(f"undeclared LoadUnitS3 cover case: {name}")
        self.cases.sample({"case": name}, details=False)

    def observe(self, **_) -> None:
        """Every bin is an explicitly asserted case."""
