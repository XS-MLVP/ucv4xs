"""Semantic functional coverage for the integrated NewStoreUnit."""
from __future__ import annotations

from toffee import Bin, CoverGroupDef, CoverPointDef

NSU_CASES = (
    "e2e.stin_issued_and_sq_address_written",
    "e2e.tlb_request_same_cycle",
    "e2e.stin_ready_follows_tail_priority",
    "e2e.nuke_query_same_cycle_as_sq_address",
    "e2e.lfst_update_same_cycle",
    "e2e.feedback_one_cycle_later",
    "e2e.writeback_three_cycles_later",
    "e2e.writeback_payload",
    "e2e.exception_info_sideband",
    "e2e.no_writeback_for_prefetch",
    "e2e.vector_has_no_rob_writeback",
    "e2e.redirect_drops_beat_at_every_stage",
    "e2e.mmio_needs_exception_to_write_back",
    "e2e.normal_store_is_clean",
    "e2e.unalign_head_injects_tail_through_s0",
    "e2e.unalign_tail_reaches_sq_address",
    "e2e.cross_page_tail_requests_unalign_queue",
    "e2e.tlb_miss_sets_tlb_miss_and_replay",
    "e2e.illegal_issue_forces_replay",
    "e2e.trigger_breakpoint_reaches_exception_info",
    "e2e.back_to_back_stores_stay_ordered",
    "e2e.idle_pipeline_is_quiet",
)
GROUP = CoverGroupDef(
    "nsu_case",
    (CoverPointDef("case", {name: Bin.values(name) for name in NSU_CASES},
                   description="集成 NewStoreUnit 的端到端语义：同拍 S1 输出、反馈与写回延迟、"
                               "head/tail 环回、异常与 trigger 贯通、背靠背有序、空流水静默。"),),
    description="NewStoreUnit 集成语义情形清单。",
)


class NewStoreUnitCoverage:
    def __init__(self) -> None:
        self.cases = GROUP.instantiate("new_store_unit.case")

    def sample_case(self, name: str) -> None:
        if name not in NSU_CASES:
            raise KeyError(f"undeclared NewStoreUnit cover case: {name}")
        self.cases.sample({"case": name}, details=False)

    def observe(self, **_) -> None:
        """Every bin is an explicitly asserted case."""
