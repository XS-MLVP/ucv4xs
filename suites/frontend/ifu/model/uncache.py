"""Reference model for IfuUncacheUnit.

Intent: an instruction fetch that misses the cache but targets a non-cacheable
or MMIO page must leave the cache pipeline and issue a single uncached read.
Before issuing, an access whose semantics are not idempotent (MMIO, or a
PBMT=IO page) must wait until older instructions have drained; an ordinary
non-cacheable main-memory access may issue immediately.  The request is held
until the bus accepts it and is stalled, not dropped, while the IFU cannot
accept a response.  Completion latches the read data and translates the bus
status into an instruction exception, then produces exactly one response pulse
and returns to idle.  A flush aborts any phase and a late bus response is
discarded.

The model is a four-phase state machine at the architectural level
(accept -> maybe wait -> send -> receive), with explicit registers for the
captured request and response.
"""

from __future__ import annotations

from dataclasses import dataclass

PMA = 0
NC = 1
IO = 2
PBMT_RSVD = 3

EXC_NONE = 0
EXC_AF = 3
EXC_HWE = 5

IDLE = "idle"
WAIT_COMMIT = "wait_commit"
SEND = "send"
WAIT_RESP = "wait_response"


@dataclass
class Inputs:
    flush: int = 0
    req_valid: int = 0
    req_paddr: int = 0
    req_is_mmio: int = 0
    req_pbmt: int = 0
    is_first_instr: int = 0
    ifu_stall: int = 0
    empty_after: int = 0
    to_ready: int = 1
    from_valid: int = 0
    from_data: int = 0
    from_corrupt: int = 0
    from_denied: int = 0
    from_need_resend: int = 0


@dataclass
class Outputs:
    req_ready: int
    resp_valid: int
    resp_data: int
    resp_exception: int
    resp_need_resend: int
    to_valid: int
    to_paddr: int
    to_mem_back_mm: int
    to_mem_page_nc: int


class UncacheModel:
    def __init__(self) -> None:
        self.phase = IDLE
        self.paddr = 0
        self.is_mmio = 0
        self.pbmt = 0
        self.finish = 0
        self.data = 0
        self.exception = EXC_NONE
        self.need_resend = 0
        # Counters make white-box shortcuts visible: a request may be
        # accepted only once and completion only once per accepted request.
        self.accepted = 0
        self.completed = 0
        self.aborted = 0

    def outputs(self, inputs: Inputs) -> Outputs:
        send = self.phase == SEND
        return Outputs(
            req_ready=int(self.phase == IDLE),
            resp_valid=self.finish,
            resp_data=self.data,
            resp_exception=self.exception,
            resp_need_resend=self.need_resend,
            to_valid=int(send and not inputs.ifu_stall),
            to_paddr=self.paddr,
            to_mem_back_mm=int(not self.is_mmio),
            to_mem_page_nc=int(self.pbmt == NC),
        )

    @staticmethod
    def decode_exception(corrupt: int, denied: int) -> int:
        if denied:
            return EXC_AF
        if corrupt:
            return EXC_HWE
        return EXC_NONE

    def tick(self, inputs: Inputs) -> None:
        if inputs.flush:
            if self.phase != IDLE:
                # Accepted but not yet completed: the flush ends the obligation.
                self.aborted += 1
            self.phase = IDLE
            self.finish = 0
            self.data = 0
            self.exception = EXC_NONE
            self.need_resend = 0
            self.paddr = 0
            return
        # The completion pulse lasts one cycle; a new phase transition can
        # only set it again at a later response.
        self.finish = 0
        if self.phase == IDLE:
            if inputs.req_valid:
                self.accepted += 1
                self.paddr = inputs.req_paddr
                self.is_mmio = inputs.req_is_mmio
                self.pbmt = inputs.req_pbmt
                waits = bool(inputs.req_is_mmio or inputs.req_pbmt == IO)
                self.phase = WAIT_COMMIT if waits else SEND
        elif self.phase == WAIT_COMMIT:
            if inputs.is_first_instr or inputs.empty_after:
                self.phase = SEND
        elif self.phase == SEND:
            if not inputs.ifu_stall and inputs.to_ready:
                self.phase = WAIT_RESP
        elif self.phase == WAIT_RESP:
            if inputs.from_valid:
                self.completed += 1
                self.data = inputs.from_data
                self.exception = self.decode_exception(inputs.from_corrupt, inputs.from_denied)
                self.need_resend = inputs.from_need_resend
                self.finish = 1
                self.phase = IDLE
