"""Load a Picker package and provide the suite's cycle conventions.

The harness owns only how an input level is written, how a cycle is advanced
and how an output is sampled.  Protocol meaning and expected values stay in the
reference models and checkers.
"""

from __future__ import annotations

from suites.frontend.ibuffer import ROOT as _SUITE_ROOT

import importlib.util
import sys
from pathlib import Path
from typing import Any, Mapping

from ucv.runtime import native_seed

SUITE_ROOT = _SUITE_ROOT
DUT_ROOT = SUITE_ROOT / "dut"

#: DUT directory name -> generated top-level Python class.
DUT_CLASSES = {
    "vtype_gen": "VTypeGenDut",
    "ibuffer": "IBufferDut",
}


def load_class(name: str) -> type:
    if name not in DUT_CLASSES:
        raise ValueError(f"unknown IBuffer DUT {name!r}")
    directory = DUT_ROOT / name
    module_name = f"ibuffer_picker_{name}_{id(directory)}"
    spec = importlib.util.spec_from_file_location(
        module_name, directory / "__init__.py",
        submodule_search_locations=[str(directory)]
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load Picker package {directory}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return getattr(module, "DUT" + DUT_CLASSES[name])


class DutHarness:
    """One Picker DUT plus deterministic input/clock/sampling conventions."""

    def __init__(self, name: str, *, seed: int | None = None) -> None:
        self.name = name
        cls = load_class(name)
        self.module = sys.modules[cls.__module__]
        # ``rand+reset+0`` zeroes register randomization at time zero so an
        # explicit reset is the only source of initial FSM state.
        arguments = [name, native_seed() if seed is None else f"+verilator+seed+{seed}",
                     "+verilator+rand+reset+0"]
        self.dut = cls(self.module.xsp.StringVector(arguments), coverage_filename="")
        self.clocked = "clock" in vars(self.dut)
        if self.clocked:
            self.dut.InitClock("clock")
        self._inputs: dict[str, Any] = {}
        for attribute, signal in vars(self.dut).items():
            if attribute == "dut":
                continue
            if (callable(getattr(signal, "IsInIO", None)) and signal.IsInIO()
                    and not signal.IsOutIO()):
                signal.AsImmWrite()
                self._inputs[attribute] = signal
        self._finished = False
        self._reset_done = False

    # -- input / output -----------------------------------------------------
    def set(self, **levels: int) -> None:
        for attribute, value in levels.items():
            signal = self._inputs.get(attribute)
            if signal is None:
                raise KeyError(f"{self.name}: unknown or non-input port {attribute!r}")
            signal.Set(int(value))

    def set_many(self, levels: Mapping[str, int]) -> None:
        self.set(**dict(levels))

    def input_names(self) -> tuple[str, ...]:
        return tuple(self._inputs)

    def all_port_names(self) -> tuple[str, ...]:
        return tuple(name for name in vars(self.dut) if name != "dut")

    def read(self, attribute: str) -> int:
        signal = getattr(self.dut, attribute, None)
        if signal is None:
            raise KeyError(f"{self.name}: no port {attribute!r}")
        return int(signal.U())

    def port_width(self, attribute: str) -> int:
        signal = getattr(self.dut, attribute, None)
        if signal is None:
            raise KeyError(f"{self.name}: no port {attribute!r}")
        return int(signal.mWidth)

    def is_input(self, attribute: str) -> bool:
        signal = getattr(self.dut, attribute, None)
        return bool(signal is not None and callable(getattr(signal, "IsInIO", None))
                    and signal.IsInIO() and not signal.IsOutIO())

    def is_output(self, attribute: str) -> bool:
        signal = getattr(self.dut, attribute, None)
        return bool(signal is not None and callable(getattr(signal, "IsOutIO", None))
                    and signal.IsOutIO())

    def has_port(self, attribute: str) -> bool:
        return getattr(self.dut, attribute, None) is not None

    def read_many(self, *attributes: str) -> tuple[int, ...]:
        return tuple(self.read(attribute) for attribute in attributes)

    def refresh(self) -> None:
        self.dut.RefreshComb()

    def step(self, cycles: int = 1) -> None:
        if not self.clocked:
            raise RuntimeError(f"{self.name} has no clock")
        self.dut.Step(cycles)

    def settle(self) -> None:
        """Evaluate clockless logic and advance simulated time once."""
        if self.clocked:
            self.refresh()
        else:
            self.dut.Step(1)

    def reset_once(self) -> None:
        if self.clocked and not self._reset_done:
            self.reset()
            self._reset_done = True

    def reset(self, cycles: int = 3) -> None:
        if not self.clocked:
            self.zero_inputs()
            self.settle()
            return
        # A quiet environment prevents a leftover request from being accepted
        # on the reset de-assertion edge.
        for name, signal in self._inputs.items():
            if name not in {"clock", "reset"}:
                signal.Set(0)
        self.set(reset=1)
        self.step(cycles)
        self.set(reset=0)
        self.step(1)

    def finish(self) -> None:
        if not self._finished:
            self._finished = True
            self.dut.Finish()

    # -- convenience --------------------------------------------------------
    def zero_inputs(self) -> None:
        for signal in self._inputs.values():
            signal.Set(0)

    def dump_inputs(self) -> dict[str, int]:
        return {name: int(signal.U()) for name, signal in self._inputs.items()}
