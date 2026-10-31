"""Named pin groups over the generated flat-port DUT.

A driver binds the pins it owns; a monitor binds the pins it reads.  The DUT
rejects two owners claiming the same pin while a test is running, so a silent
double-drive cannot pass as a functional observation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable
from typing import Mapping

from suites.frontend.ftq.harness import Dut


class Pins:
    """A logical view over physical pin names for one DUT."""

    def __init__(self, dut: Dut, names: Mapping[str, str], *, name: str) -> None:
        if not name:
            raise ValueError("pin group needs a name")
        missing = sorted({pin for pin in names.values()} - set(dut._inputs) - dut.output_names())
        if missing:
            raise KeyError(f"{name}: missing pins {missing}")
        self.dut = dut
        self.name = name
        self.names = dict(names)

    def physical(self, logical: str) -> str:
        try:
            return self.names[logical]
        except KeyError as error:
            raise KeyError(f"{self.name} has no logical pin {logical!r}") from error

    def set(self, **values: int | bool) -> None:
        for logical, value in values.items():
            self.dut.input(self.physical(logical)).Set(int(value))

    def u(self, logical: str) -> int:
        return self.dut.u(self.physical(logical))

    def b(self, logical: str) -> bool:
        return self.dut.b(self.physical(logical))

    def claim(self, owner: str, *, inputs_only: bool = True) -> None:
        for logical, pin in self.names.items():
            if inputs_only and pin not in self.dut._inputs:
                continue
            self.dut.claim(pin, owner)


@dataclass(frozen=True)
class LanePins:
    """One request lane: a valid pulse plus a payload bundle."""

    valid: str
    payload: Mapping[str, str]


def prefix_pins(dut: Dut, prefix: str, *, name: str) -> Mapping[str, str]:
    """Map physical pin suffix -> logical name for one input prefix."""

    values = {}
    for pin in dut.input_names():
        if pin.startswith(prefix):
            values[pin.removeprefix(prefix)] = pin
    if not values:
        raise KeyError(f"{name}: no pins under prefix {prefix!r}")
    return values


def encode_lane(prefix: str, fields: Mapping[str, str], values: Mapping[str, int | bool]) -> dict[str, int]:
    """Encode a typed request into physical flat-pin values."""

    encoded = {prefix + "valid": 1}
    for logical, value in values.items():
        try:
            encoded[prefix + fields[logical]] = int(value)
        except KeyError as error:
            raise KeyError(f"lane encoding has no field {logical!r}") from error
    return encoded


def clear_prefix(dut: Dut, *prefixes: str) -> None:
    for prefix in prefixes:
        for pin in dut.input_names():
            if pin.startswith(prefix):
                dut.input(pin).Set(0)
    dut.refresh()


def names_for(prefix: str, fields: Iterable[str], mapping: Mapping[str, str]) -> dict[str, str]:
    return {field: prefix + mapping[field] for field in fields}
