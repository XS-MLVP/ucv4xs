"""Semantic functional coverage for CtrlUnit."""
from __future__ import annotations

from toffee import Bin, CoverGroupDef, CoverPointDef, CrossDef

CTRL_BANKS = 32
DELAY_CLASSES = ("zero", "one", "small", "large")


def bank_class(bank_mask: int) -> str:
    bits = bank_mask.bit_count()
    if bits == 0:
        return "none"
    if bits == 1:
        return "single"
    if bits == CTRL_BANKS:
        return "all"
    return "multi"


def delay_class(delay: int) -> str:
    if delay == 0:
        return "zero"
    if delay == 1:
        return "one"
    if delay <= 4:
        return "small"
    return "large"


def tag_mask_class(mask: int) -> str:
    if mask == 0:
        return "zero"
    if mask.bit_count() == 1:
        return "single_bit"
    if mask == (1 << 36) - 1:
        return "full"
    return "partial"


ACCESS_DEFINITION = CoverGroupDef(
    "cu_access",
    (
        CoverPointDef(
            "opcode",
            {"write": Bin.values("write"), "read": Bin.values("read")},
            description="TL 写响应 AccessAck 与读响应 AccessAckData 两条路径。",
        ),
        CoverPointDef(
            "register_index",
            {str(index): Bin.values(index) for index in range(11)},
            description="ctrl/delay/tagMask/8 个 data mask 组共 11 个地址索引。",
        ),
        CoverPointDef(
            "write_mask",
            {"full": Bin.values("full"), "partial": Bin.values("partial")},
            description="整 8 字节掩码生效；部分字节掩码的写被忽略。",
        ),
        CoverPointDef(
            "d_handshake",
            {"immediate": Bin.values("immediate"), "held_then_released": Bin.values("held_then_released")},
            description="D 通道立即握手完成，以及先反压再释放的完成路径。",
        ),
    ),
    description="CtrlUnit TileLink 寄存器访问：opcode、地址、字节掩码与 D 握手。",
)

REGS_DEFINITION = CoverGroupDef(
    "cu_regs",
    (
        CoverPointDef(
            "target",
            {
                "ctrl": Bin.values("ctrl"),
                "delay": Bin.values("delay"),
                "tag_mask": Bin.values("tag_mask"),
                "data_mask": Bin.values("data_mask"),
            },
            description="四类寄存器各自独立可写可读。",
        ),
        CoverPointDef(
            "readback",
            {"match": Bin.values("match"), "masked_hold": Bin.values("masked_hold")},
            description="写入后读回一致；部分掩码写后读回保持旧值。",
        ),
    ),
    description="CtrlUnit 寄存器读回与掩码保持语义。",
)

INJECT_DEFINITION = CoverGroupDef(
    "cu_inject",
    (
        CoverPointDef(
            "component",
            {"tag": Bin.values("tag"), "data": Bin.values("data")},
            description="tag 组件与 data 组件两条伪错误注入通路。",
        ),
        CoverPointDef(
            "bank_select",
            {name: Bin.values(name) for name in ("none", "single", "multi", "all")},
            description="bank 位图选择 0/1/多/全部 bank 时的 valid 行为。",
        ),
        CoverPointDef(
            "delay_class",
            {name: Bin.values(name) for name in DELAY_CLASSES},
            description="无延迟、1 拍、短延迟与长延迟的 counter 递减路径。",
        ),
        CoverPointDef(
            "persist",
            {"single_shot": Bin.values("single_shot"), "persistent": Bin.values("persistent")},
            description="非 persist 捕获后清 ese；persist 保持并重复注入。",
        ),
        CoverPointDef(
            "consumer_ready",
            {"immediate": Bin.values("immediate"), "backpressured": Bin.values("backpressured")},
            description="消费者立即接收与先反压再接收。",
        ),
        CoverPointDef(
            "tag_mask_shape",
            {name: Bin.values(name) for name in ("zero", "single_bit", "partial", "full")},
            description="tag 注入掩码从全零、单 bit 到部分/全 36 bit。",
        ),
    ),
    (
        CrossDef("component_x_bank", ("component", "bank_select"),
                 description="tag/data 组件 × bank 选择类别的完整组合。"),
        CrossDef("delay_x_persist", ("delay_class", "persist"),
                 description="延迟类别 × 单次/持续注入的完整组合。"),
    ),
    description="CtrlUnit 伪错误注入：组件、bank、延迟、持续与背压。",
)


class CtrlUnitCoverage:
    def __init__(self) -> None:
        self.access = ACCESS_DEFINITION.instantiate("ctrl_unit.access")
        self.regs = REGS_DEFINITION.instantiate("ctrl_unit.regs")
        self.inject = INJECT_DEFINITION.instantiate("ctrl_unit.inject")

    def sample_access(self, opcode: str, index: int, mask: str = "full",
                      handshake: str = "immediate") -> None:
        self.access.sample({"opcode": opcode, "register_index": index,
                            "write_mask": mask, "d_handshake": handshake},
                           details=False)

    def sample_regs(self, target: str, readback: str = "match") -> None:
        self.regs.sample({"target": target, "readback": readback}, details=False)

    def sample_inject(self, component: str, bank_mask: int, delay: int,
                      persist: bool, ready: str, tag_mask: int) -> None:
        self.inject.sample(
            {
                "component": component,
                "bank_select": bank_class(bank_mask),
                "delay_class": delay_class(delay),
                "persist": "persistent" if persist else "single_shot",
                "consumer_ready": ready,
                "tag_mask_shape": tag_mask_class(tag_mask),
            },
            details=False,
        )
