"""FTQ agent: owns producers, consumers, monitors and the pointer checker."""

from __future__ import annotations

import dataclasses
from typing import Iterable
from typing import Mapping
from typing import Sequence

from suites.frontend.ftq.commit_queue.checker.model import CommitChecker
from suites.frontend.ftq.drivers.signal import LevelDriver
from suites.frontend.ftq.drivers.signal import PulseDriver
from suites.frontend.ftq.drivers.signal import ResetDriver
from suites.frontend.ftq.monitors.cycle import EdgeMonitor
from suites.frontend.ftq.monitors.cycle import InvariantMonitor
from suites.frontend.ftq.ports import Pins
from suites.frontend.ftq.ftq.bundle.ports import FtqPorts
from suites.frontend.ftq.ftq.checker.model import FtqChecker
from suites.frontend.ftq.ftq.driver.encoding import encode_backend_redirect
from suites.frontend.ftq.ftq.driver.encoding import encode_callret
from suites.frontend.ftq.ftq.driver.encoding import encode_ifu_redirect
from suites.frontend.ftq.ftq.driver.encoding import encode_meta
from suites.frontend.ftq.ftq.driver.encoding import encode_prediction
from suites.frontend.ftq.ftq.driver.encoding import encode_resolve
from suites.frontend.ftq.ftq.monitor import decode
from suites.frontend.ftq.ftq.transaction.types import BackendRedirect
from suites.frontend.ftq.ftq.transaction.types import BackendWrite
from suites.frontend.ftq.ftq.transaction.types import CommitEvent
from suites.frontend.ftq.ftq.transaction.types import Consumers
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


def _union(dut: Dut, groups: Sequence[Pins], name: str) -> Pins:
    names = {}
    for index, group in enumerate(groups):
        for logical, pin in group.names.items():
            names[f"{index}.{logical}"] = pin
    return Pins(dut, names, name=name)


