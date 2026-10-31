"""Semantic functional coverage for StoreUnitS1 (store address stage 1).

Each bin is an explicitly asserted behaviour from ``docs/contracts/store-s1.md``.
"""
from __future__ import annotations

from toffee import Bin, CoverGroupDef, CoverPointDef

S1_CASES = (
    # Pipeline and kill.
    "pipe.idle",
    "pipe.reset_clears_valid",
    "pipe.normal_beat_registers",
    "pipe.field_fidelity",
    "kill.redirect_same_slot",
    "kill.redirect_after_slot",
    "kill.redirect_younger_survives",
    "kill.redirect_invalid_survives",
    "kill.redirect_former_ordering",
    "kill.illegal_issue",
    "kill.illegal_issue_without_redirect",
    "kill.young_cross_head",
    "kill.young_cross_head_not_needed_when_addr_ready",
    "kill.tlb_req_kill_follows_kill",
    # TLB response handling.
    "tlb.hit",
    "tlb.miss",
    "tlb.no_response",
    "tlb.pbmt_zeroed_on_miss",
    # Exceptions.
    "exc.pf_from_either_field",
    "exc.af_from_either_field",
    "exc.gpf_from_either_field",
    "exc.breakpoint_from_trigger_action_zero",
    "exc.debug_mode_from_trigger_action_one",
    "exc.no_exception",
    "exc.exceptions_require_tlb_hit",
    # SQ address write.
    "sqaddr.base_fields",
    "sqaddr.cbo_aligns_vaddr_and_paddr",
    "sqaddr.cbo_forces_size_qb_and_wline",
    "sqaddr.tlb_miss_flag",
    "sqaddr.unalign_flag",
    "sqaddr.cross16_from_entrance_or_head",
    "sqaddr.last_request_from_head",
    "sqaddr.suppressed_for_prefetch",
    # STA nuke query.
    "nuke.issued_on_fire_and_tlb_hit",
    "nuke.suppressed_without_tlb_hit",
    "nuke.suppressed_for_prefetch",
    "nuke.match_type_cacheline_for_cbo",
    "nuke.match_type_word_for_normal",
    # Unaligned tail.
    "tail.injected_on_head",
    "tail.next_16b_address",
    "tail.fullva_from_tlb_response",
    "tail.mask_high_half",
    "tail.not_injected_without_head",
    # Unaligned queue.
    "queue.requires_tail_entrance_and_cross_page",
    "queue.requires_both_tlb_hits",
    "queue.requires_ready",
    "queue.not_for_scalar_only",
    # RS feedback.
    "feedback.scalar_fire_without_head",
    "feedback.hit_equals_tlb_hit",
    "feedback.tail_requires_both_hits",
    "feedback.tail_cross_page_requires_queue_ready",
    "feedback.force_replay_on_illegal_issue",
    "feedback.force_replay_on_young_cross_head",
    "feedback.need_rs_replay_bit",
    "feedback.not_for_vector",
    "feedback.not_for_head_beat",
    # LFST.
    "lfst.updated_for_scalar_cacheable",
    "lfst.not_for_prefetch",
    "lfst.not_for_tail",
    "lfst.requires_tlb_hit",
    # Trigger wiring.
    "trigger.vector_stride_detection",
    "trigger.cbo_mode",
    "trigger.trigger_goes_to_pipe_out",
)

GROUP_DEFINITION = CoverGroupDef(
    "s1_case",
    (
        CoverPointDef(
            "case",
            {name: Bin.values(name) for name in S1_CASES},
            description="StoreUnitS1 的可读语义情形：kill 组合、TLB 响应、异常、SQ 地址写、"
                        "STA nuke 查询、非对齐尾段与队列、RS 反馈、LFST 与 trigger 接线。",
        ),
    ),
    description="StoreUnitS1 语义情形清单。",
)


class StoreS1Coverage:
    def __init__(self) -> None:
        self.cases = GROUP_DEFINITION.instantiate("store_s1.case")

    def sample_case(self, name: str) -> None:
        if name not in S1_CASES:
            raise KeyError(f"undeclared StoreUnitS1 cover case: {name}")
        self.cases.sample({"case": name}, details=False)

    def observe(self, **_) -> None:
        """Every bin is an explicitly asserted case; no automatic sampling."""
