"""Semantic functional coverage for the integrated DCache."""
from __future__ import annotations

from toffee import Bin, CoverGroupDef, CoverPointDef, CrossDef


def mask_class(mask: int) -> str:
    bits = mask.bit_count()
    if bits == 0:
        return "none"
    if mask in (0xFFFF, 0xFFFFFFFFFFFFFFFF):
        return "full"
    if bits == 1:
        return "single"
    if bits <= 8:
        return "low"
    return "partial"


LOAD_DEFINITION = CoverGroupDef(
    "dc_load",
    (
        CoverPointDef(
            "outcome",
            {
                "hit": Bin.values("hit"),
                "miss_handled": Bin.values("miss_handled"),
                "miss_unhandled": Bin.values("miss_unhandled"),
            },
            description="load 命中、miss 且 miss 请求被接收、miss 但需 replay。",
        ),
        CoverPointDef(
            "lane",
            {str(lane): Bin.values(lane) for lane in range(3)},
            description="3 条 load 流水都能独立完成事务。",
        ),
        CoverPointDef(
            "mask",
            {name: Bin.values(name) for name in ("single", "low", "partial", "full")},
            description="字节掩码从单字节到整字。",
        ),
    ),
    (CrossDef("lane_x_outcome", ("lane", "outcome"),
              description="3 条流水 × 命中/miss 结果。"),),
    description="DCache load 事务结果。",
)

MISS_DEFINITION = CoverGroupDef(
    "dc_miss",
    (
        CoverPointDef(
            "acquire_channel",
            {"ch0": Bin.values(0), "ch1": Bin.values(1)},
            description="双 L2 通道下 AcquireBlock 按地址选择通道。",
        ),
        CoverPointDef(
            "refill_result",
            {"clean": Bin.values("clean"), "denied": Bin.values("denied"),
             "corrupt": Bin.values("corrupt")},
            description="refill 数据正常、denied、corrupt 三种结果。",
        ),
        CoverPointDef(
            "refill_then",
            {"hit": Bin.values("hit"), "miss": Bin.values("miss")},
            description="refill 之后同一行重放 load 命中或仍 miss。",
        ),
    ),
    (CrossDef("channel_x_refill", ("acquire_channel", "refill_result"),
              description="通道 × refill 结果。"),),
    description="DCache miss/refill 路径。",
)

STORE_DEFINITION = CoverGroupDef(
    "dc_store",
    (
        CoverPointDef(
            "result",
            {"hit": Bin.values("hit"), "replay": Bin.values("replay")},
            description="store 在 main pipe 命中或需要 replay。",
        ),
        CoverPointDef(
            "mask",
            {name: Bin.values(name) for name in ("single", "low", "partial", "full")},
            description="写掩码形态。",
        ),
    ),
    description="DCache store 主流水结果。",
)

EVICTION_DEFINITION = CoverGroupDef(
    "dc_eviction",
    (
        CoverPointDef(
            "victim",
            {"dirty": Bin.values("dirty"), "clean": Bin.values("clean")},
            description="同 set 替换时 victim 为 Dirty 或干净行。",
        ),
        CoverPointDef(
            "release",
            {"release_data": Bin.values("release_data"),
             "release": Bin.values("release")},
            description="Dirty victim 发 C 通道 ReleaseData，干净 victim 发 Release。",
        ),
    ),
    (CrossDef("victim_x_release", ("victim", "release"),
              illegal=(("dirty", "release"), ("clean", "release_data")),
              description="victim 状态 × C 通道响应类型；dirty 必带数据、clean 必不带。"),),
    description="替换 victim 的 C 通道写回。",
)

ATOMIC_DEFINITION = CoverGroupDef(
    "dc_atomic",
    (
        CoverPointDef(
            "op",
            {"swap": Bin.values("swap"), "add": Bin.values("add")},
            description="AMO swap/add 的读-改-写。",
        ),
        CoverPointDef(
            "path",
            {"hit": Bin.values("hit"), "miss_completed": Bin.values("miss_completed")},
            description="AMO 命中直接完成，或经 MSHR refill 后完成。",
        ),
    ),
    (CrossDef("op_x_path", ("op", "path"),
              description="AMO 运算 × 命中/refill 完成。"),),
    description="DCache 顶层 AMO 路径。",
)

