"""Semantic functional coverage for MainPipe."""
from __future__ import annotations

from toffee import Bin, CoverGroupDef, CoverPointDef, CrossDef


STORE_DEFINITION = CoverGroupDef(
    "mp_store",
    (
        CoverPointDef(
            "outcome",
            {
                "hit": Bin.values("hit"),
                "miss_accepted": Bin.values("miss_accepted"),
                "replay": Bin.values("replay"),
            },
            description="store 命中写回、miss 被 miss queue 接收、miss queue 反压导致 replay。",
        ),
        CoverPointDef(
            "mask",
            {
                "word": Bin.values("word"),
                "partial": Bin.values("partial"),
                "line": Bin.values("line"),
            },
            description="8 字节字写、部分字节掩码、整行 64B 写。",
        ),
        CoverPointDef(
            "meta_update",
            {
                "none": Bin.values("none"),
                "to_dirty": Bin.values("to_dirty"),
            },
            description="命中时 coh 状态不变（已是 Dirty）或从 Trunk 升到 Dirty。",
        ),
    ),
    (CrossDef("outcome_x_mask", ("outcome", "mask"),
              description="store 结果 × 掩码形态。"),),
    description="MainPipe store 路径。",
)

ATOMIC_DEFINITION = CoverGroupDef(
    "mp_atomic",
    (
        CoverPointDef(
            "op",
            {"swap": Bin.values("swap"), "add": Bin.values("add")},
            description="AMO swap 与 AMO add 的读-改-写语义。",
        ),
        CoverPointDef(
            "outcome",
            {
                "hit": Bin.values("hit"),
                "miss": Bin.values("miss"),
                "miss_replay": Bin.values("miss_replay"),
            },
            description="AMO 命中回写、miss 送入 miss queue、miss queue 反压 replay。",
        ),
        CoverPointDef(
            "mask",
            {"full_word": Bin.values("full_word"), "partial": Bin.values("partial")},
            description="AMO 字节掩码：整个 8 字节字或部分字节。",
        ),
    ),
    (CrossDef("op_x_outcome", ("op", "outcome"),
              description="AMO 运算 × 命中/miss。"),),
    description="MainPipe atomic 路径。",
)

PROBE_DEFINITION = CoverGroupDef(
    "mp_probe",
    (
        CoverPointDef(
            "param",
            {"toT": Bin.values("toT"), "toB": Bin.values("toB"),
             "toN": Bin.values("toN")},
            description="probe 要求的权限目标：TtoT/TtoB/TtoN。",
        ),
        CoverPointDef(
            "new_coh",
            {"trunk": Bin.values("trunk"), "branch": Bin.values("branch"),
             "nothing": Bin.values("nothing")},
            description="probe 之后缓存的 coh 状态。",
        ),
        CoverPointDef(
            "data",
            {"with_data": Bin.values("with_data"),
             "without_data": Bin.values("without_data")},
            description="降级时是否把整行数据写回 C 通道。",
        ),
        CoverPointDef(
            "hit",
            {"hit": Bin.values("hit"), "miss": Bin.values("miss")},
            description="probe 命中缓存行或该行不在缓存中。",
        ),
    ),
    description="MainPipe probe 路径。",
)

REFILL_DEFINITION = CoverGroupDef(
    "mp_refill",
    (
        CoverPointDef(
            "kind",
            {"load": Bin.values("load"), "store": Bin.values("store"),
             "amo": Bin.values("amo")},
            description="load miss refill（Trunk）、store miss refill（Dirty）与 AMO miss 的 refill 完成（Dirty）。",
        ),
        CoverPointDef(
            "slot",
            {str(way): Bin.values(way) for way in range(4)},
            description="refill 落到 replacer 选出的 way。",
        ),
        CoverPointDef(
            "error",
            {"clean": Bin.values("clean"), "denied": Bin.values("denied"),
             "corrupt": Bin.values("corrupt")},
            description="refill 正常、denied、corrupt 三种错误标记。",
        ),
    ),
    (CrossDef("slot_x_error", ("slot", "error"),
              description="refill way × 错误类型。"),),
    description="MainPipe refill 写回路径。",
)

