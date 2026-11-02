"""FTQ agent: owns producers, consumers, monitors and the pointer checker."""

from __future__ import annotations

import dataclasses
from typing import Iterable
from typing import Sequence

from toffee import Scoreboard
from suites.frontend.ftq.monitors.cycle import EdgeMonitor
from suites.frontend.ftq.monitors.cycle import InvariantMonitor
from suites.frontend.ftq.ftq.bundle.ports import FtqPorts
from suites.frontend.ftq.ftq.bundle.abi import metadata_inputs
from suites.frontend.ftq.ftq.bundle.slots import FtqInputPorts
from suites.frontend.ftq.ftq.driver.slots import FtqInputDriver
from suites.frontend.ftq.ftq.transaction.cycle import FtqInput, InputReceipt, allocation_plan
from suites.frontend.ftq.ftq.checker.model import FtqChecker
from suites.frontend.ftq.ftq.checker.commit import FtqCommits
from suites.frontend.ftq.ftq.checker.frontend import FtqFrontend
from suites.frontend.ftq.ftq.driver.encoding import encode_callret
from suites.frontend.ftq.ftq.driver.encoding import encode_prediction
from suites.frontend.ftq.ftq.monitor import decode
from suites.frontend.ftq.ftq.transaction.types import BackendRedirect
from suites.frontend.ftq.ftq.transaction.types import BackendWrite
from suites.frontend.ftq.ftq.transaction.types import CommitEvent
from suites.frontend.ftq.ftq.transaction.types import Entry
from suites.frontend.ftq.ftq.transaction.types import FetchRequest
from suites.frontend.ftq.ftq.transaction.types import FlushEvent
from suites.frontend.ftq.ftq.transaction.types import IfuRedirect
from suites.frontend.ftq.ftq.transaction.types import Meta
from suites.frontend.ftq.ftq.transaction.types import Pointers
from suites.frontend.ftq.ftq.transaction.types import PrefetchRequest
from suites.frontend.ftq.ftq.transaction.types import Prediction
from suites.frontend.ftq.ftq.transaction.types import PredictionOffer
from suites.frontend.ftq.ftq.transaction.types import PredictionSpec
from suites.frontend.ftq.ftq.transaction.types import RedirectEvent
from suites.frontend.ftq.ftq.transaction.types import Topdown
from suites.frontend.ftq.ftq.transaction.types import TrainingEntry
from suites.frontend.ftq.harness import Dut
from suites.frontend.ftq.oracle import CallRet
from suites.frontend.ftq.resolve_queue.transaction.types import ResolveReport


