"""Semantic functional coverage for the MissQueue."""
from __future__ import annotations

from toffee import Bin, CoverGroupDef, CoverPointDef, CrossDef


ALLOC_DEFINITION = CoverGroupDef(
    "mq_alloc",
    (
        CoverPointDef(
            "kind",
            {"load": Bin.values("load"), "store": Bin.values("store"),
             "store_full": Bin.values("store_full"), "amo": Bin.values("amo")},
            description="load miss（AcquireBlock）、store 部分写、store 整行写（AcquirePerm）与 AMO miss。",
        ),
        CoverPointDef(
            "channel",
            {"0": Bin.values(0), "1": Bin.values(1)},
            description="按块地址选择 L2 通道 0/1。",
        ),
        CoverPointDef(
            "port",
            {"mainpipe": Bin.values("mainpipe"), "loadpipe": Bin.values("loadpipe")},
            description="请求来自 MainPipe（queryMQ 0）或 LoadPipe（queryMQ 1-3）。",
        ),
    ),
    (CrossDef("kind_x_channel", ("kind", "channel"),
              description="miss 类型 × L2 通道。"),),
    description="MSHR 分配与 Acquire 发起。",
)

MERGE_DEFINITION = CoverGroupDef(
    "mq_merge",
    (
        CoverPointDef(
            "window",
            {"before_grant": Bin.values("before_grant"),
             "after_grant": Bin.values("after_grant")},
            description="同一块的新请求在首个 refill beat 之前可合并，之后被拒绝。",
        ),
        CoverPointDef(
            "same_alias",
            {"match": Bin.values("match"), "mismatch": Bin.values("mismatch")},
            description="合并要求 tag 相同且虚拟地址 alias 一致。",
        ),
    ),
    (CrossDef("window_x_alias", ("window", "same_alias"),
              description="合并窗口 × alias 一致性。"),),
    description="MSHR 合并判定。",
)

REFILL_DEFINITION = CoverGroupDef(
    "mq_refill",
    (
        CoverPointDef(
            "beats",
            {"two_beats": Bin.values("two_beats")},
            description="64B 行由两个 32B GrantData beat 组成，顺序与地址一致。",
        ),
        CoverPointDef(
            "install",
            {"mainpipe": Bin.values("mainpipe")},
            description="refill 完成后向 MainPipe 发出 line install 请求。",
        ),
        CoverPointDef(
            "error",
            {"clean": Bin.values("clean"), "denied": Bin.values("denied"),
             "corrupt": Bin.values("corrupt")},
            description="refill 无错误 / denied / corrupt。",
        ),
    ),
    (CrossDef("beats_x_error", ("beats", "error"),
              description="refill beat 数与错误类型。"),),
    description="refill 数据汇聚与向 MainPipe 安装。",
)

RELEASE_DEFINITION = CoverGroupDef(
    "mq_release",
    (
        CoverPointDef(
            "finish",
            {"sent": Bin.values("sent")},
            description="Acquire 的 Finish 握手（sink 回传）。",
        ),
        CoverPointDef(
            "reuse",
            {"slot0": Bin.values("slot0"), "slot1": Bin.values("slot1"),
             "other": Bin.values("other")},
            description="完成后释放的 MSHR 槽位被后续 miss 重新分配。",
        ),
    ),
    description="MSHR 完成、Finish 与槽位复用。",
)

BLOCK_DEFINITION = CoverGroupDef(
    "mq_block",
    (
        CoverPointDef(
            "probe",
            {"hit": Bin.values("hit"), "miss": Bin.values("miss")},
            description="probe 的块地址与 in-flight MSHR 相同时阻止 probe（block=1）。",
        ),
        CoverPointDef(
            "replace",
            {"hit": Bin.values("hit"), "miss": Bin.values("miss")},
            description="replace 的块地址与 in-flight MSHR 相同时阻止替换。",
        ),
    ),
    description="in-flight MSHR 对 probe/replace 的阻塞。",
)

