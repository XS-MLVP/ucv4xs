"""Small uc-toffee harness for the generated FTQ DUTs.

The DUT packages are produced by Picker from the complete DefaultConfig
XiangShan RTL.  Tests drive the real ports through xspcomm and advance the
clock through toffee's ``Execution``/``XCommClockBackend``.  No RTL or
generated binding is modified.
"""

from __future__ import annotations
from suites.frontend.ftq import ROOT as _SUITE_ROOT

import importlib.util
from pathlib import Path
import sys
from typing import Any
from typing import Iterable
from typing import Mapping

from toffee import ClockCycles
from toffee import Execution
from toffee import XCommClockBackend


ROOT = _SUITE_ROOT
DUT_ROOT = ROOT / "dut"


class Dut:
    """One live native model plus its owned toffee execution."""

    _serial = 0

    def __init__(self, name: str, coverage_path: Path | None) -> None:
        type(self)._serial += 1
        self.name = name
        self.coverage_path = coverage_path
        package = DUT_ROOT / name
        if not (package / "__init__.py").is_file():
            raise RuntimeError(f"missing generated DUT {package}")
        module_name = f"ftq_native_{name}_{self._serial}"
        spec = importlib.util.spec_from_file_location(
            module_name,
            package / "__init__.py",
            submodule_search_locations=[str(package)],
        )
        if spec is None or spec.loader is None:
            raise RuntimeError(f"cannot load generated DUT {package}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        exported = [value for key, value in vars(module).items() if key.startswith("DUT")]
        if len(exported) != 1:
            raise RuntimeError(f"expected one exported DUT class in {package}")
        self._module = module
        self.dut = exported[0](
            [],
            coverage_filename="" if coverage_path is None else str(coverage_path),
        )
        self.dut.InitClock("clock")
        self._inputs: dict[str, Any] = {}
        for key in dir(self.dut):
            signal = getattr(self.dut, key)
            if callable(getattr(signal, "IsInIO", None)) and signal.IsInIO() and not signal.IsOutIO():
                if key == "clock":
                    continue
                signal.AsImmWrite()
                signal.Set(0)
                self._inputs[key] = signal
        self._backend: XCommClockBackend | None = None
        self._execution: Execution | None = None
        self._finished = False
        self._internal: dict[str, Any] = {}
        self._invariants = name == "ftq"
        self._monitors: list[Any] = []
        self._claims: dict[str, str] = {}

    def input_names(self) -> tuple[str, ...]:
        return tuple(self._inputs)

    def output_names(self) -> frozenset[str]:
        cached = getattr(self, "_output_names", None)
        if cached is not None:
            return cached
        names = set()
        for key in dir(self.dut):
            signal = getattr(self.dut, key)
            if callable(getattr(signal, "IsOutIO", None)) and signal.IsOutIO():
                names.add(key)
        self._output_names = frozenset(names)
        return self._output_names

    def claim(self, pin: str, owner: str) -> None:
        """Register pin ownership; two live drivers may not share a pin."""

        previous = self._claims.get(pin)
        if previous not in (None, owner):
            raise RuntimeError(f"pin {pin} already owned by {previous}, cannot claim for {owner}")
        self._claims[pin] = owner

    def add_monitor(self, monitor: Any) -> None:
        self._monitors.append(monitor)

    def __enter__(self) -> "Dut":
        return self

    def __exit__(self, *exc: object) -> None:
        if self._execution is not None:
            raise RuntimeError("leave the async Dut context before the sync context")
        self._finish()

    def input(self, name: str) -> Any:
        try:
            return self._inputs[name]
        except KeyError as error:
            raise KeyError(f"{self.name} has no input named {name!r}") from error

    def set(self, values: Mapping[str, int | bool]) -> None:
        for name, value in values.items():
            self.input(name).Set(int(value))

    def set_many(self, values: Iterable[tuple[str, int | bool]]) -> None:
        for name, value in values:
            self.input(name).Set(int(value))

    def refresh(self) -> None:
        """Propagate immediate input writes through combinational logic."""
        if self._backend is not None:
            self._backend.refresh_comb()
        else:
            self.dut.xclock.RefreshComb()

    def u(self, name: str) -> int:
        return int(getattr(self.dut, name).U())

    def b(self, name: str) -> bool:
        return bool(self.u(name))

    def signal(self, path: str) -> Any:
        try:
            return self._internal[path]
        except KeyError:
            handle = self.dut.GetInternalSignal(path)
            if handle is None:
                raise KeyError(f"{self.name} has no internal signal {path!r}") from None
            self._internal[path] = handle
            return handle

    def internal(self, path: str) -> int:
        return int(self.signal(path).U())

    def internal_u(self, module: str, signal: str) -> int:
        return self.internal(f"{self.dut.__class__.__name__.removeprefix('DUT')}_top.{module}.{signal}")

    def _owner(self, name: str, index: int = 0) -> tuple[int, int]:
        base = f"FtqDut_top.Ftq.{name}_ptrs_{index}"
        return (self.internal(base + "_flag"), self.internal(base + "_value"))

    @staticmethod
    def _after(left: tuple[int, int], right: tuple[int, int]) -> bool:
        """CircularQueuePtr ``>``: flag xor value-compare (not a 7-bit key)."""

        return bool((left[0] ^ right[0]) ^ (left[1] > right[1]))

    @staticmethod
    def _full(left: tuple[int, int], right: tuple[int, int]) -> bool:
        return left[0] != right[0] and left[1] == right[1]

    @staticmethod
    def _distance(enq: tuple[int, int], deq: tuple[int, int]) -> int:
        if enq[0] == deq[0]:
            return enq[1] - deq[1]
        return 64 + enq[1] - deq[1]

    def check_invariants(self) -> None:
        """Check the pointer contract the design declares as XSError.

        The generated RTL strips those assertions (no ``$fatal`` remains), so
        this passive monitor replaces them for pointer ownership.  It mirrors
        the same circular-pointer comparisons and full-queue suppression, so a
        wrap cannot be mistaken for a violation.  The FTQ agent also registers
        an ``InvariantMonitor`` over the same contract; this transport-level
        check keeps the guard active even when a test does not start an agent.
        """

        if not self._invariants:
            return
        bpu = self._owner("bpuPtr")
        pf = self._owner("pfPtr")
        fetch = self._owner("fetchPtr")
        commit = self._owner("commitPtr")
        pnr = self._owner("pnrPtr")
        problems = []
        if self._after(fetch, bpu) and not self._full(bpu, fetch):
            problems.append(f"fetch {fetch} runs ahead of bpu {bpu}")
        if self._after(pf, bpu) and not self._full(bpu, pf):
            problems.append(f"pf {pf} runs ahead of bpu {bpu}")
        if self._after(pnr, bpu) and not self._full(pnr, bpu):
            problems.append(f"pnr {pnr} runs ahead of bpu {bpu}")
        distance = self._distance(bpu, commit)
        if not 0 <= distance <= 64:
            problems.append(f"commit is not behind bpu within one lap: {commit} vs {bpu}")
        if problems:
            raise AssertionError("FTQ pointer invariant violated: " + ", ".join(problems))

    async def __aenter__(self) -> "Dut":
        self._backend = XCommClockBackend(self.dut.GetXClock())
        self._execution = Execution(self._backend, max_batch_ticks=512)
        await self._execution.__aenter__()
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        try:
            if self._execution is not None:
                await self._execution.__aexit__(None, None, None)
        finally:
            if self._backend is not None:
                self._backend.close()
            self._execution = None
            self._backend = None
            self._finish()

    def _finish(self) -> None:
        if not self._finished:
            self._finished = True
            self.dut.Finish()

    async def reset(self, asserted: int = 2, released: int = 2) -> None:
        self.dut.reset.Set(1)
        await self.edge(asserted)
        self.dut.reset.Set(0)
        await self.edge(released)
        self.refresh()

    async def edge(self, cycles: int = 1) -> None:
        if self._backend is None:
            raise RuntimeError("Dut must be entered before advancing the clock")
        await ClockCycles(self.dut.clock, cycles)
        self.refresh()
        self.check_invariants()
        for monitor in self._monitors:
            monitor.observe(self)

    async def pulse(self, values: Mapping[str, int | bool], *, hold: int = 1) -> None:
        """Hold a one-cycle request and release it before the next edge.

        The generated model commits immediate writes on the next rising edge;
        one extra edge makes the post-request state visible to tests.
        """

        self.set(values)
        self.refresh()
        await self.edge(hold)
        for name in values:
            self.input(name).Set(0)
        self.refresh()
        await self.edge(1)


def coverage_path(directory: Path, dut: str, nodeid: str) -> Path:
    safe = nodeid.replace("::", "-").replace("/", "-").replace(".", "-")
    target = directory / dut / f"{safe}.dat"
    target.parent.mkdir(parents=True, exist_ok=True)
    return target
