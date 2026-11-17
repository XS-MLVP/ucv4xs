"""Functional coverage owned by bitmapcache."""
from __future__ import annotations

from toffee import Bin, CoverGroupDef, CoverPointDef


BITMAPCACHE_DEFINITION = CoverGroupDef(
    "bitmapcache",
    (
        CoverPointDef("event", {"refill": Bin.values("refill"), "hit": Bin.values("hit"),
                                "miss": Bin.values("miss"), "clear": Bin.values("clear"),
                                "flush": Bin.values("flush")},
                      description="bitmap cache 回填、命中、缺失、BCLEAR 和 flush。"),
        CoverPointDef("byte", {str(v): Bin.values(v) for v in range(8)},
                      description="命中时按 PPN 低 3 位选择数据字节。"),
        CoverPointDef("order", {str(v): Bin.values(v) for v in range(8)},
                      description="请求 order 原样返回。"),
    ),
    description="BitmapCache 64 位位图字缓存语义。",
)


class BitmapCacheCoverage:
    def __init__(self) -> None:
        self.group = BITMAPCACHE_DEFINITION.instantiate("bitmapcache")

    def sample(self, event: str, byte: int = 0, order: int = 0) -> None:
        self.group.sample({"event": event, "byte": byte, "order": order},
                          details=False)
