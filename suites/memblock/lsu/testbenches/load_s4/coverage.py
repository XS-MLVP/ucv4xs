"""Semantic functional coverage for LoadUnitS4."""
from __future__ import annotations

from toffee import Bin, CoverGroupDef, CoverPointDef

S4_CASES = (
    "pass.valid_follows_input",
    "pass.all_fields_identical",
    "pass.idle_keeps_valid_low",
    "pass.bits_are_dont_care_when_invalid",
    "pass.full_width_toggle",
    "pass.cause_bits_all_present",
)
GROUP = CoverGroupDef(
    "s4_case",
    (CoverPointDef("case", {name: Bin.values(name) for name in S4_CASES},
                   description="LoadUnitS4 无状态直通：valid 跟随输入，41 个字段"
                               "（含 11 个 cause 位）逐位相同。"),),
    description="LoadUnitS4 语义情形清单。",
)


class LoadS4Coverage:
    def __init__(self) -> None:
        self.cases = GROUP.instantiate("load_s4.case")

    def sample_case(self, name: str) -> None:
        if name not in S4_CASES:
            raise KeyError(f"undeclared LoadUnitS4 cover case: {name}")
        self.cases.sample({"case": name}, details=False)

    def observe(self, **_) -> None:
        """Every bin is an explicitly asserted case."""
