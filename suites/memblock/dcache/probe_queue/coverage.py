"""Semantic functional coverage for ProbeQueue."""
from __future__ import annotations

from toffee import Bin, CoverGroupDef, CoverPointDef, CrossDef

PROBE_DEFINITION = CoverGroupDef(
    "pq_probe",
    (
        CoverPointDef(
            "param",
            {
                "to_b": Bin.values("to_b"),
                "to_n": Bin.values("to_n"),
                "to_t": Bin.values("to_t"),
            },
            description="B 通道 probe 的权限目标：TtoB/TtoN/TtoT。",
        ),
        CoverPointDef(
            "need_data",
            {"yes": Bin.values("yes"), "no": Bin.values("no")},
            description="MainPipe 请求是否需要回收数据。",
        ),
        CoverPointDef(
            "lrsc",
            {"blocked": Bin.values("blocked"), "free": Bin.values("free")},
            description="probe 地址与 LR/SC 保留块重叠时被阻塞，否则放行。",
        ),
    ),
    description="ProbeQueue B 通道受理与 MainPipe 请求编码。",
)


def param_name(param: int) -> str:
    return {0: "to_b", 1: "to_n", 2: "to_t"}.get(param, "to_b")


class ProbeQueueCoverage:
    def __init__(self) -> None:
        self.probe = PROBE_DEFINITION.instantiate("probe_queue.probe")

    def sample(self, param: int, need_data: int, blocked: bool) -> None:
        self.probe.sample({
            "param": param_name(param),
            "need_data": "yes" if need_data else "no",
            "lrsc": "blocked" if blocked else "free",
        }, details=False)