CMO_DEFINITION = CoverGroupDef(
    "mq_cmo",
    (
        CoverPointDef(
            "opcode",
            {"clean": Bin.values("clean"), "flush": Bin.values("flush"),
             "inval": Bin.values("inval")},
            description="cbo.clean / cbo.flush / cbo.inval 分别映射到 A 通道 12/13/14。",
        ),
        CoverPointDef(
            "channel",
            {"0": Bin.values(0), "1": Bin.values(1)},
            description="CMO 按块地址 bit6 选择 L2 通道。",
        ),
        CoverPointDef(
            "resp",
            {"ok": Bin.values("ok"), "denied": Bin.values("denied"),
             "corrupt": Bin.values("corrupt")},
            description="D 通道 CBOAck 的 denied/corrupt 回传到 LSQ。",
        ),
    ),
    (CrossDef("opcode_x_resp", ("opcode", "resp"),
              description="CMO 操作 × 响应状态。"),),
    description="CMO 请求与响应。",
)

STORE_FLAG_DEFINITION = CoverGroupDef(
    "mq_store_flag",
    (
        CoverPointDef(
            "state",
            {"empty": Bin.values("empty"), "pending": Bin.values("pending")},
            description="mshr_store_empty 在无 store miss 时为 1，有 store miss 时为 0。",
        ),
    ),
    description="store miss 占用标志。",
)


def miss_kind(cmd: int, full_overwrite: bool) -> str:
    if cmd in (4, 8, 9, 10, 11, 12, 13, 14, 15, 24, 26, 27, 28, 29):
        return "amo"
    if cmd in (1, 17):
        return "store_full" if full_overwrite else "store"
    return "load"


class MissQueueCoverage:
    def __init__(self) -> None:
        self.alloc = ALLOC_DEFINITION.instantiate("miss_queue.alloc")
        self.merge = MERGE_DEFINITION.instantiate("miss_queue.merge")
        self.refill = REFILL_DEFINITION.instantiate("miss_queue.refill")
        self.release = RELEASE_DEFINITION.instantiate("miss_queue.release")
        self.block = BLOCK_DEFINITION.instantiate("miss_queue.block")
        self.cmo = CMO_DEFINITION.instantiate("miss_queue.cmo")
        self.store_flag = STORE_FLAG_DEFINITION.instantiate("miss_queue.store_flag")

    def sample_alloc(self, cmd: int, full_overwrite: bool, channel: int,
                     port: int) -> None:
        kind = miss_kind(cmd, full_overwrite)
        self.alloc.sample({"kind": kind, "channel": channel,
                           "port": "mainpipe" if port == 0 else "loadpipe"},
                          details=False)

    def sample_merge(self, before_grant: bool, alias_match: bool) -> None:
        self.merge.sample({
            "window": "before_grant" if before_grant else "after_grant",
            "same_alias": "match" if alias_match else "mismatch",
        }, details=False)

    def sample_refill(self, error: str) -> None:
        self.refill.sample({"beats": "two_beats", "install": "mainpipe",
                            "error": error}, details=False)

    def sample_release(self, released_id: int) -> None:
        slot = "slot0" if released_id == 0 else "slot1" if released_id == 1 else "other"
        self.release.sample({"finish": "sent", "reuse": slot}, details=False)

    def sample_block(self, probe_hit: bool, replace_hit: bool) -> None:
        self.block.sample({"probe": "hit" if probe_hit else "miss",
                           "replace": "hit" if replace_hit else "miss"},
                          details=False)

    def sample_cmo(self, opcode: int, channel: int,
                   resp: str) -> None:
        name = {0: "clean", 1: "flush", 2: "inval"}.get(opcode, "clean")
        self.cmo.sample({"opcode": name, "channel": channel, "resp": resp},
                        details=False)

    def sample_store_flag(self, empty: bool) -> None:
        self.store_flag.sample({"state": "empty" if empty else "pending"},
                               details=False)
