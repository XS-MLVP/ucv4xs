"""Port-level environment for CtrlUnit.

Calibrated timing on the generated RTL:

* A-channel handshake at a rising edge, one outstanding transaction;
* `d_valid` is high in the following cycle; a write commits at the D handshake
  edge, a read returns its data in the `d_valid` cycle;
* pseudo-error requests are captured into a one-stage pipeline at the edge
  after the control write commits, so `io_pseudoError_*_valid` appears one
  cycle later (plus `delay` cycles when `ede=1`);
* a non-persistent request clears `ese` at capture time, even if the consumer
  never accepts it.
"""
from __future__ import annotations

from dataclasses import dataclass

from toffee import RisingEdge

from .coverage import CtrlUnitCoverage

BANKS = 32
TAG_MASK_BITS = 36
SOURCE = 5
SIZE = 3


@dataclass(frozen=True)
class CtrlFields:
    ese: bool = False
    persist: bool = False
    ede: bool = False
    comp: int = 0
    bank: int = 0

    def value(self) -> int:
        return ((self.ese & 1) | (self.persist << 1) | (self.ede << 2)
                | (self.comp << 3) | (self.bank << 4))

    @classmethod
    def from_value(cls, value: int) -> "CtrlFields":
        return cls(ese=bool(value & 1), persist=bool((value >> 1) & 1),
                   ede=bool((value >> 2) & 1), comp=(value >> 3) & 1,
                   bank=(value >> 4) & ((1 << BANKS) - 1))