PREFETCH_DEFINITION = CoverGroupDef(
    "mp_prefetch",
    (
        CoverPointDef(
            "outcome",
            {"hit": Bin.values("hit"), "miss": Bin.values("miss")},
            description="prefetch 命中已有行或产生 prefetch miss。",
        ),
        CoverPointDef(
            "source",
            {str(source): Bin.values(str(source)) for source in range(8)},
            description="prefetch 来源编号随 refill 写入 prefetch flag。",
        ),
    ),
    description="MainPipe prefetch 路径。",
)

LRSC_DEFINITION = CoverGroupDef(
    "mp_lrsc",
    (
        CoverPointDef(
            "op",
            {"lr": Bin.values("lr"), "sc": Bin.values("sc")},
            description="LR 建立保留集、SC 条件写。",
        ),
        CoverPointDef(
            "reservation",
            {"valid": Bin.values("valid"), "invalid": Bin.values("invalid"),
             "cleared": Bin.values("cleared")},
            description="SC 时保留集有效/从未建立/已被 invalid_resv_set 清除。",
        ),
        CoverPointDef(
            "outcome",
            {"write": Bin.values("write"), "no_write": Bin.values("no_write")},
            description="SC 成功后写回、SC 失败不写。",
        ),
    ),
    description="LR/SC 保留集路径。",
)

CAS_DEFINITION = CoverGroupDef(
    "mp_amo_cas",
    (
        CoverPointDef(
            "width",
            {"b": Bin.values("b"), "h": Bin.values("h"), "w": Bin.values("w"),
             "d": Bin.values("d"), "q": Bin.values("q")},
            description="AMOCAS 比较宽度：1/2/4/8/16 字节。",
        ),
        CoverPointDef(
            "result",
            {"match": Bin.values("match"), "mismatch": Bin.values("mismatch")},
            description="比较值命中（写回 ama_data）或不命中（保持原值）。",
        ),
        CoverPointDef(
            "outcome",
            {"hit": Bin.values("hit"), "miss": Bin.values("miss")},
            description="CAS 命中缓存行或转入 miss queue。",
        ),
    ),
    (CrossDef("width_x_result", ("width", "result"),
              description="比较宽度 × 匹配结果。"),),
    description="AMO compare-and-swap 路径。",
)

EVICTION_DEFINITION = CoverGroupDef(
    "mp_refill_evict",
    (
        CoverPointDef(
            "coh",
            {"dirty": Bin.values("dirty"), "trunk": Bin.values("trunk"),
             "branch": Bin.values("branch"), "nothing": Bin.values("nothing")},
            description="refill 替换出去的 victim 行权限：脏行必须走 C 通道释放，无效行不释放。",
        ),
        CoverPointDef(
            "wb",
            {"release_with_data": Bin.values("release_with_data"),
             "release_without_data": Bin.values("release_without_data"),
             "no_release": Bin.values("no_release")},
            description="victim 被替换时是否生成 Release 以及是否带数据。",
        ),
    ),
    description="refill 替换时 victim 行的写回。",
)

FLAG_ERROR_DEFINITION = CoverGroupDef(
    "mp_flag_error",
    (
        CoverPointDef(
            "kind",
            {"denied": Bin.values("denied"), "corrupt": Bin.values("corrupt")},
            description="extra meta（prefetch/access 标志）中的 denied/corrupt 错误。",
        ),
        CoverPointDef(
            "report",
            {"l2": Bin.values("l2")},
            description="flag 错误走 L2/CSR 标记路径（report_to_beu=0），不进入 ECC 的 BEU 路径。",
        ),
    ),
    description="extra meta/flag 错误上报。",
)

ECC_DEFINITION = CoverGroupDef(
    "mp_ecc_error",
    (
        CoverPointDef(
            "kind",
            {"tag": Bin.values("tag"), "data": Bin.values("data")},
            description="tag ECC 与 bank data ECC 错误。",
        ),
        CoverPointDef(
            "report",
            {"beu": Bin.values("beu")},
            description="ECC 错误上报 BEU，并标记写回数据 corrupt。",
        ),
    ),
    description="MainPipe ECC 错误上报。",
)

ADDRESS_DEFINITION = CoverGroupDef(
    "mp_address",
    (
        CoverPointDef(
            "set_class",
            {"zero": Bin.values("zero"), "low": Bin.values("low"),
             "high": Bin.values("high"), "max": Bin.values("max")},
            description="tag/meta 读索引覆盖 set 0/低位/高位/255。",
        ),
        CoverPointDef(
            "way",
            {str(way): Bin.values(way) for way in range(4)},
            description="命中 way 0..3 与 refill way 0..3。",
        ),
    ),
    (CrossDef("set_x_way", ("set_class", "way"),
              description="set 区间 × way。"),),
    description="MainPipe 地址分解与 way 选择。",
)


