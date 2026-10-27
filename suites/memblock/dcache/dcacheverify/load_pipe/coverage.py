"""Semantic functional coverage for LoadPipe."""
from __future__ import annotations

from toffee import Bin, CoverGroupDef, CoverPointDef, CrossDef

from .model import mask_class


def cmd_class(cmd: int) -> str:
    return {0: "load", 1: "load_fp", 2: "lui", 3: "lr"}.get(cmd, "other")


TRANSACTION_DEFINITION = CoverGroupDef(
    "lp_transaction",
    (
        CoverPointDef(
            "outcome",
            {
                "hit": Bin.values("hit"),
                "miss": Bin.values("miss"),
                "handled": Bin.values("handled"),
                "miss_suppressed": Bin.values("miss_suppressed"),
            },
            description="命中、普通 miss、miss 被 miss queue 接收并 handled、miss 被抑制。",
        ),
        CoverPointDef(
            "way",
            {str(way): Bin.values(way) for way in range(4)},
            description="tag 命中 4 个 way 中任意一个时 bank data 的 way_en 对应。",
        ),
        CoverPointDef(
            "cmd",
            {name: Bin.values(name) for name in ("load", "load_fp", "lui", "lr")},
            description="load 类操作码的请求路径。",
        ),
        CoverPointDef(
            "mask",
            {name: Bin.values(name) for name in
             ("single_byte", "byte_range", "full", "load128")},
            description="字节掩码形态与 load128 强制 16B 访问。",
        ),
    ),
    (CrossDef("outcome_x_way", ("outcome", "way"),
              description="命中/miss 结果 × 4 个 way。"),),
    description="LoadPipe 事务结果与访问形态。",
)

MISS_DEFINITION = CoverGroupDef(
    "lp_miss",
    (
        CoverPointDef(
            "suppression",
            {
                "none": Bin.values("none"),
                "mshr_full": Bin.values("mshr_full"),
                "wbq_block": Bin.values("wbq_block"),
                "spec_unconfirmed": Bin.values("spec_unconfirmed"),
            },
            description="miss 请求被 mshr full / wbq block / 未确认 speculative miss 抑制。",
        ),
        CoverPointDef(
            "handled",
            {"accepted": Bin.values("accepted"), "not_handled": Bin.values("not_handled")},
            description="miss queue 接收后 miss_resp.handled 回传。",
        ),
        CoverPointDef(
            "specmiss",
            {"normal": Bin.values("normal"), "spec_confirmed": Bin.values("spec_confirmed")},
            description="普通 miss 与 speculative miss 确认后的 miss 请求。",
        ),
    ),
    description="LoadPipe miss 请求与抑制。",
)

CONFLICT_DEFINITION = CoverGroupDef(
    "lp_conflict",
    (
        CoverPointDef(
            "conflict",
            {
                "none": Bin.values("none"),
                "bank": Bin.values("bank"),
                "rr_bank": Bin.values("rr_bank"),
            },
            description="bank conflict / round-robin bank conflict 对 S2 输出的影响。",
        ),
    ),
    description="LoadPipe bank 冲突。",
)


class LoadPipeCoverage:
    def __init__(self) -> None:
        self.transaction = TRANSACTION_DEFINITION.instantiate("load_pipe.transaction")
        self.miss = MISS_DEFINITION.instantiate("load_pipe.miss")
        self.conflict = CONFLICT_DEFINITION.instantiate("load_pipe.conflict")

    def sample(self, *, hit: bool, way: int, cmd: int, mask: int, load128: bool,
               mshr_full: bool, specmiss: bool, handled: bool,
               bank_conflict: bool, wbq_block: bool) -> None:
        if hit:
            outcome = "hit"
        elif handled:
            outcome = "handled"
        elif mshr_full or wbq_block or specmiss:
            outcome = "miss_suppressed"
        else:
            outcome = "miss"
        shape = mask_class(mask, load128)
        if shape not in ("single_byte", "byte_range", "full", "load128"):
            shape = "byte_range"
        self.transaction.sample({"outcome": outcome, "way": way,
                                 "cmd": cmd_class(cmd), "mask": shape},
                                details=False)
        suppression = ("mshr_full" if mshr_full else
                       "wbq_block" if wbq_block else
                       "spec_unconfirmed" if specmiss else "none")
        self.miss.sample({
            "suppression": suppression,
            "handled": "accepted" if handled else "not_handled",
            "specmiss": "spec_confirmed" if (specmiss and not mshr_full) else "normal",
        }, details=False)
        self.conflict.sample({"conflict": "bank" if bank_conflict else "none"},
                             details=False)

    def sample_rr_conflict(self) -> None:
        self.conflict.sample({"conflict": "rr_bank"}, details=False)
