"""Semantic functional coverage for MissReadyGen."""
from __future__ import annotations

from toffee import Bin, CoverGroupDef, CoverPointDef, CrossDef

READY_CLASSES = {
    "none": 0,
    "ch0": 1,
    "ch1": 2,
    "ch2": 4,
    "ch3": 8,
    "all": 15,
    "mixed": 5,
}


def ready_class(mask: int) -> str:
    for name, value in READY_CLASSES.items():
        if mask == value:
            return name
    return "mixed"


CHANNEL_DEFINITION = CoverGroupDef(
    "mrg_channel",
    (
        CoverPointDef(
            "channel",
            {str(ch): Bin.values(ch) for ch in range(4)},
            description="4 路 miss 请求通道各自独立直通。",
        ),
        CoverPointDef(
            "valid",
            {"valid": Bin.values(1), "invalid": Bin.values(0)},
            description="通道有效与无效两种状态都原样传递。",
        ),
        CoverPointDef(
            "ready_class",
            {name: Bin.values(name) for name in READY_CLASSES},
            description="MissQueue 的 ready 位图：单路、全 0、全 1 与混合。",
        ),
        CoverPointDef(
            "packet_kind",
            {"wide": Bin.values("wide"), "narrow": Bin.values("narrow")},
            description="通道 0 的宽 payload（store/atomic）与 1..3 的 load/spec payload。",
        ),
    ),
    (CrossDef("channel_x_valid", ("channel", "valid"),
              description="4 路 × 有效/无效组合。"),
     CrossDef("channel_x_ready", ("channel", "ready_class"),
              description="4 路 × ready 位图类别。")),
    description="MissReadyGen 四路直通：通道、valid、ready 与载荷类别。",
)

FIELD_DEFINITION = CoverGroupDef(
    "mrg_field",
    (
        CoverPointDef(
            "payload_shape",
            {
                "zero": Bin.values("zero"),
                "all_ones": Bin.values("all_ones"),
                "walking_bit": Bin.values("walking_bit"),
                "random": Bin.values("random"),
            },
            description="宽/窄 payload 从全零、全一、单 bit walking 到随机值的位保真。",
        ),
        CoverPointDef(
            "field_group",
            {
                "address": Bin.values("address"),
                "metadata": Bin.values("metadata"),
                "amo": Bin.values("amo"),
                "store": Bin.values("store"),
            },
            description="地址、元数据、AMO 载荷、store 载荷四组字段分别透传。",
        ),
    ),
    description="MissReadyGen payload 位域保真。",
)

INDEPENDENCE_DEFINITION = CoverGroupDef(
    "mrg_independence",
    (
        CoverPointDef(
            "valid_pattern",
            {
                "single": Bin.values("single"),
                "multi": Bin.values("multi"),
                "none": Bin.values("none"),
                "all": Bin.values("all"),
            },
            description="同一拍只有一路、多路、全无、四路全有效时互不影响。",
        ),
        CoverPointDef(
            "change_mode",
            {
                "stable": Bin.values("stable"),
                "changed": Bin.values("changed"),
            },
            description="输入保持不变时输出保持；改变输入后同一拍反映新值。",
        ),
    ),
    description="MissReadyGen 通道独立性与零状态组合语义。",
)


class MissReadyGenCoverage:
    def __init__(self) -> None:
        self.channel = CHANNEL_DEFINITION.instantiate("miss_ready_gen.channel")
        self.field = FIELD_DEFINITION.instantiate("miss_ready_gen.field")
        self.independence = INDEPENDENCE_DEFINITION.instantiate("miss_ready_gen.independence")

    def sample_channel(self, channel: int, valid: int, ready_mask: int,
                       packet_kind: str) -> None:
        self.channel.sample({"channel": channel, "valid": valid,
                             "ready_class": ready_class(ready_mask),
                             "packet_kind": packet_kind}, details=False)

    def sample_field(self, shape: str, group: str) -> None:
        self.field.sample({"payload_shape": shape, "field_group": group}, details=False)

    def sample_independence(self, pattern: str, change: str = "changed") -> None:
        self.independence.sample({"valid_pattern": pattern, "change_mode": change},
                                 details=False)
