"""Agent for ICachePrefetchPipe plus its external peers.

The DUT expects the ITLB, the metadata array, the miss unit and the way-lookup
queue. Each is modelled from its published contract:

* the ITLB answer is a level (``miss`` plus the translation payload) that the
  prefetch pipe samples one cycle after accepting a request,
* the metadata array returns four ways for each read port; the tag comparison
  that decides a hit happens inside the DUT,
* the miss unit accepts requests and (for this pipe) does not need to return
  data for the request to complete,
* the way-lookup queue always accepts.

The agent presents an FTQ request for one sampling edge and then waits for the
DUT's observable events (way-lookup write, miss request) instead of encoding a
fixed latency.
"""

from __future__ import annotations

from typing import Any

from toffee import ClockCycles
from toffee import Execution
from toffee.signals import sample_signal

from icacheverify.common.driver.level import LevelDriver
from icacheverify.prefetchpipe.bundle.ports import PrefetchPipePorts
from icacheverify.prefetchpipe.model import prefetchpipe as model
from icacheverify.prefetchpipe.model.prefetchpipe import ItlbResponse
from icacheverify.prefetchpipe.model.prefetchpipe import MetaEntry
from icacheverify.prefetchpipe.model.prefetchpipe import Outcome
from icacheverify.prefetchpipe.model.prefetchpipe import PrefetchRequest
from icacheverify.prefetchpipe.model.prefetchpipe import WayWrite


SETTLE_CYCLES = 28


