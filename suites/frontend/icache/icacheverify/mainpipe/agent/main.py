"""Agent for ICacheMainPipe plus its external peers.

The DUT has no companions in a module test, so the agent plays them:

* the **FTQ** and the **way-lookup queue** present a fetch request,
* the **data array** answers the read request with a deterministic per-bank
  image (``line_image``),
* the **miss unit** accepts ``missReq`` and returns a refill,
* the **PMP** supplies the access-fault / MMIO answer,
* the **IFU** always accepts the response.

Only the DUT's published ports are observed. Timing is event driven: a request
is presented for exactly one sampling edge and the agent then waits for the
DUT's observable response (``toIfu.req.valid`` or ``missReq.valid``) instead of
assuming a fixed pipeline latency.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from toffee import ClockCycles
from toffee import Execution
from toffee.signals import sample_signal

from icacheverify.common.driver.level import LevelDriver
from icacheverify.mainpipe.bundle.ports import MainPipePorts
from icacheverify.mainpipe.model import mainpipe as model
from icacheverify.mainpipe.model.mainpipe import FetchRequest
from icacheverify.mainpipe.model.mainpipe import MissResponse
from icacheverify.mainpipe.model.mainpipe import Outcome
from icacheverify.mainpipe.model.mainpipe import WayEntry
from icacheverify.mainpipe.model.mainpipe import line_image


SETTLE_CYCLES = 24


class MainPipeAgent:
    def __init__(self, dut: Any) -> None:
        self.dut = dut
        self.ports = MainPipePorts.bind(dut)
        self.ftq_driver = LevelDriver(self.ports.ftq)
        self.way_driver = LevelDriver(self.ports.waylookup)
        self.data_ready_driver = LevelDriver(self.ports.data_ready)
        self.data_resp_driver = LevelDriver(self.ports.data_resp)
        self.miss_driver = LevelDriver(self.ports.miss_resp)
        self.miss_ready_driver = LevelDriver(self.ports.miss_ready)
        self.pmp_driver = LevelDriver(self.ports.pmp_resp)
        self.flush_driver = LevelDriver(self.ports.flush)
        self.bpu_driver = LevelDriver(self.ports.bpu_flush)
        self.ecc_driver = LevelDriver(self.ports.ecc_enable)
        self.ifu_ready_driver = LevelDriver(self.ports.ifu_ready)
        self._execution: Execution | None = None
        self.last_outcome: Outcome | None = None
        self.last_touches: tuple[model.Touch, ...] = ()
        self.last_two_fetch = 0
        self.last_corrupt: tuple[int, int, int, int] = (0, 0, 0, 0)
        self.last_error_valid = 0

    # -- lifecycle ----------------------------------------------------------
    async def start(self, execution: Execution) -> "MainPipeAgent":
        self._execution = execution
        self.idle_inputs()
        await self.reset()
        return self

    async def aclose(self) -> None:
        for driver in (self.ftq_driver, self.way_driver, self.data_ready_driver,
                       self.data_resp_driver, self.miss_driver,
                       self.miss_ready_driver, self.pmp_driver,
                       self.flush_driver, self.bpu_driver,
                       self.ecc_driver, self.ifu_ready_driver):
            driver.close()
        self._execution = None

    def idle_inputs(self) -> None:
        self.ftq_driver.set({key: 0 for key in self.ports.ftq.bits.fields})
        self.way_driver.set({key: 0 for key in self.ports.waylookup.bits.fields})
        self.data_ready_driver.set({"ready": 1})
        self.data_resp_driver.set({key: 0 for key in self.ports.data_resp.bits.fields})
        self.miss_driver.set({"valid": 0, "blkPAddr": 0, "vSetIdx": 0, "data": 0,
                              "maybeRvcMap": 0, "corrupt": 0, "denied": 0})
        self.miss_ready_driver.set({"ready": 1})
        self.pmp_driver.set({"instr": 0, "mmio": 0})
        self.flush_driver.set({"flush": 0})
        self.bpu_driver.set(self._bpu_idle())
        self.ecc_driver.set({"ecc": 0})
        self.ifu_ready_driver.set({"ready": 1})

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
        """BPU redirect rule: the request is flushed when the redirect target
        is not after it (``!isAfter(redirect, request)``), i.e. the request is
        at or younger than the redirect.
        """
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

    def ifu_valid(self) -> int:
        return self._bit(self.ports.to_ifu.bits["valid"])

    def miss_valid(self) -> int:
        return self._bit(self.ports.miss_req.bits["valid"])

    def data_req_valid(self) -> int:
        return self._bit(self.ports.data_req.bits["valid"])

    # -- drives -------------------------------------------------------------
    def _data_payload(self, req0: FetchRequest, req1: FetchRequest,
                      way0: WayEntry, way1: WayEntry) -> dict[str, int]:
        payload = {key: 0 for key in self.ports.data_resp.bits.fields}
        for port, (req, way) in enumerate(((req0, way0), (req1, way1))):
            if not req.valid or (port == 1 and not req1.valid):
                continue
            cross = model.is_cross_line(req.vaddr, req.end_position)
            # The bank belongs to line 0 when it is at or above the fetch's
            # starting bank, and to the cross-line tail otherwise.
            low = (req.vaddr >> 3) & (model.DATA_BANKS - 1)
            for bank in range(model.DATA_BANKS):
                line = 1 if bank < low else 0
                if line == 1 and not cross:
                    continue
                if way.waymask[line]:
                    words = (way.words if way.words is not None
                             else line_image(way.vset[line],
                                             model._hit_way(way.waymask[line])))
                    word = words[bank]
                    payload[f"d{port}_{bank}"] = word
                    payload[f"c{port}_{bank}"] = 0
        return payload

    def _ftq_payload(self, req0: FetchRequest, req1: FetchRequest) -> dict[str, int]:
        payload = {key: 0 for key in self.ports.ftq.bits.fields}
        payload["valid"] = int(bool(req0.valid or req1.valid))
        for index, req in enumerate((req0, req1)):
            prefix = f"r{index}_"
            payload.update({
                # PrunedAddr carries address[..:1]; the low bit is always zero.
                prefix + "vAddr_0_addr": req.vaddr >> 1,
                prefix + "vAddr_1_addr": req.next_vaddr >> 1,
                prefix + "endPosition": req.end_position,
                prefix + "taken": req.taken,
                prefix + "bankSel_0": req.bank_sel[0],
                prefix + "bankSel_1": req.bank_sel[1],
                prefix + "vSetIdx_0": req.vset[0],
                prefix + "vSetIdx_1": req.vset[1],
                prefix + "ftqIdx_flag": 0,
                prefix + "ftqIdx_value": req.ftq_idx & 0x3F,
            })
        payload["r0_hasBackendException"] = req0.has_backend_exception
        payload["r0_hasSatpFlush"] = req0.has_satp_flush
        payload["r1_valid"] = req1.valid
        return {key: value for key, value in payload.items()
                if key in self.ports.ftq.bits.fields}

    def _way_payload(self, way0: WayEntry, way1: WayEntry) -> dict[str, int]:
        payload = {key: 0 for key in self.ports.waylookup.bits.fields}
        for index, way in enumerate((way0, way1)):
            prefix = f"r{index}_"
            values = {
                "isMmio": way.is_mmio,
                "itlbPbmt": way.itlb_pbmt,
                "maybeRvcMap_0": way.rvc_map[0],
                "maybeRvcMap_1": way.rvc_map[1],
                "metaCodes_0": way.meta_codes[0],
                "metaCodes_1": way.meta_codes[1],
                "vSetIdx_0": way.vset[0],
                "vSetIdx_1": way.vset[1],
                "waymask_0": way.waymask[0],
                "waymask_1": way.waymask[1],
                # PrunedAddr carries guest-address[..:1]; the low bit is zero.
                "gpAddr_addr": way.gpaddr >> 1,
                "isForVSnonLeafPTE": way.vs_non_leaf,
                "itlbException_value": way.itlb_exception,
            }
            for name, value in values.items():
                key = prefix + name
                if key in payload:
                    payload[key] = value
        if "r0_pTag" in payload:
            payload["r0_pTag"] = way0.ptag
        payload["valid"] = int(bool(way0.valid))
        if "r1_valid" in payload:
            payload["r1_valid"] = int(bool(way1.valid))
        return payload

    # -- operations ---------------------------------------------------------
    async def pulse_request(self, req0: FetchRequest, req1: FetchRequest,
                            way0: WayEntry, way1: WayEntry) -> None:
        """Present a request pair for exactly one sampling edge."""
        self.ftq_driver.set(self._ftq_payload(req0, req1))
        self.way_driver.set(self._way_payload(way0, way1))
        await self._edge()
        self.last_two_fetch = self._bit(self.ports.to_ftq_two)
        self.ftq_driver.set({key: 0 for key in self.ports.ftq.bits.fields})
        self.way_driver.set({key: 0 for key in self.ports.waylookup.bits.fields})
        await self._edge()
        self.last_touches = self.touches()

    async def send(
        self,
        req0: FetchRequest,
        req1: FetchRequest | None = None,
        way0: WayEntry | None = None,
        way1: WayEntry | None = None,
        *,
        pmp_instr: int = 0,
        pmp_mmio: int = 0,
        refill: MissResponse | list[MissResponse] | None = None,
        check: bool = True,
        mask_unread_banks: bool = False,
        bpu_s2: tuple[int, int] | None = None,
        bpu_s3: tuple[int, int] | None = None,
        ifu_stall_cycles: int = 0,
        miss_stall_cycles: int = 0,
    ) -> Outcome | None:
        """Present one request pair and run it to an IFU response."""
        req1 = req1 or FetchRequest(0, 0, 0, 0, valid=0)
        way0 = way0 or WayEntry(waymask=(0, 0), vset=req0.vset, ptag=0)
        way1 = way1 or WayEntry(waymask=(0, 0), vset=req1.vset, valid=0)
        self.pmp_driver.set({"instr": pmp_instr, "mmio": pmp_mmio})
        self.bpu_driver.set(self._bpu_payload(bpu_s2, bpu_s3))
        blocked = bool(
            (bpu_s2 is not None and self._not_after(bpu_s2, req0.ftq_idx))
            or (bpu_s3 is not None and self._not_after(bpu_s3, req0.ftq_idx)))
        self.data_resp_driver.set(self._data_payload(req0, req1, way0, way1))
        if ifu_stall_cycles:
            self.ifu_ready_driver.set({"ready": 0})
        if miss_stall_cycles:
            # Backpressure must be in place before the request is offered;
            # lowering ready after the request appears would race with the
            # accepting edge.
            self.miss_ready_driver.set({"ready": 0})
        await self._edge()

        before_refill = model.predict(req0, req1, way0, way1,
                                      pmp_instr=pmp_instr, pmp_mmio=pmp_mmio,
                                      miss=None,
                                      data_array_banks=mask_unread_banks)
        refills = list(refill) if isinstance(refill, list) else (
            [refill] if refill is not None else [])
        # The model checks the final response against the refill that matters
        # for each line; for multi-line misses the caller supplies one refill per
        # line and the last one is used for the outcome prediction.
        expected = model.predict(req0, req1, way0, way1, pmp_instr=pmp_instr,
                                 pmp_mmio=pmp_mmio, miss=refills or None,
                                 data_array_banks=mask_unread_banks)
        self.last_outcome = expected
        if before_refill.missing_lines and not refills:
            raise AssertionError("the model expects a refill but none was supplied")
        if len(before_refill.missing_lines) != len(refills):
            raise AssertionError(
                f"model expects {len(before_refill.missing_lines)} refill(s), "
                f"test supplied {len(refills)}")

        if blocked:
            # A redirect at or before the request's FTQ index kills it in
            # stage 0: nothing may be accepted, requested, or returned.
            await self.pulse_request(req0, req1, way0, way1)
            for _ in range(SETTLE_CYCLES):
                if self.ifu_valid():
                    raise AssertionError(
                        "a BPU-flushed fetch still returned an IFU response")
                if self.miss_valid():
                    raise AssertionError(
                        "a BPU-flushed fetch still requested a miss")
                await self._edge()
            self.bpu_driver.set(self._bpu_idle())
            return None

        # A request is presented for exactly one sampling edge: the level is
        # committed on the first edge and withdrawn on the second, so it cannot
        # be accepted twice by the decoupled input.
        await self.pulse_request(req0, req1, way0, way1)

        sent = 0
        for _ in range(SETTLE_CYCLES):
            if self.miss_valid() and sent < len(refills):
                if miss_stall_cycles:
                    # The miss unit is busy: the request must be held, not
                    # dropped, until ``missReq.ready`` comes back.
                    held = (self._value(self.ports.miss_req, "blkPAddr"),
                            self._value(self.ports.miss_req, "vSetIdx"))
                    for _ in range(miss_stall_cycles):
                        await self._edge()
                        if not self.miss_valid():
                            raise AssertionError(
                                "the miss request dropped under backpressure")
                        if not self._bit(self.ports.perf_pending_miss):
                            raise AssertionError(
                                "perf.pendingMiss dropped while the miss request "
                                "was blocked")
                        if (self._value(self.ports.miss_req, "blkPAddr"),
                                self._value(self.ports.miss_req, "vSetIdx")) != held:
                            raise AssertionError(
                                "the miss request changed under backpressure")
                    self.miss_ready_driver.set({"ready": 1})
                    await self._edge()
                    miss_stall_cycles = 0
                expected_line = before_refill.missing_lines[sent]
                req, way = ((req0, way0) if expected_line[0] == 0 else (req1, way1))
                block, vset = model.expected_miss_request(req, way, expected_line[1])
                dut_block = self._value(self.ports.miss_req, "blkPAddr")
                dut_vset = self._value(self.ports.miss_req, "vSetIdx")
                if (dut_block, dut_vset) != (block, vset):
                    raise AssertionError(
                        f"miss request {sent} ({dut_block:#x},{dut_vset:#x}) != "
                        f"model ({block:#x},{vset:#x})")
                payload = refills[sent]
                self.miss_driver.set({
                    "valid": 1,
                    "blkPAddr": payload.block,
                    "vSetIdx": payload.vset,
                    "data": payload.data,
                    "maybeRvcMap": payload.maybe_rvc_map,
                    "corrupt": payload.corrupt,
                    "denied": payload.denied,
                })
                sent += 1
                await self._edge()
                continue
            if self.ifu_valid():
                for _ in range(ifu_stall_cycles):
                    # The response must stay valid until the IFU accepts it.
                    if not self.ifu_valid():
                        raise AssertionError(
                            "the IFU response dropped before it was accepted")
                    await self._edge()
                if ifu_stall_cycles:
                    self.ifu_ready_driver.set({"ready": 1})
                    await self._edge()
                break
            await self._edge()
        else:
            raise TimeoutError("no IFU response and no miss request from the main pipe")

        observed = self.sample_ifu()
        if mask_unread_banks:
            # A data-array read is masked by the FTQ bank select.  Banks outside
            # it are not part of the fetch; the pipe presents whatever its
            # stage-1 registers held, so those lanes are don't-care rather than
            # zero and are masked on both sides of the comparison.
            observed = replace(
                observed,
                blocks=(_mask_unread_banks(req0, observed.blocks[0]),
                        _mask_unread_banks(req1, observed.blocks[1])))
            expected = replace(
                expected,
                blocks=(_mask_unread_banks(req0, expected.blocks[0]),
                        _mask_unread_banks(req1, expected.blocks[1])))
        observed = replace(observed, touches=self.last_touches,
                           two_fetch_valid=self.last_two_fetch)
        if check:
            compare_outcomes(observed, expected)
        await self._edge()
        # The parity/ECC report is published one cycle after the IFU response.
        self.last_corrupt = self.corrupt_flags()
        self.last_error_valid = self.error_valid()
        self.miss_driver.set({"valid": 0, "blkPAddr": 0, "vSetIdx": 0, "data": 0,
                              "maybeRvcMap": 0, "corrupt": 0, "denied": 0})
        self.bpu_driver.set(self._bpu_idle())
        await self._edge()
        return observed

    def sample_ifu(self) -> Outcome:
        bits = self.ports.to_ifu.bits

        def present(field: str) -> bool:
            return field in bits.fields

        def block(index: int) -> model.IfuBlock:
            valid = 1 if index == 0 else self._value(
                self.ports.to_ifu, "info1_valid")
            def read(name: str, _index: int = index) -> int:
                field = f"info{_index}_{name}"
                return self._value(self.ports.to_ifu, field) if field in bits.fields else 0
            return model.IfuBlock(
                valid=valid,
                start_vaddr=read("startVAddr") << 1,
                ftq_idx=((read("ftqIdx_flag") << 6) | read("ftqIdx_value")),
                taken_valid=read("takenValid"),
                taken_bits=read("takenBits"),
                size=read("size"),
                data=read("data"),
                cross_line=read("crossLine") if present(f"info{index}_crossLine") else 0,
                exception=read("exception"),
                pmp_mmio=read("pmpMmio"),
                backend_exception=read("backendException")
                if present(f"info{index}_backendException") else 0,
                has_satp_flush=read("hasSatpFlush")
                if present(f"info{index}_hasSatpFlush") else 0,
                vs_non_leaf=read("vsNonLeaf"),
                itlb_pbmt=read("pbmt") if present(f"info{index}_pbmt") else 0,
                paddr=(read("paddr") << 1) if present(f"info{index}_paddr") else 0,
                gpaddr=(read("gpaddr") << 1) if present(f"info{index}_gpaddr") else 0,
            )

        return model.Outcome(
            two_fetch_valid=self._bit(self.ports.to_ftq_two),
            ifu_valid=self.ifu_valid(),
            maybe_rvc_map=self._value(self.ports.to_ifu, "maybeRvcMap"),
            first_range=self._value(self.ports.to_ifu, "firstRange"),
            total_range=self._value(self.ports.to_ifu, "totalRange"),
            blocks=(block(0), block(1)),
            pending_miss=self._bit(self.ports.perf_pending_miss),
            raw_hits=(self._bit(self.ports.perf_raw_hits[0]),
                      self._bit(self.ports.perf_raw_hits[1])),
            touches=tuple(),
        )

    # -- simple probes ------------------------------------------------------
    def touches(self) -> tuple[model.Touch, ...]:
        bits = self.ports.replacer_touch.bits
        found = []
        for req in range(2):
            for line in range(2):
                if self._value(self.ports.replacer_touch, f"valid{req}{line}"):
                    found.append(model.Touch(
                        req=req, line=line,
                        vset=self._value(self.ports.replacer_touch, f"vset{req}{line}"),
                        way=self._value(self.ports.replacer_touch, f"way{req}{line}")))
        return tuple(found)

    async def flush(self, cycles: int = 2) -> None:
        self.flush_driver.set({"flush": 1})
        for _ in range(cycles):
            await self._edge()
        self.flush_driver.set({"flush": 0})
        await self._edge()
        await self._edge()

    async def ecc_on(self) -> None:
        self.ecc_driver.set({"ecc": 1})
        await self._edge()

    async def ecc_off(self) -> None:
        self.ecc_driver.set({"ecc": 0})
        await self._edge()

    def error_valid(self) -> int:
        return self._bit(self.ports.error_valid)

    def corrupt_flags(self) -> tuple[int, int, int, int]:
        return tuple(self._value(self.ports.to_ifu, f"corrupt{i}{j}")
                     for i in range(2) for j in range(2))


_UNPUBLISHED_INFO1 = frozenset({
    "cross_line", "pmp_mmio", "backend_exception", "has_satp_flush",
    "itlb_pbmt", "paddr",
})


def _mask_unread_banks(req: model.FetchRequest, block: model.IfuBlock) -> model.IfuBlock:
    bank_low = (req.vaddr >> 3) & (model.DATA_BANKS - 1)
    cross = model.is_cross_line(req.vaddr, req.end_position)
    data = 0
    for bank in range(model.DATA_BANKS):
        line = 1 if bank < bank_low else 0
        if line == 1 and not cross:
            continue
        if not ((req.bank_sel[line] >> bank) & 1):
            continue
        data |= ((block.data >> (64 * bank)) & model.WORD_MASK) << (64 * bank)
    return replace(block, data=data)


def compare_outcomes(observed: Outcome, expected: Outcome) -> None:
    """Field-by-field comparison with a readable diff."""
    problems: list[str] = []
    if observed.ifu_valid != expected.ifu_valid:
        problems.append(f"ifu_valid {observed.ifu_valid} != {expected.ifu_valid}")
    for name in ("maybe_rvc_map", "first_range", "total_range",
                 "two_fetch_valid", "raw_hits"):
        if getattr(observed, name) != getattr(expected, name):
            problems.append(f"{name} {getattr(observed, name)} != {getattr(expected, name)}")
    if observed.touches != expected.touches:
        problems.append(f"touches {observed.touches} != {expected.touches}")
    for index in (0, 1):
        got, want = observed.blocks[index], expected.blocks[index]
        if got.valid != want.valid:
            problems.append(f"info{index}.valid {got.valid} != {want.valid}")
            continue
        if not want.valid:
            continue
        for field in want.__dataclass_fields__:
            if field == "valid":
                continue
            if field == "data" and want.exception in (
                    model.EXC_HWE, model.EXC_AF):
                # A corrupt or denied refill is not installed: the array may
                # return stale storage and the instruction bytes are not
                # architecturally consumed.  The exception is the result.
                continue
            if index == 1 and field in _UNPUBLISHED_INFO1:
                # Firtool folds these request-1 outputs away (they are constant
                # zero in the Scala module), so they are not observable.
                continue
            if getattr(got, field) != getattr(want, field):
                problems.append(
                    f"info{index}.{field} {getattr(got, field)} != {getattr(want, field)}")
    if problems:
        raise AssertionError("main pipe response mismatch:\n  " + "\n  ".join(problems))
