"""Semantic functional coverage for StoreUnitS0 (store address stage 0).

Each bin is an explicitly asserted behaviour from ``docs/contracts/store-s0.md``.
"""
from __future__ import annotations

from toffee import Bin, CoverGroupDef, CoverPointDef

S0_CASES = (
    # Request-source arbitration and the fixed-latency pipeline.
    "pipe.idle_outputs_invalid",
    "pipe.scalar_is_accepted_and_registered",
    "pipe.one_cycle_latency",
    "pipe.field_fidelity",
    "pipe.reset_clears_valid",
    "arb.tail_has_priority",
    "arb.tail_blocks_stin_ready",
    "arb.scalar_ready_when_no_tail",
    "arb.tail_without_stin",
    # TLB request (combinational, not gated by kill).
    "tlb.issued_for_scalar",
    "tlb.issued_for_tail",
    "tlb.not_issued_when_idle",
    "tlb.checkfullva_from_instr_type",
    "tlb.cmd_distinguishes_cbo_zero",
    "tlb.hyperinst_from_fuoptype",
    "tlb.is_prefetch_bit",
    "tlb.issued_even_when_killed",
    # Scalar field synthesis.
    "scalar.vaddr_and_fullva_sign_extend",
    "scalar.vaddr_wraps_to_50_bits",
    "scalar.size_from_fuoptype",
    "scalar.mask_byte_offset",
    "scalar.mask_cbo_full_line",
    "scalar.mask_shifts_by_16b_offset",
    # Redirect kill.
    "kill.same_slot_flush",
    "kill.flush_after_older",
    "kill.younger_target_survives",
    "kill.invalid_redirect_survives",
    "kill.former_ordering",
    "kill.wrap_flag_ordering",
    # Illegal issue.
    "illegal.sqidx_inside_window_legal",
    "illegal.sqidx_at_window_end_illegal",
    "illegal.sqidx_before_deq_illegal",
    "illegal.wrap_window",
    # Derived qualifiers.
    "align.scalar_aligned_by_size",
    "align.scalar_misaligned",
    "align.cbo_forced_aligned",
    "align.prefetch_forced_aligned",
    "align.tail_forced_unaligned",
    "unalignhead.scalar_crosses_16b",
    "unalignhead.scalar_within_16b",
    "unalignhead.tail_suppressed",
    "cross4k.scalar_crosses_page",
    "cross4k.scalar_within_page",
    "cross4k.tail_inherits_from_input",
    "cross4k.cbo_never_crosses_page",
    "addrready.match",
    "addrready.no_match",
)

GROUP_DEFINITION = CoverGroupDef(
    "s0_case",
    (
        CoverPointDef(
            "case",
            {name: Bin.values(name) for name in S0_CASES},
            description="StoreUnitS0 的可读语义情形：仲裁与固定延迟、TLB 请求、标量字段合成、"
                        "redirect kill、非法发射、对齐/跨 16B/跨页/地址就绪。",
        ),
    ),
    description="StoreUnitS0 语义情形清单。",
)


class StoreS0Coverage:
    def __init__(self) -> None:
        self.cases = GROUP_DEFINITION.instantiate("store_s0.case")

    def sample_case(self, name: str) -> None:
        if name not in S0_CASES:
            raise KeyError(f"undeclared StoreUnitS0 cover case: {name}")
        self.cases.sample({"case": name}, details=False)

    def observe(self, **_) -> None:
        """Every bin is an explicitly asserted case; no automatic sampling."""
