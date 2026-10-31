"""Functional coverage for TlbStorageWrapper: replacement + pass-through."""
from __future__ import annotations

from toffee import Bin, CoverGroupDef, CoverPointDef

NA = -1

REPLACE_DEFINITION = CoverGroupDef(
    "wrapper_replace",
    (
        CoverPointDef(
            "victim_way",
            {**{str(way): Bin.values(way) for way in range(48)},
             "not_applicable": Bin.ignore(Bin.values(NA))},
            description="PLRU 选中的 victim way；覆盖每个 way 都被实际替换选中过。",
        ),
        CoverPointDef(
            "victim_state",
            {
                "invalid": Bin.values("invalid"),
                "valid": Bin.values("valid"),
                "not_applicable": Bin.ignore(Bin.values(NA)),
            },
            description="替换时 victim 原本无效（首次填充或淘汰后）还是已有有效翻译。",
        ),
        CoverPointDef(
            "replacement_timing",
            {
                "normal": Bin.values("normal"),
                "same_cycle_lookup": Bin.values("same_cycle_lookup"),
                "not_applicable": Bin.ignore(Bin.values(NA)),
            },
            description="普通回填，以及与查找同拍发生的回填。",
        ),
        CoverPointDef(
            "plru_update_source",
            {
                "refill": Bin.values("refill"),
                "read_hit": Bin.values("read_hit"),
            },
            description="PLRU 状态由回填 way 或读命中 way 更新。",
        ),
    ),
    description="TlbStorageWrapper 的 PLRU victim 选择与更新来源。",
)

LOOKUP_DEFINITION = CoverGroupDef(
    "wrapper_lookup",
    (
        CoverPointDef(
            "context",
            {
                "bare_no_s2": Bin.values("bare_no_s2"),
                "stage1_only": Bin.values("stage1_only"),
                "stage2_only": Bin.values("stage2_only"),
                "two_stage": Bin.values("two_stage"),
            },
            description="wrapper 透传的真实翻译阶段上下文。",
        ),
        CoverPointDef(
            "outcome",
            {
                "hit": Bin.values("hit"),
                "miss": Bin.values("miss"),
            },
            description="查找命中或未命中。",
        ),
        CoverPointDef(
            "hit_way_class",
            {
                "low_half": Bin.values("low_half"),
                "high_half": Bin.values("high_half"),
                "not_applicable": Bin.ignore(Bin.values(NA)),
            },
            description="命中 way 落在 48-way 的低半区或高半区，证明内部 way 不被 wrapper 固定。",
        ),
    ),
    description="wrapper 对外查找透传结果。",
)

FENCE_DEFINITION = CoverGroupDef(
    "wrapper_fence",
    (
        CoverPointDef(
            "fence_kind",
            {
                "all_all": Bin.values("all_all"),
                "addr_asid": Bin.values("addr_asid"),
                "hfencev": Bin.values("hfencev"),
                "hfenceg": Bin.values("hfenceg"),
            },
            description="wrapper 对普通/虚拟化失效的透传。",
        ),
        CoverPointDef(
            "fence_effect",
            {
                "cleared": Bin.values("cleared"),
                "survived": Bin.values("survived"),
            },
            description="失效目标被清除、非目标保留。",
        ),
    ),
    description="wrapper 失效透传语义。",
)

RESET_DEFINITION = CoverGroupDef(
    "wrapper_reset",
    (
        CoverPointDef(
            "reset_context",
            {
                "empty": Bin.values("empty"),
                "with_valid_entries": Bin.values("with_valid_entries"),
            },
            description="复位清空有效条目，并把 PLRU 状态归零。",
        ),
    ),
    description="wrapper 复位语义。",
)

TIMING_DEFINITION = CoverGroupDef(
    "wrapper_timing",
    (
        CoverPointDef(
            "response",
            {
                "one_cycle_latency": Bin.values("one_cycle_latency"),
                "valid_drop": Bin.values("valid_drop"),
                "same_cycle_suppressed": Bin.values("same_cycle_suppressed"),
            },
            description="查找响应节拍与同拍回填屏蔽。",
        ),
    ),
    description="wrapper 响应时序。",
)


class WrapperCoverage:
    def __init__(self) -> None:
        self.replace = REPLACE_DEFINITION.instantiate("wrapper.replace")
        self.lookup = LOOKUP_DEFINITION.instantiate("wrapper.lookup")
        self.fence = FENCE_DEFINITION.instantiate("wrapper.fence")
        self.reset = RESET_DEFINITION.instantiate("wrapper.reset")
        self.timing = TIMING_DEFINITION.instantiate("wrapper.timing")

    def sample_refill(self, way: int, state: str, entry) -> None:
        self.replace.sample(
            {
                "victim_way": way,
                "victim_state": state,
                "replacement_timing": "normal",
                "plru_update_source": "refill",
            },
            details=False,
        )

    def sample_same_cycle(self, way: int) -> None:
        self.replace.sample(
            {
                "victim_way": way,
                "victim_state": "valid",
                "replacement_timing": "same_cycle_lookup",
                "plru_update_source": "refill",
            },
            details=False,
        )
        self.timing.sample({"response": "same_cycle_suppressed"}, details=False)

    def sample_lookup(self, context: str, hit: bool, way: int | None) -> None:
        self.lookup.sample(
            {
                "context": context,
                "outcome": "hit" if hit else "miss",
                "hit_way_class": (
                    ("low_half" if way is not None and way < 24 else "high_half")
                    if hit
                    else NA
                ),
            },
            details=False,
        )
        if hit:
            self.replace.sample(
                {
                    "victim_way": NA,
                    "victim_state": NA,
                    "replacement_timing": NA,
                    "plru_update_source": "read_hit",
                },
                details=False,
            )
        self.timing.sample({"response": "one_cycle_latency"}, details=False)

    def sample_fence(self, kind: str, effects: list[str]) -> None:
        for effect in effects:
            self.fence.sample({"fence_kind": kind, "fence_effect": effect}, details=False)

    def sample_reset(self, context: str) -> None:
        self.reset.sample({"reset_context": context}, details=False)
