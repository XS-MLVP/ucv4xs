"""Semantic functional coverage for WritebackQueue."""
from __future__ import annotations

from toffee import Bin, CoverGroupDef, CoverPointDef, CrossDef

RELEASE_DEFINITION = CoverGroupDef(
    "wbq_release",
    (
        CoverPointDef(
            "kind",
            {
                "release_data": Bin.values("release_data"),
                "release": Bin.values("release"),
                "probe_ack": Bin.values("probe_ack"),
                "probe_ack_data": Bin.values("probe_ack_data"),
            },
            description="带数据写回、纯 Release、ProbeAck 与 ProbeAckData 四种 C 通道响应。",
        ),
        CoverPointDef(
            "channel",
            {"ch0": Bin.values(0), "ch1": Bin.values(1)},
            description="按地址 bit6 选择的双 L2 通道。",
        ),
        CoverPointDef(
            "voluntary",
            {"yes": Bin.values("yes"), "no": Bin.values("no")},
            description="主动让出与被动 probe 合并。",
        ),
    ),
    description="WritebackQueue C 通道响应。",
)

ACK_DEFINITION = CoverGroupDef(
    "wbq_ack",
    (
        CoverPointDef(
            "result",
            {"freed": Bin.values("freed"), "pending": Bin.values("pending")},
            description="ReleaseAck 后条目释放；未响应前保持占用。",
        ),
    ),
    description="WritebackQueue 条目生命周期。",
)

BLOCK_DEFINITION = CoverGroupDef(
    "wbq_block",
    (
        CoverPointDef(
            "match",
            {
                "same_block": Bin.values("same_block"),
                "other_block": Bin.values("other_block"),
            },
            description="miss 请求与该条目同块时被阻塞，其它块不受影响。",
        ),
    ),
    description="WritebackQueue 对 miss 请求的阻塞。",
)


def release_kind(opcode: int, has_data: bool) -> str:
    if opcode == 7:
        return "release_data"
    if opcode == 6:
        return "release"
    if opcode == 5:
        return "probe_ack_data"
    return "probe_ack"


class WritebackQueueCoverage:
    def __init__(self) -> None:
        self.release = RELEASE_DEFINITION.instantiate("writeback_queue.release")
        self.ack = ACK_DEFINITION.instantiate("writeback_queue.ack")
        self.block = BLOCK_DEFINITION.instantiate("writeback_queue.block")

    def sample_release(self, info: dict, channel: int, voluntary: bool) -> None:
        self.release.sample({
            "kind": release_kind(info["opcode"], info.get("has_data", True)),
            "channel": channel,
            "voluntary": "yes" if voluntary else "no",
        }, details=False)

    def sample_ack(self, freed: bool) -> None:
        self.ack.sample({"result": "freed" if freed else "pending"}, details=False)

    def sample_block(self, matched: bool) -> None:
        self.block.sample({"match": "same_block" if matched else "other_block"},
                          details=False)
