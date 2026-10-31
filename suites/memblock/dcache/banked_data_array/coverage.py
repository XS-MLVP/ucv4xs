"""Semantic functional coverage for BankedDataArray."""
from __future__ import annotations

from toffee import Bin, CoverGroupDef, CoverPointDef, CrossDef

from .model import BANKS, VWORD_BANKS, bank_base


def mask_class(mask: int) -> str:
    bits = mask.bit_count()
    if bits == 0:
        return "none"
    if bits == 1:
        return "single"
    if bits == VWORD_BANKS:
        return "one_vword"
    if bits == BANKS:
        return "all"
    return "partial"


def line_mask_class(mask: int) -> str:
    bits = mask.bit_count()
    if bits == 0:
        return "none"
    if bits == 1:
        return "single"
    if bits == BANKS:
        return "all"
    return "partial"


def base_class(addr: int) -> str:
    base = bank_base(addr)
    if base == 0:
        return "base_0"
    if base == 24:
        return "base_24"
    return "base_mid"


READ_DEFINITION = CoverGroupDef(
    "bda_read",
    (
        CoverPointDef(
            "port",
            {str(port): Bin.values(port) for port in range(3)},
            description="3 个 load 读端口独立访问同一组 bank。",
        ),
        CoverPointDef(
            "way",
            {str(way): Bin.values(way) for way in range(4)},
            description="way_en 单 hot 选择 4 个 way 中的任意一个。",
        ),
        CoverPointDef(
            "bank_mask",
            {name: Bin.values(name) for name in
             ("none", "single", "one_vword", "partial", "all")},
            description="bankMask 从空、单 bank、一个 16B vword 到全 32 bank。",
        ),
        CoverPointDef(
            "window_base",
            {name: Bin.values(name) for name in ("base_0", "base_mid", "base_24")},
            description="返回窗口的起始 bank：0/中间/24（回绕边界）。",
        ),
    ),
    (CrossDef("port_x_way", ("port", "way"), description="3 个读端口 × 4 个 way。"),
     CrossDef("mask_x_window", ("bank_mask", "window_base"),
              description="bankMask 形态 × 返回窗口起点。")),
    description="BankedDataArray 读路径：端口、way、bankMask 与返回窗口。",
)

WRITE_DEFINITION = CoverGroupDef(
    "bda_write",
    (
        CoverPointDef(
            "wmask",
            {name: Bin.values(name) for name in
             ("none", "single", "one_vword", "partial", "all")},
            description="写掩码从空、单 bank、一个 vword 到整条线。",
        ),
        CoverPointDef(
            "dup_valid",
            {name: Bin.values(name) for name in
             ("none", "single", "one_vword", "partial", "all")},
            description="per-bank 复制写端口 valid 位图与 wmask 共同门控写入。",
        ),
        CoverPointDef(
            "way",
            {str(way): Bin.values(way) for way in range(4)},
            description="复制写端口 way_en 选择写入的 way。",
        ),
        CoverPointDef(
            "bank",
            {**{str(bank): Bin.values(bank) for bank in range(BANKS)},
             "not_applicable": Bin.ignore(Bin.values(-1))},
            description="32 个 bank 槽位都能被独立写入。",
        ),
    ),
    (CrossDef("wmask_x_dup", ("wmask", "dup_valid"),
              description="写掩码 × 复制写端口位图。"),),
    description="BankedDataArray 写路径：掩码、复制端口、way 与 bank 槽位。",
)

LINE_DEFINITION = CoverGroupDef(
    "bda_line",
    (
        CoverPointDef(
            "way",
            {str(way): Bin.values(way) for way in range(4)},
            description="整线读的 way 选择。",
        ),
        CoverPointDef(
            "rmask",
            {name: Bin.values(name) for name in ("none", "single", "partial", "all")},
            description="整线读的 bank 掩码。",
        ),
        CoverPointDef(
            "hold",
            {"fresh": Bin.values("fresh"), "stalled": Bin.values("stalled")},
            description="can_go/can_resp 打入新数据，或 stall 保持上次结果。",
        ),
    ),
    description="BankedDataArray 整线读：way、rmask 与输出保持。",
)

CONFLICT_DEFINITION = CoverGroupDef(
    "bda_conflict",
    (
        CoverPointDef(
            "kind",
            {
                "read_read": Bin.values("read_read"),
                "read_line": Bin.values("read_line"),
                "write_read": Bin.values("write_read"),
            },
            description="读-读、读-线、写-读三类 bank 冲突。",
        ),
        CoverPointDef(
            "role",
            {
                "winner": Bin.values("winner"),
                "loser": Bin.values("loser"),
                "not_applicable": Bin.ignore(Bin.values("not_applicable")),
            },
            description="读-读冲突中按 lqIdx 最老的端口获胜，败者上报 replay。",
        ),
    ),
    description="BankedDataArray bank 冲突。",
)

ECC_DEFINITION = CoverGroupDef(
    "bda_ecc",
    (
        CoverPointDef(
            "context",
            {"read": Bin.values("read"), "line": Bin.values("line")},
            description="普通 8-bank 读与 32-bank 整线读。",
        ),
        CoverPointDef(
            "check",
            {"roundtrip": Bin.values("roundtrip"),
             "injected_xor": Bin.values("injected_xor")},
            description="功能数据往返逐位一致；伪错误注入按 bank 异或生效。",
        ),
    ),
    description="BankedDataArray data ECC：数据往返与伪错误注入。",
)


class BankedDataArrayCoverage:
    def __init__(self) -> None:
        self.read = READ_DEFINITION.instantiate("banked_data_array.read")
        self.write = WRITE_DEFINITION.instantiate("banked_data_array.write")
        self.line = LINE_DEFINITION.instantiate("banked_data_array.line")
        self.conflict = CONFLICT_DEFINITION.instantiate("banked_data_array.conflict")
        self.ecc = ECC_DEFINITION.instantiate("banked_data_array.ecc")

    def sample_read(self, port: int, way: int, bank_mask: int, addr: int) -> None:
        self.read.sample({"port": port, "way": way,
                          "bank_mask": mask_class(bank_mask),
                          "window_base": base_class(addr)}, details=False)

    def sample_write(self, wmask: int, dup_valid: int, way: int) -> None:
        selected = [bank for bank in range(BANKS)
                    if (wmask >> bank) & 1 and (dup_valid >> bank) & 1]
        # Record the mask classes even when no bank is selected (none/partial
        # combinations are meaningful behaviours, not missing data).
        for bank in selected or [-1]:
            self.write.sample({"wmask": mask_class(wmask),
                               "dup_valid": mask_class(dup_valid),
                               "way": way, "bank": bank}, details=False)

    def sample_line(self, way: int, rmask: int, hold: bool) -> None:
        self.line.sample({"way": way, "rmask": line_mask_class(rmask),
                          "hold": "stalled" if hold else "fresh"}, details=False)

    def sample_conflict(self, kind: str, role: str = "not_applicable") -> None:
        self.conflict.sample({"kind": kind, "role": role}, details=False)

    def sample_ecc(self, context: str, kind: str = "roundtrip") -> None:
        """Record an ECC check: data round-trip or pseudo-error injection.

        The delayed error flag is *observed* separately (known issue
        BDA-ECC-DELAYED-FLAG) and is deliberately not encoded as a coverage
        bin, so that the buggy flag cannot mask the data-correctness check.
        """
        self.ecc.sample({"context": context, "check": kind}, details=False)