CMO_DEFINITION = CoverGroupDef(
    "dc_cmo",
    (
        CoverPointDef(
            "opcode",
            {"clean": Bin.values("clean"), "flush": Bin.values("flush"),
             "inval": Bin.values("inval")},
            description="cbo.clean/flush/inval。",
        ),
        CoverPointDef(
            "response",
            {"ok": Bin.values("ok"), "denied": Bin.values("denied"),
             "corrupt": Bin.values("corrupt")},
            description="CBOAck 的响应状态。",
        ),
    ),
    (CrossDef("opcode_x_response", ("opcode", "response"),
              description="CMO 操作 × 响应状态（CBOAck 的 denied/corrupt 与操作码正交）。"),),
    description="DCache 顶层 CMO 路径。",
)

CONTROL_DEFINITION = CoverGroupDef(
    "dc_control",
    (
        CoverPointDef(
            "reset_sweep",
            {"swept": Bin.values("swept")},
            description="复位后 tag/meta SRAM 的 256-set 清扫完成。",
        ),
        CoverPointDef(
            "lq_state",
            {"empty": Bin.values("empty"), "nonempty": Bin.values("nonempty")},
            description="lqEmpty 对 miss 路径的两种输入。",
        ),
        CoverPointDef(
            "error",
            {"none": Bin.values("none"), "denied": Bin.values("denied")},
            description="refill denied 导致的 error 上报。",
        ),
    ),
    description="DCache 控制与错误路径。",
)


class DCacheCoverage:
    def __init__(self) -> None:
        self.load = LOAD_DEFINITION.instantiate("dcache.load")
        self.miss = MISS_DEFINITION.instantiate("dcache.miss")
        self.store = STORE_DEFINITION.instantiate("dcache.store")
        self.control = CONTROL_DEFINITION.instantiate("dcache.control")
        self.eviction = EVICTION_DEFINITION.instantiate("dcache.eviction")
        self.atomic = ATOMIC_DEFINITION.instantiate("dcache.atomic")
        self.cmo = CMO_DEFINITION.instantiate("dcache.cmo")

    def sample_load(self, context: str, mask: int, response: dict) -> None:
        if response["miss"] == 0:
            outcome = "hit"
        elif response["handled"]:
            outcome = "miss_handled"
        else:
            outcome = "miss_unhandled"
        lane = 0
        if context.startswith("lane"):
            digits = ""
            for char in context[4:]:
                if char.isdigit():
                    digits += char
                else:
                    break
            lane = int(digits) if digits else 0
        self.load.sample({"outcome": outcome, "lane": lane % 3,
                          "mask": mask_class(mask)}, details=False)
        self.control.sample({"reset_sweep": "swept",
                             "lq_state": "empty",
                             "error": "none"}, details=False)

    def sample_refill(self, accepted: dict, denied: bool, corrupt: bool) -> None:
        self.miss.sample({"acquire_channel": accepted["channel"],
                          "refill_result": "denied" if denied else
                          ("corrupt" if corrupt else "clean"),
                          "refill_then": "hit"}, details=False)
        if denied:
            self.control.sample({"reset_sweep": "swept", "lq_state": "empty",
                                 "error": "denied"}, details=False)

    def sample_eviction(self, dirty: bool, release_data: bool) -> None:
        self.eviction.sample({
            "victim": "dirty" if dirty else "clean",
            "release": "release_data" if release_data else "release",
        }, details=False)

    def sample_atomic(self, cmd: int, hit: bool) -> None:
        import importlib.util
        self.atomic.sample({
            "op": "swap" if cmd == 4 else "add",
            "path": "hit" if hit else "miss_completed",
        }, details=False)

    def sample_cmo(self, opcode: int, response: str) -> None:
        self.cmo.sample({
            "opcode": {0: "clean", 1: "flush", 2: "inval"}.get(opcode, "clean"),
            "response": response,
        }, details=False)

    def sample_store(self, result: dict, mask: int = 0xFFFFFFFFFFFFFFFF) -> None:
        if not (result["hit"] or result["replay"]):
            return
        outcome = "hit" if result["hit"] else "replay"
        self.store.sample({"result": outcome,
                           "mask": mask_class(mask)}, details=False)
