"""Functional coverage owned by bitmap."""
from __future__ import annotations

from toffee import Bin, CoverGroupDef, CoverPointDef


BITMAP_DEFINITION = CoverGroupDef(
    "bitmap",
    (
        CoverPointDef("event", {"cache_hit": Bin.values("cache_hit"),
                                "cache_miss": Bin.values("cache_miss"),
                                "pmp_fail": Bin.values("pmp_fail"),
                                "refill": Bin.values("refill"),
                                "wakeup": Bin.values("wakeup"),
                                "flush": Bin.values("flush"),
                                "multi": Bin.values("multi")},
                      description="bitmap 检查的缓存命中/缺失、PMP 故障、回填、wakeup、flush 和多请求。"),
        CoverPointDef("level", {str(v): Bin.values(v) for v in range(4)},
                      description="页表级别决定 effective PPN 的 VPN 合并方式。"),
        CoverPointDef("result", {"pass": Bin.values("pass"), "fail": Bin.values("fail")},
                      description="bitmap 检查通过或失败。"),
    ),
    description="Bitmap 位图检查语义。",
)


class BitmapCoverage:
    def __init__(self) -> None:
        self.group = BITMAP_DEFINITION.instantiate("bitmap")

    def sample(self, event: str, level: int = 0, result: str = "pass") -> None:
        self.group.sample({"event": event, "level": level, "result": result},
                          details=False)
