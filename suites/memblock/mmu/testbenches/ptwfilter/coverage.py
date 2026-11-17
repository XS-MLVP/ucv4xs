"""Functional coverage owned by ptwfilter."""
from __future__ import annotations

from toffee import Bin, CoverGroupDef, CoverPointDef


FILTER_DEFINITION = CoverGroupDef(
    "ptwfilter",
    (
        CoverPointDef("event", {"enqueue": Bin.values("enqueue"), "issue": Bin.values("issue"),
                                "match_resp": Bin.values("match_resp"),
                                "mismatch_resp": Bin.values("mismatch_resp"),
                                "merge": Bin.values("merge"), "flush": Bin.values("flush"),
                                "full": Bin.values("full")},
                      description="入队、向 PTW 发出、匹配/不匹配响应、重复合并、flush 和满。"),
        CoverPointDef("stage", {str(v): Bin.values(v) for v in range(4)},
                      description="待处理请求的翻译阶段编码。"),
        CoverPointDef("getgpa", {"set": Bin.values("set"), "clear": Bin.values("clear")},
                      description="请求的 getGpa 属性在响应中透传。"),
    ),
    description="PTWFilter 8 项待处理队列与响应匹配。",
)


class FilterCoverage:
    def __init__(self) -> None:
        self.group = FILTER_DEFINITION.instantiate("ptwfilter")

    def sample(self, event: str, stage: int = 0, getgpa: int = 0) -> None:
        self.group.sample({"event": event, "stage": stage,
                           "getgpa": "set" if getgpa else "clear"}, details=False)
