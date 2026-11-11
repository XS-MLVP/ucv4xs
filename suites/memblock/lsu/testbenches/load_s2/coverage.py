"""Semantic functional coverage for LoadUnitS2."""
from __future__ import annotations

from toffee import Bin, CoverGroupDef, CoverPointDef

CASES = (
    "kill.current_redirect",
    "kill.hardware_prefetch_suppressed",
    "forward.sq_covers_the_mask",
    "forward.sbuffer_covers_the_mask",
    "forward.uncache_covers_the_mask",
    "forward.mshr_covers_the_mask",
    "forward.tld_response_completes",
    "forward.sq_data_invalid_blocks",
    "dcache.access_needed_when_not_covered",
    "uncache.nc_from_pbmt",
    "uncache.mmio_from_pbmt_or_pmp",
    "exception.af_from_pmp",
    "exception.af_from_vector_uncache",
    "exception.am_misaligned_nc",
    "exception.af_misaligned_mmio",
    "exception.hwe_from_corrupt_forward",
    "exception.denied_forward_raises_af",
    "cause.uncache_first_access",
    "cause.nc_replay_still_invalid",
    "cause.forward_invalid",
    "cause.addr_invalid_store_set",
    "cause.tlb_miss",
    "cause.sq_data_invalid",
    "cause.mshr_nack",
    "cause.dcache_miss",
    "cause.bank_conflict",
    "cause.rar_nack",
    "cause.raw_nack",
    "cause.nuke",
    "cause.special_mode",
    "fastreplay.mshr_nack_alone",
    "fastreplay.bank_conflict_alone",
    "fastreplay.nuke_first_excludes_cause2",
    "fastreplay.data_invalid_with_std_write",
    "fastreplay.eligibility_blocks",
    "rrbank.conflict_candidate",
    "nukequery.data_valid_sources",
    "nukequery.request_fields",
    "wakeup.clean_load_wakes_up",
    "wakeup.exception_writes_back",
    "matchinvalid.reported",
    "prefetchtrain.issued_load_trains",
    "perf.four_counters",
    "reg.payload_holds",
)
GROUP = CoverGroupDef(
    "ls2_case",
    (CoverPointDef("case", {name: Bin.values(name) for name in CASES},
                   description="LoadUnitS2 的可读语义情形：kill/硬件预取、forward 覆盖与 DCache 需求、"
                               "NC/MMIO 分类、异常重算、C0..C11 replay 原因、fast replay 四条路径、"
                               "RAR/RAW 查询、wakeup/writeback、prefetch train 与四个 perf 计数。"),),
    description="LoadUnitS2 语义情形清单。",
)


class LoadS2Coverage:
    def __init__(self) -> None:
        self.cases = GROUP.instantiate("load_s2.case")

    def sample_case(self, name: str) -> None:
        if name not in CASES:
            raise KeyError(f"undeclared LoadUnitS2 cover case: {name}")
        self.cases.sample({"case": name}, details=False)

    def observe(self, **_) -> None:
        """Every bin is an explicitly asserted case."""
