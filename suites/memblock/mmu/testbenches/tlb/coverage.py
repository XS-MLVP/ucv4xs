"""Functional coverage for the TLB (ITLB) parent."""
from __future__ import annotations

from toffee import Bin, CoverGroupDef, CoverPointDef

NA = -1

LOOKUP_DEFINITION = CoverGroupDef(
    "tlb_lookup",
    (
        CoverPointDef(
            "translation_mode",
            {
                "bare": Bin.values("bare"),
                "sv39": Bin.values("sv39"),
                "sv48": Bin.values("sv48"),
            },
            description="地址翻译处于 Bare、Sv39 或 Sv48 模式。",
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
            "exception",
            {
                "none": Bin.values("none"),
                "pf": Bin.values("pf"),
                "af": Bin.values("af"),
                "fake_or_nonleaf": Bin.values("fake_or_nonleaf"),
                "not_applicable": Bin.ignore(Bin.values(NA)),
            },
            description="命中时的异常类别：无异常、page fault、access fault、fake/non-leaf 标志。",
        ),
    ),
    description="TLB 顶层请求/翻译结果。",
)

PTW_DEFINITION = CoverGroupDef(
    "tlb_ptw",
    (
        CoverPointDef(
            "request",
            {
                "miss_request": Bin.values("miss_request"),
                "no_request_on_hit": Bin.values("no_request_on_hit"),
                "s2xlate_request": Bin.values("s2xlate_request"),
            },
            description="miss 发起 PTW 请求、hit 不请求、以及两阶段上下文请求。",
        ),
        CoverPointDef(
            "refill",
            {
                "stage1_refill": Bin.values("stage1_refill"),
                "two_stage_refill": Bin.values("two_stage_refill"),
            },
            description="PTW 响应回填 stage1 或两阶段翻译。",
        ),
    ),
    description="TLB 与 PTW 的请求/响应关系。",
)

EXCEPTION_DEFINITION = CoverGroupDef(
    "tlb_exception",
    (
        CoverPointDef(
            "fault_type",
            {
                "pf_x": Bin.values("pf_x"),
                "pf_u": Bin.values("pf_u"),
                "pf_a": Bin.values("pf_a"),
                "af_set": Bin.values("af_set"),
                "fake": Bin.values("fake"),
                "none": Bin.values("none"),
            },
            description="命中 PTE 的 x/u/a 权限失败、A 位失败、fake PTE 或无故障。",
        ),
    ),
    description="TLB 命中 PTE 的异常语义。",
)

SFENCE_DEFINITION = CoverGroupDef(
    "tlb_sfence",
    (
        CoverPointDef(
            "fence_form",
            {
                "all_all": Bin.values("all_all"),
                "all_asid": Bin.values("all_asid"),
                "addr": Bin.values("addr"),
                "hfencev": Bin.values("hfencev"),
                "hfenceg": Bin.values("hfenceg"),
            },
            description="sfence/hfence 失效形式在 TLB 顶层的透传。",
        ),
        CoverPointDef(
            "fence_effect",
            {
                "cleared": Bin.values("cleared"),
                "survived": Bin.values("survived"),
            },
            description="目标条目被清除、无关条目保留。",
        ),
    ),
    description="TLB 顶层失效透传。",
)

RESET_DEFINITION = CoverGroupDef(
    "tlb_reset",
    (
        CoverPointDef(
            "reset_context",
            {
                "empty": Bin.values("empty"),
                "with_valid_entries": Bin.values("with_valid_entries"),
            },
            description="复位清空有效翻译或从空状态开始。",
        ),
    ),
    description="TLB 复位语义。",
)


class TlbCoverage:
    def __init__(self) -> None:
        self.lookup = LOOKUP_DEFINITION.instantiate("tlb.lookup")
        self.ptw = PTW_DEFINITION.instantiate("tlb.ptw")
        self.exception = EXCEPTION_DEFINITION.instantiate("tlb.exception")
        self.sfence = SFENCE_DEFINITION.instantiate("tlb.sfence")
        self.reset = RESET_DEFINITION.instantiate("tlb.reset")

    def sample_lookup(self, mode: str, hit: bool, exception: str | None) -> None:
        self.lookup.sample(
            {
                "translation_mode": mode,
                "outcome": "hit" if hit else "miss",
                "exception": exception if exception is not None else NA,
            },
            details=False,
        )

    def sample_ptw_request(self, s2xlate: int) -> None:
        self.ptw.sample(
            {"request": "s2xlate_request" if s2xlate else "miss_request",
             "refill": "stage1_refill"},
            details=False,
        )

    def sample_no_ptw(self) -> None:
        self.ptw.sample({"request": "no_request_on_hit", "refill": "stage1_refill"}, details=False)

    def sample_ptw_refill(self, data) -> None:
        self.ptw.sample(
            {"request": "miss_request",
             "refill": "two_stage_refill" if data.s2xlate else "stage1_refill"},
            details=False,
        )

    def sample_exception(self, kind: str) -> None:
        self.exception.sample({"fault_type": kind}, details=False)

    def sample_sfence(self, rs1: int, rs2: int, hv: int, hg: int,
                      effects: tuple[str, ...] = ("cleared",)) -> None:
        form = "hfencev" if hv else "hfenceg" if hg else (
            "all_all" if rs1 and rs2 else "all_asid" if rs1 else "addr"
        )
        for effect in effects:
            self.sfence.sample({"fence_form": form, "fence_effect": effect}, details=False)

    def sample_reset(self, context: str) -> None:
        self.reset.sample({"reset_context": context}, details=False)
