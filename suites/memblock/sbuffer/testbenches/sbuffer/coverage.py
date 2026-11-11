"""Semantic functional coverage for the Sbuffer top level.

Groups are split by event type so a sample only carries fields that are
meaningful for that event; "not applicable" values use ignore bins and never
enter the denominator.
"""
from __future__ import annotations

from toffee import Bin, CoverGroupDef, CoverPointDef

NA = -1

ENQ_DEFINITION = CoverGroupDef(
    "sbuffer_enq",
    (
        CoverPointDef(
            "enqueue_kind",
            {
                "new_line": Bin.values("new_line"),
                "merge_same_vtag": Bin.values("merge_same_vtag"),
                "merge_diff_vtag": Bin.values("merge_diff_vtag"),
                "same_cycle_same_tag": Bin.values("same_cycle_same_tag"),
                "same_cycle_diff_tags": Bin.values("same_cycle_diff_tags"),
                "blocked_full": Bin.values("blocked_full"),
                "blocked_drain": Bin.values("blocked_drain"),
            },
            description="入队关系：新行、同虚标签合并、跨虚标签合并触发 uarch drain、同拍同/异标签双写、满阻塞与 drain 阻塞。",
        ),
        CoverPointDef(
            "write_lane",
            {
                **{str(lane): Bin.values(lane) for lane in range(4)},
                "not_applicable": Bin.ignore(Bin.values(NA)),
            },
            description="一笔 store 落在 64B 行的哪个 16B lane；lane 由地址低 2 位选择。",
        ),
    ),
    description="Sbuffer 入队关系与行内 lane 选择。",
)

CAPACITY_DEFINITION = CoverGroupDef(
    "sbuffer_capacity",
    (
        CoverPointDef(
            "capacity",
            {
                "not_full": Bin.values("not_full"),
                "full": Bin.values("full"),
                "resumed": Bin.values("resumed"),
            },
            description="容量语义：未满、16 行全有效时 sbFull 阻塞入队、写出释放后有空间恢复接受。",
        ),
    ),
    description="Sbuffer 容量与 sbFull 语义。",
)

SAMEBLOCK_DEFINITION = CoverGroupDef(
    "sbuffer_sameblock",
    (
        CoverPointDef(
            "sameblock",
            {
                "allocate_while_inflight": Bin.values("allocate_while_inflight"),
                "request_blocked": Bin.values("request_blocked"),
                "released": Bin.values("released"),
            },
            description="同一 cache block 已有 inflight 写请求时，新行可以分配但其写回必须等待该请求返回。",
        ),
    ),
    description="Sbuffer 同块串行语义。",
)

REQ_DEFINITION = CoverGroupDef(
    "sbuffer_writeout",
    (
        CoverPointDef(
            "req_reason",
            {
                "timeout": Bin.values("timeout"),
                "capacity_replace": Bin.values("capacity_replace"),
                "drain_flush": Bin.values("drain_flush"),
                "drain_uarch": Bin.values("drain_uarch"),
                "replay_retry": Bin.values("replay_retry"),
            },
            description="DCache 写出的触发原因：行超时、容量替换、flush drain、uarch drain、replay 后重试。",
        ),
        CoverPointDef(
            "req_payload",
            {
                "lane0": Bin.values("lane0"),
                "lane1": Bin.values("lane1"),
                "lane2": Bin.values("lane2"),
                "lane3": Bin.values("lane3"),
            },
            description="写请求携带的行内 16B lane 内容；请求 mask/data 必须与 DUT 保存的行一致。",
        ),
    ),
    description="Sbuffer 写出请求的触发原因与 payload。",
)

REPLAY_DEFINITION = CoverGroupDef(
    "sbuffer_replay",
    (
        CoverPointDef(
            "replay",
            {
                "replay_resp": Bin.values("replay_resp"),
                "retry_req": Bin.values("retry_req"),
                "final_hit": Bin.values("final_hit"),
            },
            description="replay 响应保持行有效，超时后同一行重发写请求，最终 hit 释放。",
        ),
    ),
    description="Sbuffer replay/重试语义。",
)

