"""Semantic functional coverage for the integrated NewLoadUnit."""
from __future__ import annotations

from toffee import Bin, CoverGroupDef, CoverPointDef

CASES = (
    "xstage.scalar_load_end_to_end",
    "xstage.aligned_dcache_data",
    "xstage.cross_16b_head_tail_loopback",
    "xstage.tail_data_merge",
    "xstage.dcache_backpressure",
    "xstage.replay_lane_priority",
    "xstage.replay_younger_dropped",
    "xstage.fast_replay_reenters_pipeline",
    "xstage.redirect_kills_pipeline",
    "xstage.tlb_miss_replay",
    "xstage.tlb_fault_exception",
    "xstage.uncache_bypass_read",
    "xstage.vector_load_writes_vector_rf",
    "xstage.trigger_breakpoint_propagates",
    "xstage.rar_violation_rolls_back",
    "xstage.nuke_query_fields",
    "xstage.prefetch_train_pulse",
    "xstage.sw_prefetch_path",
    "xstage.prefetch_hint",
    "xstage.perf_counter_delay",
    "xstage.exception_info_record",
    "xstage.wakeup_and_rf_write",
    "xstage.no_write_on_redirect",
    "xstage.idle_holds_outputs",
    "xstage.lq_write_cause_encoding",
)
GROUP = CoverGroupDef(
    "nlu_case",
    (CoverPointDef("case", {name: Bin.values(name) for name in CASES},
                   description="NewLoadUnit 整体语义情形：一条 load 从 ldin 到 ldout/lqWrite 的跨级时序、"
                               "跨 16B head/tail 环回与数据合并、replay/fast replay 反馈、TLB miss/异常、"
                               "uncache/向量/trigger、nuke/revoke/rollback、预取训练与性能计数。"),),
    description="NewLoadUnit 整体语义情形清单。",
)


class NewLoadUnitCoverage:
    def __init__(self) -> None:
        self.cases = GROUP.instantiate("new_load_unit.case")

    def sample_case(self, name: str) -> None:
        if name not in CASES:
            raise KeyError(f"undeclared NewLoadUnit cover case: {name}")
        self.cases.sample({"case": name}, details=False)

    def observe(self, **_) -> None:
        """Every bin is an explicitly asserted case."""
