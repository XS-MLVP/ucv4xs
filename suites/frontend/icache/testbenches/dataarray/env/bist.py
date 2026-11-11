"""Drive the MBIST child interface of an SRAM-backed DUT.

The cache arrays expose the memory-BIST pipeline at the chip boundary so each
SRAM can be tested independently of the functional pipeline.  A BIST command is
a level interface: the command is registered by the pipeline, the addressed SRAM
takes the read/write on the acknowledge cycle, and the ack is reported one cycle
later.  The helper drives exactly one command at a time so a test can associate
each acknowledge with one array.

This is test-access semantics, not functional cache behaviour: it is used to
prove that every SRAM instance is reachable from the boundary.
"""

from __future__ import annotations

from typing import Any
from typing import Awaitable
from typing import Callable

from toffee.signals import sample_signal


# Input leaves of the MBIST child interface.  ``addr`` is the write address and
# ``addr_rd`` the read address; both are present on the generated DUT even when
# the schema omits one of them.
INPUTS = ("req", "all", "writeen", "be", "array", "addr", "indata",
          "readen", "addr_rd")


class BistBank:
    """The MBIST command port of one array instance (and its sub-arrays)."""

    def __init__(self, dut: Any, children: tuple[str, ...] = ("",)) -> None:
        self.dut = dut
        self.children = tuple(children)
        self.inputs: dict[str, dict[str, Any]] = {}
        self.outputs: dict[str, dict[str, Any]] = {}
        for child in self.children:
            prefix = "boreChildrenBd_bore" + (f"_{child}" if child else "")
            self.inputs[child] = {
                leaf: getattr(dut, f"{prefix}_{leaf}") for leaf in INPUTS
            }
            self.outputs[child] = {
                "ack": getattr(dut, f"{prefix}_ack"),
                "outdata": getattr(dut, f"{prefix}_outdata"),
            }

    def idle(self) -> None:
        for child in self.children:
            for signal in self.inputs[child].values():
                signal.Set(0)
                signal.AsRiseWrite()

    def ack(self, child: str) -> int:
        return int(sample_signal(self.outputs[child]["ack"]).as_int()) & 1

    def outdata(self, child: str) -> int:
        return int(sample_signal(self.outputs[child]["outdata"]).as_int())

    async def command(
        self,
        edge: Callable[[], Awaitable[None]],
        child: str,
        *,
        array: int = 0,
        all_arrays: int = 0,
        readen: int = 1,
        writeen: int = 0,
        be: int = 0,
        addr: int = 0,
        addr_rd: int = 0,
        indata: int = 0,
        hold: int = 2,
        observe: int = 4,
    ) -> tuple[int, int]:
        """Issue one BIST command and return (ack, outdata)."""
        signals = self.inputs[child]
        values = {
            "req": 1,
            "all": all_arrays,
            "writeen": writeen,
            "be": be,
            "array": array,
            "addr": addr,
            "indata": indata,
            "readen": readen,
            "addr_rd": addr_rd,
        }
        for leaf, value in values.items():
            signals[leaf].Set(value)
        # The command reaches the pipeline on the next edge; the acknowledge
        # (``req`` registered) is visible on the edge after that.
        for _ in range(hold):
            await edge()
        ack = self.ack(child)
        for signal in signals.values():
            signal.Set(0)
        # A BIST read is registered inside the macro: the data appears two
        # edges after the acknowledge, so sample it after a short settle.
        for _ in range(observe):
            await edge()
        outdata = self.outdata(child)
        return ack, outdata
