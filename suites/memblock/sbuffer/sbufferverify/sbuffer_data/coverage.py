"""Semantic functional coverage for SbufferData.

Every bin states a microarchitectural behaviour, not a raw signal value list.
Sampling happens only after the byte-level checker accepted the transaction.
Groups are split by event type so each sample only carries fields that are
meaningful for that event.
"""
from __future__ import annotations

from toffee import Bin, CoverGroupDef, CoverPointDef, CrossDef

from .model import BYTES, LANES, LINES, WriteRequest

WBITS = (1 << BYTES) - 1
NOT_APPLICABLE = -1


def classify_write_shape(req: WriteRequest) -> str:
    if req.wline:
        return "wline_zero" if req.data == 0 else "wline_payload"
    mask = req.mask
    if mask == 0:
        return "no_bytes"
    if mask == WBITS:
        return "full_lane"
    bits = mask.bit_count()
    if bits == 1:
        return "single_byte"
    # A contiguous run has the form 0b0*1+0*.
    low = (mask & -mask).bit_length() - 1
    run = mask >> low
    if run & (run + 1) == 0:
        return "byte_range"
    return "scattered"


def selected_lines(wvec: int) -> list[int]:
    return [line for line in range(LINES) if (wvec >> line) & 1]


def classify_port_usage(writes: tuple[WriteRequest, ...]) -> str:
    if len(writes) == 1:
        return "single"
    first, second = writes
    first_lines = selected_lines(first.wvec)
    second_lines = selected_lines(second.wvec)
    if not set(first_lines) & set(second_lines):
        return "dual_disjoint_lines"
    if first.wline or second.wline:
        return "dual_same_byte_overlap"
    if first.lane != second.lane:
        return "dual_same_line_other_lane"
    if first.mask & second.mask:
        return "dual_same_byte_overlap"
    return "dual_same_lane_disjoint_bytes"


def classify_flush_extent(wvec: int) -> str:
    bits = wvec.bit_count()
    if bits == 1:
        return "single_line"
    if bits == 2:
        return "two_lines"
    if bits == 3:
        return "three_lines"
    if bits == LINES:
        return "all_lines"
    return "many_lines"


def classify_flush_concurrency(wvec: int, writes: tuple[WriteRequest, ...]) -> str:
    if not writes:
        return "flush_only"
    write_lines: set[int] = set()
    for req in writes:
        write_lines.update(selected_lines(req.wvec))
    if write_lines & set(selected_lines(wvec)):
        return "with_write_same_line"
    return "with_write_other_line"


WRITE_DEFINITION = CoverGroupDef(
    "sbuffer_data_write",
    (
        CoverPointDef(
            "write_shape",
            {
                "single_byte": Bin.values("single_byte"),
                "byte_range": Bin.values("byte_range"),
                "scattered": Bin.values("scattered"),
                "full_lane": Bin.values("full_lane"),
                "no_bytes": Bin.values("no_bytes"),
                "wline_zero": Bin.values("wline_zero"),
                "wline_payload": Bin.values("wline_payload"),
            },
            description="写请求粒度形态：单字节、连续区间、散布字节、整 16B lane、空掩码、整行写（零/非零载荷）。",
        ),
        CoverPointDef(
            "byte_lane",
            {
                **{str(index): Bin.values(index) for index in range(BYTES)},
                "not_applicable": Bin.ignore(Bin.values(NOT_APPLICABLE)),
            },
            description="mask 的每一位独立选择 16B lane 内的一个字节位置。",
        ),
        CoverPointDef(
            "write_line_slot",
            {str(index): Bin.values(index) for index in range(LINES)},
            description="16 个 Store Buffer 行槽都能被写请求独立选中并保存数据。",
        ),
        CoverPointDef(
            "lane_slot",
            {str(index): Bin.values(index) for index in range(LANES)},
            description="vwordOffset 低 2 位选择的 4 个 16B lane 都是独立存储窗口。",
        ),
        CoverPointDef(
            "port_usage",
            {
                "single": Bin.values("single"),
                "dual_disjoint_lines": Bin.values("dual_disjoint_lines"),
                "dual_same_line_other_lane": Bin.values("dual_same_line_other_lane"),
                "dual_same_lane_disjoint_bytes": Bin.values("dual_same_lane_disjoint_bytes"),
                "dual_same_byte_overlap": Bin.values("dual_same_byte_overlap"),
            },
            description="单端口、双端口异行、同行异 lane、同 lane 不重叠字节，以及同字节重叠时的端口优先级。",
        ),
        CoverPointDef(
            "offset_alias",
            {
                "low_or_zero": Bin.values("low_or_zero"),
                "high_bits_ignored": Bin.values("high_bits_ignored"),
            },
            description="lane 选择只使用 vwordOffset 低 2 位，高位页码不改变目标 lane。",
        ),
    ),
    (
        CrossDef(
            "write_line_x_lane",
            ("write_line_slot", "lane_slot"),
            description="16 行 × 4 个 16B lane 的存储窗口两两独立，共 64 种组合。",
        ),
    ),
    description="SbufferData 写路径：按字节掩码 merge、整行广播、行/lane 选择与双端口并发。",
)

