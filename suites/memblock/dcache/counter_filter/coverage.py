"""Semantic functional coverage for CounterFilter."""
from __future__ import annotations

from toffee import Bin, CoverGroupDef, CoverPointDef, CrossDef


def idx_class(idx: int) -> str:
    if idx == 0:
        return "zero"
    if idx == 255:
        return "max"
    if idx < 128:
        return "low"
    return "high"


MAX_INFLIGHT = 12  # 4 residency cycles x 3 load ports


def occupancy_class(occupancy: int) -> str:
    if occupancy == 0:
        return "empty"
    if occupancy >= MAX_INFLIGHT:
        return "max_inflight"
    return "partial"


QUERY_DEFINITION = CoverGroupDef(
    "cf_query",
    (
        CoverPointDef(
            "result",
            {"hit": Bin.values("hit"), "miss": Bin.values("miss"),
             "invalid": Bin.values("invalid")},
            description="查询命中、未命中、以及 req_valid=0 的无效查询。",
        ),
        CoverPointDef(
            "query_port",
            {str(port): Bin.values(port) for port in range(3)},
            description="3 个查询端口并行独立搜索同一个 entry 集合。",
        ),
        CoverPointDef(
            "way",
            {str(way): Bin.values(way) for way in range(4)},
            description="set/way 匹配必须同时命中索引与路号。",
        ),
        CoverPointDef(
            "idx_class",
            {name: Bin.values(name) for name in ("zero", "low", "high", "max")},
            description="索引 0/低/高/255 都在同一比较路径上。",
        ),
        CoverPointDef(
            "occupancy",
            {name: Bin.values(name) for name in ("empty", "partial", "max_inflight")},
            description="空、部分占用、4 阶段满带宽（12 项在途）三种占用度下的查询。",
        ),
    ),
    (CrossDef("port_x_result", ("query_port", "result"),
              description="3 个查询端口 × 命中/未命中。"),
     CrossDef("result_x_way", ("result", "way"),
              description="命中/未命中 × 4 个 way。")),
    description="CounterFilter 查询：命中语义、端口独立、索引/way 匹配与占用度。",
)

ENQ_DEFINITION = CoverGroupDef(
    "cf_enq",
    (
        CoverPointDef(
            "ports_used",
            {str(count): Bin.values(count) for count in range(4)},
            description="同拍 0/1/2/3 个 load 端口入队。",
        ),
        CoverPointDef(
            "relation",
            {"distinct": Bin.values("distinct"), "same_line": Bin.values("same_line"),
             "none": Bin.values("none")},
            description="多端口写入不同 line 或同一 line 的重复项。",
        ),
        CoverPointDef(
            "capacity",
            {"normal": Bin.values("normal"), "max_inflight": Bin.values("max_inflight")},
            description="普通入队，以及 4 个流水阶段 × 3 端口全部在途的 12 项边界。",
        ),
        CoverPointDef(
            "wrap",
            {"no_wrap": Bin.values("no_wrap"), "wrapped": Bin.values("wrapped")},
            description="环形指针在 15 处回绕。",
        ),
    ),
    description="CounterFilter 入队：端口数、重复 line、容量与指针回绕。",
)

LIFETIME_DEFINITION = CoverGroupDef(
    "cf_lifetime",
    (
        CoverPointDef(
            "age",
            {
                "hit_age_0": Bin.values(0),
                "hit_age_1": Bin.values(1),
                "hit_age_2": Bin.values(2),
                "hit_age_3": Bin.values(3),
                "expired_miss": Bin.values(4),
                "not_applicable": Bin.ignore(Bin.values(-1)),
            },
            description="条目在入队后的第 0..3 拍可命中，第 4 拍后被清除。",
        ),
    ),
    description="CounterFilter 条目生命周期。",
)


class CounterFilterCoverage:
    def __init__(self) -> None:
        self.query = QUERY_DEFINITION.instantiate("counter_filter.query")
        self.enq = ENQ_DEFINITION.instantiate("counter_filter.enq")
        self.lifetime = LIFETIME_DEFINITION.instantiate("counter_filter.lifetime")

    def sample_query(self, port: int, result: str, idx: int, way: int,
                     occupancy: int, age: int | None,
                     expired: bool = False) -> None:
        self.query.sample({"result": result, "query_port": port, "way": way,
                           "idx_class": idx_class(idx),
                           "occupancy": occupancy_class(occupancy)}, details=False)
        if result == "hit":
            self.lifetime.sample({"age": age if age is not None else -1}, details=False)
        elif result == "miss" and expired:
            self.lifetime.sample({"age": 4}, details=False)

    def sample_enq(self, ports_used: int, relation: str, occupancy: int,
                   wrapped: bool, full: bool) -> None:
        self.enq.sample({"ports_used": ports_used, "relation": relation,
                         "capacity": "max_inflight" if full else "normal",
                         "wrap": "wrapped" if wrapped else "no_wrap"}, details=False)
