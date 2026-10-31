"""Semantic functional coverage for DuplicatedTagArray.

Every bin states a microarchitectural behaviour, not a raw signal value list.
Sampling happens only after the reference comparison succeeded.
"""
from __future__ import annotations

from toffee import Bin, CoverGroupDef, CoverPointDef, CrossDef

ALTERNATING = int("10" * 43, 2)

SET_CLASSES = ("boundary_0", "low", "mid", "high", "boundary_255")


def set_class(index: int) -> str:
    if index == 0:
        return "boundary_0"
    if index == 255:
        return "boundary_255"
    if index < 64:
        return "low"
    if index < 192:
        return "mid"
    return "high"


def mask_class(way_en: int) -> str:
    bits = way_en.bit_count()
    return {0: "none", 1: "single", 2: "pair", 3: "triple", 4: "all"}[bits]


def tag_class(tag: int) -> str:
    if tag == 0:
        return "zero"
    bits = tag.bit_count()
    if bits == 1:
        return "single_bit"
    if bits <= 18:
        return "multi_bit"
    return "dense"


READ_DEFINITION = CoverGroupDef(
    "dta_read",
    (
        CoverPointDef(
            "read_port",
            {str(port): Bin.values(port) for port in range(4)},
            description="4 份标签副本的每个读端口都能独立返回目标 set 的 4-way 码字。",
        ),
        CoverPointDef(
            "way",
            {str(way): Bin.values(way) for way in range(4)},
            description="读端口返回的每个 way 槽位都承载独立的 tag/ECC。",
        ),
        CoverPointDef(
            "set_class",
            {name: Bin.values(name) for name in SET_CLASSES},
            description="set 地址的低/中/高区间与 0/255 边界都通过同一寻址路径访问。",
        ),
        CoverPointDef(
            "read_order",
            {
                "single": Bin.values("single"),
                "back_to_back_same_set": Bin.values("back_to_back_same_set"),
                "back_to_back_diff_set": Bin.values("back_to_back_diff_set"),
            },
            description="单次读、连续读同一 set、连续读不同 set 都按拍返回各自数据。",
        ),
    ),
    (CrossDef("port_x_way", ("read_port", "way"),
              description="4 个读端口 × 4 个 way 的完整组合。"),),
    description="DuplicatedTagArray 读路径：副本一致性、way 完整性、set 寻址与背靠背读。",
)

WRITE_DEFINITION = CoverGroupDef(
    "dta_write",
    (
        CoverPointDef(
            "way_mask",
            {name: Bin.values(name) for name in ("none", "single", "pair", "triple", "all")},
            description="way_en 选择 0/1/2/3/4 个 way 时只更新选中槽位。",
        ),
        CoverPointDef(
            "tag_class",
            {name: Bin.values(name) for name in ("zero", "single_bit", "multi_bit", "dense")},
            description="标签载荷从全零、单 bit、多 bit 到稠密值都能原样保存并生成校验。",
        ),
        CoverPointDef(
            "set_class",
            {name: Bin.values(name) for name in SET_CLASSES},
            description="写地址覆盖低/中/高区间与边界 set。",
        ),
        CoverPointDef(
            "write_target",
            {
                "same_set_rewrite": Bin.values("same_set_rewrite"),
                "new_set": Bin.values("new_set"),
            },
            description="同一 set 重复写与切换到新 set 都不产生跨行污染。",
        ),
    ),
    (CrossDef("mask_x_set_class", ("way_mask", "set_class"),
              description="way 掩码 × set 区间，验证寻址与掩码相互独立。"),),
    description="DuplicatedTagArray 写路径：way 掩码、标签形态、set 区间与重复写。",
)