FLUSH_DEFINITION = CoverGroupDef(
    "sbuffer_data_flush",
    (
        CoverPointDef(
            "flush_extent",
            {
                "single_line": Bin.values("single_line"),
                "two_lines": Bin.values("two_lines"),
                "three_lines": Bin.values("three_lines"),
                "many_lines": Bin.values("many_lines"),
                "all_lines": Bin.values("all_lines"),
            },
            description="清理是行级位图：单行、双行、三行、多行和全部 16 行都能同拍清理。",
        ),
        CoverPointDef(
            "flush_line_slot",
            {str(index): Bin.values(index) for index in range(LINES)},
            description="16 个行槽都能被 DCache 命中清理独立选中并清空 mask。",
        ),
        CoverPointDef(
            "flush_concurrency",
            {
                "flush_only": Bin.values("flush_only"),
                "with_write_same_line": Bin.values("with_write_same_line"),
                "with_write_other_line": Bin.values("with_write_other_line"),
            },
            description="清理单独发生、与同行写同拍、与其它行写同拍三种并发关系。",
        ),
    ),
    description="SbufferData 清理路径：按行清 mask、保数据、多行位图与写并发。",
)

RESET_DEFINITION = CoverGroupDef(
    "sbuffer_data_reset",
    (
        CoverPointDef(
            "reset_context",
            {
                "reset_idle": Bin.values("reset_idle"),
                "reset_pending_write": Bin.values("reset_pending_write"),
                "reset_with_flush": Bin.values("reset_with_flush"),
            },
            description="复位在空闲、在途写、以及与清理同拍三种上下文中的行为。",
        ),
    ),
    description="SbufferData 复位：清空全部 mask，并取消在途写。",
)

IDLE_DEFINITION = CoverGroupDef(
    "sbuffer_data_idle",
    (
        CoverPointDef(
            "idle_context",
            {
                "after_write": Bin.values("after_write"),
                "after_flush": Bin.values("after_flush"),
                "after_reset": Bin.values("after_reset"),
            },
            description="写后、清理后、复位后的空闲拍输出保持，不发生自发变化。",
        ),
    ),
    description="SbufferData 空闲保持：无请求时 dataOut/maskOut 不变化。",
)


class SbufferDataCoverage:
    def __init__(self) -> None:
        self.write = WRITE_DEFINITION.instantiate("sbuffer_data.write")
        self.flush = FLUSH_DEFINITION.instantiate("sbuffer_data.flush")
        self.reset = RESET_DEFINITION.instantiate("sbuffer_data.reset")
        self.idle = IDLE_DEFINITION.instantiate("sbuffer_data.idle")

    def sample_op(self, writes: tuple[WriteRequest, ...], flush: int | None) -> None:
        port_usage = classify_port_usage(writes) if writes else None
        for req in writes:
            shape = classify_write_shape(req)
            alias = "high_bits_ignored" if req.vword_offset >> 2 else "low_or_zero"
            for line in selected_lines(req.wvec):
                lanes = range(LANES) if req.wline else (req.lane,)
                for lane in lanes:
                    self.write.sample(
                        {
                            "write_shape": shape,
                            "byte_lane": (
                                req.mask.bit_length() - 1
                                if shape == "single_byte"
                                else NOT_APPLICABLE
                            ),
                            "write_line_slot": line,
                            "lane_slot": lane,
                            "port_usage": port_usage,
                            "offset_alias": alias,
                        },
                        details=False,
                    )
        if flush is not None:
            extent = classify_flush_extent(flush)
            concurrency = classify_flush_concurrency(flush, writes)
            for line in selected_lines(flush):
                self.flush.sample(
                    {
                        "flush_extent": extent,
                        "flush_line_slot": line,
                        "flush_concurrency": concurrency,
                    },
                    details=False,
                )

    def sample_reset(self, context: str) -> None:
        self.reset.sample({"reset_context": context}, details=False)

    def sample_idle(self, context: str) -> None:
        self.idle.sample({"idle_context": context}, details=False)
