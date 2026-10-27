"""Agent for ICacheWayLookup.

The agent owns every clock edge so tests never touch signals directly.

Clocking policy
---------------
DUT inputs are rise-write (see ``DutFactory.initialize_dut_inputs``), so a
driven level becomes visible to the RTL one edge later. Writes therefore take
exactly two edges; reads are not assumed to have a fixed latency and are
observed as events instead. Only residency checkpoints (empty/occupancy) are
compared cycle-exactly, which is what the module's contract actually promises.
"""

from __future__ import annotations

from typing import Any

from toffee import ClockCycles
from toffee import Execution
from toffee.data import compile_sampler
from toffee.signals import sample_signal

from icacheverify.common.driver.level import LevelDriver
from icacheverify.common.monitor.cycle import CycleMonitor
from icacheverify.waylookup.bundle.ports import WayLookupPorts
from icacheverify.waylookup.checker.residency import ResidencyChecker
from icacheverify.waylookup.driver.encoding import encode_control
from icacheverify.waylookup.driver.encoding import encode_write
from icacheverify.waylookup.model.queue import Refill
from icacheverify.waylookup.model.queue import ResidentEntry
from icacheverify.waylookup.model.queue import WayLookupModel
from icacheverify.waylookup.model.queue import idx_from_block
from icacheverify.waylookup.model.queue import ptag_from_block
from icacheverify.waylookup.monitor.decode import decode_read
from icacheverify.waylookup.transaction.types import ItlbException
from icacheverify.waylookup.transaction.types import WayLookupEntry
from icacheverify.waylookup.transaction.types import WayLookupRead
from icacheverify.waylookup.transaction.types import WayLookupWrite


PREFETCH_DEPTH = 32
READ_TIMEOUT_CYCLES = 256


def _idle_write_payload(index: int) -> dict:
    """All-zero payload so an idle port cannot inject stale metadata."""
    payload: dict = {
        "entry": {
            "vSetIdx": (0, 0),
            "waymask": (0, 0),
            "pTag": 0,
            "maybeRvcMap": (0, 0),
            "metaCodes": (0, 0),
            "isMmio": 0,
            "itlbPbmt": 0,
        },
        "ftqIdx": {"flag": 0, "value": 0},
    }
    if index == 0:
        payload["exceptionEntry"] = {
            "itlbException_value": 0, "gpAddr_addr": 0, "isForVSnonLeafPTE": 0,
        }
    return payload


