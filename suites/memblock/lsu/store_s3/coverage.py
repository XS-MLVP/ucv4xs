"""Semantic functional coverage for StoreUnitS3."""
from __future__ import annotations

from toffee import Bin, CoverGroupDef, CoverPointDef

S3_CASES = (
    "pipeout.only_head_beats",
    "pipeout.head_registers_one_cycle",
    "pipeout.tail_suppressed",
    "pipeout.killed_by_redirect",
    "pipeout.field_fidelity",
    "pipeout.reset_clears_valid",
    "delay.normal_store_written_back",
    "delay.one_cycle_latency",
    "delay.mmio_suppressed_without_exception",
    "delay.mmio_allowed_with_exception",
    "delay.cbo_suppressed_without_exception",
    "delay.prefetch_suppressed",
    "delay.head_suppressed",
    "delay.replay_suppressed",
    "delay.killed_by_redirect",
    "delay.vector_produces_no_writeback",
    "mix.exception_payload_from_concat_when_head_has_exception",
    "mix.normal_payload_from_pipe_when_head_is_clean",
    "mix.control_fields_stay_from_pipe",
    "stout.debug_is_mmio",
    "stout.debug_is_ncio",
    "stout.debug_is_ncio_requires_not_mem_back_mm",
    "exc.gpaddr_truncated_to_50_bits",
    "exc.vaddr_is_fullva",
    "exc.sideband_fields",
    "exc.valid_matches_stout",
)
GROUP = CoverGroupDef(
    "s3_case",
    (CoverPointDef("case", {name: Bin.values(name) for name in S3_CASES},
                   description="StoreUnitS3 的可读语义情形：head-only pipeOut、写回延迟管线的"
                               "过滤条件、head/tail 混合载荷、stout 调试位与 exceptionInfo 侧带。"),),
    description="StoreUnitS3 语义情形清单。",
)


class StoreS3Coverage:
    def __init__(self) -> None:
        self.cases = GROUP.instantiate("store_s3.case")

    def sample_case(self, name: str) -> None:
        if name not in S3_CASES:
            raise KeyError(f"undeclared StoreUnitS3 cover case: {name}")
        self.cases.sample({"case": name}, details=False)

    def observe(self, **_) -> None:
        """Every bin is an explicitly asserted case."""