FLUSH_DEFINITION = CoverGroupDef(
    "sbuffer_flush",
    (
        CoverPointDef(
            "flush_kind",
            {
                "normal": Bin.values("normal"),
                "cmo": Bin.values("cmo"),
                "uarch": Bin.values("uarch"),
            },
            description="三种排空：普通 flush（需 sqempty）、CMO flush（只看 mshr_store_empty）、uarch drain（合并虚别名触发）。",
        ),
        CoverPointDef(
            "empty_gating",
            {
                "normal_after_all": Bin.values("normal_after_all"),
                "sqempty_hold": Bin.values("sqempty_hold"),
                "cmo_ignores_sq": Bin.values("cmo_ignores_sq"),
            },
            description="flush.empty 的完成条件：行全部写出、输入与 MSHR 条件满足；普通 flush 必须等 sqempty。",
        ),
    ),
    description="Sbuffer 排空与 empty 门控语义。",
)

FWD_DEFINITION = CoverGroupDef(
    "sbuffer_forward",
    (
        CoverPointDef(
            "forward_result",
            {
                "no_match": Bin.values("no_match"),
                "active": Bin.values("active"),
                "inflight": Bin.values("inflight"),
                "active_over_inflight": Bin.values("active_over_inflight"),
                "mismatch_vtag": Bin.values("mismatch_vtag"),
                "mismatch_ptag": Bin.values("mismatch_ptag"),
                "killed": Bin.values("killed"),
            },
            description="转发结果：无匹配、active 命中、仅 inflight 命中、active 覆盖 inflight、虚实标签单向不一致告警、kill 抑制告警。",
        ),
        CoverPointDef(
            "forward_lane",
            {str(lane): Bin.values(lane) for lane in range(3)},
            description="三路 load 转发端口都能独立返回数据。",
        ),
        CoverPointDef(
            "forward_vaddr_lane",
            {str(lane): Bin.values(lane) for lane in range(4)},
            description="转发查询落在 64B 行的哪个 16B lane；返回数据必须来自该 lane。",
        ),
    ),
    description="Sbuffer 到 LoadUnit 的转发语义。",
)

RESET_DEFINITION = CoverGroupDef(
    "sbuffer_reset",
    (
        CoverPointDef(
            "reset_context",
            {
                "idle": Bin.values("idle"),
                "with_entries": Bin.values("with_entries"),
            },
            description="复位时缓冲区为空或存在未写出的行；复位后不保留旧行和旧写请求。",
        ),
    ),
    description="Sbuffer 复位语义。",
)


class SbufferCoverage:
    def __init__(self) -> None:
        self.enq = ENQ_DEFINITION.instantiate("sbuffer.enq")
        self.capacity = CAPACITY_DEFINITION.instantiate("sbuffer.capacity")
        self.sameblock = SAMEBLOCK_DEFINITION.instantiate("sbuffer.sameblock")
        self.writeout = REQ_DEFINITION.instantiate("sbuffer.writeout")
        self.replay = REPLAY_DEFINITION.instantiate("sbuffer.replay")
        self.flush = FLUSH_DEFINITION.instantiate("sbuffer.flush")
        self.forward = FWD_DEFINITION.instantiate("sbuffer.forward")
        self.reset = RESET_DEFINITION.instantiate("sbuffer.reset")

    def sample_enqueue(self, kind: str, lanes) -> None:
        if lanes:
            for lane in lanes:
                self.enq.sample({"enqueue_kind": kind, "write_lane": lane}, details=False)
        else:
            self.enq.sample({"enqueue_kind": kind, "write_lane": NA}, details=False)

    def sample_enqueue_partial(self, kind: str, lanes) -> None:
        self.enq.sample({"enqueue_kind": kind, "write_lane": lanes[0] if lanes else NA}, details=False)

    def sample_capacity(self, value: str) -> None:
        self.capacity.sample({"capacity": value}, details=False)

    def sample_sameblock(self, value: str) -> None:
        self.sameblock.sample({"sameblock": value}, details=False)

    def sample_request(self, reason: str, lanes) -> None:
        for lane in lanes:
            self.writeout.sample({"req_reason": reason, "req_payload": f"lane{lane}"}, details=False)

    def sample_replay(self, value: str) -> None:
        self.replay.sample({"replay": value}, details=False)

    def sample_flush(self, kind: str, gating: str) -> None:
        self.flush.sample({"flush_kind": kind, "empty_gating": gating}, details=False)

    def sample_forward(self, result: str, load_lane: int, vaddr_lane: int) -> None:
        self.forward.sample(
            {"forward_result": result, "forward_lane": load_lane, "forward_vaddr_lane": vaddr_lane},
            details=False,
        )

    def sample_reset(self, context: str) -> None:
        self.reset.sample({"reset_context": context}, details=False)