class CtrlUnitEnv:
    def __init__(self, dut, coverage: CtrlUnitCoverage | None = None) -> None:
        self.dut = dut
        self.coverage = coverage
        self.a = {
            "valid": dut.auto_in_a_valid,
            "opcode": dut.auto_in_a_bits_opcode,
            "size": dut.auto_in_a_bits_size,
            "source": dut.auto_in_a_bits_source,
            "addr": dut.auto_in_a_bits_address,
            "mask": dut.auto_in_a_bits_mask,
            "data": dut.auto_in_a_bits_data,
        }
        self.d = {
            "ready": dut.auto_in_d_ready,
            "valid": dut.auto_in_d_valid,
            "opcode": dut.auto_in_d_bits_opcode,
            "size": dut.auto_in_d_bits_size,
            "source": dut.auto_in_d_bits_source,
            "data": dut.auto_in_d_bits_data,
        }
        self.a_ready = dut.auto_in_a_ready
        self.pe_ready = [dut.io_pseudoError_0_ready, dut.io_pseudoError_1_ready]
        self.pe0 = {
            "valid": dut.io_pseudoError_0_valid,
            "bank0_valid": dut.io_pseudoError_0_bits_0_valid,
            "mask": dut.io_pseudoError_0_bits_0_mask,
        }
        self.pe1 = {
            "valid": dut.io_pseudoError_1_valid,
            "bank_valid": [getattr(dut, f"io_pseudoError_1_bits_{bank}_valid")
                           for bank in range(BANKS)],
            "mask": [getattr(dut, f"io_pseudoError_1_bits_{bank}_mask")
                     for bank in range(BANKS)],
        }
        self.reads = 0
        self.writes = 0

    # ---------------------------------------------------------------- helpers
    def _val(self, signal) -> int:
        return int(signal.value)

    def _idle(self) -> None:
        self.a["valid"].Set(0)
        self.d["ready"].Set(0)
        for signal in self.pe_ready:
            signal.Set(0)

    async def edge(self) -> None:
        await RisingEdge(self.dut.clock)

    def set_pe_ready(self, component: int, ready: bool) -> None:
        self.pe_ready[component].Set(1 if ready else 0)

    def pe_tag(self) -> tuple[int, int, int]:
        return (self._val(self.pe0["valid"]), self._val(self.pe0["bank0_valid"]),
                self._val(self.pe0["mask"]))

    def pe_data(self) -> list[tuple[int, int]]:
        return [(self._val(valid), self._val(mask))
                for valid, mask in zip(self.pe1["bank_valid"], self.pe1["mask"])]

    # ---------------------------------------------------------------- reset
    async def reset(self) -> None:
        self._idle()
        self.dut.reset.Set(1)
        await self.edge()
        await self.edge()
        self.dut.reset.Set(0)
        await self.edge()
        await self.edge()

    # ---------------------------------------------------------------- TL access
    def _drive(self, addr: int, data: int, mask: int, opcode: int,
               source: int = SOURCE) -> None:
        self.a["valid"].Set(1)
        self.a["opcode"].Set(opcode)
        self.a["size"].Set(SIZE)
        self.a["source"].Set(source)
        self.a["addr"].Set(addr)
        self.a["mask"].Set(mask)
        self.a["data"].Set(data)

    def _check_d(self, opcode: int, what: str, source: int = SOURCE) -> int:
        if not self._val(self.d["valid"]):
            raise AssertionError(f"{what}: d_valid not asserted after A handshake")
        got_opcode = self._val(self.d["opcode"])
        if got_opcode != opcode:
            raise AssertionError(f"{what}: d opcode {got_opcode} != {opcode}")
        if self._val(self.d["source"]) != source:
            raise AssertionError(f"{what}: d source {self._val(self.d['source'])} != {source}")
        if self._val(self.d["size"]) != SIZE:
            raise AssertionError(f"{what}: d size not echoed")
        return self._val(self.d["data"])

    async def send_write(self, index: int, data: int, mask: int = 0xFF,
                         addr: int | None = None, source: int = SOURCE) -> None:
        if not 0 <= index < 11:
            raise ValueError(f"register index out of range: {index}")
        address = index * 8 if addr is None else addr
        self._drive(address, data, mask, opcode=0, source=source)
        self.d["ready"].Set(1)
        await self.edge()
        self._check_d(0, f"write index {index}", source)
        accepted = self._val(self.dut.auto_in_a_ready)
        self.a["valid"].Set(0)
        # The queue is full now: a new A request must not be accepted.
        if accepted:
            raise AssertionError("A channel still accepts while D response is outstanding")

    async def complete_d(self) -> None:
        self.d["ready"].Set(1)
        await self.edge()
        if self._val(self.d["valid"]):
            raise AssertionError("D response did not complete on handshake")
        self.d["ready"].Set(0)

    async def write(self, index: int, data: int, mask: int = 0xFF, *,
                    handshake: str = "immediate", addr: int | None = None,
                    source: int = SOURCE) -> None:
        await self.send_write(index, data, mask, addr=addr, source=source)
        if handshake == "immediate":
            await self.complete_d()
        self.writes += 1
        if self.coverage is not None:
            self.coverage.sample_access(
                "write", index, "full" if mask == 0xFF else "partial",
                "immediate" if handshake == "immediate" else "held_then_released")
            target = {0: "ctrl", 1: "delay", 2: "tag_mask"}.get(index, "data_mask")
            self.coverage.sample_regs(target, "match" if mask == 0xFF else "masked_hold")

    async def read(self, index: int, *, handshake: str = "immediate",
                   addr: int | None = None, source: int = SOURCE) -> int:
        if not 0 <= index < 11:
            raise ValueError(f"register index out of range: {index}")
        address = index * 8 if addr is None else addr
        self._drive(address, 0, 0, opcode=4, source=source)
        self.d["ready"].Set(1)
        await self.edge()
        data = self._check_d(1, f"read index {index}", source)
        self.a["valid"].Set(0)
        await self.edge()
        if self._val(self.d["valid"]):
            raise AssertionError("read D response did not complete")
        self.d["ready"].Set(0)
        self.reads += 1
        if self.coverage is not None:
            self.coverage.sample_access("read", index, "full", "immediate")
        return data

    async def read_held(self, index: int, *, source: int = SOURCE) -> int:
        """Read with d_ready low; the response data must stay stable."""
        self._drive(index * 8, 0, 0, opcode=4, source=source)
        self.d["ready"].Set(0)
        await self.edge()
        data = self._check_d(1, f"held read index {index}", source)
        self.a["valid"].Set(0)
        for _ in range(3):
            await self.edge()
            if self._val(self.d["data"]) != data:
                raise AssertionError("read data changed while D was backpressured")
            if self._val(self.a_ready):
                raise AssertionError("A channel ready while D response is pending")
        self.d["ready"].Set(1)
        await self.edge()
        if self._val(self.d["valid"]):
            raise AssertionError("held read did not complete")
        self.d["ready"].Set(0)
        self.reads += 1
        if self.coverage is not None:
            self.coverage.sample_access("read", index, "full", "held_then_released")
        return data

    async def try_write_while_full(self, index: int, data: int) -> bool:
        """Return whether A was accepted while a previous D response is pending."""
        self.d["ready"].Set(0)
        self._drive(index * 8, data, 0xFF, opcode=0)
        await self.edge()
        accepted = bool(self._val(self.dut.auto_in_a_ready))
        self.a["valid"].Set(0)
        return accepted

    # ---------------------------------------------------------------- inject
    async def program_ctrl(self, fields: CtrlFields) -> None:
        await self.write(0, fields.value())

    async def program_delay(self, delay: int) -> None:
        await self.write(1, delay)

    async def program_tag_mask(self, mask: int) -> None:
        await self.write(2, mask & ((1 << 40) - 1))

    async def program_data_mask(self, group: int, value: int) -> None:
        await self.write(3 + group, value)

    async def quiesce(self) -> None:
        """Consume any pending request and clear the control register."""
        self.set_pe_ready(0, True)
        self.set_pe_ready(1, True)
        await self.write(0, 0)
        for _ in range(4):
            await self.edge()
        self.set_pe_ready(0, False)
        self.set_pe_ready(1, False)

    async def drain(self, cycles: int = 16) -> None:
        self.set_pe_ready(0, True)
        self.set_pe_ready(1, True)
        for _ in range(cycles):
            await self.edge()
        self.set_pe_ready(0, False)
        self.set_pe_ready(1, False)

    async def wait_tag_valid(self, limit: int = 32) -> int | None:
        for cycle in range(limit):
            if self._val(self.pe0["valid"]):
                return cycle
            await self.edge()
        return None
