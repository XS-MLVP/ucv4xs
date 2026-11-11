"""Semantic functional coverage for StoreUnitS2."""
from __future__ import annotations

from toffee import Bin, CoverGroupDef, CoverPointDef

S2_CASES = (
    "pipe.idle",
    "pipe.reset_clears_valid",
    "pipe.fire_without_redirect",
    "pipe.killed_by_redirect",
    "pipe.clear_valid_for_younger_redirect",
    "pipe.field_fidelity",
    "memtype.nc_from_pbmt_one",
    "memtype.mmio_from_pbmt_two",
    "memtype.mmio_from_pbmt_zero_and_pmp",
    "memtype.pma_is_normal",
    "memtype.pbmt_default_is_normal",
    "memtype.requires_tlb_hit",
    "memtype.blocked_by_tlb_exception",
    "memtype.mem_back_type_mm_follows_pmp_mmio",
    "memtype.mem_back_type_mm_cleared_by_tlb_inaccessible",
    "exc.pmp_st_denies",
    "exc.pmp_ld_denies_only_cbo_nonzero",
    "exc.vector_uncache_faults",
    "exc.cbo_uncache_faults",
    "exc.mmio_misaligned_faults",
    "exc.nc_misaligned_sets_exception6",
    "exc.nc_misaligned_pmp_denied_is_not_exception6",
    "exc.passthrough_has_exception",
    "exc.passthrough_exception_bits",
    "sqre.valid_is_fire",
    "sqre.has_exception_gated_by_fire",
    "sqre.last_request_from_head",
    "head.tlb_hit_needs_fire_head_and_tlb_hit",
)
GROUP = CoverGroupDef(
    "s2_case",
    (CoverPointDef("case", {name: Bin.values(name) for name in S2_CASES},
                   description="StoreUnitS2 的可读语义情形：kill/fire、PBMT/PMP 存储类型、"
                               "访问异常与错位异常、toSqAddrRe 组合输出与非对齐 head 的 TLB 命中。"),),
    description="StoreUnitS2 语义情形清单。",
)


class StoreS2Coverage:
    def __init__(self) -> None:
        self.cases = GROUP.instantiate("store_s2.case")

    def sample_case(self, name: str) -> None:
        if name not in S2_CASES:
            raise KeyError(f"undeclared StoreUnitS2 cover case: {name}")
        self.cases.sample({"case": name}, details=False)

    def observe(self, **_) -> None:
        """Every bin is an explicitly asserted case."""