class FtqAgent:
    def __init__(self, dut: Dut) -> None:
        self.dut = dut
        self.ports = FtqPorts.bind(dut)
        self.input_ports = FtqInputPorts(dut, self.ports)
        self.input_driver = FtqInputDriver(dut, self.input_ports)
        self.input_scoreboard = Scoreboard('ftq.input-slots')
        self._frame = FtqInput()
        self._slot = self._epoch = 0
        self._input_receipts = []
        self._resetting = self._used = self._busy = self._failed = False
        self._finished = False
        self._inflight = None
        self.checker = FtqChecker()
        self.commit_checker = FtqCommits()
        self.frontend = FtqFrontend()
        self._prediction_revision = 0
        self.training_monitor = EdgeMonitor(
            "ftq.training", lambda d: decode.training(d, self.ports))
        self.commit_monitor = EdgeMonitor(
            "ftq.commit", lambda d: decode.commit_event(d, self.ports))
        self.redirect_monitor = EdgeMonitor(
            "ftq.redirect", lambda d: decode.redirect_event(d, self.ports))
        self.prefetch_monitor = EdgeMonitor(
            "ftq.prefetch", lambda d: decode.prefetch(d, self.ports),
            history=64)
        self.fetch_monitor = EdgeMonitor(
            "ftq.fetch", lambda d: decode.fetch(d, self.ports), history=64)
        self.flush_monitor = EdgeMonitor(
            "ftq.flush", lambda d: decode.flush(d, self.ports), history=64)
        self.topdown_monitor = EdgeMonitor(
            "ftq.topdown", lambda d: decode.topdown(d, self.ports), history=64)
        self.private_monitor = EdgeMonitor(
            "ftq.backend_write", lambda d: decode.backend_write(d, self.ports),
            history=64)
        self.owners_monitor = EdgeMonitor('ftq.owners', decode.pointers, history=64)
        self.pointer_monitor = InvariantMonitor(
            "ftq.pointers", self.checker.check_pointers)
        self.last_redirect_topdown: Topdown | None = None
        self._started = False

    async def start(self) -> "FtqAgent":
        if self._used:
            raise RuntimeError('FTQ agent cannot be restarted')
        self._used = True
        for monitor in (self.training_monitor, self.commit_monitor,
                        self.redirect_monitor, self.prefetch_monitor,
                        self.fetch_monitor, self.flush_monitor,
                        self.topdown_monitor, self.private_monitor,
                        self.owners_monitor,
                        self.pointer_monitor):
            self.dut.add_monitor(monitor)
        await self.input_driver.__aenter__()
        self._started = True
        self.input_driver.present(self._frame)
        return self

    async def aclose(self) -> None:
        self.input_driver.close()
        self._started = False

    def _require_clean(self):
        if not self._started:
            raise RuntimeError('FTQ agent is not running')
        if self._failed or self._inflight is not None:
            raise RuntimeError('FTQ has unreconciled input work after failure/cancellation')
        if self.input_scoreboard.status.failed:
            raise RuntimeError('FTQ has a prior input comparison failure')
        self.commit_checker.require_clean()
        self.frontend.require_clean()
        self.dut.check_sampling()

    def _enter_work(self):
        if self._busy:
            raise RuntimeError('concurrent FTQ input work is not supported')
        self._require_clean()
        if self._finished:
            raise RuntimeError('FTQ input stream is finished')
        self._busy = True

    def _present(self, frame, *, new_prediction=False):
        if new_prediction or frame.prediction is not self._frame.prediction:
            self._prediction_revision += 1
        self.input_driver.present(frame)
        self.frontend.present(frame, self._prediction_revision)
        self._frame = frame

    def _check_frontend_preview(self):
        self._require_clean()
        observations = {monitor.name: monitor.sample(self.dut) for monitor in (
            self.training_monitor, self.redirect_monitor, self.prefetch_monitor, self.fetch_monitor,
            self.flush_monitor, self.topdown_monitor, self.private_monitor)}
        observations['ftq.owners'] = self.owners_monitor.sample(self.dut)
        try:
            self.frontend.check_phase(self._frame, observations, self._slot + 1)
        except BaseException:
            self._failed = True
            raise

    def _stage(self, **values):
        frame = dataclasses.replace(self._frame, **values)
        self.input_ports.encode(frame)
        self._enter_work()
        try:
            self._present(frame, new_prediction='prediction' in values)
            self._check_frontend_preview()
        except BaseException:
            self._failed = True
            raise
        finally:
            self._busy = False

    async def _cycle(self, frame):
        self._slot += 1
        self._inflight = frame
        if frame.prediction is not self._frame.prediction:
            self._prediction_revision += 1
        self.frontend.begin_slot(frame, self._prediction_revision, self._slot)
        event = await self.input_driver.send(frame)
        cycle = self.dut.cycle_history[-1]
        assert cycle.after.event.tick == event.tick, 'FTQ input/observation tick mismatch'
        expected = self.input_ports.encode(frame)
        for sample in (cycle.before, cycle.after):
            self.input_scoreboard.check(expected=expected, actual=dict(sample.value.inputs))
        self.commit_checker.advance_slot(frame, self._slot,
            dict(cycle.before.value.observations)['ftq.commit'],
            dict(cycle.after.value.observations)['ftq.commit'], event.tick)
        self.frontend.advance_slot(frame, self._slot, dict(cycle.before.value.observations),
                                   dict(cycle.after.value.observations), event.tick)
        if frame.reset and not self._resetting:
            self._epoch += 1
        self._resetting = frame.reset
        self._input_receipts.append(InputReceipt(self._epoch, self._slot, frame, event.tick))
        self._frame = frame
        self._inflight = None

    async def _run(self, frames, *, final=None, tap=None):
        frames = tuple(frames)
        for frame in (*frames, *((final,) if final is not None else ())):
            self.input_ports.encode(frame)
        self._enter_work()
        result = None
        try:
            for index, frame in enumerate(frames):
                await self._cycle(frame)
                if index == 0 and tap is not None:
                    result = tap()
            if final is not None:
                self._present(final)
            return result
        except BaseException:
            self._failed = True
            raise
        finally:
            self._busy = False

    async def _pulse(self, name, value, *, release_edge=True, tap=None):
        active = dataclasses.replace(self._frame, **{name: value})
        idle_value = getattr(FtqInput(), name)
        released = dataclasses.replace(active, **{name: idle_value})
        frames = (active, released) if release_edge else (active,)
        return await self._run(frames, final=released, tap=tap)

    async def reset(self, *, asserted=2, released=2) -> None:
        if any(type(value) is not int or value < 1 for value in (asserted, released)):
            raise ValueError('FTQ reset needs positive integer budgets')
        await self._run((FtqInput(reset=True),) * asserted + (FtqInput(),) * released)
        for monitor in (self.training_monitor, self.commit_monitor,
                        self.redirect_monitor, self.prefetch_monitor,
                        self.fetch_monitor, self.flush_monitor,
                        self.topdown_monitor, self.private_monitor):
            monitor.clear()
        self.owners_monitor.clear()
        self.checker = FtqChecker()
        self.last_redirect_topdown = None

    async def step(self, cycles: int = 1) -> None:
        if type(cycles) is not int or cycles < 1:
            raise ValueError('FTQ step needs a positive integer cycle budget')
        await self._run((self._frame,) * cycles)

    async def cycle(self, frame: FtqInput):
        """One complete simultaneous slot, retained until explicitly replaced."""
        await self._run((frame,))

    def input_receipt(self):
        self._require_clean()
        return tuple(self._input_receipts)

    def receipt(self):
        self._require_clean()
        return dict(inputs=self.input_receipt(), commits=self.commit_checker.receipt(), frontend=self.frontend.receipt())

    async def drain_training(self, *, cycles=24):
        """Explicit BPU consumer schedule; finish never invents readiness."""
        if type(cycles) is not int or cycles < 1:
            raise ValueError('FTQ training drain needs a positive integer cycle budget')
        await self.consumers(train=1)
        for _ in range(cycles):
            await self.step(1)
            if not self.frontend.audit():
                break
        else:
            self._failed = True
            raise AssertionError('FTQ explicit training drain budget exhausted')
        await self.consumers(train=0)
        await self.step(2)

    async def finish(self, *, cycles=66):
        """Bounded local obligations; not full-machine program completion.

        Readiness stays as explicitly supplied. No callret/metadata/ROB commit,
        ready, redirect, response or reset is invented to erase outstanding work.
        Unaccepted backpressured ICache offers remain explicitly in the receipt;
        a handoff is not an ICache reply or an invented backend retirement.
        """
        if self._finished:
            return self.receipt()
        if type(cycles) is not int or cycles < 2:
            raise ValueError('FTQ finish needs at least two idle observation cycles')
        self._enter_work()
        idle = FtqInput(consumers=self._frame.consumers)
        try:
            if self._frame != idle:
                raise AssertionError('FTQ staged producers remain active; explicitly release them')
            if (self.frontend.audit() or self.frontend.receivers.pending_resolve is not None) and not idle.consumers.train:
                raise AssertionError('FTQ accepted training reports remain; explicitly drain training')
            quiet = 0
            for _ in range(cycles):
                await self._cycle(idle)
                pending = self.commit_checker.audit()
                quiet = quiet + 1 if not pending and self.frontend.quiet(idle, self._slot + 1) else 0
                if quiet >= 2:
                    break
            else:
                raise AssertionError('FTQ finish budget exhausted with pending local obligations')
            assert not self.commit_checker.audit(), 'FTQ accepted commits remain unfinished'
            self._finished = True
            return self.receipt()
        except BaseException:
            self._failed = True
            raise
        finally:
            self._busy = False

    async def consumers(self, **values: int) -> None:
        """Update the readiness levels, keeping channels that are not named."""

        spec = dataclasses.replace(self._frame.consumers, **values)
        self._stage(consumers=spec)

    # ------------------------------------------------------------------ producer

    async def offer(self, prediction: Prediction) -> PredictionOffer:
        """Drive a prediction without taking an edge; call complete_offer()."""

        encode_prediction(prediction)
        self._stage(prediction=prediction)
        value = decode.prediction_offer(self.dut, self.ports)
        return PredictionOffer(ready=value.ready, wen=value.wen,
                               index=value.index, start_pc=value.start_pc)

    async def complete_offer(self) -> None:
        """Deassert the whole prediction request, not just ``valid``.

        The generated RTL updates bpuPtr from the s2/s3 override bits without
        re-checking prediction.valid, so a stale override bit is a producer
        protocol violation rather than a legal idle value.
        """

        self._stage(prediction=None)

    async def predict(self, prediction: Prediction) -> PredictionOffer:
        """Offer one prediction as the BPU producer; requires ready."""

        offer = await self.offer(prediction)
        if not offer.ready:
            self._failed = True
            raise AssertionError(f"prediction offered while not ready: {offer}")
        released = dataclasses.replace(self._frame, prediction=None)
        await self._run((self._frame, released))
        return offer

    async def override(self, prediction: Prediction) -> PredictionOffer:
        """Offer an s2/s3 override; override requests ignore prediction.ready."""

        encode_prediction(prediction)
        if not (prediction.s2_override or prediction.s3_override):
            raise ValueError("override() needs s2_override or s3_override")
        offer = await self.offer(prediction)
        released = dataclasses.replace(self._frame, prediction=None)
        await self._run((self._frame, released))
        return offer

    async def write_meta(self, meta: Meta) -> None:
        await self._pulse('meta', meta)

    def meta_payload(self, value: int) -> dict[str, int]:
        """All-ones or all-zeros for every stored metadata payload bit.

        The payload spans fields whose widths are defined by the generated
        binding, so the bundle exposes the widths instead of each test pin.
        """

        if type(value) is not int or value not in (0, 1):
            raise ValueError('metadata fill must be an integer bit')
        return {name: (1 << width) - 1 if value else 0 for name, width in metadata_inputs().items()}

    async def drive_backend_redirect(self, event: BackendRedirect) -> tuple[RedirectEvent | None, FlushEvent]:
        """Present the redirect without taking an edge."""

        self._stage(backend_redirect=event)
        return (self.redirect_monitor.sample(self.dut), self.flush_monitor.sample(self.dut))

    async def release_backend_redirect(self) -> None:
        """Release the redirect pins without advancing the clock."""

        self._stage(backend_redirect=None)

    async def finish_backend_redirect(self) -> None:
        # Keep the request asserted for the accepting edge, then release it.
        released = dataclasses.replace(self._frame, backend_redirect=None)
        await self._run((self._frame, released))

    async def backend_redirect(self, event: BackendRedirect) -> tuple[RedirectEvent | None, FlushEvent]:
        return await self._pulse('backend_redirect', event, tap=self._capture_redirect)

    def _capture_redirect(self):
        self.last_redirect_topdown = self.topdown_monitor.sample(self.dut)
        return self.redirect_monitor.sample(self.dut), self.flush_monitor.sample(self.dut)

    async def drive_ifu_redirect(self, event: IfuRedirect) -> None:
        """Present the IFU redirect without taking an edge."""

        self._stage(ifu_redirect=event)

    async def release_ifu_redirect(self) -> None:
        """Release the IFU redirect pins without advancing the clock."""

        self._stage(ifu_redirect=None)

    async def finish_ifu_redirect(self) -> None:
        await self._run((dataclasses.replace(self._frame, ifu_redirect=None),))

    async def ifu_redirect(self, event: IfuRedirect) -> tuple[RedirectEvent | None, FlushEvent]:
        return await self._pulse('ifu_redirect', event, tap=self._capture_redirect)

    async def resolve_hold(self, reports: Iterable[ResolveReport]) -> None:
        """Present resolve lanes without taking an edge (handshake tests)."""

        reports = tuple(reports)
        if len(reports) > 3:
            raise ValueError("backend accepts at most three lane reports")
        self._stage(resolve=reports + (None,) * (3 - len(reports)))

    async def resolve_stream(self, groups: Sequence[Sequence[ResolveReport]]) -> None:
        """Drive adjacent resolve groups without an idle gap between them."""

        frames = []
        for group in groups:
            if len(group) > 3:
                raise ValueError("backend accepts at most three lane reports")
            frames.append(dataclasses.replace(self._frame, resolve=tuple(group) + (None,) * (3 - len(group))))
        frames.append(dataclasses.replace(self._frame, resolve=(None,) * 3))
        await self._run(frames)

    async def resolve_release(self) -> None:
        self._stage(resolve=(None,) * 3)

    async def resolve(self, reports: Iterable[ResolveReport], *,
                      source: str = "backend") -> None:
        reports = tuple(reports)
        if not reports:
            raise ValueError("resolve() needs at least one report")
        if source != "backend":
            raise ValueError("FTQ accepts only the three backend resolve lanes")
        if len(reports) > 3:
            raise ValueError("backend accepts at most three lane reports")
        await self._pulse('resolve', reports + (None,) * (3 - len(reports)))

    def set_resolve_lanes(self, lanes: Sequence[ResolveReport | None]) -> None:
        """Set lane pins without advancing the clock."""

        if len(lanes) != 3:
            raise ValueError("backend lane vector has exactly three entries")
        self._stage(resolve=tuple(lanes))

    async def resolve_cycle(self, lanes: Sequence[ResolveReport | None]) -> None:
        """Present lanes for exactly one edge, without a release edge."""

        if len(lanes) != 3:
            raise ValueError("backend lane vector has exactly three entries")
        await self._run((dataclasses.replace(self._frame, resolve=tuple(lanes)),))

    async def resolve_lanes(self, lanes: Sequence[ResolveReport | None]) -> None:
        if len(lanes) != 3:
            raise ValueError("backend lane vector has exactly three entries")
        await self._pulse('resolve', tuple(lanes))

    async def callret_rows(self, rows: Sequence[CallRet | None]) -> None:
        if len(rows) != len(self.ports.callret):
            raise ValueError(f"expected {len(self.ports.callret)} call-return lanes")
        await self._pulse('callret', tuple(rows), release_edge=False)

    async def callret(self, lane: int, row: CallRet) -> None:
        if type(lane) is not int or not 0 <= lane < len(self.ports.callret):
            raise ValueError(f"call-return lane {lane} outside 0..7")
        encode_callret(row)
        rows = [None] * 8
        rows[lane] = row
        await self.callret_rows(rows)

    async def release_callret(self) -> None:
        self._stage(callret=(None,) * 8)

    async def commit(self, index: int, flag: int = 0) -> None:
        await self._pulse('commit', (flag, index))

    async def ahead_set(self, index: int, flag: int = 0) -> None:
        await self._run((dataclasses.replace(self._frame, ahead=(flag, index)),))

    async def ahead_clear(self) -> None:
        self._stage(ahead=None)

    # ------------------------------------------------------------------ producer helper

    async def allocate(self, specs: Sequence[PredictionSpec], *,
                       consume: bool = False, with_meta: bool = True,
                       meta_limit: int | None = None,
                       start_index: int = 0,
                       start_flag: int = 0) -> list[int]:
        """Admit predictions with the same timing the BPU producer uses."""

        plan = allocation_plan(specs, consume=consume, with_meta=with_meta, meta_limit=meta_limit,
                               start_index=start_index, start_flag=start_flag)
        if consume:
            await self.consumers(prefetch=1, mainpipe=1)
        pcs = []
        for index, (prediction, meta) in enumerate(plan):
            offer = await self.offer(prediction)
            if not offer.ready:
                self._failed = True
                raise AssertionError(f"prediction {index} offered without room")
            pcs.append(prediction.start_pc)
            await self.step(1)
            await self.complete_offer()
            await self.step(1)
            if meta is not None:
                await self.write_meta(meta)
        return pcs

    # ------------------------------------------------------------------ observation

    def prediction_ready(self) -> bool:
        self._require_clean()
        self._check_frontend_preview()
        return self.ports.prediction_ready.b("ready")

    def prefetch(self) -> PrefetchRequest:
        self._require_clean()
        self._check_frontend_preview()
        return self.prefetch_monitor.sample(self.dut)

    def fetch(self) -> FetchRequest:
        self._require_clean()
        self._check_frontend_preview()
        return self.fetch_monitor.sample(self.dut)

    def training(self) -> TrainingEntry | None:
        self._require_clean()
        self._check_frontend_preview()
        return self.training_monitor.sample(self.dut)

    def commit_event(self) -> CommitEvent | None:
        self._require_clean()
        value = self.commit_monitor.sample(self.dut)
        try:
            self.commit_checker.check_phase(value, reset=self._frame.reset)
        except BaseException:
            self._failed = True
            raise
        return value

    def redirect_event(self) -> RedirectEvent | None:
        self._require_clean()
        self._check_frontend_preview()
        return self.redirect_monitor.sample(self.dut)

    def flush(self) -> FlushEvent:
        self._require_clean()
        self._check_frontend_preview()
        return self.flush_monitor.sample(self.dut)

    def topdown(self) -> Topdown:
        self._require_clean()
        self._check_frontend_preview()
        return self.topdown_monitor.sample(self.dut)

    def redirect_topdown(self) -> Topdown:
        self._require_clean()
        if self.last_redirect_topdown is None:
            raise AssertionError("no redirect topdown snapshot was captured")
        return self.last_redirect_topdown

    def backend_write(self) -> BackendWrite:
        self._require_clean()
        self._check_frontend_preview()
        return self.private_monitor.sample(self.dut)

    def pointers(self) -> Pointers:
        self._require_clean()
        return decode.pointers(self.dut)

    def entry(self, index: int) -> Entry:
        self._require_clean()
        return decode.entry(self.dut, index)

    def meta_redirect(self, index: int, field: str) -> int:
        self._require_clean()
        return self.dut.internal(f"FtqDut_top.Ftq.metaQueueRedirect_{index}_{field}")

    def meta_resolve(self, index: int, field: str) -> int:
        self._require_clean()
        return self.dut.internal(f"FtqDut_top.Ftq.metaQueueResolve_{index}_{field}")

    def meta_commit(self, index: int, field: str) -> int:
        self._require_clean()
        return self.dut.internal(f"FtqDut_top.Ftq.metaQueueCommit_{index}_{field}")

    def assert_training_mask(self) -> None:
        training = self.training()
        if training is not None and not self.checker.training_mask_ok(training):
            raise AssertionError("training contains a branch after the first mispredict")
