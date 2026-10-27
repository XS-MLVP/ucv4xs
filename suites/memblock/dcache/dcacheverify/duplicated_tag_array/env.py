"""Port-level environment for DuplicatedTagArray.

Timing contract (calibrated on the generated RTL):

* a write driven before a rising edge commits at that edge and blocks reads
  during the same cycle (`io_read_3_ready` low);
* a read driven before a rising edge returns its 4-way codewords right after
  that edge (one-cycle SRAM latency);
* after reset deassertion the internal 256-set clear sweep takes 256 edges;
  reads are refused until the sweep completes.

Only public ports are touched. Every accepted read is compared with the model
before functional coverage is sampled.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from toffee import RisingEdge

from .coverage import DuplicatedTagArrayCoverage
from .model import SETS, WAYS, DuplicatedTagArrayModel

SWEEP_CYCLES = 256


@dataclass(frozen=True)
class Write:
    index: int
    way_en: int
    tag: int


class DuplicatedTagArrayEnv:
    def __init__(self, dut, coverage: DuplicatedTagArrayCoverage | None = None) -> None:
        self.dut = dut
        self.coverage = coverage
        self.model = DuplicatedTagArrayModel()
        self.read_valid = [getattr(dut, f"io_read_{port}_valid") for port in range(4)]
        self.read_idx = [getattr(dut, f"io_read_{port}_bits_idx") for port in range(4)]
        self.read_ready = dut.io_read_3_ready
        self.resp = [[getattr(dut, f"io_resp_{port}_{way}") for way in range(WAYS)]
                     for port in range(4)]
        self.write_valid = dut.io_write_valid
        self.write_idx = dut.io_write_bits_idx
        self.write_way = dut.io_write_bits_way_en
        self.write_tag = dut.io_write_bits_tag
        self.mbist = {
            "array": dut.boreChildrenBd_bore_array,
            "all": dut.boreChildrenBd_bore_all,
            "req": dut.boreChildrenBd_bore_req,
            "ack": dut.boreChildrenBd_bore_ack,
            "writeen": dut.boreChildrenBd_bore_writeen,
            "be": dut.boreChildrenBd_bore_be,
            "addr": dut.boreChildrenBd_bore_addr,
            "indata": dut.boreChildrenBd_bore_indata,
            "readen": dut.boreChildrenBd_bore_readen,
            "addr_rd": dut.boreChildrenBd_bore_addr_rd,
            "outdata": dut.boreChildrenBd_bore_outdata,
        }
        self.checked_reads = 0
        self.blocked_reads = 0

    # ---------------------------------------------------------------- helpers
    def _val(self, signal) -> int:
        return int(signal.value)

    def resp_words(self, port: int) -> list[int]:
        return [self._val(signal) for signal in self.resp[port]]

    def _idle(self) -> None:
        for signal in self.read_valid:
            signal.Set(0)
        self.write_valid.Set(0)

    def _drive_reads(self, reads: Iterable[tuple[int, int]]) -> None:
        request = {port: idx for port, idx in reads}
        for port in range(4):
            signal = self.read_valid[port]
            if port in request:
                signal.Set(1)
                self.read_idx[port].Set(request[port])
            else:
                signal.Set(0)

    def _drive_write(self, write: Write | None) -> None:
        if write is None:
            self.write_valid.Set(0)
            return
        self.write_valid.Set(1)
        self.write_idx.Set(write.index)
        self.write_way.Set(write.way_en)
        self.write_tag.Set(write.tag)

    async def edge(self) -> None:
        await RisingEdge(self.dut.clock)

    # ---------------------------------------------------------------- reset
    async def reset(self) -> None:
        """Full reset including the 256-cycle clear sweep."""
        self._idle()
        self.dut.reset.Set(1)
        await self.edge()
        await self.edge()
        self.dut.reset.Set(0)
        for _ in range(SWEEP_CYCLES + 1):
            await self.edge()
        # Two idle edges let the single-port SRAM see RW0_en low again.
        await self.edge()
        await self.edge()
        self.model.reset()
        self.checked_reads = 0
        if self.coverage is not None:
            self.coverage.sample_reset("after_sweep")

    async def observe_sweep(self) -> dict:
        """Release reset and probe the clear sweep before it completes."""
        self._idle()
        self.dut.reset.Set(1)
        await self.edge()
        await self.edge()
        self.dut.reset.Set(0)
        ready_during = []
        for index in range(8):
            self._drive_reads([(0, index)])
            await self.edge()
            ready_during.append(self._val(self.read_ready))
        self._idle()
        for _ in range(SWEEP_CYCLES + 1 - 8):
            await self.edge()
        self.model.reset()
        if self.coverage is not None:
            self.coverage.sample_reset("sweep_in_progress")
        return {
            "ready_during_sweep": ready_during,
            "ready_after_sweep": self._val(self.read_ready),
        }

    # ---------------------------------------------------------------- access
    async def write(self, index: int, way_en: int, tag: int, *,
                    target: str = "new_set", order: str = "single") -> None:
        self._drive_reads(())
        self._drive_write(Write(index, way_en, tag))
        await self.edge()
        self.write_valid.Set(0)
        self.model.write(index, way_en, tag)
        if self.coverage is not None:
            self.coverage.sample_write(index, way_en, tag, target)
            self.coverage.sample_conflict("write_only")

    async def read(self, port: int, index: int, *, order: str = "single",
                   check: bool = True) -> list[int]:
        self._drive_write(None)
        self._drive_reads([(port, index)])
        await self.edge()
        ready = self._val(self.read_ready)
        words = self.resp_words(port)
        self._drive_reads(())
        if not ready:
            raise AssertionError(
                f"read port {port} set {index} was not accepted (ready={ready})")
        if check:
            expected = self.model.read(index)
            if words != expected:
                raise AssertionError(
                    f"read port {port} set {index}: expected "
                    f"{[hex(w) for w in expected]}, got {[hex(w) for w in words]}")
        self.checked_reads += 1
        if self.coverage is not None:
            self.coverage.sample_read(port, index, order)
            self.coverage.sample_conflict("read_only")
        return words

    async def read_all_ports(self, index: int, *, order: str = "single") -> None:
        expected = None
        for port in range(4):
            words = await self.read(port, index, order=order)
            if expected is None:
                expected = words
            elif words != expected:
                raise AssertionError(
                    f"tag duplicates disagree on set {index}: port {port} "
                    f"{[hex(w) for w in words]} != {[hex(w) for w in expected]}")

    async def denied_read_during_write(self, port: int, read_index: int,
                                       write: Write, relation: str | None = None) -> None:
        """Assert read and write in the same cycle; the read must be refused."""
        self._drive_write(write)
        self._drive_reads([(port, read_index)])
        await self.edge()
        ready = self._val(self.read_ready)
        self._drive_reads(())
        self.write_valid.Set(0)
        if ready:
            raise AssertionError(
                f"read port {port} was accepted while a write occupied the port")
        self.model.write(write.index, write.way_en, write.tag)
        self.blocked_reads += 1
        if self.coverage is not None:
            relation = relation or ("same_set" if read_index == write.index
                                    else "different_set")
            self.coverage.sample_conflict("read_blocked_by_write", relation)
            self.coverage.sample_write(write.index, write.way_en, write.tag,
                                       "same_set_rewrite" if relation == "same_set"
                                       else "new_set")

    async def read_after_write(self, port: int, index: int) -> list[int]:
        words = await self.read(port, index, order="after_write")
        if self.coverage is not None:
            self.coverage.sample_conflict("read_after_write")
        return words

    # ---------------------------------------------------------------- mbist
    def _mbist_idle(self) -> None:
        self.mbist["req"].Set(0)
        self.mbist["writeen"].Set(0)
        self.mbist["readen"].Set(0)
        self.mbist["all"].Set(0)

    async def mbist_write(self, array: int, addr: int, data: int,
                          be: int = 0b11, all_sram: bool = False) -> int:
        self.mbist["array"].Set(array)
        self.mbist["all"].Set(1 if all_sram else 0)
        self.mbist["be"].Set(be)
        self.mbist["addr"].Set(addr)
        self.mbist["addr_rd"].Set(addr)
        self.mbist["indata"].Set(data)
        self.mbist["writeen"].Set(1)
        self.mbist["req"].Set(1)
        await self.edge()
        ack = self._val(self.mbist["ack"])
        self.mbist["req"].Set(0)
        self.mbist["writeen"].Set(0)
        self.mbist["all"].Set(0)
        await self.edge()
        if self.coverage is not None:
            self.coverage.sample_mbist(array, "write", data)
        return ack

    async def mbist_read(self, array: int, addr_rd: int,
                         all_sram: bool = False) -> int:
        self.mbist["array"].Set(array)
        self.mbist["all"].Set(1 if all_sram else 0)
        self.mbist["addr_rd"].Set(addr_rd)
        self.mbist["readen"].Set(1)
        self.mbist["req"].Set(1)
        await self.edge()
        ack = self._val(self.mbist["ack"])
        self.mbist["req"].Set(0)
        self.mbist["readen"].Set(0)
        self.mbist["all"].Set(0)
        # ack cycle -> SRAM read edge -> rdataReg edge (MBIST output register)
        await self.edge()
        await self.edge()
        data = self._val(self.mbist["outdata"])
        if self.coverage is not None:
            self.coverage.sample_mbist(array, "read", data)
        if not ack:
            raise AssertionError(f"MBIST read array {array:#x} was not acknowledged")
        return data

    async def idle(self, cycles: int = 2) -> None:
        self._idle()
        for _ in range(cycles):
            await self.edge()

    async def read_every_set(self, port: int = 0) -> None:
        """Read all 256 sets back-to-back, checking the model each cycle."""
        order = "back_to_back_diff_set"
        for index in range(SETS):
            self._drive_write(None)
            self._drive_reads([(port, index)])
            await self.edge()
            words = self.resp_words(port)
            expected = self.model.read(index)
            if words != expected:
                raise AssertionError(
                    f"bulk read set {index}: expected {[hex(w) for w in expected]}, "
                    f"got {[hex(w) for w in words]}")
            self.checked_reads += 1
            if self.coverage is not None:
                self.coverage.sample_read(port, index, order)
        self._drive_reads(())
