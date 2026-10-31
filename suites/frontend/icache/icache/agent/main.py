"""Agent for the whole ICache plus every external peer it needs.

Peers, all driven from their published contract:

* **memory** on the TileLink A/D channel: accepts acquires and returns the two
  256-bit beats of a 64-byte line whose content is a pure function of the
  physical block address,
* **FTQ**: presents the same fetch issue to the prefetch pipe and the main pipe,
* **ITLB**: a one-cycle pipelined responder (request sampled during the cycle it
  is offered, translation driven in the next cycle), with an optional multi-cycle
  ``miss`` phase,
* **PMP**: a combinational responder for the address currently under check,
* **IFU**: always ready,
* **ECC-control register slave**: the TileLink register block at
  ``0x38022080`` that toggles ECC checking and injects an error.

The agent is event driven: a fetch is held on the FTQ channels until both pipes
accept it, the memory peer answers acquires as they appear, and the agent waits
for ``toIfu.req.valid`` instead of assuming a pipeline latency.  Every observed
acquire is checked against the reference model's predicted refill set, so an
unexpected memory request (a false miss) fails immediately.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import Any
from typing import Callable

from toffee import ClockCycles
from toffee import Execution
from toffee.signals import sample_signal

from suites.frontend.icache.drivers.level import LevelDriver
from suites.frontend.icache.icache.bundle.ports import ICachePorts
from suites.frontend.icache.icache.case.definitions import prefetch_case as derive_case
from suites.frontend.icache.icache.model import icache as model
from suites.frontend.icache.icache.model.icache import Expectation
from suites.frontend.icache.icache.model.icache import Fill
from suites.frontend.icache.icache.model.icache import ICacheIntegrationModel
from suites.frontend.icache.icache.model.icache import ItlbAnswer
from suites.frontend.icache.icache.model import icache as _icache_model
from suites.frontend.icache.mainpipe.agent.main import compare_outcomes
from suites.frontend.icache.mainpipe.model.mainpipe import FetchRequest
from suites.frontend.icache.mainpipe.model.mainpipe import Outcome


SETTLE_CYCLES = 96
REFILL_BEATS = 2
CTRL_BASE = 0x3802_2080
ECC_CTRL = CTRL_BASE + 0x0
ECC_IADDR = CTRL_BASE + 0x8

# EccCtrlBundle bit layout (first declared field is the most significant):
# iError[9:7], iStatus[6:4], iTarget[3:2], inject[1], enable[0].
ECC_ENABLE = 1 << 0
ECC_INJECT = 1 << 1
ECC_TARGET_DATA = 2 << 2
ECC_TARGET_META = 0 << 2


@dataclass
class MemoryLine:
    """One refill the memory peer will return."""

    block: int
    data: int
    corrupt: int = 0
    denied: int = 0


@dataclass
class _InFlight:
    block: int
    source: int
    data: int
    corrupt: int
    denied: int
    beat: int = 0


class ICacheAgent:
    def __init__(self, dut: Any, *, variant: int = 0) -> None:
        self.dut = dut
        self.ports = ICachePorts.bind(dut)
        self.model = ICacheIntegrationModel(variant=variant)
        self.variant = variant

        self.ftq_main_driver = LevelDriver(self.ports.ftq_main)
        self.ftq_pref_driver = LevelDriver(self.ports.ftq_pref)
        self.flush_bpu_driver = LevelDriver(self.ports.flush_from_bpu)
        self.redirect_driver = LevelDriver(self.ports.redirect_flush)
        self.csr_driver = LevelDriver(self.ports.csr_pf)
        self.fencei_driver = LevelDriver(self.ports.fencei)
        self.wfi_driver = LevelDriver(self.ports.wfi_req)
        self.ifu_ready_driver = LevelDriver(self.ports.ifu_ready)
        self.itlb_driver = LevelDriver(self.ports.itlb_resp)
        self.pmp0_driver = LevelDriver(self.ports.pmp0_resp)
        self.pmp1_driver = LevelDriver(self.ports.pmp1_resp)
        self.soft_driver = LevelDriver(self.ports.soft_prefetch)
        self.mem_a_driver = LevelDriver(self.ports.mem_a_ready)
        self.mem_d_driver = LevelDriver(self.ports.mem_d)
        self.ctrl_a_driver = LevelDriver(self.ports.ctrl_a)
        self.ctrl_d_driver = LevelDriver(self.ports.ctrl_d_ready)
        self.bist_driver = LevelDriver(self.ports.bist_in)

        self._execution: Execution | None = None

        # ITLB peer: a one-cycle pipeline plus a hold-miss phase.
        self.itlb_translate: Callable[[int], ItlbAnswer] = self._default_translate
        self.itlb_hold_miss = 0
        self.itlb_answer: ItlbAnswer | None = None
        self._itlb_captured: ItlbAnswer | None = None

        # PMP peer.
        self.pmp_responder: Callable[[int], tuple[int, int]] = lambda addr: (0, 0)

        # Memory peer.
        self._pending: list[_InFlight] = []
        self._current: _InFlight | None = None
        self.auto_memory = True
        self.expected_fills: dict[int, Fill] = {}
        self.allow_unexpected = False
        # Acquires that were not predicted by the demand-fetch model.  They are
        # tolerated only inside a window that explicitly expects a side effect
        # (a software prefetch), and are always recorded so a test can assert
        # that *nothing else* escaped during that window.
        self.unexpected: list[tuple[int, int]] = []

        self.acquires: list[tuple[int, int]] = []
        self.acquire_aliases: list[int] = []
        self.last_corrupt: tuple[int, int, int, int] = (0, 0, 0, 0)
        self.last_error_valid = 0
        self.last_error_paddr = 0
        self.last_two_fetch = 0
        self.last_observed: Outcome | None = None
        self._fill_cycle: dict[int, int] = {}
        self.cycles = 0

        self.last_outcome: Outcome | None = None

    # -- lifecycle ----------------------------------------------------------
    async def start(self, execution: Execution) -> "ICacheAgent":
        self._execution = execution
        self.idle_inputs()
        await self.reset()
        return self

    async def aclose(self) -> None:
        for driver in (self.ftq_main_driver, self.ftq_pref_driver,
                       self.flush_bpu_driver, self.redirect_driver,
                       self.csr_driver, self.fencei_driver, self.wfi_driver,
                       self.ifu_ready_driver, self.itlb_driver, self.pmp0_driver,
                       self.pmp1_driver, self.soft_driver, self.mem_a_driver,
                       self.mem_d_driver, self.ctrl_a_driver, self.ctrl_d_driver,
                       self.bist_driver):
            driver.close()
        self._execution = None

    def idle_inputs(self) -> None:
        self.ftq_main_driver.set({key: 0 for key in self.ports.ftq_main.bits.fields})
        self.ftq_pref_driver.set({key: 0 for key in self.ports.ftq_pref.bits.fields})
        self.flush_bpu_driver.set({"s2_valid": 0, "s2_flag": 0, "s2_value": 0,
                                   "s3_valid": 0, "s3_flag": 0, "s3_value": 0})
        self.redirect_driver.set({"flush": 0})
        self.csr_driver.set({"enable": 1})
        self.fencei_driver.set({"fencei": 0})
        self.wfi_driver.set({"wfiReq": 0})
        self.ifu_ready_driver.set({"ready": 1})
        self.itlb_driver.set({"miss": 0, "paddr": 0, "pbmt": 0, "gpaddr": 0,
                              "pf": 0, "af": 0, "gpf": 0, "vsNonLeaf": 0})
        self.pmp0_driver.set({"instr": 0, "mmio": 0})
        self.pmp1_driver.set({"instr": 0, "mmio": 0})
        self.soft_driver.set({"valid0": 0, "vaddr0": 0, "valid1": 0, "vaddr1": 0,
                              "valid2": 0, "vaddr2": 0})
        self.mem_a_driver.set({"ready": 1})
        self.mem_d_driver.set({"valid": 0, "opcode": 0, "source": 0, "data": 0,
                               "corrupt": 0, "denied": 0})
        self.ctrl_a_driver.set({"valid": 0, "opcode": 0, "size": 3, "source": 0,
                                "address": 0, "mask": 0, "data": 0})
        self.ctrl_d_driver.set({"ready": 1})
        self.bist_driver.set({key: 0 for key in self.ports.bist_in.bits.fields})

    itlb_drive_early = True

    async def _edge(self) -> None:
        """Advance one cycle, driving every combinational peer around it."""
        self._sample_itlb_request()
        if self.itlb_drive_early:
            self._drive_itlb_response()
        self._sample_acquire()
        self._drive_pmp()
        await ClockCycles(self.dut.clock, 1)
        self.cycles += 1
        if not self.itlb_drive_early:
            self._drive_itlb_response()
        self._advance_memory()

    async def reset(self, cycles: int = 8, sweep: int = 320) -> None:
        """Reset the DUT and wait out the SRAM clear sweep.

        The array macros clear every set through their own write port, which
        keeps ``read.req.ready`` low for as many cycles as there are sets
        (256), so the cache is not usable until that sweep has finished.  The
        registers are randomised before the first reset edge, so anything the
        memory peer sees before reset takes effect is discarded.
        """
        self.idle_inputs()
        self.allow_unexpected = True
        self.dut.reset.Set(1)
        for _ in range(cycles):
            await self._edge()
        self.acquires.clear()
        self._pending.clear()
        self._current = None
        self.dut.reset.Set(0)
        for _ in range(sweep):
            await self._edge()
        self.model = ICacheIntegrationModel(variant=self.variant)
        # Discard every acquire the peer saw while the registers were
        # randomised and the arrays were sweeping; only traffic after reset is
        # subject to the "unexpected acquire" contract.
        self.acquires.clear()
        self.unexpected.clear()
        self._pending.clear()
        self._current = None
        self.expected_fills.clear()
        self.allow_unexpected = False

    # -- low-level observation ---------------------------------------------
    @staticmethod
    def _bit(signal: Any) -> int:
        return int(sample_signal(signal).as_int()) & 1

    def _value(self, binding, field: str) -> int:
        return int(sample_signal(binding.bits[field]).as_int())

    def ifu_valid(self) -> int:
        return self._bit(self.ports.ifu.bits["valid"])

    def ftq_main_fire(self) -> int:
        return int(self._bit(self.ports.ftq_main.bits["valid"])
                   and self._bit(self.ports.ftq_main_ready))

    def ftq_pref_fire(self) -> int:
        return int(self._bit(self.ports.ftq_pref.bits["valid"])
                   and self._bit(self.ports.ftq_pref_ready))

    def mem_a_valid(self) -> int:
        return self._bit(self.ports.mem_a.bits["valid"])

    def wfi_safe(self) -> int:
        return self._bit(self.ports.wfi_safe)

    def error_valid(self) -> int:
        return self._bit(self.ports.error.bits["valid"])

    def itlb_flush_pipe(self) -> int:
        return self._bit(self.ports.itlb_flush_pipe)

    def bist_ack(self, child: int) -> int:
        return self._value(self.ports.bist_out, f"c{child}_ack")

    def bist_outdata(self, child: int) -> int:
        return self._value(self.ports.bist_out, f"c{child}_outdata")

    async def bist_command(self, child: int, *, array: int = 0, all_arrays: int = 0,
                           readen: int = 1, writeen: int = 0, addr: int = 0,
                           addr_rd: int = 0, be: int = 0,
                           indata: int = 0) -> int:
        """Drive one MBIST command to one SRAM child, returning its ack."""
        payload = {key: 0 for key in self.ports.bist_in.bits.fields}
        payload[f"c{child}_req"] = 1
        payload[f"c{child}_array"] = array
        payload[f"c{child}_all"] = all_arrays
        payload[f"c{child}_readen"] = readen
        payload[f"c{child}_writeen"] = writeen
        payload[f"c{child}_addr"] = addr
        payload[f"c{child}_addr_rd"] = addr_rd
        payload[f"c{child}_be"] = be
        payload[f"c{child}_indata"] = indata
        self.bist_driver.set(payload)
        await self._edge()
        await self._edge()
        ack = self.bist_ack(child)
        self.bist_driver.set({key: 0 for key in self.ports.bist_in.bits.fields})
        await self._edge()
        await self._edge()
        return ack

    async def wait_for(self, predicate, *, what: str,
                       cycles: int = SETTLE_CYCLES) -> None:
        for _ in range(cycles):
            if predicate():
                return
            await self._edge()
        if not predicate():
            raise TimeoutError(f"{what} did not happen within {cycles} cycles")

    # -- ITLB / PMP peers ---------------------------------------------------
    @staticmethod
    def _default_translate(vaddr: int) -> ItlbAnswer:
        # Identity map in 4 KiB pages: the physical page is the virtual page.
        return ItlbAnswer(paddr=vaddr & ((1 << 48) - 1))

    def _sample_itlb_request(self) -> None:
        if not self._bit(self.ports.itlb_req.bits["valid"]):
            return
        vaddr = self._value(self.ports.itlb_req, "vaddr")
        if self.itlb_answer is not None:
            answer = self.itlb_answer
        else:
            answer = self.itlb_translate(vaddr)
        if self.itlb_hold_miss:
            answer = ItlbAnswer(paddr=answer.paddr, pbmt=answer.pbmt,
                                gpaddr=answer.gpaddr, pf=answer.pf,
                                gpf=answer.gpf, af=answer.af,
                                vs_non_leaf=answer.vs_non_leaf, miss=1)
        self._itlb_captured = answer

    def _drive_itlb_response(self) -> None:
        if self._itlb_captured is None:
            return
        answer = self._itlb_captured
        self.itlb_driver.set({
            "miss": answer.miss,
            "paddr": answer.paddr,
            "pbmt": answer.pbmt,
            "gpaddr": answer.gpaddr,
            "pf": answer.pf,
            "af": answer.af,
            "gpf": answer.gpf,
            "vsNonLeaf": answer.vs_non_leaf,
        })

    def _drive_pmp(self) -> None:
        for request, driver in ((self.ports.pmp0_req, self.pmp0_driver),
                                (self.ports.pmp1_req, self.pmp1_driver)):
            addr = self._value(request, "addr")
            instr, mmio = self.pmp_responder(addr)
            driver.set({"instr": instr, "mmio": mmio})

    # -- memory peer --------------------------------------------------------
    def _sample_acquire(self) -> None:
        if not (self.mem_a_valid() and self._bit(self.ports.mem_a.bits["valid"])):
            return
        address = self._value(self.ports.mem_a, "address")
        source = self._value(self.ports.mem_a, "source")
        alias = self._value(self.ports.mem_a, "user_alias")
        block = address >> model.BLOCK_OFF_BITS
        self.acquires.append((block, source))
        self.acquire_aliases.append(alias)
        fill = self.expected_fills.get(block)
        if fill is None:
            self.unexpected.append((block, source))
            if not self.allow_unexpected:
                raise AssertionError(
                    f"unexpected memory acquire for block {block:#x} "
                    f"(expected {sorted(self.expected_fills)})")
            data = model.memory_data(block, self.variant)
            corrupt = denied = 0
        else:
            data = fill.data
            corrupt = fill.corrupt
            denied = fill.denied
        # The acquire also carries the alias tag for L2: vSetIdx[7:6].
        expected_alias = (fill.vset >> 6) & 0b11 if fill is not None else None
        if expected_alias is not None and alias != expected_alias:
            raise AssertionError(
                f"acquire alias tag {alias} != vSetIdx[7:6] {expected_alias}")
        self._pending.append(_InFlight(block=block, source=source, data=data,
                                       corrupt=corrupt, denied=denied))

    def _advance_memory(self) -> None:
        if not self.auto_memory:
            return
        if self._current is None and self._pending:
            self._current = self._pending.pop(0)
        if self._current is None:
            self.mem_d_driver.set({"valid": 0, "opcode": 0, "source": 0,
                                   "data": 0, "corrupt": 0, "denied": 0})
            return
        current = self._current
        beat = (current.data >> (256 * current.beat)) & ((1 << 256) - 1)
        self.mem_d_driver.set({
            "valid": 1,
            "opcode": 1,          # TileLink AccessAckData
            "source": current.source,
            "data": beat,
            "corrupt": current.corrupt,
            "denied": current.denied,
        })
        current.beat += 1
        if current.beat >= REFILL_BEATS:
            self._current = None

    # -- FTQ peer -----------------------------------------------------------
    def _main_payload(self, req0: FetchRequest, req1: FetchRequest) -> dict[str, int]:
        payload = {key: 0 for key in self.ports.ftq_main.bits.fields}
        payload["valid"] = 1
        for index, req in enumerate((req0, req1)):
            prefix = f"r{index}_"
            values = {
                "vAddr_0_addr": req.vaddr >> 1,
                "vAddr_1_addr": req.next_vaddr >> 1,
                "endPosition": req.end_position,
                "taken": req.taken,
                "bankSel_0": req.bank_sel[0],
                "bankSel_1": req.bank_sel[1],
                "vSetIdx_0": req.vset[0],
                "vSetIdx_1": req.vset[1],
                "ftqIdx_flag": 0,
                "ftqIdx_value": req.ftq_idx & 0x3F,
            }
            for name, value in values.items():
                key = prefix + name
                if key in payload:
                    payload[key] = value
        payload["r0_hasBackendException"] = req0.has_backend_exception
        payload["r0_hasSatpFlush"] = req0.has_satp_flush
        payload["r1_valid"] = req1.valid
        return payload

    def _pref_payload(self, req0: FetchRequest, req1: FetchRequest,
                      case: int) -> dict[str, int]:
        payload = {key: 0 for key in self.ports.ftq_pref.bits.fields}
        payload["valid"] = 1
        payload["twoPrefetchCase"] = case
        for index, req in enumerate((req0, req1)):
            prefix = f"r{index}_"
            values = {
                "startVAddr_addr": req.vaddr >> 1,
                "nextLineVAddr_addr": req.next_vaddr >> 1,
                "vSetIdx_0": req.vset[0],
                "vSetIdx_1": req.vset[1],
                "isCrossLine": model.is_cross_line(req.vaddr, req.end_position),
                "ftqIdx_flag": 0,
                "ftqIdx_value": req.ftq_idx & 0x3F,
            }
            for name, value in values.items():
                key = prefix + name
                if key in payload:
                    payload[key] = value
        payload["r0_backendException"] = req0.backend_exception
        return payload

    async def _accept_fetch(self, req0: FetchRequest, req1: FetchRequest,
                            case: int) -> None:
        """Present one FTQ issue to both pipes, accepting each exactly once.

        A decoupled producer holds ``valid`` until ``ready`` is observed and
        drops it immediately: the consumer samples the old value on the next
        edge (the accept) and the new zero afterwards.  Clocking an extra edge
        after the observation would leave ``valid`` high long enough for a pipe
        that has already finished to enqueue the same fetch a second time.
        """
        self.ftq_main_driver.set(self._main_payload(req0, req1))
        self.ftq_pref_driver.set(self._pref_payload(req0, req1, case))
        idle_main = {key: 0 for key in self.ports.ftq_main.bits.fields}
        idle_pref = {key: 0 for key in self.ports.ftq_pref.bits.fields}
        await self._edge()   # the payload reaches the DUT on this edge
        main_done = pref_done = False
        for _ in range(SETTLE_CYCLES):
            if not pref_done and self._bit(self.ports.ftq_pref_ready):
                self.ftq_pref_driver.set(idle_pref)
                pref_done = True
            if not main_done and self._bit(self.ports.ftq_main_ready):
                self.last_two_fetch = self._bit(self.ports.to_ftq_two)
                self.ftq_main_driver.set(idle_main)
                main_done = True
            if main_done and pref_done:
                break
            await self._edge()
        else:
            raise TimeoutError(
                f"FTQ request not accepted (main={main_done}, pref={pref_done})")
        # No trailing edge: a hit answers in the very next cycle and the caller
        # must observe that response before it is consumed.

    # -- fetch operations ---------------------------------------------------
    async def send(
        self,
        req0: FetchRequest,
        req1: FetchRequest | None = None,
        *,
        case: int | None = None,
        itlb: ItlbAnswer | None = None,
        pmp_instr: int = 0,
        pmp_mmio: int = 0,
        corrupt_refill: int = 0,
        denied_refill: int = 0,
        check: bool = True,
        undefined: tuple[str, ...] = (),
    ) -> Outcome:
        """Present one fetch issue and compare the response against the model.

        ``undefined`` names response fields that the architecture genuinely does
        not determine for this stimulus (for example instruction bytes of a line
        that was just reported corrupt, or the stitched RVC map of two refills
        that arrive in a timing-dependent order).  Only those fields are skipped;
        every other field, including the number of acquires and the miss
        requests, is still checked.  This is a bounded tolerance, not a global
        ``check=False``.
        """
        req1 = req1 or FetchRequest(0, 0, 0, 0, valid=0)
        if case is None:
            case = derive_case(req0, req1)
        itlb = itlb or self.itlb_translate(req0.vaddr)
        self.pmp_responder = lambda addr: (pmp_instr, pmp_mmio)

        expected = self.model.expect(
            req0, req1, itlb=itlb, pmp_instr=pmp_instr, pmp_mmio=pmp_mmio,
            corrupt_refill=corrupt_refill, denied_refill=denied_refill)
        self.itlb_answer = itlb
        self.expected_fills = dict(expected.fill_by_block)
        self.last_outcome = expected.outcome
        start = len(self.acquires)

        await self._accept_fetch(req0, req1, case)
        observed = await self._wait_response(expected, start)
        self.model.fetch_count += 1
        for fill in expected.fills:
            self.model.commit_fill(fill)
        for touch in expected.touches:
            self.model.commit_hit(touch)
        self.expected_fills = {}
        if check:
            self._compare(observed, expected, undefined=undefined)
        self.itlb_answer = None
        if any(block.exception for block in observed.blocks if block.valid):
            # An exception redirects the front end; the way-lookup entry that
            # carries an exception is only released by that flush.
            await self.redirect_flush()
        return observed

    def _compare(self, observed: Outcome, expected: Expectation,
                 *, undefined: tuple[str, ...] = ()) -> None:
        """Compare the response, ignoring what the chip does not publish.

        Two things are outside the observable contract:

        * the replacer touch, which has no chip-level port;
        * data banks that belong to no line of the fetch, which the data array
          never reads and therefore holds stale register contents.
        """
        got_blocks = []
        want_blocks = []
        for index in (0, 1):
            banks = expected.data_masks[index]
            mask = sum(((1 << 64) - 1) << (64 * bank) for bank in range(8)
                       if (banks >> bank) & 1)
            got_blocks.append(dataclasses.replace(
                observed.blocks[index], data=observed.blocks[index].data & mask))
            want_blocks.append(dataclasses.replace(
                expected.outcome.blocks[index],
                data=expected.outcome.blocks[index].data & mask))
        # ``toIfu.perf.hits`` is a performance hint, not part of the fetch
        # result: it reports the raw way-lookup result of request 0.  Only the
        # first line's bit is architecturally tied to this fetch (the second
        # slot is the speculative next-line lookup), so only it is compared.
        def raw_hits(hits):
            return (hits[0], 0)

        def scrub(outcome):
            # Blank the top-level fields the caller declared undefined, so the
            # shared comparator cannot flag them, while every other field is
            # still compared.
            updates = {}
            for name in undefined:
                if name in ("maybe_rvc_map", "first_range", "total_range",
                            "two_fetch_valid", "raw_hits"):
                    updates[name] = 0
            return dataclasses.replace(outcome, **updates)

        def scrub_blocks(blocks):
            out = []
            for block in blocks:
                updates = {name: 0 for name in undefined
                           if name in block.__dataclass_fields__}
                out.append(dataclasses.replace(block, **updates))
            return tuple(out)

        compare_outcomes(
            scrub(dataclasses.replace(
                observed, blocks=scrub_blocks(got_blocks), touches=(),
                raw_hits=raw_hits(observed.raw_hits))),
            scrub(dataclasses.replace(
                expected.outcome, blocks=scrub_blocks(want_blocks), touches=(),
                raw_hits=raw_hits(expected.outcome.raw_hits))))

    async def _wait_response(self, expected: Expectation, start: int = 0) -> Outcome:
        for _ in range(SETTLE_CYCLES):
            if self.ifu_valid():
                break
            await self._edge()
        else:
            raise TimeoutError(
                f"no IFU response (acquires={self.acquires[-4:]})")
        observed = self.sample_ifu()
        self.last_observed = observed
        # ``toIfu.corrupt`` is a stage-2 signal (one cycle after the response)
        # and ``io.error`` one register later, so observe both together.
        corrupt = [0, 0, 0, 0]
        self.last_error_valid = 0
        for _ in range(5):
            for index, (i, j) in enumerate(
                    ((0, 0), (0, 1), (1, 0), (1, 1))):
                corrupt[index] |= self._value(
                    self.ports.ifu, f"corrupt{i}{j}")
            if self.error_valid():
                self.last_error_valid = 1
                self.last_error_paddr = self._value(self.ports.error, "paddr")
            await self._edge()
        self.last_corrupt = tuple(corrupt)
        observed_blocks = {block for block, _ in self.acquires[start:]}
        missing = set(expected.fill_blocks) - observed_blocks
        if missing:
            raise AssertionError(
                f"model expected refills for {sorted(missing)}, "
                f"observed {sorted(self.acquires)}")
        return observed

    async def prefetch_only(self, req: FetchRequest, *,
                            case: int = 0,
                            settle: int = 30) -> list[tuple[int, int]]:
        """Present one prefetch request with no matching main-pipe request.

        The prefetch pipe writes the way-lookup entry and (on a miss) issues the
        refill, but the entry is not consumed, so a later refill response can
        correct or invalidate it in place.
        """
        absent = FetchRequest(0, 0, 0, 0, valid=0)
        idle = {key: 0 for key in self.ports.ftq_pref.bits.fields}
        previous = self.allow_unexpected
        self.allow_unexpected = True
        before = len(self.acquires)
        before_unexpected = len(self.unexpected)
        self.ftq_pref_driver.set(self._pref_payload(req, absent, case))
        await self._edge()
        for _ in range(SETTLE_CYCLES):
            if self._bit(self.ports.ftq_pref_ready):
                break
            await self._edge()
        else:
            raise TimeoutError("prefetch request was not accepted")
        self.ftq_pref_driver.set(idle)
        for _ in range(settle):
            await self._edge()
        self.allow_unexpected = previous
        # The prefetch path legitimately fetches the lines it names, but nothing
        # else: an acquire outside those blocks means the pipeline started work
        # the FTQ never authorised.
        allowed = {self.itlb_translate(vaddr).paddr >> model.BLOCK_OFF_BITS
                   for vaddr in (req.vaddr, req.next_vaddr)}
        stray = [(block, source)
                 for block, source in self.unexpected[before_unexpected:]
                 if block not in allowed]
        if stray:
            raise AssertionError(
                "an FTQ prefetch fetched a block it never named: "
                f"{[(hex(b), s) for b, s in stray]} "
                f"(named {[hex(b) for b in sorted(allowed)]})")
        return self.acquires[before:]

    async def send_main_only(self, req: FetchRequest, *,
                             itlb: ItlbAnswer | None = None,
                             check: bool = True,
                             case: int = 0,
                             undefined: tuple[str, ...] = ()) -> Outcome:
        """Consume one way-lookup entry with a main-pipe-only request.

        This is how the FTQ would replay a fetch whose entry was queued by the
        prefetch pipe; it lets a test observe the entry after an in-place update
        (a refill has corrected or invalidated it).
        """
        absent = FetchRequest(0, 0, 0, 0, valid=0)
        itlb = itlb or self.itlb_translate(req.vaddr)
        expected = self.model.expect(req, absent, itlb=itlb)
        self.expected_fills = dict(expected.fill_by_block)
        self.itlb_answer = itlb
        self.last_outcome = expected.outcome
        start = len(self.acquires)
        idle = {key: 0 for key in self.ports.ftq_main.bits.fields}
        self.ftq_main_driver.set(self._main_payload(req, absent))
        await self._edge()
        for _ in range(SETTLE_CYCLES):
            if self._bit(self.ports.ftq_main_ready):
                break
            await self._edge()
        else:
            raise TimeoutError("main-only request was not accepted")
        self.last_two_fetch = self._bit(self.ports.to_ftq_two)
        self.ftq_main_driver.set(idle)
        observed = await self._wait_response(expected, start)
        for fill in expected.fills:
            self.model.commit_fill(fill)
        for touch in expected.touches:
            self.model.commit_hit(touch)
        self.expected_fills = {}
        if check:
            self._compare(observed, expected, undefined=undefined)
        self.itlb_answer = None
        return observed

    def sample_ifu(self) -> Outcome:
        bits = self.ports.ifu.bits

        def present(field: str) -> bool:
            return field in bits.fields

        def read(index: int, name: str) -> int:
            return self._value(self.ports.ifu, f"info{index}_{name}")

        def block(index: int) -> "_icache_model.mp.IfuBlock":
            valid = 1 if index == 0 else (
                self._value(self.ports.ifu, "info1_valid")
                if present("info1_valid") else 0)
            return _icache_model.mp.IfuBlock(
                valid=valid,
                start_vaddr=read(index, "startVAddr") << 1,
                ftq_idx=(read(index, "ftqIdx_flag") << 6)
                | read(index, "ftqIdx_value"),
                taken_valid=read(index, "takenValid"),
                taken_bits=read(index, "takenBits"),
                size=read(index, "size"),
                data=read(index, "data"),
                cross_line=(self._bit(self.ports.ifu.bits["perfDoubleLine"])
                            if index == 0 else 0),
                exception=read(index, "exception"),
                pmp_mmio=(read(index, "pmpMmio")
                          if present(f"info{index}_pmpMmio") else 0),
                backend_exception=(read(index, "backendException")
                                   if present(f"info{index}_backendException") else 0),
                has_satp_flush=(read(index, "hasSatpFlush")
                                if present(f"info{index}_hasSatpFlush") else 0),
                vs_non_leaf=read(index, "vsNonLeaf"),
                itlb_pbmt=(read(index, "pbmt")
                           if present(f"info{index}_pbmt") else 0),
                paddr=((read(index, "paddr") << 1)
                       if present(f"info{index}_paddr") else 0),
                gpaddr=((read(index, "gpaddr") << 1)
                        if present(f"info{index}_gpaddr") else 0),
            )

        return Outcome(
            two_fetch_valid=self.last_two_fetch,
            ifu_valid=self.ifu_valid(),
            maybe_rvc_map=self._value(self.ports.ifu, "maybeRvcMap"),
            first_range=self._value(self.ports.ifu, "firstRange"),
            total_range=self._value(self.ports.ifu, "totalRange"),
            blocks=(block(0), block(1)),
            pending_miss=self._bit(self.ports.ifu.bits["missBubble"]),
            raw_hits=(self._bit(self.ports.ifu.bits["perfHit0"]),
                      self._bit(self.ports.ifu.bits["perfHit1"])),
            touches=tuple(),
        )

    # -- redirects ----------------------------------------------------------
    async def bpu_s3_flush(self, flag: int, value: int, cycles: int = 2) -> None:
        """Pulse the BPU stage-3 redirect interface."""
        self.flush_bpu_driver.set({
            "s2_valid": 0, "s2_flag": 0, "s2_value": 0,
            "s3_valid": 1, "s3_flag": flag, "s3_value": value,
        })
        for _ in range(cycles):
            await self._edge()
        self.flush_bpu_driver.set({
            "s2_valid": 0, "s2_flag": 0, "s2_value": 0,
            "s3_valid": 0, "s3_flag": 0, "s3_value": 0,
        })
        await self._edge()
        await self._edge()

    async def redirect_flush(self, cycles: int = 2) -> None:
        self.redirect_driver.set({"flush": 1})
        for _ in range(cycles):
            await self._edge()
        self.redirect_driver.set({"flush": 0})
        await self._edge()
        await self._edge()

    async def fence_i(self, cycles: int = 2) -> None:
        self.fencei_driver.set({"fencei": 1})
        for _ in range(cycles):
            await self._edge()
        self.fencei_driver.set({"fencei": 0})
        await self._edge()
        await self._edge()
        self.model.invalidate_all()

    async def set_wfi(self, value: int) -> None:
        self.wfi_driver.set({"wfiReq": value})
        await self._edge()
        await self._edge()

    async def soft_prefetch(self, vaddr: int,
                            port: int = 0) -> list[tuple[int, int]]:
        """Pulse a software prefetch request (prefetch.i retires once).

        Any load unit may retire the hint; the ICache accepts three request
        ports with port 0 at the highest priority.
        """
        if port not in (0, 1, 2):
            raise ValueError("soft-prefetch port must be 0, 1 or 2")
        previous = self.allow_unexpected
        self.allow_unexpected = True
        before = len(self.acquires)
        before_unexpected = len(self.unexpected)
        request = {"valid0": 0, "vaddr0": 0, "valid1": 0, "vaddr1": 0,
                   "valid2": 0, "vaddr2": 0}
        request[f"valid{port}"] = 1
        request[f"vaddr{port}"] = vaddr
        self.soft_driver.set(request)
        await self._edge()
        self.soft_driver.set({"valid0": 0, "vaddr0": 0, "valid1": 0,
                              "vaddr1": 0, "valid2": 0, "vaddr2": 0})
        for _ in range(SETTLE_CYCLES):
            await self._edge()
        self.allow_unexpected = previous
        # Only the hinted line may be fetched.  Any other block that escaped
        # during the window is a real defect (e.g. a concurrent FTQ issue being
        # processed without its handshake), so it is not silently tolerated.
        escaped = self.unexpected[before_unexpected:]
        expected_blocks = {vaddr >> model.BLOCK_OFF_BITS}
        stray = [(block, source) for block, source in escaped
                 if block not in expected_blocks]
        if stray:
            raise AssertionError(
                "a software prefetch fetched an unrelated block: "
                f"{[(hex(b), s) for b, s in stray]} "
                f"(only {[hex(b) for b in expected_blocks]} was requested)")
        return self.acquires[before:]

    # -- ECC control registers ---------------------------------------------
    async def ctrl_write(self, address: int, data: int) -> int:
        self.ctrl_a_driver.set({
            "valid": 1, "opcode": 0, "size": 3, "source": 1,
            "address": address, "mask": 0xFF, "data": data,
        })
        for _ in range(SETTLE_CYCLES):
            if self._bit(self.ports.ctrl_a_ready):
                break
            await self._edge()
        else:
            raise TimeoutError("ECC control register did not accept a write")
        await self._edge()
        self.ctrl_a_driver.set({"valid": 0, "opcode": 0, "size": 3, "source": 0,
                                "address": 0, "mask": 0, "data": 0})
        opcode, _ = await self._ctrl_response()
        if opcode != 0:
            raise AssertionError(f"write acknowledged with opcode {opcode} != 0")
        return opcode

    async def ctrl_read(self, address: int) -> int:
        self.ctrl_a_driver.set({
            "valid": 1, "opcode": 4, "size": 3, "source": 2,
            "address": address, "mask": 0xFF, "data": 0,
        })
        for _ in range(SETTLE_CYCLES):
            if self._bit(self.ports.ctrl_a_ready):
                break
            await self._edge()
        else:
            raise TimeoutError("ECC control register did not accept a read")
        await self._edge()
        self.ctrl_a_driver.set({"valid": 0, "opcode": 0, "size": 3, "source": 0,
                                "address": 0, "mask": 0, "data": 0})
        opcode, data = await self._ctrl_response()
        if opcode != 1:
            raise AssertionError(f"read returned opcode {opcode} != 1")
        return data

    async def _ctrl_response(self) -> tuple[int, int]:
        for _ in range(SETTLE_CYCLES):
            if self._bit(self.ports.ctrl_d.bits["valid"]):
                opcode = self._value(self.ports.ctrl_d, "opcode")
                data = self._value(self.ports.ctrl_d, "data")
                await self._edge()
                return opcode, data
            await self._edge()
        raise TimeoutError("no response from the ECC control register")

    async def inject_ecc_error(self, paddr: int) -> None:
        """Ask the control unit to poison the cached line containing ``paddr``."""
        # enable=1, target=DataArray, inject=1
        await self.ctrl_write(ECC_IADDR, paddr)
        await self.ctrl_write(ECC_CTRL, ECC_ENABLE | ECC_INJECT | ECC_TARGET_DATA)
        for _ in range(SETTLE_CYCLES):
            status = await self.ctrl_read(ECC_CTRL)
            state = (status >> 4) & 0b111
            if state == 2:       # Injected
                return
            if state == 7:       # Error
                error = status & 0b111
                raise AssertionError(
                    f"ECC injection failed with error code {error}")
        raise TimeoutError("ECC injection did not complete")
