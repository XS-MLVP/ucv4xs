"""Semantic functional coverage for Arbiter7_LoadStageIO."""
from __future__ import annotations

from toffee import Bin, CoverGroupDef, CoverPointDef

SOURCES = (0, 1, 2, 3, 5)
SOURCE_NAMES = {0: "unalignTail", 1: "replayHiPrio", 2: "fastReplay",
                3: "replayLoPrio", 5: "scalarIssue"}

CASES = (
    "arb.bubble",
    "arb.single_unalign_tail",
    "arb.single_replay_hi",
    "arb.single_fast_replay",
    "arb.single_replay_lo",
    "arb.single_scalar_issue",
    "arb.adjacent_pairs_all_sources",
    "arb.all_five_valid",
    "ready.slot0_follows_out_ready",
    "ready.lower_slots_blocked_by_higher_valid",
    "ready.out_ready_low_blocks_everything",
    "entrance.constant_reencoding",
    "entrance.fast_replay_passthrough",
    "entrance.bubble_is_0x80",
    "field.full_through",
    "field.single_bit_gated_slot5",
    "field.missing_slot5_defaults",
    "field.paddr_only_for_fast_replay",
    "field.size_forced_q_for_tail",
    "field.pfttype_zero_for_replays",
    "field.noquery_bubble_and_slot2",
    "isolation.unselected_source_mutation",
)
GROUP = CoverGroupDef(
    "arb7_case",
    (CoverPointDef("case", {name: Bin.values(name) for name in CASES},
                   description="五源固定优先级仲裁：选中/ready/entrance 重编码、"
                               "六类字段的逐字段保真、未选中源隔离。"),),
    description="Arbiter7_LoadStageIO 语义情形清单。",
)


class LoadArbiterCoverage:
    def __init__(self) -> None:
        self.cases = GROUP.instantiate("load_arbiter.case")

    def sample_case(self, name: str) -> None:
        if name not in CASES:
            raise KeyError(f"undeclared load arbiter cover case: {name}")
        self.cases.sample({"case": name}, details=False)

    def observe(self, **_) -> None:
        """Every bin is an explicitly asserted case."""