class PrefetchPipeAgent:
    def __init__(self, dut: Any) -> None:
        self.dut = dut
        self.ports = PrefetchPipePorts.bind(dut)
        self.ftq_driver = LevelDriver(self.ports.ftq)
        self.itlb_driver = LevelDriver(self.ports.itlb_resp)
        self.meta_driver = LevelDriver(self.ports.meta_resp)
        self.miss_driver = LevelDriver(self.ports.miss_resp)
        self.pmp_driver = LevelDriver(self.ports.pmp_resp)
        self.csr_driver = LevelDriver(self.ports.csr_pf)
        self.flush_driver = LevelDriver(self.ports.flush)
        self.bpu_driver = LevelDriver(self.ports.bpu_flush)
        self.meta_ready_driver = LevelDriver(self.ports.meta_ready)
        self.miss_ready_driver = LevelDriver(self.ports.miss_ready)
        self.way_ready_drivers = tuple(
            LevelDriver(binding) for binding in self.ports.way_ready)
        self._execution: Execution | None = None
        self.last_outcome: Outcome | None = None
        self.last_meta_sets: tuple[int, int] = (0, 0)
        self.last_meta_double = 0
        self.last_itlb_vaddr = 0
        self.pf_enable = 1

    # -- lifecycle ----------------------------------------------------------
    async def start(self, execution: Execution) -> "PrefetchPipeAgent":
        self._execution = execution
        self.idle_inputs()
        await self.reset()
        return self

    async def aclose(self) -> None:
        for driver in (self.ftq_driver, self.itlb_driver, self.meta_driver,
                       self.miss_driver, self.pmp_driver, self.csr_driver,
                       self.flush_driver, self.bpu_driver,
                       self.meta_ready_driver, self.miss_ready_driver,
                       *self.way_ready_drivers):
            driver.close()
        self._execution = None

    def idle_inputs(self) -> None:
        self.ftq_driver.set({key: 0 for key in self.ports.ftq.bits.fields})
        self.itlb_driver.set({"miss": 0, "paddr": 0, "pbmt": 0, "gpaddr": 0,
                              "pf": 0, "af": 0, "gpf": 0, "vsNonLeaf": 0})
        self.meta_driver.set({key: 0 for key in self.ports.meta_resp.bits.fields})
        self.miss_driver.set({"valid": 0, "blkPAddr": 0, "vSetIdx": 0,
                              "waymask": 0, "maybeRvcMap": 0, "corrupt": 0})
        self.pmp_driver.set({"instr": 0, "mmio": 0})
        self.csr_driver.set({"enable": 1})
        self.flush_driver.set({"flush": 0})
        self.bpu_driver.set(self._bpu_idle())
        self.meta_ready_driver.set({"ready": 1})
        self.miss_ready_driver.set({"ready": 1})
        for driver in self.way_ready_drivers:
            driver.set({"ready": 1})

    @staticmethod
    def _bpu_idle() -> dict[str, int]:
        return {"s2_valid": 0, "s2_flag": 0, "s2_value": 0,
                "s3_valid": 0, "s3_flag": 0, "s3_value": 0}

    @classmethod
    def _bpu_payload(cls, s2: tuple[int, int] | None,
                     s3: tuple[int, int] | None) -> dict[str, int]:
        payload = cls._bpu_idle()
        if s2 is not None:
            payload.update(s2_valid=1, s2_flag=s2[0] & 1, s2_value=s2[1] & 0x3F)
        if s3 is not None:
            payload.update(s3_valid=1, s3_flag=s3[0] & 1, s3_value=s3[1] & 0x3F)
        return payload

    @staticmethod
    def _not_after(ptr: tuple[int, int], ftq_idx: int) -> bool:
        flag, value = ptr[0] & 1, ptr[1] & 0x3F
        req_flag, req_value = (ftq_idx >> 6) & 1, ftq_idx & 0x3F
        is_after = (flag ^ req_flag) ^ int(value > req_value)
        return not is_after

    async def _edge(self) -> None:
        await ClockCycles(self.dut.clock, 1)

    async def reset(self, cycles: int = 4) -> None:
        self.idle_inputs()
        self.dut.reset.Set(1)
        for _ in range(cycles):
            await self._edge()
        self.dut.reset.Set(0)
        await self._edge()
        await self._edge()

    # -- observation --------------------------------------------------------
    @staticmethod
    def _bit(signal: Any) -> int:
        return int(sample_signal(signal).as_int()) & 1

    def _value(self, binding, field: str) -> int:
        return int(sample_signal(binding.bits[field]).as_int())

    def ftq_ready(self) -> int:
        return self._bit(self.ports.ftq_ready)

    def way_valid(self, port: int = 0) -> int:
        return self._bit(self.ports.way[port].bits["valid"])

    def ftq_ready(self) -> int:
        from toffee.signals import sample_signal
        return int(sample_signal(self.ports.ftq_ready).as_int()) & 1

    def miss_valid(self) -> int:
        return self._bit(self.ports.miss_req.bits["valid"])

    def meta_req_valid(self) -> int:
        return self._bit(self.ports.meta_req.bits["valid"])

    def itlb_req_valid(self) -> int:
        return self._bit(self.ports.itlb_req.bits["valid"])

    def pending_itlb_miss(self) -> int:
        return self._bit(self.ports.pending_itlb_miss)

    def itlb_flush_pipe(self) -> int:
        return self._bit(self.ports.itlb_flush_pipe)

    # -- drives -------------------------------------------------------------
    def drive_itlb(self, response: ItlbResponse) -> None:
        self.itlb_driver.set({
            "miss": response.miss,
            "paddr": response.paddr,
            "pbmt": response.pbmt,
            "gpaddr": response.gpaddr,
            "pf": response.pf,
            "af": response.af,
            "gpf": response.gpf,
            "vsNonLeaf": response.vs_non_leaf,
        })

    def drive_meta(self, meta: tuple[tuple[MetaEntry, ...], tuple[MetaEntry, ...]]) -> None:
        payload = {key: 0 for key in self.ports.meta_resp.bits.fields}
        for port in range(model.PORTS):
            entries = meta[port]
            for way in range(model.WAYS):
                if way < len(entries) and entries[way].valid:
                    entry = entries[way]
                    payload[f"p{port}_w{way}_valid"] = 1
                    payload[f"p{port}_w{way}_tag"] = entry.ptag
                    payload[f"p{port}_w{way}_rvc"] = entry.rvc
                    payload[f"p{port}_w{way}_code"] = entry.code
        self.meta_driver.set(payload)

    def _ftq_payload(self, req0: PrefetchRequest,
                     req1: PrefetchRequest, case: int) -> dict[str, int]:
        payload = {key: 0 for key in self.ports.ftq.bits.fields}
        payload["valid"] = 1
        payload["twoPrefetchCase"] = case
        for index, req in enumerate((req0, req1)):
            prefix = f"r{index}_"
            values = {
                "startVAddr": req.vaddr >> 1,
                "nextLineVAddr": req.next_vaddr >> 1,
                "isCrossLine": req.is_cross_line,
                "vSetIdx_0": req.vset[0],
                "vSetIdx_1": req.vset[1],
                "ftqIdx_flag": 0,
                "ftqIdx_value": req.ftq_idx & 0x3F,
            }
            for name, value in values.items():
                key = prefix + name
                if key in payload:
                    payload[key] = value
        payload["r0_isSoftPrefetch"] = req0.is_soft_prefetch
        payload["r0_backendException"] = req0.backend_exception
        return payload

    async def pulse_request(self, req0: PrefetchRequest, req1: PrefetchRequest,
                            case: int) -> None:
        """Present the FTQ request for one sampling edge."""
        self.ftq_driver.set(self._ftq_payload(req0, req1, case))
        await self._edge()
        # Capture the stage-0 read requests while the FTQ request is visible:
        # they disappear as soon as stage 1 takes over.
        if self.meta_req_valid():
            self.last_meta_sets = (self._value(self.ports.meta_req, "vSetIdx_0"),
                                   self._value(self.ports.meta_req, "vSetIdx_1"))
            self.last_meta_double = self._bit(self.ports.meta_req.bits["isDoubleLine"])
        if self.itlb_req_valid():
            self.last_itlb_vaddr = self._value(self.ports.itlb_req, "vaddr")
        self.ftq_driver.set({key: 0 for key in self.ports.ftq.bits.fields})
        await self._edge()

    # -- operations ---------------------------------------------------------
    async def send(
        self,
        req0: PrefetchRequest,
        req1: PrefetchRequest | None = None,
        *,
        case: int = model.CASE_CONFLICT,
        itlb: ItlbResponse | None = None,
        meta: tuple[tuple[MetaEntry, ...], tuple[MetaEntry, ...]] | None = None,
        pmp_instr: int = 0,
        pmp_mmio: int = 0,
        check: bool = True,
        bpu_s2: tuple[int, int] | None = None,
        bpu_s3: tuple[int, int] | None = None,
        distinct_misses: bool = False,
    ) -> Outcome | None:
        req1 = req1 or PrefetchRequest(0, 0, 0, 0)
        itlb = itlb or ItlbResponse()
        meta = meta or ((), ())
        self.drive_itlb(itlb)
        self.drive_meta(meta)
        self.pmp_driver.set({"instr": pmp_instr, "mmio": pmp_mmio})
        self.bpu_driver.set(self._bpu_payload(bpu_s2, bpu_s3))
        blocked = bool(
            not req0.is_soft_prefetch
            and ((bpu_s2 is not None and self._not_after(bpu_s2, req0.ftq_idx))
                 or (bpu_s3 is not None
                     and self._not_after(bpu_s3, req0.ftq_idx))))
        await self._edge()

        expected = model.predict(req0, req1, case=case, itlb=itlb, meta=meta,
                                 pmp_instr=pmp_instr, pmp_mmio=pmp_mmio,
                                 pf_enable=self.pf_enable)
        self.last_outcome = expected
        if blocked:
            # A redirect at or before the request's FTQ index kills it in
            # stage 0 (hardware prefetch only; a retired prefetch.i is not on
            # the fetched path and is exempt).
            await self.pulse_request(req0, req1, case)
            for _ in range(SETTLE_CYCLES):
                if self.way_valid(0):
                    raise AssertionError(
                        "a BPU-flushed prefetch still wrote the way lookup")
                if self.miss_valid():
                    raise AssertionError(
                        "a BPU-flushed prefetch still requested a miss")
                await self._edge()
            self.bpu_driver.set(self._bpu_idle())
            return None
        await self.pulse_request(req0, req1, case)
        observed = await self.wait_result(
            expected, check=check,
            distinct_misses=distinct_misses)
        self.bpu_driver.set(self._bpu_idle())
        return observed

    async def wait_result(self, expected: Outcome, *, check: bool = True,
                          writes: tuple[WayWrite, WayWrite] | None = None,
                          distinct_misses: bool = False) -> Outcome:
        misses: list[tuple[int, int]] = []
        meta_sets = getattr(self, "last_meta_sets", (0, 0))
        meta_double = getattr(self, "last_meta_double", 0)
        itlb_vaddr = getattr(self, "last_itlb_vaddr", 0)
        for _ in range(SETTLE_CYCLES):
            if self.meta_req_valid():
                meta_sets = (self._value(self.ports.meta_req, "vSetIdx_0"),
                             self._value(self.ports.meta_req, "vSetIdx_1"))
                meta_double = self._bit(self.ports.meta_req.bits["isDoubleLine"])
            if self.itlb_req_valid():
                itlb_vaddr = self._value(self.ports.itlb_req, "vaddr")
            if writes is None and self.way_valid(0):
                writes = (self.sample_write(0), self.sample_write(1))
            if self.miss_valid():
                miss = (self._value(self.ports.miss_req, "blkPAddr"),
                        self._value(self.ports.miss_req, "vSetIdx"))
                if distinct_misses:
                    # The arbiter may present the same request for more than
                    # one cycle; only a *new* payload proves the next request
                    # reached the port.
                    if miss not in misses:
                        misses.append(miss)
                else:
                    misses.append(miss)
            if (writes is not None and len(misses) >= len(expected.misses)):
                break
            await self._edge()
        if writes is None:
            if not expected.writes[0].valid and not expected.writes[1].valid:
                # A soft prefetch produces no write at all; give the pipe time
                # to run its course and report the empty result.
                for _ in range(SETTLE_CYCLES):
                    if self.miss_valid():
                        misses.append((self._value(self.ports.miss_req, "blkPAddr"),
                                       self._value(self.ports.miss_req, "vSetIdx")))
                    await self._edge()
                writes = (self.sample_write(0), self.sample_write(1))
            else:
                raise TimeoutError("the prefetch pipe never wrote the way lookup")
        observed = Outcome(
            writes=writes,
            misses=tuple(misses[:len(expected.misses)]),
            meta_sets=meta_sets,
            meta_double=meta_double,
            itlb_vaddr=itlb_vaddr,
            pending_itlb_miss=self.pending_itlb_miss(),
        )
        if check:
            compare_outcomes(observed, expected)
        return observed

    def sample_write(self, port: int) -> WayWrite:
        binding = self.ports.way[port]
        fields = binding.bits.fields

        def read(name: str, default: int = 0) -> int:
            return (self._value(binding, name) if name in fields else default)

        return WayWrite(
            valid=read("valid"),
            ftq_idx=(read("ftqIdx_flag") << 6) | read("ftqIdx_value"),
            vset=(read("vSetIdx_0"), read("vSetIdx_1")),
            waymask=(read("waymask_0"), read("waymask_1")),
            ptag=read("pTag"),
            rvc=(read("rvc_0"), read("rvc_1")),
            code=(read("code_0"), read("code_1")),
            is_mmio=read("isMmio"),
            itlb_pbmt=read("itlbPbmt"),
            exception=read("exception"),
            gpaddr=read("gpAddr") << 1,
            vs_non_leaf=read("vsNonLeaf"),
        )

    async def flush(self, cycles: int = 2) -> None:
        self.flush_driver.set({"flush": 1})
        for _ in range(cycles):
            await self._edge()
        self.flush_driver.set({"flush": 0})
        await self._edge()
        await self._edge()


