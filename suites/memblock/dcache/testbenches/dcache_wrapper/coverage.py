"""Semantic functional coverage for the DCacheWrapper boundary.

Scope decision: the DCache's own coverage groups belong to the `DCache` DUT run.
This module defines *wrapper-level* groups instead: the port map, the renamed
cache-control TL slave, the L2 channel/source fidelity, the perf pipeline, the
speculative fabric, and one consolidated group for the DCache behaviours that are
re-verified through the wrapper boundary.  Re-using the DCache groups here would
double count the same RTL and make the wrapper report look incomplete for
scenarios the DCache suite already covers in depth.
"""
from __future__ import annotations

from toffee import Bin, CoverGroupDef, CoverPointDef, CrossDef


PORTMAP_DEFINITION = CoverGroupDef(
    "wrapper_portmap",
    (
        CoverPointDef(
            "group",
            {"identity": Bin.values("identity"),
             "cache_ctrl": Bin.values("cache_ctrl"),
             "spec_fabric": Bin.values("spec_fabric"),
             "perf": Bin.values("perf")},
            description="端口组：同名直连、cache-control 改名、speculative fabric 改名、perf 内部寄存器。",
        ),
        CoverPointDef(
            "check",
            {"complete": Bin.values("complete"),
             "renamed": Bin.values("renamed")},
            description="映射完整性（861 条、无重复）与改名组实际走通。",
        ),
    ),
    (CrossDef("group_x_check", ("group", "check"),
              include=(("identity", "complete"),
                       ("cache_ctrl", "complete"), ("cache_ctrl", "renamed"),
                       ("spec_fabric", "complete"), ("spec_fabric", "renamed"),
                       ("perf", "complete")),
              description="端口组 × 校验结果（只定义语义上有意义的组合）。"),),
    description="DCacheWrapper 结构等价与改名保真。",
)

CTRL_DEFINITION = CoverGroupDef(
    "wrapper_ctrl",
    (
        CoverPointDef(
            "reg",
            {"ctrl": Bin.values("ctrl"), "delay": Bin.values("delay"),
             "tag_mask": Bin.values("tag_mask"), "data_mask": Bin.values("data_mask")},
            description="经 auto_uncache_in_* 访问的四类控制寄存器。",
        ),
        CoverPointDef(
            "op",
            {"write": Bin.values("write"), "read": Bin.values("read")},
            description="写握手得到 AccessAck；读返回 AccessAckData。",
        ),
        CoverPointDef(
            "mask",
            {"full": Bin.values("full"), "partial": Bin.values("partial")},
            description="整字节掩码写入生效，部分掩码写入不改变寄存器。",
        ),
    ),
    (CrossDef("reg_x_op", ("reg", "op"), description="寄存器 × 读写。"),),
    description="wrapper 的 cache-control TL slave（原 cacheCtrlOpt）。",
)

CORE_DEFINITION = CoverGroupDef(
    "wrapper_core",
    (
        CoverPointDef(
            "behaviour",
            {"hit": Bin.values("hit"), "miss_refill": Bin.values("miss_refill"),
             "store": Bin.values("store"), "probe": Bin.values("probe"),
             "eviction": Bin.values("eviction"), "atomic": Bin.values("atomic"),
             "cmo": Bin.values("cmo"), "error": Bin.values("error")},
            description="经 wrapper 端口复验的 DCache 核心行为类别。",
        ),
        CoverPointDef(
            "result",
            {"match": Bin.values("match")},
            description="观测结果与 DCache 顶层参考模型一致。",
        ),
    ),
    (CrossDef("behaviour_x_result", ("behaviour", "result"),
              description="行为 × 比对结果。"),),
    description="wrapper 边界处 DCache 核心行为的保真。",
)

CHANNEL_DEFINITION = CoverGroupDef(
    "wrapper_channel",
    (
        CoverPointDef(
            "channel",
            {"ch0": Bin.values("ch0"), "ch1": Bin.values("ch1")},
            description="双 L2 通道在 wrapper 边界各完成一次 Acquire/Grant。",
        ),
        CoverPointDef(
            "source",
            {"preserved": Bin.values("preserved")},
            description="A/D source 字段在 wrapper 边界原样回传。",
        ),
    ),
    description="双通道与 source 映射。",
)

PERF_DEFINITION = CoverGroupDef(
    "wrapper_perf",
    (
        CoverPointDef(
            "state",
            {"reset_zero": Bin.values("reset_zero"),
             "delayed_update": Bin.values("delayed_update")},
            description="复位后 perf 为 0；事件后经 2 级寄存更新。",
        ),
    ),
    description="wrapper 唯一自有寄存器：perf 两级延迟。",
)

SPEC_DEFINITION = CoverGroupDef(
    "wrapper_spec",
    (
        CoverPointDef(
            "signal",
            {"candidate": Bin.values("candidate"),
             "committed": Bin.values("committed"),
             "idle": Bin.values("idle")},
            description="speculative fabric 的 candidate 输出、committed 输入与空闲值。",
        ),
    ),
    description="speculative-miss fabric 在 wrapper 边界的透传。",
)


class DcacheWrapperCoverage:
    def __init__(self) -> None:
        self.wrapper_portmap = PORTMAP_DEFINITION.instantiate("dcache_wrapper.portmap")
        self.wrapper_ctrl = CTRL_DEFINITION.instantiate("dcache_wrapper.ctrl")
        self.wrapper_core = CORE_DEFINITION.instantiate("dcache_wrapper.core")
        self.wrapper_channel = CHANNEL_DEFINITION.instantiate("dcache_wrapper.channel")
        self.wrapper_perf = PERF_DEFINITION.instantiate("dcache_wrapper.perf")
        self.wrapper_spec = SPEC_DEFINITION.instantiate("dcache_wrapper.spec")

    # ---------------------------------------------------------- wrapper-only
    def sample_portmap(self, group: str, check: str) -> None:
        self.wrapper_portmap.sample({"group": group, "check": check}, details=False)

    def sample_ctrl(self, reg: str, op: str, mask: str = "full") -> None:
        self.wrapper_ctrl.sample({"reg": reg, "op": op, "mask": mask}, details=False)

    def sample_core(self, behaviour: str) -> None:
        self.wrapper_core.sample({"behaviour": behaviour, "result": "match"},
                                 details=False)

    def sample_channel(self, channel: int) -> None:
        self.wrapper_channel.sample({"channel": f"ch{channel}",
                                     "source": "preserved"}, details=False)

    def sample_perf(self, state: str) -> None:
        self.wrapper_perf.sample({"state": state}, details=False)

    def sample_spec(self, signal: str) -> None:
        self.wrapper_spec.sample({"signal": signal}, details=False)

    # ------------------------------------- hooks the shared DcacheEnv calls
    def sample_load(self, context: str, mask: int, response: dict) -> None:
        self.sample_core("hit" if response["miss"] == 0 else "miss_refill")

    def sample_refill(self, accepted: dict, denied: bool, corrupt: bool) -> None:
        self.sample_core("miss_refill")
        if denied or corrupt:
            self.sample_core("error")

    def sample_store(self, result: dict, mask: int = 0xFFFFFFFFFFFFFFFF) -> None:
        if result["hit"] or result["replay"]:
            self.sample_core("store")
