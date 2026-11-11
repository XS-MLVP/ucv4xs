"""Semantic functional coverage for MissTrack."""
from __future__ import annotations

from toffee import Bin, CoverGroupDef, CoverPointDef, CrossDef

SPEC_DEFINITION = CoverGroupDef(
    "mt_spec",
    (
        CoverPointDef(
            "result",
            {
                "idle": Bin.values("idle"),
                "resolved": Bin.values("resolved"),
                "candidate": Bin.values("candidate"),
                "suppressed": Bin.values("suppressed"),
            },
            description="S1 观察：无 load、表项命中（resident/pending 内部合流）、UNKNOWN 候选、多命中抑制。",
        ),
        CoverPointDef(
            "lane",
            {str(lane): Bin.values(lane) for lane in range(3)},
            description="3 条 load 流水独立查询同一张表。",
        ),
    ),
    (CrossDef("lane_x_result", ("lane", "result"),
              description="3 条 load 流水 × 5 种 S1 结果。"),),
    description="MissTrack S0→S1 推测查询结果。",
)

EVENT_DEFINITION = CoverGroupDef(
    "mt_event",
    (
        CoverPointDef(
            "source",
            {
                "none": Bin.values("none"),
                "install": Bin.values("install"),
                "alloc": Bin.values("alloc"),
                "train": Bin.values("train"),
                "mixed": Bin.values("mixed"),
            },
            description="表更新来源：安装、分配、s2 命中训练、同拍混合。",
        ),
        CoverPointDef(
            "install_way",
            {
                "single": Bin.values("single"),
                "multi": Bin.values("multi"),
                "not_applicable": Bin.ignore(Bin.values("not_applicable")),
            },
            description="安装必须携带单 way；多 way 安装被忽略。",
        ),
        CoverPointDef(
            "maintenance",
            {
                "none": Bin.values("none"),
                "invalidate": Bin.values("invalidate"),
                "clear": Bin.values("clear"),
            },
            description="失效与清除对表的维护事件。",
        ),
    ),
    description="MissTrack 表更新事件。",
)

TABLE_DEFINITION = CoverGroupDef(
    "mt_table",
    (
        CoverPointDef(
            "occupancy",
            {"empty": Bin.values("empty"), "partial": Bin.values("partial"),
             "full": Bin.values("full")},
            description="表占用度：空、部分、16 项全满。",
        ),
        CoverPointDef(
            "victim",
            {"invalid_slot": Bin.values("invalid_slot"),
             "oldest": Bin.values("oldest"),
             "not_applicable": Bin.ignore(Bin.values("not_applicable"))},
            description="替换策略：优先空槽，否则最老（age 最大，tie 取低索引）。",
        ),
        CoverPointDef(
            "age",
            {"young": Bin.values("young"), "saturated": Bin.values("saturated"),
             "not_applicable": Bin.ignore(Bin.values("not_applicable"))},
            description="age 递增并在 7 饱和。",
        ),
    ),
    description="MissTrack 表占用、替换与 age 维护。",
)

LIFECYCLE_DEFINITION = CoverGroupDef(
    "mt_lifecycle",
    (
        CoverPointDef(
            "owner",
            {"live": Bin.values("live"), "retired": Bin.values("retired"),
             "not_applicable": Bin.ignore(Bin.values("not_applicable"))},
            description="pending 项在 owner 仍有效时保留，owner 消失后退休。",
        ),
        CoverPointDef(
            "invalidate",
            {"hit": Bin.values("hit"), "miss": Bin.values("miss"),
             "not_applicable": Bin.ignore(Bin.values("not_applicable"))},
            description="失效按 idx+way 命中 resident 项，或与表项不重叠。",
        ),
    ),
    description="MissTrack 项生命周期。",
)


class MissTrackCoverage:
    def __init__(self) -> None:
        self.spec = SPEC_DEFINITION.instantiate("miss_track.spec")
        self.event = EVENT_DEFINITION.instantiate("miss_track.event")
        self.table = TABLE_DEFINITION.instantiate("miss_track.table")
        self.lifecycle = LIFECYCLE_DEFINITION.instantiate("miss_track.lifecycle")

    def sample_spec(self, lane: int, spec, load) -> None:
        if not load.s1_valid:
            result = "idle"
        elif not spec.valid:
            result = "suppressed"
        elif spec.candidate:
            result = "candidate"
        else:
            result = "resolved"
        self.spec.sample({"result": result, "lane": lane}, details=False)

    def sample_events(self, install, allocs, loads, invalidate, clear, model) -> None:
        sources = []
        if install.valid:
            sources.append("install")
        if any(alloc.valid for alloc in allocs):
            sources.append("alloc")
        if any(load.s2_valid and load.s2_hit for load in loads):
            sources.append("train")
        if not sources:
            source = "none"
        elif len(sources) == 1:
            source = sources[0]
        else:
            source = "mixed"
        if install.valid:
            way = "single" if install.way.bit_count() == 1 else "multi"
        else:
            way = "not_applicable"
        maintenance = "clear" if clear else ("invalidate" if invalidate.valid else "none")
        self.event.sample({"source": source, "install_way": way,
                           "maintenance": maintenance}, details=False)
        valid_entries = [entry for entry in model.entries if entry.valid]
        if not valid_entries:
            occupancy = "empty"
        elif len(valid_entries) == 16:
            occupancy = "full"
        else:
            occupancy = "partial"
        ages = [entry.age for entry in valid_entries]
        age = "saturated" if 7 in ages else ("young" if ages else "not_applicable")
        self.table.sample({"occupancy": occupancy, "victim": "not_applicable",
                           "age": age}, details=False)

    def sample_victim(self, kind: str, occupancy: str = "full") -> None:
        self.table.sample({"occupancy": occupancy, "victim": kind,
                           "age": "not_applicable"}, details=False)

    def sample_lifecycle(self, owner: str | None = None, invalidate: str | None = None) -> None:
        self.lifecycle.sample({
            "owner": owner if owner is not None else "not_applicable",
            "invalidate": invalidate if invalidate is not None else "not_applicable",
        }, details=False)