class FtqAgent:
    def __init__(self, dut: Dut) -> None:
        self.dut = dut
        self.ports = FtqPorts.bind(dut)
        self.reset_driver = ResetDriver(
            dut, Pins(dut, {"reset": "reset"}, name="ftq.reset"))
        self.prediction_driver = PulseDriver(dut, self.ports.prediction)
        self.meta_driver = PulseDriver(dut, self.ports.meta)
        self.backend_redirect_driver = PulseDriver(dut, self.ports.backend_redirect)
        self.ifu_redirect_driver = PulseDriver(dut, self.ports.ifu_redirect)
        self.resolve_driver = PulseDriver(
            dut, _union(dut, self.ports.resolve, "ftq.resolve"))
        self.callret_driver = PulseDriver(
            dut, _union(dut, self.ports.callret, "ftq.callret"))
        self.commit_driver = PulseDriver(dut, self.ports.commit)
        self.consumer_driver = LevelDriver(dut, self.ports.consumers)
        self.ahead_driver = PulseDriver(dut, self.ports.ahead)
        self.checker = FtqChecker()
        self.commit_checker = CommitChecker()
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
        self.pointer_monitor = InvariantMonitor(
            "ftq.pointers", self.checker.check_pointers)
        self.last_redirect_topdown: Topdown | None = None
        self._consumers = Consumers()
        self._started = False

    async def start(self) -> "FtqAgent":
        if self._started:
            raise RuntimeError("FTQ agent already started")
        for monitor in (self.training_monitor, self.commit_monitor,
                        self.redirect_monitor, self.prefetch_monitor,
                        self.fetch_monitor, self.flush_monitor,
                        self.topdown_monitor, self.private_monitor,
                        self.pointer_monitor):
            self.dut.add_monitor(monitor)
        self._started = True
        return self

    async def aclose(self) -> None:
        for monitor in (self.training_monitor, self.commit_monitor,
                        self.redirect_monitor, self.prefetch_monitor,
                        self.fetch_monitor, self.flush_monitor,
                        self.topdown_monitor, self.private_monitor):
            monitor.clear()
        self.ahead_driver.close()
        self.consumer_driver.close()
        self.commit_driver.close()
        self.callret_driver.close()
        self.resolve_driver.close()
        self.ifu_redirect_driver.close()
        self.backend_redirect_driver.close()
        self.meta_driver.close()
        self.prediction_driver.close()
        self.reset_driver.pins.set(reset=0)
        self._started = False

    async def reset(self) -> None:
        self._consumers = Consumers()
        await self.consumer_driver.set(_consumer_values(self._consumers))
        await self.reset_driver.send()
        for monitor in (self.training_monitor, self.commit_monitor,
                        self.redirect_monitor, self.prefetch_monitor,
                        self.fetch_monitor, self.flush_monitor,
                        self.topdown_monitor, self.private_monitor):
            monitor.clear()
        self.checker = FtqChecker()
        self.commit_checker = CommitChecker()

    async def step(self, cycles: int = 1) -> None:
        await self.dut.edge(cycles)

    async def consumers(self, **values: int) -> None:
        """Update the readiness levels, keeping channels that are not named."""

        spec = dataclasses.replace(self._consumers, **values)
        self._consumers = spec
        await self.consumer_driver.set(_consumer_values(spec))

    # ------------------------------------------------------------------ producer

    async def offer(self, prediction: Prediction) -> PredictionOffer:
        """Drive a prediction without taking an edge; call complete_offer()."""

        self.prediction_driver.pins.set(**encode_prediction(prediction))
        # The s3 write pointer is shared by the meta channel and an s3
        # override; the meta driver owns both uses so they cannot double-drive.
        self.meta_driver.pins.set(
            s3_flag=prediction.s3_flag,
            s3_value=(prediction.s3_ptr or 0) if prediction.s3_override else 0)
        self.dut.refresh()
        value = decode.prediction_offer(self.dut, self.ports)
        return PredictionOffer(ready=value.ready, wen=value.wen,
                               index=value.index, start_pc=value.start_pc)

    async def complete_offer(self) -> None:
        """Deassert the whole prediction request, not just ``valid``.

        The generated RTL updates bpuPtr from the s2/s3 override bits without
        re-checking prediction.valid, so a stale override bit is a producer
        protocol violation rather than a legal idle value.
        """

        self.prediction_driver.pins.set(**{
            logical: 0 for logical in self.ports.prediction.names})
        self.dut.refresh()

    async def predict(self, prediction: Prediction) -> PredictionOffer:
        """Offer one prediction as the BPU producer; requires ready."""

        offer = await self.offer(prediction)
        if not offer.ready:
            raise AssertionError(f"prediction offered while not ready: {offer}")
        await self.step(1)
        await self.complete_offer()
        await self.step(1)
        return offer

    async def override(self, prediction: Prediction) -> PredictionOffer:
        """Offer an s2/s3 override; override requests ignore prediction.ready."""

        if not (prediction.s2_override or prediction.s3_override):
            raise ValueError("override() needs s2_override or s3_override")
        offer = await self.offer(prediction)
        await self.step(1)
        await self.complete_offer()
        await self.step(1)
        return offer

    async def write_meta(self, meta: Meta) -> None:
        values = encode_meta(meta)
        values["s3_flag"] = meta.flag
        values["s3_value"] = meta.index
        await self.meta_driver.send(values)

    def meta_payload(self, value: int) -> dict[str, int]:
        """All-ones or all-zeros for every stored metadata payload bit.

        The payload spans fields whose widths are defined by the generated
        binding, so the bundle exposes the widths instead of each test pin.
        """

        fields = {}
        for logical, physical in self.ports.meta.names.items():
            if logical in ("valid", "s3_flag", "s3_value"):
                continue
            width = max(1, int(self.dut.input(physical).W()))
            fields[logical] = (1 << width) - 1 if value else 0
        return fields

    async def drive_backend_redirect(self, event: BackendRedirect) -> tuple[RedirectEvent | None, FlushEvent]:
        """Present the redirect without taking an edge."""

        self.backend_redirect_driver.pins.set(**encode_backend_redirect(event))
        self.dut.refresh()
        return (decode.redirect_event(self.dut, self.ports),
                decode.flush(self.dut, self.ports))

    async def release_backend_redirect(self) -> None:
        """Release the redirect pins without advancing the clock."""

        self.backend_redirect_driver.pins.set(**{
            logical: 0 for logical in self.ports.backend_redirect.names})
        self.dut.refresh()

    async def finish_backend_redirect(self) -> None:
        # Keep the request asserted for the accepting edge, then release it.
        await self.step(1)
        await self.release_backend_redirect()
        await self.step(1)

    async def backend_redirect(self, event: BackendRedirect) -> tuple[RedirectEvent | None, FlushEvent]:
        self.backend_redirect_driver.pins.set(**encode_backend_redirect(event))
        self.dut.refresh()
        await self.step(1)
        redirect = decode.redirect_event(self.dut, self.ports)
        flush = decode.flush(self.dut, self.ports)
        self.last_redirect_topdown = decode.topdown(self.dut, self.ports)
        self.backend_redirect_driver.pins.set(valid=0)
        self.dut.refresh()
        await self.step(1)
        return redirect, flush

    async def drive_ifu_redirect(self, event: IfuRedirect) -> None:
        """Present the IFU redirect without taking an edge."""

        self.ifu_redirect_driver.pins.set(**encode_ifu_redirect(event))
        self.dut.refresh()

    async def release_ifu_redirect(self) -> None:
        """Release the IFU redirect pins without advancing the clock."""

        self.ifu_redirect_driver.pins.set(**{
            logical: 0 for logical in self.ports.ifu_redirect.names})
        self.dut.refresh()

    async def finish_ifu_redirect(self) -> None:
        await self.release_ifu_redirect()
        await self.step(1)

    async def ifu_redirect(self, event: IfuRedirect) -> tuple[RedirectEvent | None, FlushEvent]:
        self.ifu_redirect_driver.pins.set(**encode_ifu_redirect(event))
        self.dut.refresh()
        await self.step(1)
        redirect = decode.redirect_event(self.dut, self.ports)
        flush = decode.flush(self.dut, self.ports)
        self.last_redirect_topdown = decode.topdown(self.dut, self.ports)
        self.ifu_redirect_driver.pins.set(valid=0)
        self.dut.refresh()
        await self.step(1)
        return redirect, flush

    async def resolve_hold(self, reports: Iterable[ResolveReport]) -> None:
        """Present resolve lanes without taking an edge (handshake tests)."""

        reports = tuple(reports)
        if len(reports) > 3:
            raise ValueError("backend accepts at most three lane reports")
        values = {f"{lane}.valid": 0 for lane in range(3)}
        for lane, report in enumerate(reports):
            values.update({f"{lane}.{logical}": value
                           for logical, value in encode_resolve(report).items()})
        self.resolve_driver.pins.set(**values)
        self.dut.refresh()

    async def resolve_stream(self, groups: Sequence[Sequence[ResolveReport]]) -> None:
        """Drive adjacent resolve groups without an idle gap between them."""

        for group in groups:
            if len(group) > 3:
                raise ValueError("backend accepts at most three lane reports")
            values = {f"{lane}.valid": 0 for lane in range(3)}
            for lane, report in enumerate(group):
                values.update({f"{lane}.{logical}": value
                               for logical, value in encode_resolve(report).items()})
            self.resolve_driver.pins.set(**values)
            self.dut.refresh()
            await self.step(1)
        await self.resolve_release()
        await self.step(1)

    async def resolve_release(self) -> None:
        self.resolve_driver.pins.set(**{f"{lane}.valid": 0 for lane in range(3)})
        self.dut.refresh()

    async def resolve(self, reports: Iterable[ResolveReport], *,
                      source: str = "backend") -> None:
        reports = tuple(reports)
        if not reports:
            raise ValueError("resolve() needs at least one report")
        if source != "backend":
            raise ValueError("FTQ accepts only the three backend resolve lanes")
        if len(reports) > 3:
            raise ValueError("backend accepts at most three lane reports")
        values = {}
        for lane, report in enumerate(reports):
            for logical, value in encode_resolve(report).items():
                values[f"{lane}.{logical}"] = value
        await self.resolve_driver.send(values)

    def set_resolve_lanes(self, lanes: Sequence[ResolveReport | None]) -> None:
        """Set lane pins without advancing the clock."""

        if len(lanes) != 3:
            raise ValueError("backend lane vector has exactly three entries")
        values: dict[str, int] = {f"{lane}.valid": 0 for lane in range(3)}
        for lane, report in enumerate(lanes):
            if report is None:
                continue
            values.update({f"{lane}.{logical}": value
                           for logical, value in encode_resolve(report).items()})
        self.resolve_driver.pins.set(**values)
        self.dut.refresh()

    async def resolve_cycle(self, lanes: Sequence[ResolveReport | None]) -> None:
        """Present lanes for exactly one edge, without a release edge."""

        if len(lanes) != 3:
            raise ValueError("backend lane vector has exactly three entries")
        values: dict[str, int] = {f"{lane}.valid": 0 for lane in range(3)}
        for lane, report in enumerate(lanes):
            if report is None:
                continue
            values.update({f"{lane}.{logical}": value
                           for logical, value in encode_resolve(report).items()})
        self.resolve_driver.pins.set(**values)
        self.dut.refresh()
        await self.step(1)

    async def resolve_lanes(self, lanes: Sequence[ResolveReport | None]) -> None:
        if len(lanes) != 3:
            raise ValueError("backend lane vector has exactly three entries")
        values: dict[str, int] = {f"{lane}.valid": 0 for lane in range(3)}
        for lane, report in enumerate(lanes):
            if report is None:
                continue
            values.update({f"{lane}.{logical}": value
                           for logical, value in encode_resolve(report).items()})
        await self.resolve_driver.send(values)

    async def callret_rows(self, rows: Sequence[CallRet | None]) -> None:
        if len(rows) != len(self.ports.callret):
            raise ValueError(f"expected {len(self.ports.callret)} call-return lanes")
        values: dict[str, int] = {}
        for lane, row in enumerate(rows):
            values[f"{lane}.valid"] = int(row is not None)
            values[f"{lane}.ras"] = 0 if row is None else row.ras
            values[f"{lane}.ptr"] = 0 if row is None else row.ptr
        self.callret_driver.pins.set(**values)
        self.dut.refresh()
        await self.step(1)
        await self.release_callret()

    async def callret(self, lane: int, row: CallRet) -> None:
        if not 0 <= lane < len(self.ports.callret):
            raise ValueError(f"call-return lane {lane} outside 0..7")
        values = {f"{index}.valid": 0 for index in range(len(self.ports.callret))}
        values.update({f"{lane}.{logical}": value
                       for logical, value in encode_callret(row).items()})
        self.callret_driver.pins.set(**values)
        self.dut.refresh()
        await self.step(1)
        await self.release_callret()

    async def release_callret(self) -> None:
        self.callret_driver.pins.set(**{
            f"{index}.valid": 0 for index in range(len(self.ports.callret))
        })
        self.dut.refresh()

    async def commit(self, index: int, flag: int = 0) -> None:
        await self.commit_driver.send({"valid": 1, "flag": flag, "ptr": index})

    async def ahead_set(self, index: int, flag: int = 0) -> None:
        self.ahead_driver.pins.set(valid=1, flag=flag, value=index)
        self.dut.refresh()
        await self.step(1)

    async def ahead_clear(self) -> None:
        self.ahead_driver.pins.set(valid=0)
        self.dut.refresh()

    # ------------------------------------------------------------------ producer helper

    async def allocate(self, specs: Sequence[PredictionSpec], *,
                       consume: bool = False, with_meta: bool = True,
                       meta_limit: int | None = None,
                       start_index: int = 0,
                       start_flag: int = 0) -> list[int]:
        """Admit predictions with the same timing the BPU producer uses."""

        if consume:
            await self.consumers(prefetch=1, mainpipe=1)
        pcs = []
        for index, spec in enumerate(specs):
            prediction = Prediction(start_pc=spec.start_pc, taken=spec.taken,
                                    end_position=spec.end_position)
            offer = await self.offer(prediction)
            if not offer.ready:
                raise AssertionError(f"prediction {index} offered without room")
            pcs.append(spec.start_pc)
            await self.step(1)
            await self.complete_offer()
            await self.step(1)
            if with_meta and (meta_limit is None or index < meta_limit):
                absolute = start_index + index
                await self.write_meta(Meta(
                    absolute % 64, flag=(start_flag + absolute // 64) & 1,
                    fields=spec.meta))
        return pcs

    # ------------------------------------------------------------------ observation

    def prediction_ready(self) -> bool:
        return self.ports.prediction_ready.b("ready")

    def prefetch(self) -> PrefetchRequest:
        return self.prefetch_monitor.sample(self.dut)

    def fetch(self) -> FetchRequest:
        return self.fetch_monitor.sample(self.dut)

    def training(self) -> TrainingEntry | None:
        return self.training_monitor.sample(self.dut)

    def commit_event(self) -> CommitEvent | None:
        return self.commit_monitor.sample(self.dut)

    def redirect_event(self) -> RedirectEvent | None:
        return self.redirect_monitor.sample(self.dut)

    def flush(self) -> FlushEvent:
        return self.flush_monitor.sample(self.dut)

    def topdown(self) -> Topdown:
        return self.topdown_monitor.sample(self.dut)

    def redirect_topdown(self) -> Topdown:
        if self.last_redirect_topdown is None:
            raise AssertionError("no redirect topdown snapshot was captured")
        return self.last_redirect_topdown

    def backend_write(self) -> BackendWrite:
        return self.private_monitor.sample(self.dut)

    def pointers(self) -> Pointers:
        return decode.pointers(self.dut)

    def entry(self, index: int) -> Entry:
        return decode.entry(self.dut, index)

    def meta_redirect(self, index: int, field: str) -> int:
        return self.dut.internal(f"FtqDut_top.Ftq.metaQueueRedirect_{index}_{field}")

    def meta_resolve(self, index: int, field: str) -> int:
        return self.dut.internal(f"FtqDut_top.Ftq.metaQueueResolve_{index}_{field}")

    def meta_commit(self, index: int, field: str) -> int:
        return self.dut.internal(f"FtqDut_top.Ftq.metaQueueCommit_{index}_{field}")

    def assert_training_mask(self) -> None:
        training = self.training()
        if training is not None and not self.checker.training_mask_ok(training):
            raise AssertionError("training contains a branch after the first mispredict")


def _consumer_values(spec: Consumers) -> dict[str, int]:
    return {
        "prefetch": spec.prefetch,
        "mainpipe": spec.mainpipe,
        "train": spec.train,
        "real_two_fetch": spec.real_two_fetch,
    }
