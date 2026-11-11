"""Independent checker for the VTypeGen leaf DUT."""

from __future__ import annotations

from toffee import Scoreboard

from suites.frontend.ibuffer.testbenches.vtype_gen.model import DECODE_WIDTH
from suites.frontend.ibuffer.testbenches.vtype_gen.model import INIT_VTYPE
from suites.frontend.ibuffer.testbenches.vtype_gen.model import Outputs
from suites.frontend.ibuffer.testbenches.vtype_gen.model import VType

FIELDS = ("illegal", "vma", "vta", "vsew", "vlmul")


def _flat_vtypes(outputs: Outputs) -> dict[str, int]:
    flat: dict[str, int] = {}
    for name in ("vtype", "specvtype"):
        window = getattr(outputs, name)
        for lane in range(DECODE_WIDTH):
            for field in FIELDS:
                flat[f"{name}_{lane}_{field}"] = getattr(window[lane], field)
    return flat


def check_outputs(expected: Outputs, observed: Outputs, *, phase: str) -> None:
    if not isinstance(expected, Outputs) or not isinstance(observed, Outputs):
        raise TypeError("VTypeGen checker requires complete semantic Outputs")
    expected_fields = _flat_vtypes(expected)
    observed_fields = _flat_vtypes(observed)
    Scoreboard(f"vtype_gen.{phase}").check(
        expected=expected_fields, actual=observed_fields)


def check_reset(observed: Outputs, *, phase: str) -> None:
    expected = Outputs(vtype=(INIT_VTYPE,) * DECODE_WIDTH,
                       specvtype=(INIT_VTYPE,) * DECODE_WIDTH)
    check_outputs(expected, observed, phase=f"reset.{phase}")


def check_lane(expected: Outputs, lane: int, vtype: VType) -> None:
    assert expected.vtype[lane] == vtype, (
        f"lane {lane}: expected {vtype}, got {expected.vtype[lane]}")
