"""Semantic functional coverage for StoreUnitS4."""
from __future__ import annotations

from toffee import Bin, CoverGroupDef, CoverPointDef

S4_CASES = (
    "pass.valid_follows_input",
    "pass.all_fields_identical",
    "pass.idle_keeps_valid_low",
    "pass.bits_are_dont_care_when_invalid",
    "pass.full_width_toggle",
)
GROUP = CoverGroupDef(
    "s4_case",
    (CoverPointDef("case", {name: Bin.values(name) for name in S4_CASES},
                   description="StoreUnitS4 是无状态直通：valid 跟随输入，13 个字段逐位相同。"),),
    description="StoreUnitS4 语义情形清单。",
)


class StoreS4Coverage:
    def __init__(self) -> None:
        self.cases = GROUP.instantiate("store_s4.case")

    def sample_case(self, name: str) -> None:
        if name not in S4_CASES:
            raise KeyError(f"undeclared StoreUnitS4 cover case: {name}")
        self.cases.sample({"case": name}, details=False)

    def observe(self, **_) -> None:
        """Every bin is an explicitly asserted case."""
