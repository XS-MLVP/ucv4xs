"""Independent contract model for the InstrUncache top level.

With ``nMmioEntry == 1`` the top is the Entry plus:

* a 1:1 response arbiter (separately verified);
* D-channel source qualification: only the single client source 0 may complete
  the outstanding request;
* the WFI safety aggregation, which for one entry is the entry's own safety.

The model composes the contract-level EntryModel; it never replaces the real
Entry/Arbiter RTL in the DUT.  The top keeps the real generated modules and the
composition only supplies expected values.
"""

from __future__ import annotations

from dataclasses import dataclass

from suites.frontend.instr_uncache.testbenches.instr_uncache_entry.model import Inputs as EntryInputs
from suites.frontend.instr_uncache.testbenches.instr_uncache_entry.model import EntryModel
from suites.frontend.instr_uncache.testbenches.instr_uncache_entry.model import LEGAL_MAX_ADDR
from suites.frontend.instr_uncache.testbenches.instr_uncache_entry.model import StimulusError
from suites.frontend.instr_uncache.testbenches.instr_uncache_entry.model import _binary
from suites.frontend.instr_uncache.testbenches.instr_uncache_entry.model import _even_address


@dataclass(frozen=True)
class Inputs:
    reset: int = 0
    req_valid: int = 0
    req_addr: int = 0
    req_mem_back_mm: int = 0
    req_mem_page_nc: int = 0
    a_ready: int = 1
    d_valid: int = 0
    d_source: int = 0
    d_data: int = 0
    d_corrupt: int = 0
    d_denied: int = 0
    wfi_req: int = 0

    def __post_init__(self) -> None:
        for name in ("reset", "req_valid", "req_mem_back_mm", "req_mem_page_nc",
                     "a_ready", "d_valid", "d_source", "d_corrupt", "d_denied",
                     "wfi_req"):
            _binary(getattr(self, name), name)
        _even_address(self.req_addr, "req_addr")
        if not isinstance(self.d_data, int) or not 0 <= self.d_data < (1 << 64):
            raise StimulusError("d_data must be an unsigned 64-bit value")
        if self.d_denied and not self.d_corrupt:
            raise StimulusError("TileLink requires denied => corrupt on D")

    def entry_inputs(self) -> EntryInputs:
        return EntryInputs(
            reset=self.reset,
            req_valid=self.req_valid,
            req_addr=self.req_addr,
            req_mem_back_mm=self.req_mem_back_mm,
            req_mem_page_nc=self.req_mem_page_nc,
            acquire_ready=self.a_ready,
            # D ready is tied true and source 0 is the only client source.
            grant_valid=int(bool(self.d_valid) and self.d_source == 0),
            grant_data=self.d_data,
            grant_corrupt=self.d_corrupt,
            grant_denied=self.d_denied,
            wfi_req=self.wfi_req,
        )


@dataclass(frozen=True)
class Outputs:
    req_ready: int
    a_valid: int
    a_addr: int
    a_mem_page_nc: int
    a_mem_back_mm: int
    resp_valid: int
    resp_data: int
    resp_corrupt: int
    resp_denied: int
    resp_need_resend: int
    wfi_safe: int

    def __post_init__(self) -> None:
        for name in ("req_ready", "a_valid", "a_mem_page_nc", "a_mem_back_mm",
                     "resp_valid", "resp_corrupt", "resp_denied",
                     "resp_need_resend", "wfi_safe"):
            _binary(getattr(self, name), name)
        _even_address(self.a_addr, "a_addr", limit=1 << 48)
        if not isinstance(self.resp_data, int) or not 0 <= self.resp_data < (1 << 32):
            raise StimulusError("resp_data must be an unsigned 32-bit value")

    def as_dict(self) -> dict[str, int]:
        return {name: getattr(self, name) for name in self.__dataclass_fields__}


class TopModel:
    def __init__(self) -> None:
        self.entry = EntryModel()
        self.filtered_grants = 0
        self.source0_grants = 0

    @property
    def state(self) -> str:
        return self.entry.state

    @property
    def outstanding(self) -> int:
        return self.entry.outstanding

    def outputs(self, inputs: Inputs) -> Outputs:
        if not isinstance(inputs, Inputs):
            raise TypeError("top model requires protocol Inputs")
        entry = self.entry.outputs(inputs.entry_inputs())
        return Outputs(
            req_ready=entry.req_ready,
            a_valid=entry.acquire_valid,
            a_addr=entry.acquire_addr,
            a_mem_page_nc=entry.acquire_mem_page_nc,
            a_mem_back_mm=entry.acquire_mem_back_mm,
            resp_valid=entry.resp_valid,
            resp_data=entry.resp_data,
            resp_corrupt=entry.resp_corrupt,
            resp_denied=entry.resp_denied,
            resp_need_resend=entry.resp_need_resend,
            wfi_safe=entry.wfi_safe,
        )

    def tick(self, inputs: Inputs) -> None:
        if inputs.d_valid:
            if inputs.d_source == 0:
                self.source0_grants += 1
            else:
                self.filtered_grants += 1
        self.entry.tick(inputs.entry_inputs())

    def audit(self) -> None:
        self.entry.audit()

    def snapshot(self) -> dict[str, object]:
        return {**self.entry.snapshot(), "filtered_grants": self.filtered_grants,
                "source0_grants": self.source0_grants}


def reset_snapshot() -> Outputs:
    return Outputs(1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1)


TopInputs = Inputs
TopOutputs = Outputs
