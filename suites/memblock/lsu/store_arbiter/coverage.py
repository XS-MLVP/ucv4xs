"""Semantic functional coverage for Arbiter3_StoreStageIO.

Every coverpoint names a micro-architectural behaviour from the contract, and
every declared bin is reachable by a legal stimulus. Bins that would encode
impossible combinations are deliberately not declared: the arbiter's output
source, its ``entrance`` encoding and the scalar ``ready`` bit are three views
of one decision, so they are collapsed into one ``beat_kind`` bin instead of
being crossed with each other.
"""
from __future__ import annotations

from toffee import Bin, CoverGroupDef, CoverPointDef, CrossDef

# The four legal beats: (out.valid, entrance, scalar_ready) are fully implied.
BEAT_KINDS = (
    "idle_bubble",          # valid=0, entrance=prefetch(0x2), ready=1
    "tail_only_grant",      # valid=1, entrance=unalignTail(0x1), ready=0
    "scalar_only_grant",    # valid=1, entrance=scalarIssue(0x8), ready=1
    "both_tail_priority",   # valid=1, entrance=unalignTail(0x1), ready=0
)

SHAPES = ("zero", "all_ones", "mixed")

TAIL_GROUPS = ("accessType", "uop_index", "robIdx", "sqIdx", "address", "mask_size")
SCALAR_GROUPS = TAIL_GROUPS + ("store_set",)

# Concrete isolation cases: each flips a source that must not become visible.
ISOLATION_CASES = (
    "scalar_ssid_no_leak",
    "scalar_storeSetHit_no_leak",
    "tail_instrType_constant",
    "tail_exceptionVec19_no_leak",
)

GROUP_FIELDS = {
    "tail": {
        "accessType": ["accessType_instrType", "accessType_isCbo",
                       "accessType_isCboNoZero"],
        "uop_index": ["uop_ftqPtr_flag", "uop_ftqPtr_value", "uop_ftqOffset",
                      "uop_fuOpType", "uop_isRVC", "uop_exceptionVec_19"],
        "robIdx": ["uop_robIdx_flag", "uop_robIdx_value", "uop_robIdx_isFormer"],
        "sqIdx": ["uop_sqIdx_first_flag", "uop_sqIdx_second_flag",
                  "uop_sqIdx_value"],
        "address": ["vaddr", "fullva"],
        "mask_size": ["size", "mask"],
    },
    "scalar": {
        "accessType": ["accessType_isCbo", "accessType_isCboNoZero"],
        "uop_index": ["uop_ftqPtr_flag", "uop_ftqPtr_value", "uop_ftqOffset",
                      "uop_fuOpType", "uop_isRVC"],
        "robIdx": ["uop_robIdx_flag", "uop_robIdx_value", "uop_robIdx_isFormer"],
        "sqIdx": ["uop_sqIdx_first_flag", "uop_sqIdx_second_flag",
                  "uop_sqIdx_value"],
        "address": ["vaddr", "fullva"],
        "mask_size": ["size", "mask"],
        "store_set": ["ssid", "storeSetHit"],
    },
}

FIELD_WIDTHS = {
    "accessType_instrType": 3, "accessType_isCbo": 1, "accessType_isCboNoZero": 1,
    "uop_exceptionVec_19": 1, "uop_isRVC": 1, "uop_ftqPtr_flag": 1,
    "uop_ftqPtr_value": 6, "uop_ftqOffset": 5, "uop_fuOpType": 12,
    "uop_robIdx_flag": 1, "uop_robIdx_value": 8, "uop_robIdx_isFormer": 1,
    "uop_sqIdx_first_flag": 1, "uop_sqIdx_second_flag": 1, "uop_sqIdx_value": 6,
    "vaddr": 50, "fullva": 64, "size": 3, "mask": 16, "ssid": 6,
    "storeSetHit": 1,
}


def beat_kind(in0_valid: int, in1_valid: int, entrance: int, ready: int) -> str:
    if in0_valid and in1_valid:
        return "both_tail_priority"
    if in0_valid:
        return "tail_only_grant"
    if in1_valid:
        return "scalar_only_grant"
    return "idle_bubble"


def payload_shape(payload: dict[str, int]) -> str:
    if not payload or all(value == 0 for value in payload.values()):
        return "zero"
    if all(value == (1 << FIELD_WIDTHS[name]) - 1 for name, value in payload.items()):
        return "all_ones"
    return "mixed"


SELECTION_DEFINITION = CoverGroupDef(
    "arb3_selection",
    (
        CoverPointDef(
            "beat_kind",
            {name: Bin.values(name) for name in BEAT_KINDS},
            description="四种合法拍型：空闲 bubble、仅尾段、仅标量、同拍双有效时尾段优先；"
                        "每种拍型隐含 out.valid 与 entrance 编码。",
        ),
        CoverPointDef(
            "scalar_ready",
            {"granted": Bin.values(1), "backpressured": Bin.values(0)},
            description="标量源 ready：尾段占用时被反压，其余情况可接收。",
        ),
    ),
    description="S0 store 请求源仲裁：拍型（含输出源与 entrance）与标量反压。",
)

PAYLOAD_DEFINITION = CoverGroupDef(
    "arb3_payload",
    (
        CoverPointDef(
            "payload_group",
            {f"tail.{name}": Bin.values(f"tail.{name}") for name in TAIL_GROUPS}
            | {f"scalar.{name}": Bin.values(f"scalar.{name}") for name in SCALAR_GROUPS},
            description="被选中源的字段组：尾段 6 组、标量 7 组（标量独有 storeSet）。",
        ),
        CoverPointDef(
            "shape",
            {name: Bin.values(name) for name in SHAPES},
            description="字段组位型：全零、全一、混合位，防止单一常量下的假通过。",
        ),
    ),
    (CrossDef("group_x_shape", ("payload_group", "shape"),
              description="13 个字段组 × 3 种位型，确保每组都做过非零非全一的比较。"),),
    description="仲裁输出的字段级保真。",
)

ISOLATION_DEFINITION = CoverGroupDef(
    "arb3_isolation",
    (
        CoverPointDef(
            "isolation_case",
            {name: Bin.values(name) for name in ISOLATION_CASES},
            description="未选中源翻转后输出必须不变：标量 ssid/storeSetHit 不泄漏，"
                        "尾段的 instrType/exceptionVec19 不被标量路径改写。",
        ),
    ),
    description="源隔离：未选中源的任意比特不得影响输出。",
)


class StoreArbiterCoverage:
    def __init__(self) -> None:
        self.selection = SELECTION_DEFINITION.instantiate("store_arbiter.selection")
        self.payload = PAYLOAD_DEFINITION.instantiate("store_arbiter.payload")
        self.isolation = ISOLATION_DEFINITION.instantiate("store_arbiter.isolation")

    def sample(self, in0_valid: int, in1_valid: int, entrance: int,
               in0: dict[str, int], in1: dict[str, int], ready: int) -> None:
        self.selection.sample({
            "beat_kind": beat_kind(in0_valid, in1_valid, entrance, ready),
            "scalar_ready": 1 if ready else 0,
        }, details=False)
        if in0_valid:
            source, payload = "tail", in0
        elif in1_valid:
            source, payload = "scalar", in1
        else:
            return
        for name, fields in GROUP_FIELDS[source].items():
            self.payload.sample({
                "payload_group": f"{source}.{name}",
                "shape": payload_shape({field: payload[field] for field in fields}),
            }, details=False)

    def sample_isolation(self, case: str) -> None:
        self.isolation.sample({"isolation_case": case}, details=False)