CONFLICT_DEFINITION = CoverGroupDef(
    "dta_conflict",
    (
        CoverPointDef(
            "access_kind",
            {
                "read_only": Bin.values("read_only"),
                "write_only": Bin.values("write_only"),
                "read_blocked_by_write": Bin.values("read_blocked_by_write"),
                "read_after_write": Bin.values("read_after_write"),
            },
            description="单端口仲裁：只读、只写、读写同拍时读被阻塞、写后读看到新值。",
        ),
        CoverPointDef(
            "conflict_relation",
            {
                "same_set": Bin.values("same_set"),
                "different_set": Bin.values("different_set"),
                "not_applicable": Bin.ignore(Bin.values("not_applicable")),
            },
            description="读写冲突发生在同一 set 或不同 set 时读请求都被拒绝。",
        ),
    ),
    description="DuplicatedTagArray 单端口访问冲突语义。",
)

MBIST_DEFINITION = CoverGroupDef(
    "dta_mbist",
    (
        CoverPointDef(
            "array_slot",
            {f"0x{slot:02x}": Bin.values(slot) for slot in range(0x20, 0x28)},
            description="MBIST 阵列编号 0x20..0x27 分别选中 4 份 TagArray 的 8 个 TagSRAMBank。",
        ),
        CoverPointDef(
            "operation",
            {"write": Bin.values("write"), "read": Bin.values("read")},
            description="DFT 旁路写与读都经过同一 spread/ack 路径，读回原始 86-bit SRAM 行。",
        ),
        CoverPointDef(
            "payload_class",
            {
                "zero": Bin.values("zero"),
                "pattern": Bin.values("pattern"),
                "dense": Bin.values("dense"),
            },
            description="DFT 原始行数据从全零、交替模式到稠密值时都能写读一致。",
        ),
    ),
    (CrossDef("array_x_operation", ("array_slot", "operation"),
              description="8 个 bank × 读写操作全部可达。"),),
    description="DuplicatedTagArray MBIST/DFT 旁路：阵列选择、原始行写读与 ack 时序。",
)

RESET_DEFINITION = CoverGroupDef(
    "dta_reset",
    (
        CoverPointDef(
            "reset_phase",
            {
                "sweep_in_progress": Bin.values("sweep_in_progress"),
                "after_sweep": Bin.values("after_sweep"),
            },
            description="复位扫描进行中读端口关闭；扫描完成后读端口恢复且存储全零。",
        ),
    ),
    description="DuplicatedTagArray 复位扫描行为。",
)


class DuplicatedTagArrayCoverage:
    def __init__(self) -> None:
        self.read = READ_DEFINITION.instantiate("duplicated_tag_array.read")
        self.write = WRITE_DEFINITION.instantiate("duplicated_tag_array.write")
        self.conflict = CONFLICT_DEFINITION.instantiate("duplicated_tag_array.conflict")
        self.reset = RESET_DEFINITION.instantiate("duplicated_tag_array.reset")
        self.mbist = MBIST_DEFINITION.instantiate("duplicated_tag_array.mbist")

    def sample_reset(self, phase: str) -> None:
        self.reset.sample({"reset_phase": phase}, details=False)

    def sample_read(self, port: int, index: int, order: str = "single") -> None:
        for way in range(4):
            self.read.sample(
                {"read_port": port, "way": way, "set_class": set_class(index),
                 "read_order": order},
                details=False,
            )

    def sample_write(self, index: int, way_en: int, tag: int, target: str) -> None:
        self.write.sample(
            {"way_mask": mask_class(way_en), "tag_class": tag_class(tag),
             "set_class": set_class(index), "write_target": target},
            details=False,
        )

    def sample_mbist(self, array: int, operation: str, data: int) -> None:
        if data == 0:
            payload = "zero"
        elif data == ALTERNATING:
            payload = "pattern"
        else:
            payload = "dense"
        self.mbist.sample({"array_slot": array, "operation": operation,
                           "payload_class": payload}, details=False)

    def sample_conflict(self, kind: str, relation: str = "not_applicable") -> None:
        self.conflict.sample({"access_kind": kind, "conflict_relation": relation},
                             details=False)
