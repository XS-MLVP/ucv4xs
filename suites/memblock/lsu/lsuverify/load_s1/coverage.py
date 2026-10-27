"""Semantic functional coverage for LoadUnitS1."""
from __future__ import annotations

from toffee import Bin, CoverGroupDef, CoverPointDef

CASES = (
    "kill.invalid_input",
    "kill.current_redirect_younger",
    "kill.current_redirect_older_kept",
    "kill.redirect_level_same_entry",
    "kill.same_entry_isformer_order",
    "kill.one_cycle_delayed_redirect",
    "kill.two_cycle_delayed_redirect_tail_only",
    "tlb.hit_merges_paddr_fullva_pbmt",
    "tlb.miss_marks_access_result",
    "tlb.noquery_bypass_paddr",
    "tlb.noquery_without_bypass",
    "tlb.dcache_uses_second_port",
    "tlb.request_kill_and_noquery_paddr",
    "tlb.special_mode_non_head",
    "exception.pf_af_gpf_only_on_hit",
    "exception.breakpoint_from_trigger",
    "trigger.vector_unit_stride",
    "trigger.prefetch_suppresses_trigger",
    "trigger.debug_action_and_slot_chain",
    "dcache.kill_on_miss_or_exception",
    "forward.sq_sbuffer_kill_vs_uncache_kill",
    "datapath.meta_fields",
    "tail.inject_address_and_mask",
    "tail.sixteen_byte_base_mask",
    "tail.emitted_even_when_killed",
    "replay.should_fast_replay",
    "replay.should_fast_replay_suppressed",
    "replay.fast_replay_nuke_first",
    "replay.cause_11_line_match",
    "replay.cause_11_vword_match_and_overlap",
    "replay.cause_11_requires_hit_or_noquery",
    "prefetch.train_hint",
    "prefetch.software_prefetch",
    "reg.payload_captured_on_kill",
    "reg.payload_holds_when_empty",
    "perf.two_cycle_counters",
)
GROUP = CoverGroupDef(
    "ls1_case",
    (CoverPointDef("case", {name: Bin.values(name) for name in CASES},
                   description="LoadUnitS1 的可读语义情形：三级 redirect kill、TLB 合并与 miss/noQuery、"
                               "异常与 trigger、DCache/forward kill 差异、dataPath 元数据、"
                               "unalign tail 注入、fast replay/nuke 判定与输出寄存器。"),),
    description="LoadUnitS1 语义情形清单。",
)


class LoadS1Coverage:
    def __init__(self) -> None:
        self.cases = GROUP.instantiate("load_s1.case")

    def sample_case(self, name: str) -> None:
        if name not in CASES:
            raise KeyError(f"undeclared LoadUnitS1 cover case: {name}")
        self.cases.sample({"case": name}, details=False)

    def observe(self, **_) -> None:
        """Every bin is an explicitly asserted case."""
