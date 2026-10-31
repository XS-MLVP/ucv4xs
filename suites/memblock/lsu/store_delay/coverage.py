"""Semantic functional coverage for DelayPipeline (store S3 writeback delay).

Bins are checked behaviours from ``docs/contracts/store-delay.md``, including
the negative cases (a flushAfter redirect must not kill the same slot; a
redirect that misses must not disturb a beat).
"""
from __future__ import annotations

from toffee import Bin, CoverGroupDef, CoverPointDef

DELAY_CASES = (
    # Data movement.
    "delay.reset_clears_valid",
    "delay.beat_appears_after_one_cycle",
    "delay.field_fidelity",
    "delay.single_beat_not_repeated",
    "delay.back_to_back_three_beats",
    "delay.idle_holds_zero",
    # Input-side filtering.
    "kill.input_same_slot_flush",
    "kill.input_after_slot_flush_after",
    "kill.input_after_slot_flush",
    # Boundary: the registered-beat kill is not observable in this instance.
    "boundary.out_ready_tied_high_consumes_beat_in_one_cycle",
    "boundary.registered_beat_kill_is_not_observable",
    # Redirect level semantics.
    "level.flush_after_same_slot_survives",
    # ROB entry half ordering.
    "former.latter_input_killed_by_former_redirect",
    "former.former_input_survives_latter_redirect",
    # Ring wrap.
    "wrap.flag_direction_flips",
    "wrap.value_greater_with_same_flag",
    # No-op redirects.
    "redirect.invalid_never_kills",
    "redirect.younger_target_never_kills",
)

GROUP_DEFINITION = CoverGroupDef(
    "dly_case",
    (
        CoverPointDef(
            "case",
            {name: Bin.values(name) for name in DELAY_CASES},
            description="DelayPipeline 的可读语义情形：延迟/保真、入口过滤、出口压制、"
                        "flush 级别、former 次序、环形绕回与无效 redirect。",
        ),
    ),
    description="DelayPipeline 语义情形清单。",
)


class DelayPipelineCoverage:
    def __init__(self) -> None:
        self.cases = GROUP_DEFINITION.instantiate("store_delay.case")

    def sample_case(self, name: str) -> None:
        if name not in DELAY_CASES:
            raise KeyError(f"undeclared delay cover case: {name}")
        self.cases.sample({"case": name}, details=False)

    def observe(self, **_) -> None:
        """Every bin is an explicitly asserted case; no automatic sampling."""