def mask_class(mask: int) -> str:
    if mask == 0xFFFFFFFFFFFFFFFF:
        return "line"
    if (mask & 0xFFFFFFFFFFFFFFFF) == 0xFF:
        return "word"
    return "partial"


def set_class(index: int) -> str:
    if index == 0:
        return "zero"
    if index == 255:
        return "max"
    if index < 128:
        return "low"
    return "high"


class MainPipeCoverage:
    def __init__(self) -> None:
        self.store = STORE_DEFINITION.instantiate("main_pipe.store")
        self.atomic = ATOMIC_DEFINITION.instantiate("main_pipe.atomic")
        self.probe = PROBE_DEFINITION.instantiate("main_pipe.probe")
        self.refill = REFILL_DEFINITION.instantiate("main_pipe.refill")
        self.prefetch = PREFETCH_DEFINITION.instantiate("main_pipe.prefetch")
        self.lrsc = LRSC_DEFINITION.instantiate("main_pipe.lrsc")
        self.cas = CAS_DEFINITION.instantiate("main_pipe.amo_cas")
        self.eviction = EVICTION_DEFINITION.instantiate("main_pipe.refill_evict")
        self.flag_error = FLAG_ERROR_DEFINITION.instantiate("main_pipe.flag_error")
        self.ecc = ECC_DEFINITION.instantiate("main_pipe.ecc")
        self.address = ADDRESS_DEFINITION.instantiate("main_pipe.address")

    def sample_address(self, index: int, way: int) -> None:
        self.address.sample({"set_class": set_class(index), "way": way},
                            details=False)

    def sample_store(self, outcome: str, mask: int, meta_update: str,
                     index: int, way: int) -> None:
        self.store.sample({"outcome": outcome, "mask": mask_class(mask),
                           "meta_update": meta_update}, details=False)
        self.sample_address(index, way)

    def sample_atomic(self, op: str, outcome: str, mask: int) -> None:
        self.atomic.sample({"op": op, "outcome": outcome,
                            "mask": "full_word" if (mask & 0xFF) == 0xFF
                            else "partial"}, details=False)

    def sample_probe(self, param: int, new_coh: str, dirty_data: bool,
                     hit: bool) -> None:
        self.probe.sample({"param": {0: "toT", 1: "toB", 2: "toN"}.get(param, "toT"),
                           "new_coh": new_coh,
                           "data": "with_data" if dirty_data else "without_data",
                           "hit": "hit" if hit else "miss"}, details=False)

    def sample_refill(self, kind: str, way: int, error: str,
                      index: int) -> None:
        self.refill.sample({"kind": kind, "slot": way, "error": error},
                           details=False)
        self.sample_address(index, way)

    def sample_lrsc(self, op: str, reservation: str, wrote: bool) -> None:
        self.lrsc.sample({"op": op, "reservation": reservation,
                          "outcome": "write" if wrote else "no_write"},
                         details=False)

    def sample_cas(self, cmd: int, match: bool, outcome: str = "hit") -> None:
        width = {0x18: "q", 0x1A: "w", 0x1B: "d", 0x1C: "h", 0x1D: "b"}[cmd]
        self.cas.sample({"width": width,
                         "result": "match" if match else "mismatch",
                         "outcome": outcome}, details=False)

    def sample_eviction(self, coh: int, tag_match: bool) -> None:
        if tag_match:
            return
        name = {3: "dirty", 2: "trunk", 1: "branch", 0: "nothing"}.get(coh, "trunk")
        if coh == 0:
            wb = "no_release"
        elif coh == 3:
            wb = "release_with_data"
        else:
            wb = "release_without_data"
        self.eviction.sample({"coh": name, "wb": wb}, details=False)

    def sample_ecc(self, kind: str) -> None:
        self.ecc.sample({"kind": kind, "report": "beu"}, details=False)

    def sample_flag_error(self, kind: str) -> None:
        self.flag_error.sample({"kind": kind, "report": "l2"}, details=False)

    def sample_prefetch(self, hit: bool, source: int) -> None:
        self.prefetch.sample({"outcome": "hit" if hit else "miss",
                              "source": str(source)}, details=False)
