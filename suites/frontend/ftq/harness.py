"""Small uc-toffee harness for the generated FTQ DUTs.

The DUT packages are produced by Picker from the complete DefaultConfig
XiangShan RTL.  Tests drive the real ports through xspcomm and advance the
clock through toffee's ``Execution``/``XCommClockBackend``.  No RTL or
generated binding is modified.
"""

from __future__ import annotations
from suites.frontend.ftq import ROOT as _SUITE_ROOT

import importlib.util
from collections import deque
from pathlib import Path
import sys
from typing import Any
from typing import Iterable
from typing import Mapping

from toffee import ClockCycles
from toffee import Execution
from toffee import XCommClockBackend
from toffee import DriveStable, RisingEdge
from ucv.runtime import native_seed
from suites.frontend.ftq.monitors.cycle import CycleSnapshot, SampledCycle, CycleMonitor, InvariantMonitor, freeze


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
            module.xsp.StringVector([name, native_seed()]),
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
        # CommitQueue owns its own SDK full-input slots and phase monitors.
        # ResolveQueue/Ftq use the shared stream while their legacy driver APIs
        # are being migrated; do not add a second pause owner to CommitQueue.
        self._clock_slots = name != 'commit_queue'
        self._pause_context = None
        self._cycle_monitors = ()
        self._bound_monitors = []
        self._sampling_failed = self._edge_busy = False
        self._last_sample_tick = None
        self.sampled_cycles = 0
        self.cycle_history = deque(maxlen=256)

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

        self.claim_many((pin,), owner)

    def claim_many(self, pins: Iterable[str], owner: str) -> None:
        """Validate an entire driver claim before recording any ownership."""
        pins = tuple(pins)
        if not owner or type(owner) is not str:
            raise ValueError('pin owner must have a nonempty component label')
        if len(pins) != len(set(pins)):
            raise ValueError('duplicate physical inputs in one driver claim')
        for pin in pins:
            if pin not in self._inputs:
                raise KeyError(f'cannot claim non-input pin {pin!r}')
            previous = self._claims.get(pin)
            if previous is not None:
                # Labels describe components, not object identity. Two Driver
                # instances with the same label are still two physical owners.
                raise RuntimeError(f"pin {pin} already owned by {previous}, cannot claim for {owner}")
        self._claims.update((pin, owner) for pin in pins)

    def add_monitor(self, monitor: Any) -> None:
        if not self._clock_slots:
            raise RuntimeError('CommitQueue owns its separate SDK phase monitors')
        if any(item.name == monitor.name for item in self._bound_monitors):
            raise RuntimeError(f'duplicate FTQ observation channel {monitor.name}')
        self._monitors.append(monitor)
        self._bound_monitors.append(monitor)

    def _capture_cycle(self, *, before):
        self.check_sampling()
        inputs = tuple((name, int(signal.U())) for name, signal in self._inputs.items())
        values = []
        if not before:
            self.check_invariants()
        for monitor in self._monitors:
            # The existing pointer safety net is a post-edge invariant. All
            # data channels are frozen in both phases before any view changes.
            value = None if before and isinstance(monitor, InvariantMonitor) else monitor.sample(self)
            values.append((monitor.name, freeze(value)))
        return CycleSnapshot(inputs, tuple(values))

    async def _pause_clock(self):
        self._pause_context = self._execution.paused()
        await self._pause_context.__aenter__()

    def check_sampling(self):
        if self._sampling_failed:
            raise RuntimeError('FTQ has unreconciled cycle sampling after failure/cancellation')
        if self._monitors != self._bound_monitors:
            self._sampling_failed = True
            raise RuntimeError('FTQ registered observer disappeared or was replaced')
        if self._cycle_monitors and not all(monitor.active for monitor in self._cycle_monitors):
            self._sampling_failed = True
            raise RuntimeError('FTQ phase observer is closed or not active')

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
        if self._clock_slots:
            await self._pause_clock()
            self._cycle_monitors = (
                CycleMonitor(DriveStable(self.dut.clock),
                    capture=lambda _: self._capture_cycle(before=True)),
                CycleMonitor(RisingEdge(self.dut.clock),
                    capture=lambda _: self._capture_cycle(before=False)))
            for monitor in self._cycle_monitors:
                monitor.start(self._execution)
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        errors = []
        try:
            for monitor in reversed(self._cycle_monitors):
                try:
                    await monitor.aclose()
                except BaseException as error:
                    errors.append(error)
            context, self._pause_context = self._pause_context, None
            if context is not None:
                await context.__aexit__(None, None, None)
            if self._execution is not None:
                await self._execution.__aexit__(None, None, None)
        except BaseException as error:
            errors.append(error)
        finally:
            if self._backend is not None:
                self._backend.close()
            self._execution = None
            self._backend = None
            self._finish()
        if errors:
            if len(errors) == 1:
                raise errors[0]
            raise BaseExceptionGroup('FTQ observation cleanup failures', errors)

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
        if type(cycles) is not int or cycles < 1:
            raise ValueError('FTQ edge needs a positive integer cycle budget')
        if not self._clock_slots:
            # Only pre-agent initialization uses this path for CommitQueue.
            await ClockCycles(self.dut.clock, cycles)
            self.refresh()
            return
        self.check_sampling()
        if self._edge_busy:
            raise RuntimeError('concurrent FTQ clock-slot work is not supported')
        self._edge_busy = True
        try:
            remaining = cycles
            while remaining:
                # Delivery is still SDK lossless for every edge. Chunk large
                # waits so a valid user wait cannot overflow an unread queue.
                count = min(remaining, 32)
                context, self._pause_context = self._pause_context, None
                await context.__aexit__(None, None, None)
                try:
                    event = await ClockCycles(self.dut.clock, count)
                finally:
                    await self._pause_clock()
                before_monitor, after_monitor = self._cycle_monitors
                for offset in range(count):
                    before, after = await before_monitor.recv(), await after_monitor.recv()
                    expected_tick = event.tick - 2 * (count - 1 - offset)
                    assert before.event.tick + 1 == after.event.tick == expected_tick, 'FTQ stale/missing phase snapshot'
                    if self._last_sample_tick is not None:
                        assert after.event.tick == self._last_sample_tick + 2, 'FTQ skipped/repeated cycle snapshot'
                    assert isinstance(before.value, CycleSnapshot) and isinstance(after.value, CycleSnapshot)
                    names = tuple(monitor.name for monitor in self._bound_monitors)
                    assert tuple(name for name, _ in before.value.observations) == names, 'FTQ missing pre-edge channel'
                    assert tuple(name for name, _ in after.value.observations) == names, 'FTQ missing post-edge channel'
                    # All channels were captured before any decoder-view update.
                    for monitor, (_, value) in zip(self._bound_monitors, after.value.observations, strict=True):
                        monitor.record(value, after.event)
                    self._last_sample_tick = after.event.tick
                    self.sampled_cycles += 1
                    self.cycle_history.append(SampledCycle(before, after))
                remaining -= count
            return event
        except BaseException:
            self._sampling_failed = True
            raise
        finally:
            self._edge_busy = False

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
