"""Load a Picker package and provide a small cycle-level harness.

The harness owns only three things: how an input level is written, how a
cycle is advanced, and how an output is sampled.  Protocol meaning and
expected values stay in the reference models and the testcases so that a
test failure is attributable to the design rather than to helper magic.

Picker's generated class exposes one flat :class:`XData` per RTL port.  All
inputs are switched to immediate-write mode, then the caller sets levels and
advances full cycles.  The first active cycle is the one after reset is
released; sampling after ``step()`` observes the state after that rising edge.
"""

from __future__ import annotations
from suites.frontend.ifu import ROOT as _SUITE_ROOT

import importlib.util
import sys
from pathlib import Path
from typing import Any, Mapping

SUITE_ROOT = _SUITE_ROOT
DUT_ROOT = SUITE_ROOT / "dut"

#: DUT directory name -> generated top-level Python class.
DUT_CLASSES = {
    "rvc_expander": "RvcExpanderDut",
    "instr_boundary": "InstrBoundaryDut",
    "pred_checker": "PredCheckerDut",
    "uncache_unit": "IfuUncacheUnitDut",
    "frontend_trigger": "FrontendTriggerDut",
    "perf_analysis": "IfuPerfAnalysisDut",
    "ifu": "IfuDut",
}


def load_class(name: str) -> type:
    if name not in DUT_CLASSES:
        raise ValueError(f"unknown IFU DUT {name!r}")
    directory = DUT_ROOT / name
    module_name = f"ifu_picker_{name}_{id(directory)}"
    spec = importlib.util.spec_from_file_location(
        module_name, directory / "__init__.py", submodule_search_locations=[str(directory)]
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load Picker package {directory}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return getattr(module, "DUT" + DUT_CLASSES[name])


class DutHarness:
    """One Picker DUT plus deterministic input/clock/sampling conventions."""

    def __init__(self, name: str, *, seed: int = 1) -> None:
        self.name = name
        cls = load_class(name)
        self.module = sys.modules[cls.__module__]
        # Coverage is attached by the toffee managed runner after fixture
        # setup, so the package must not open a coverage file of its own.
        # ``rand+reset+0`` zeroes the Verilator register randomization at
        # time zero.  Otherwise the generated initial block can still apply
        # random values on the first active cycle (after reset is released),
        # making an FSM's state nondeterministic despite an explicit reset.
        arguments = [name, f"+verilator+seed+{seed}", "+verilator+rand+reset+0"]
        self.dut = cls(self.module.xsp.StringVector(arguments), coverage_filename="")
        self.clocked = "clock" in vars(self.dut)
        if self.clocked:
            self.dut.InitClock("clock")
        self._inputs: dict[str, Any] = {}
        for attribute, signal in vars(self.dut).items():
            if attribute == "dut":
                continue
            if callable(getattr(signal, "IsInIO", None)) and signal.IsInIO() and not signal.IsOutIO():
                signal.AsImmWrite()
                self._inputs[attribute] = signal
        self._finished = False
        self._reset_done = False
        self.pruned: dict[tuple[str, int], int] = {}

    # -- input / output -----------------------------------------------------
    def set(self, **levels: int) -> None:
        for attribute, value in levels.items():
            signal = self._inputs.get(attribute)
            if signal is None:
                raise KeyError(f"{self.name}: unknown or non-input port {attribute!r}")
            signal.Set(int(value))

    def set_pruned(self, **levels: int) -> None:
        """Drive ports that the generator removed because they are constant.

        Firtool deletes an input whose value cannot affect any output, so the
        DUT never observes it.  Silently skipping such a port would hide a
        wiring mistake; this method therefore fails if the port actually
        exists (then it must be driven through :meth:`set`), and records the
        declared constant so the classification stays auditable.
        """

        for attribute, value in levels.items():
            if getattr(self.dut, attribute, None) is not None:
                raise AssertionError(
                    f"{self.name}: {attribute!r} exists on the DUT; drive it with set() "
                    "instead of declaring it pruned")
            self.pruned[(attribute, int(value))] = self.pruned.get(
                (attribute, int(value)), 0) + 1

    def set_many(self, levels: Mapping[str, int]) -> None:
        self.set(**dict(levels))

    def input_names(self) -> tuple[str, ...]:
        return tuple(self._inputs)

    def read(self, attribute: str) -> int:
        signal = getattr(self.dut, attribute, None)
        if signal is None:
            raise KeyError(f"{self.name}: no port {attribute!r}")
        return int(signal.U())

    def port_width(self, attribute: str) -> int:
        """Return a generated port's declared width for interface audits."""

        signal = getattr(self.dut, attribute, None)
        if signal is None:
            raise KeyError(f"{self.name}: no port {attribute!r}")
        return int(signal.mWidth)

    def read_pruned(self, attribute: str, constant: int = 0) -> int:
        """Read a port that the generator proved to be a constant.

        The declared ``constant`` is a *claim about the design*, not a default:
        the method refuses ports that exist (read them directly) and records
        the claim so a later audit can compare it with the model.  Passing a
        non-zero constant is therefore an explicit statement that the pruned
        value must be that number, never a convenience fallback.
        """

        if getattr(self.dut, attribute, None) is not None:
            raise AssertionError(
                f"{self.name}: {attribute!r} exists on the DUT; read it instead of "
                "declaring it pruned")
        self.pruned[(attribute, int(constant))] = self.pruned.get(
            (attribute, int(constant)), 0) + 1
        return int(constant)

    def pruned_claims(self) -> dict[tuple[str, int], int]:
        """Every pruned-port claim made so far, with its hit count."""

        return dict(sorted(self.pruned.items()))

    def read_many(self, *attributes: str) -> tuple[int, ...]:
        return tuple(self.read(attribute) for attribute in attributes)

    def bits(self, attribute: str) -> list[int]:
        value = self.read(attribute)
        return [int(bit) for bit in format(value, "b")[::-1]] if value else [0]

    def refresh(self) -> None:
        """Re-evaluate combinational logic without advancing a clock."""

        self.dut.RefreshComb()

    def step(self, cycles: int = 1) -> None:
        if not self.clocked:
            raise RuntimeError(f"{self.name} has no clock")
        self.dut.Step(cycles)

    def settle(self) -> None:
        """Make outputs readable and advance simulated time.

        Clocked DUTs have already re-evaluated their combinational cone at the
        last edge.  Clockless units need one time step: a bare ``RefreshComb``
        evaluates logic but does not advance time, so Verilator would not
        record toggle transitions between stimulus values.
        """

        if self.clocked:
            self.refresh()
        else:
            self.dut.Step(1)

    def reset_once(self) -> None:
        """Reset exactly once, after coverage has been attached to the DUT."""

        if self.clocked and not self._reset_done:
            self.reset()
            self._reset_done = True

    def reset(self, cycles: int = 3) -> None:
        if not self.clocked:
            self.refresh()
            return
        # Reset must not accidentally accept a leftover request on the
        # de-assertion edge: drive a quiet idle environment first.
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
