"""Functional coverage owned by ptwrepeater."""
from __future__ import annotations

from toffee import Bin, CoverGroupDef, CoverPointDef


REPEATER_DEFINITION = CoverGroupDef(
    "ptwrepeater",
    (
        CoverPointDef("event", {"accept": Bin.values("accept"), "issue": Bin.values("issue"),
                                "response": Bin.values("response"), "flush": Bin.values("flush")},
                      description="请求接收、向 PTW 发出、响应持有和 flush 取消。"),
        CoverPointDef("stage", {str(v): Bin.values(v) for v in range(4)},
                      description="透传的翻译阶段编码。"),
        CoverPointDef("hold", {"held": Bin.values("held"), "released": Bin.values("released")},
                      description="PTW 响应在输出未 ready 时保持，ready 后释放。"),
    ),
    description="PTWRepeaterNB 单条非阻塞重复/保持。",
)


class RepeaterCoverage:
    def __init__(self) -> None:
        self.group = REPEATER_DEFINITION.instantiate("ptwrepeater")

    def sample(self, event: str, stage: int = 0, hold: str = "released") -> None:
        self.group.sample({"event": event, "stage": stage, "hold": hold}, details=False)