class WayLookupAgent:
    def __init__(self, dut: Any, *, depth: int = PREFETCH_DEPTH) -> None:
        self.dut = dut
        self.ports = WayLookupPorts.bind(dut)
        self.model = WayLookupModel(depth=depth, fetch_ports=len(self.ports.write))
        self.checker = ResidencyChecker(self.model)
        self.reset_driver = None
        self.control_driver = LevelDriver(self.ports.control)
        self.read_ready_driver = LevelDriver(self.ports.read_ready)
        self.update_level = LevelDriver(self.ports.update)
        # Level drivers, not per-port handshake drivers: the prefetch ports
        # must commit on the same edge, and an independent driver per port can
        # interleave its clock steps. The agent owns the one edge they share.
        self.write_payload_drivers = tuple(
            LevelDriver(port.payload) for port in self.ports.write
        )
        self.write_valid_drivers = tuple(
            LevelDriver(port.valid_binding(dut.clock)) for port in self.ports.write
        )
        self.read_monitor = CycleMonitor(
            self.ports.read.observe(dut.clock), decoder=decode_read
        )
        self._status_sampler = compile_sampler(self.ports.status.bits)
        self._reads: list[WayLookupRead] = []
        self._slot1_code = 0
        self._execution: Execution | None = None
        self._started = False

    # -- lifecycle ----------------------------------------------------------
    async def start(self, execution: Execution) -> "WayLookupAgent":
        from icacheverify.common.driver.signal import ResetDriver

        self.reset_driver = ResetDriver(self.dut)
        self._execution = execution
        await self.reset_driver.__aenter__()
        self.control_driver.set(encode_control())
        self.read_ready_driver.set({"ready": 0})
        self.update_level.set({"valid": 0, "bits": {
            "blkPAddr": 0, "vSetIdx": 0, "waymask": 0,
            "maybeRvcMap": 0, "corrupt": 0,
        }})
        for driver in self.write_valid_drivers:
            driver.set({"valid": 0})
        for index, driver in enumerate(self.write_payload_drivers):
            driver.set(_idle_write_payload(index))
        self.read_monitor.start(
            execution,
            observer=lambda transfer: self._record(transfer.value),
        )
        self._started = True
        await self.reset()
        return self

    async def aclose(self) -> None:
        try:
            await self.read_monitor.aclose()
        finally:
            for driver in (*self.write_payload_drivers, *self.write_valid_drivers):
                driver.close()
            self.control_driver.close()
            self.read_ready_driver.close()
            self.update_level.close()
            if self.reset_driver is not None:
                self.reset_driver.close()
            self._execution = None
            self._started = False

    def _record(self, value: Any) -> None:
        if value is not None:
            self._reads.append(value)

    # -- primitive cycles ---------------------------------------------------
    async def reset(self, cycles: int = 3) -> None:
        self.control_driver.set(encode_control())
        self.read_ready_driver.set({"ready": 0})
        assert self.reset_driver is not None
        await self.reset_driver.send(cycles)
        self.model = WayLookupModel(depth=self.model.depth, fetch_ports=self.model.fetch_ports)
        self.checker = ResidencyChecker(self.model)
        self._reads.clear()

    # -- operations ---------------------------------------------------------
    async def write(
        self,
        *entries: WayLookupEntry,
        ftq_value: int = 0,
        ftq_flag: int = 0,
    ) -> None:
        """Enqueue one or two entries, both committed on the same edge."""
        if not 1 <= len(entries) <= len(self.ports.write):
            raise ValueError(f"expected 1..{len(self.ports.write)} entries")
        writers = entries

        for index, entry in enumerate(writers):
            encode = encode_write if index == 0 else (
                lambda write, _encode=encode_write: _encode(write, include_exception=False))
            payload = encode(WayLookupWrite(entry=entry, ftq_flag=ftq_flag, ftq_value=ftq_value))
            self.write_payload_drivers[index].set(payload)
            self.write_valid_drivers[index].set({"valid": 1})

        if not self.rtl_write_ready():
            for driver in self.write_valid_drivers:
                driver.set({"valid": 0})
            raise AssertionError(
                f"write not accepted: ready low with {self.model.occupancy()} resident")

        # Probed against the RTL: a level driven by ``Set`` is sampled on the
        # very next rising edge, and holding it longer repeats the beat. So one
        # edge carries exactly one accepted write, and deasserting costs one
        # harmless edge.
        await ClockCycles(self.dut.clock, 1)
        self.model.step(
            write_fire=len(writers),
            write_entries=tuple(self._resident(entry) for entry in writers),
            write_ftq_flag=ftq_flag,
            write_ftq_value=ftq_value,
        )
        for driver in self.write_valid_drivers:
            driver.set({"valid": 0})
        await ClockCycles(self.dut.clock, 1)
        self.model.step()

    async def write_pair_with_refill(
        self,
        first: WayLookupEntry,
        second: WayLookupEntry,
        *,
        refill_block: int,
        refill_waymask: int,
        refill_rvc_map: int = 0,
        ftq_value: int = 0,
        ftq_flag: int = 0,
    ) -> None:
        """Dual-port write plus a refill, all committed on the same edge."""
        payloads = [
            encode_write(WayLookupWrite(entry=first, ftq_flag=ftq_flag, ftq_value=ftq_value)),
            encode_write(
                WayLookupWrite(entry=second, ftq_flag=ftq_flag, ftq_value=ftq_value),
                include_exception=False),
        ]
        refill_payload = {
            "blkPAddr": refill_block,
            "vSetIdx": idx_from_block(refill_block),
            "waymask": refill_waymask,
            "maybeRvcMap": refill_rvc_map,
            "corrupt": 0,
        }
        for driver, payload in zip(self.write_payload_drivers, payloads):
            driver.set(payload)
        for driver in self.write_valid_drivers:
            driver.set({"valid": 1})
        self.update_level.set({"valid": 1, "bits": refill_payload})
        if not self.rtl_write_ready():
            for driver in self.write_valid_drivers:
                driver.set({"valid": 0})
            self.update_level.set({"valid": 0, "bits": refill_payload})
            raise AssertionError(
                f"dual write not accepted: ready low with {self.model.occupancy()} resident")

        await ClockCycles(self.dut.clock, 1)
        self.model.step(
            write_fire=2,
            write_entries=(self._resident(first), self._resident(second)),
            write_ftq_flag=ftq_flag,
            write_ftq_value=ftq_value,
            refills=(Refill(refill_block, refill_waymask, refill_rvc_map, 0),),
        )
        for driver in self.write_valid_drivers:
            driver.set({"valid": 0})
        self.update_level.set({"valid": 0, "bits": refill_payload})
        await ClockCycles(self.dut.clock, 1)
        self.model.step()

    @staticmethod
    def _resident(entry: WayLookupEntry) -> ResidentEntry:
        """Port-0 view of a queued entry, used by the refill-update rule.

        Tests that exercise refills write single-port entries, so both ports
        carry the same set index and the port-0 view is complete.
        """
        return ResidentEntry(
            ptag=entry.ptag,
            vset_idx=entry.vset_idx[0],
            waymask=entry.waymask[0],
            maybe_rvc_map=entry.maybe_rvc_map[0],
            exception=int(bool(entry.exception.value)),
        )

    async def write_with_refill(
        self,
        entry: WayLookupEntry,
        *,
        refill_block: int,
        refill_waymask: int,
        refill_rvc_map: int = 0,
        ftq_value: int = 0,
        ftq_flag: int = 0,
    ) -> None:
        """Issue a prefetch write and a refill on the same edge.

        Both ports are valid-only in their own cycle, so they must be driven
        together; the model applies the refill to the resident entries *before*
        the new entry is appended, because a write cannot update itself.
        """
        payload = encode_write(
            WayLookupWrite(entry=entry, ftq_flag=ftq_flag, ftq_value=ftq_value))
        refill_payload = {
            "blkPAddr": refill_block,
            "vSetIdx": idx_from_block(refill_block),
            "waymask": refill_waymask,
            "maybeRvcMap": refill_rvc_map,
            "corrupt": 0,
        }
        self.write_payload_drivers[0].set(payload)
        self.write_valid_drivers[0].set({"valid": 1})
        self.update_level.set({"valid": 1, "bits": refill_payload})
        if not self.rtl_write_ready():
            self.write_valid_drivers[0].set({"valid": 0})
            self.update_level.set({"valid": 0, "bits": refill_payload})
            raise AssertionError(
                f"write not accepted: ready low with {self.model.occupancy()} resident")

        # Both ports are sampled on this edge, so the write and the refill are
        # genuinely concurrent. The model applies the refill to the entries
        # resident *before* the new one is appended.
        await ClockCycles(self.dut.clock, 1)
        self.model.step(
            write_fire=1,
            write_entries=(self._resident(entry),),
            write_ftq_flag=ftq_flag,
            write_ftq_value=ftq_value,
            refills=(Refill(refill_block, refill_waymask, refill_rvc_map, 0),),
        )
        self.write_valid_drivers[0].set({"valid": 0})
        self.update_level.set({"valid": 0, "bits": refill_payload})
        await ClockCycles(self.dut.clock, 1)
        self.model.step()

    async def refill(
        self,
        block_address: int,
        *,
        waymask: int,
        maybe_rvc_map: int = 0,
        corrupt: int = 0,
        observe_cycles: int = 2,
    ) -> None:
        """Deliver one miss response to the memo update port.

        ``block_address`` is the byte address shifted down by the block offset
        (the DUT's ``blkPAddr``); the model derives tag and set from it so the
        stimulus is a physical address, not an RTL field assignment.
        """
        self.control_driver.set(encode_control())
        # firtool prunes `data`/`denied`: the memo update consumes only the
        # set, tag, waymask, RVC map and corrupt flag.
        payload = {
            "blkPAddr": block_address,
            "vSetIdx": idx_from_block(block_address),
            "waymask": waymask,
            "maybeRvcMap": maybe_rvc_map,
            "corrupt": corrupt,
        }
        drive = {"valid": 1, "bits": payload}
        # The update port is Valid-only (no ready), so the level is committed on
        # the first edge and the effect is visible on the next.
        self.update_level.set(drive)
        await ClockCycles(self.dut.clock, 1)
        self.model.step(refills=(Refill(block_address, waymask, maybe_rvc_map, corrupt),))
        self.update_level.set({"valid": 0, "bits": payload})
        await ClockCycles(self.dut.clock, 1)
        self.model.step()
        # Let the rewritten metadata settle before the next observation.
        for _ in range(observe_cycles):
            await ClockCycles(self.dut.clock, 1)
            self.model.step()

    async def refill_and_observe_read(
        self,
        block_address: int,
        *,
        waymask: int,
        maybe_rvc_map: int = 0,
        corrupt: int = 0,
    ) -> int:
        """Drive a refill and sample ``toMainPipe.valid`` on the same edge.

        Returns the observed valid level so a test can prove the memo rewrite
        suppresses the read. The model predicts 0 when the refill touches the
        entry at the read pointer.
        """
        payload = {
            "blkPAddr": block_address,
            "vSetIdx": idx_from_block(block_address),
            "waymask": waymask,
            "maybeRvcMap": maybe_rvc_map,
            "corrupt": corrupt,
        }
        self.read_ready_driver.set({"ready": 1})
        self.update_level.set({"valid": 1, "bits": payload})
        await ClockCycles(self.dut.clock, 1)
        observed = self.rtl_read_valid()
        predicted = self.model.read_valid(
            update_slots=self.model.updated_slots(
                self.model.state, (Refill(block_address, waymask, maybe_rvc_map, corrupt),)))
        if observed != predicted:
            raise AssertionError(
                f"read.valid {observed} != predicted {predicted} while the memo is rewritten")
        self.model.step(refills=(Refill(block_address, waymask, maybe_rvc_map, corrupt),))
        # Drop both levels together: leaving ready high would let the RTL
        # consume the entry on the deassert edge, before the caller reads it.
        self.read_ready_driver.set({"ready": 0})
        self.update_level.set({"valid": 0, "bits": payload})
        await ClockCycles(self.dut.clock, 1)
        self.model.step()
        return observed

    def rtl_read_valid(self) -> int:
        return int(sample_signal(self.ports.read.valid).as_int()) & 1

    def resident(self, count: int = 1) -> tuple[ResidentEntry, ...]:
        return tuple(self.model.peek(count))

    async def expect_no_read(self, cycles: int = 8) -> None:
        """Assert that the queue presents no beat for ``cycles`` edges."""
        first = len(self._reads)
        self.read_ready_driver.set({"ready": 1})
        try:
            for _ in range(cycles):
                await ClockCycles(self.dut.clock, 1)
                self.model.step()
        finally:
            self.read_ready_driver.set({"ready": 0})
        await ClockCycles(self.dut.clock, 1)
        self.model.step()
        if len(self._reads) - first:
            raise AssertionError(
                f"queue returned {len(self._reads) - first} unexpected beats"
            )

    async def read_beats(self, count: int = 1) -> tuple[WayLookupRead, ...]:
        """Accept ``count`` beats from the main pipe.

        Latency is not assumed: the agent waits for beats to appear and fails
        only if they never do. Order is checked by the caller.
        """
        if count <= 0:
            raise ValueError("read count must be positive")
        if count > len(self.model.tags):
            raise ValueError(f"cannot read {count} beats with {len(self.model.tags)} resident")
        first = len(self._reads)
        self.read_ready_driver.set({"ready": 1})
        accepted = 0
        waited = 0
        try:
            while accepted < count:
                await ClockCycles(self.dut.clock, 1)
                waited += 1
                if waited > READ_TIMEOUT_CYCLES:
                    raise TimeoutError(
                        f"only {accepted}/{count} read beats arrived in "
                        f"{READ_TIMEOUT_CYCLES} cycles (rtl_empty={self.rtl_empty()})"
                    )
                produced = len(self._reads) - first - accepted
                if produced:
                    accepted += produced
                    self._slot1_code = int(sample_signal(
                        self.dut.io_toMainPipe_bits_wayLookupInfo_1_bits_exceptionEntry_itlbException_value
                    ).as_int())
                    self.model.step(deq=produced)
                else:
                    self.model.step()
                if accepted > count:
                    raise AssertionError(
                        f"queue returned {accepted} beats for a {count}-beat request")
                if accepted >= count:
                    break
        finally:
            self.read_ready_driver.set({"ready": 0})
        # Let the read-pointer update and the deasserted ready settle before a
        # caller samples residency checkpoints.
        await ClockCycles(self.dut.clock, 1)
        self.model.step()
        return tuple(self._reads[first:first + count])

    async def idle_cycle(self) -> None:
        """One cycle with no writes, no reads and no control change."""
        await ClockCycles(self.dut.clock, 1)
        self.model.step()

    async def flush(self) -> None:
        # Exactly one edge may assert the level: the RTL acts on every edge it
        # observes high, so holding it longer repeats the effect.
        self.control_driver.set(encode_control(flush=1))
        await ClockCycles(self.dut.clock, 1)
        self.model.step(flush=1)
        self.control_driver.set(encode_control())
        await ClockCycles(self.dut.clock, 1)
        self.model.step()

    async def stage3_flush(self, ftq_value: int, ftq_flag: int = 0, *, drop: bool = True) -> None:
        """Assert the stage-3 flush for exactly one edge.

        The RTL drops the youngest entry on every edge it samples the level
        high, so a two-edge pulse would drop two entries.
        """
        self.control_driver.set(
            encode_control(s3_valid=1, s3_flag=ftq_flag, s3_value=ftq_value)
        )
        await ClockCycles(self.dut.clock, 1)
        self.model.step(
            s3_flush_valid=1,
            s3_flush_ftq=(ftq_flag << 6) | (ftq_value & 0x3F),
        )
        self.control_driver.set(encode_control())
        await ClockCycles(self.dut.clock, 1)
        self.model.step()

    # -- observation --------------------------------------------------------
    def rtl_empty(self) -> int:
        return int(self._status_sampler()["empty"])

    def rtl_write_ready(self) -> int:
        return int(sample_signal(self.ports.write[0].ready).as_int()) & 1

    def _slot_entry(self, slot: int) -> WayLookupEntry:
        """Sample one output slot's payload (the DUT publishes both slots)."""
        prefix = f"io_toMainPipe_bits_wayLookupInfo_{slot}_bits"

        def read(name: str) -> int:
            signal = getattr(self.dut, f"{prefix}_{name}", None)
            return 0 if signal is None else int(sample_signal(signal).as_int())

        return WayLookupEntry(
            vset_idx=(read("entry_vSetIdx_0"), read("entry_vSetIdx_1")),
            waymask=(read("entry_waymask_0"), read("entry_waymask_1")),
            ptag=read("entry_pTag"),
            maybe_rvc_map=(read("entry_maybeRvcMap_0"),
                           read("entry_maybeRvcMap_1")),
            meta_codes=(read("entry_metaCodes_0"), read("entry_metaCodes_1")),
            is_mmio=read("entry_isMmio"),
            itlb_pbmt=read("entry_itlbPbmt"),
            exception=ItlbException(
                value=read("exceptionEntry_itlbException_value"),
                gpaddr=read("exceptionEntry_gpAddr_addr") << 1,
                is_for_vs_non_leaf_pte=read(
                    "exceptionEntry_isForVSnonLeafPTE"),
            ),
        )

    def slot1_valid(self) -> int:
        return int(sample_signal(
            self.dut.io_toMainPipe_bits_wayLookupInfo_1_valid).as_int()) & 1

    async def read_pair(self) -> tuple[WayLookupEntry, WayLookupEntry]:
        """Consume both output slots in one cycle (real two-fetch).

        The main pipe signals ``realTwoFetchValid`` together with ready when it
        takes two queued lookups at once; the way lookup must then advance its
        read pointer by two, not one.
        """
        self.control_driver.set(encode_control(real_two_fetch=1))
        self.read_ready_driver.set({"ready": 1})
        await ClockCycles(self.dut.clock, 1)
        first = self._slot_entry(0)
        second = self._slot_entry(1)
        self.read_ready_driver.set({"ready": 0})
        self.control_driver.set(encode_control())
        await ClockCycles(self.dut.clock, 1)
        self.model.step(deq=2)
        return first, second



    def occupancy(self) -> int:
        return self.model.occupancy()

    def tags(self) -> tuple[int, ...]:
        return tuple(self.model.tags)

    def expect_empty(self) -> None:
        self.checker.expect_empty(observed=self.rtl_empty(), context="status")