def compare_outcomes(observed: Outcome, expected: Outcome) -> None:
    problems: list[str] = []
    for port in (0, 1):
        got, want = observed.writes[port], expected.writes[port]
        if got.valid != want.valid:
            problems.append(f"way{port}.valid {got.valid} != {want.valid}")
            continue
        if not want.valid:
            continue
        for name in want.__dataclass_fields__:
            if name == "valid":
                continue
            if port == 1 and name in ("exception", "gpaddr", "vs_non_leaf"):
                # The flattened DUT publishes the exception entry once, on port 0.
                continue
            if name in ("waymask", "rvc", "code") and not expected.line1_valid[port]:
                # The second line is only read for a cross-line fetch.  For a
                # non-cross fetch the pipe may keep stale second-line metadata,
                # which the main pipe never consumes; only line 0 is defined.
                continue
            if getattr(got, name) != getattr(want, name):
                problems.append(f"way{port}.{name} {getattr(got, name)} != "
                                f"{getattr(want, name)}")
    if observed.misses != expected.misses:
        problems.append(f"misses {observed.misses} != {expected.misses}")
    for name in ("meta_sets", "meta_double", "itlb_vaddr"):
        if getattr(observed, name) != getattr(expected, name):
            problems.append(f"{name} {getattr(observed, name)} != {getattr(expected, name)}")
    if problems:
        raise AssertionError("prefetch pipe response mismatch:\n  " + "\n  ".join(problems))
