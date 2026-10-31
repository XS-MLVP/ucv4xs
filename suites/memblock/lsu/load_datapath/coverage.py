"""Semantic functional coverage for LoadUnitDataPath."""
from __future__ import annotations

from toffee import Bin, CoverGroupDef, CoverPointDef

CASES = (
    "meta.register_and_clear",
    "meta.hold_when_empty",
    "merge.sq_priority_over_all",
    "merge.uncache_requires_nc_replay",
    "merge.sbuffer_priority_over_mshr",
    "merge.mshr_priority_over_tld",
    "merge.tld_priority_over_raw",
    "merge.raw_from_dcache",
    "merge.raw_from_uncache_bypass_on_nc",
    "merge.raw_from_uncache_bypass_on_mmio",
    "rotate.each_bank_offset",
    "rotate.offset_zero_identity",
    "extend.unsigned_byte_half_word_word",
    "extend.signed_byte_half_word_word",
    "extend.double_word",
    "extend.fp16_nan_box",
    "extend.fp32_nan_box",
    "extend.unknown_optype_is_zero",
    "tail.head_data_is_merged_with_shifted_tail",
    "tail.offset_zero_uses_head_only",
    "valid.chain_latency",
)
GROUP = CoverGroupDef(
    "ldp_case",
    (CoverPointDef("case", {name: Bin.values(name) for name in CASES},
                   description="LoadUnitDataPath 的可读语义情形：元数据寄存器、五级字节合并优先级、"
                               "16 个字节偏移的旋转、9 种扩展类型、head/tail 合并与有效链。"),),
    description="LoadUnitDataPath 语义情形清单。",
)


class LoadDataPathCoverage:
    def __init__(self) -> None:
        self.cases = GROUP.instantiate("load_datapath.case")

    def sample_case(self, name: str) -> None:
        if name not in CASES:
            raise KeyError(f"undeclared LoadDataPath cover case: {name}")
        self.cases.sample({"case": name}, details=False)

    def observe(self, **_) -> None:
        """Every bin is an explicitly asserted case."""
