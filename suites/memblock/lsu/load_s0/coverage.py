"""Semantic functional coverage for LoadUnitS0."""
from __future__ import annotations

from toffee import Bin, CoverGroupDef, CoverPointDef

CASES = (
    "lane.unalign_tail_passthrough",
    "lane.entrance_codes",
    "lane.scalar_address_and_mask",
    "lane.scalar_prefetch_i",
    "lane.scalar_prefetch_r",
    "order.replay_hi",
    "order.replay_lo_when_older",
    "order.younger_replay_dropped",
    "order.replay_without_ldin_is_lo",
    "arb.all_lanes_priority",
    "arb.backpressure_ready_bitmap",
    "align.scalar_each_size",
    "align.misaligned_detected",
    "align.prefetch_skips_check",
    "align.tail_forces_unalign",
    "crossbank.unalign_head_and_wakeup_suppressed",
    "is128.crosses_8b_half",
    "is128.tail_is_always_128",
    "tlb.request_fields",
    "tlb.excludes_fast_replay",
    "tlb.checkfullva_only_first_issue",
    "tlb.hyperinst_hlvx",
    "dcache.prefetch_i_suppressed",
    "dcache.uncache_replay_suppressed",
    "dcache.normal_request",
    "fwd.sqsb_always",
    "fwd.uncache_only_hi_priority",
    "fwd.mshr_tld_forward_dchannel",
    "fwd.nc_vs_mmio",
    "wakeup.scalar_issue",
    "wakeup.suppressed_by_crossbank",
    "wakeup.source_priority",
    "reg.hold_when_empty",
    "reg.no_flush_path",
    "perf.two_cycle_counters",
)
GROUP = CoverGroupDef(
    "ls0_case",
    (CoverPointDef("case", {name: Bin.values(name) for name in CASES},
                   description="LoadUnitS0 的可读语义情形：四 lane 合成、hi/lo replay 年龄序、"
                               "五路仲裁、对齐/跨 16B/128 位、TLB 与 DCache 请求语义、"
                               "forward/bypass、wakeup、单深度输出寄存器与 perf 计数。"),),
    description="LoadUnitS0 语义情形清单。",
)


class LoadS0Coverage:
    def __init__(self) -> None:
        self.cases = GROUP.instantiate("load_s0.case")

    def sample_case(self, name: str) -> None:
        if name not in CASES:
            raise KeyError(f"undeclared LoadUnitS0 cover case: {name}")
        self.cases.sample({"case": name}, details=False)

    def observe(self, **_) -> None:
        """Every bin is an explicitly asserted case."""
