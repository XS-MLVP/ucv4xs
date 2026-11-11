"""Independent contract models for the InstrUncache unit.

The models are written from the Scala/ISA/TileLink obligations, not from the
generated RTL assignments.  They also encode the few constants that the
generated closure proved at the DUT boundary:

* response ready, D ready and grant ready are tied true by the consumers and
  are therefore absent from the extracted ports (``InstrUncacheImp.scala:88``
  and ``IfuUncacheUnit.scala:133``);
* ``flush`` is tied false by ``FrontendInlinedImp`` and is pruned with the
  ``needFlush`` register (``Frontend.scala:266``);
* with ``nMmioEntry == 1`` the request id and the response arbiter select are
  constant zero, so the entry has no ``io_id`` and the TL source is one bit.

Those constants are stated once here and audited by the port bindings; they
are not copied from RTL branches into the expected data path.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

MMIO_BUS_BYTES = 8
MMIO_BUS_BITS = MMIO_BUS_BYTES * 8
PAGE_BYTES = 4096
PAGE_OFFSET_BITS = 12
PADDR_BITS = 48
#: The generated A address is Cat(addr[46:3], 3'b0); bit 47 is fixed zero.
LEGAL_MAX_ADDR = 1 << 47

IDLE = "idle"
REFILL_REQ = "refill_req"
REFILL_RESP = "refill_resp"
SEND_RESP = "send_resp"
STATE_NAMES = (IDLE, REFILL_REQ, REFILL_RESP, SEND_RESP)


class StimulusError(ValueError):
    """The environment supplied a request/response the protocol forbids."""


def _binary(value: int, name: str) -> int:
    if not isinstance(value, int) or value not in (0, 1):
        raise StimulusError(f"{name} must be 0 or 1")
    return value


def _even_address(value: int, name: str, *, limit: int = LEGAL_MAX_ADDR) -> int:
    if not isinstance(value, int) or value < 0 or value >= limit:
        raise StimulusError(f"{name} must be an address below {limit:#x}")
    if value & 1:
        raise StimulusError(f"{name} must be 2-byte aligned")
    return value


def cross_bus_boundary(addr: int) -> int:
    """A 4B window at addr(2,1)=11 crosses the 8B bus beat."""
    return int(((addr >> 1) & 0b11) == 0b11)


def cross_page_boundary(addr: int) -> int:
    """A 4B window at addr(11,1)=all ones crosses the 4KiB page."""
    return int(((addr >> 1) & 0x7FF) == 0x7FF)


def is_rvc(data: int) -> int:
    """RISC-V: low bits != 11 selects a 16-bit instruction."""
    return int((data & 0b11) != 0b11)


def aligned_bus_address(addr: int, resending: int = 0) -> int:
    """8B-aligned Get address; the second beat is the next 8B line."""
    _even_address(addr, "addr")
    _binary(resending, "resending")
    # The extracted A address is 48 bits with bit 47 fixed zero because the
    # Scala Cat() produces only 47 bits (addr[46:3] << 3).  Legal DefaultConfig
    # physical addresses are below 2**43, so this is not reachable legally.
    return ((addr & ~(MMIO_BUS_BYTES - 1)) + resending * MMIO_BUS_BYTES) & ((1 << 47) - 1)


def fetch_window(addr: int, beat: int) -> int:
    """The 4B instruction window selected by addr(2,1) from one 8B beat."""
    _even_address(addr, "addr")
    if not isinstance(beat, int) or not 0 <= beat < (1 << MMIO_BUS_BITS):
        raise StimulusError("beat must be an unsigned 64-bit value")
    selector = (addr >> 1) & 0b11
    return (beat >> (16 * selector)) & 0xFFFF_FFFF


def refill_needs_resend(addr: int, beat: int, *, corrupt: int,
                        resending: int) -> bool:
    """Second beat is required only for a clean non-RVC 4B fetch crossing 8B."""
    _binary(corrupt, "corrupt")
    _binary(resending, "resending")
    return bool(cross_bus_boundary(addr)
                and not cross_page_boundary(addr)
                and not corrupt
                and not is_rvc(fetch_window(addr, beat))
                and not resending)


def response_needs_resend(addr: int, *, corrupt: int, resp_data: int) -> bool:
    """The completed 4B window crosses a page and is a clean 32-bit fetch."""
    _binary(corrupt, "corrupt")
    if not isinstance(resp_data, int) or not 0 <= resp_data < (1 << 32):
        raise StimulusError("resp_data must be an unsigned 32-bit value")
    return bool(cross_page_boundary(addr) and not corrupt and not is_rvc(resp_data))


@dataclass(frozen=True)
class Inputs:
    """One cycle of entry stimulus.  Reset is asynchronous in the DUT."""

    reset: int = 0
    req_valid: int = 0
    req_addr: int = 0
    req_mem_back_mm: int = 0
    req_mem_page_nc: int = 0
    acquire_ready: int = 1
    grant_valid: int = 0
    grant_data: int = 0
    grant_corrupt: int = 0
    grant_denied: int = 0
    wfi_req: int = 0

    def __post_init__(self) -> None:
        for name in ("reset", "req_valid", "req_mem_back_mm", "req_mem_page_nc",
                     "acquire_ready", "grant_valid", "grant_corrupt", "grant_denied",
                     "wfi_req"):
            _binary(getattr(self, name), name)
        _even_address(self.req_addr, "req_addr")
        if not isinstance(self.grant_data, int) or not 0 <= self.grant_data < (1 << MMIO_BUS_BITS):
            raise StimulusError("grant_data must be an unsigned 64-bit value")
        if self.grant_denied and not self.grant_corrupt:
            raise StimulusError("TileLink requires denied => corrupt on D")


@dataclass(frozen=True)
class Outputs:
    req_ready: int
    resp_valid: int
    resp_data: int
    resp_corrupt: int
    resp_denied: int
    resp_need_resend: int
    acquire_valid: int
    acquire_addr: int
    acquire_mem_page_nc: int
    acquire_mem_back_mm: int
    wfi_safe: int

    def __post_init__(self) -> None:
        for name in ("req_ready", "resp_valid", "resp_corrupt", "resp_denied",
                     "resp_need_resend", "acquire_valid", "acquire_mem_page_nc",
                     "acquire_mem_back_mm", "wfi_safe"):
            _binary(getattr(self, name), name)
        if not isinstance(self.resp_data, int) or not 0 <= self.resp_data < (1 << 32):
            raise StimulusError("resp_data must be an unsigned 32-bit value")
        _even_address(self.acquire_addr, "acquire_addr", limit=1 << 48)

    def as_dict(self) -> dict[str, int]:
        return {name: getattr(self, name) for name in self.__dataclass_fields__}


class EntryModel:
    """Four-state MMIO fetch obligation: Invalid/RefillReq/RefillResp/SendResp."""

    def __init__(self) -> None:
        self.state = IDLE
        self._req_addr = 0
        self._req_mem_back_mm = 0
        self._req_mem_page_nc = 0
        self.resending = 0
        self._resp_low = 0
        self._resp_high = 0
        self.resp_corrupt = 0
        self.resp_denied = 0
        self.accepted = 0
        self.completed = 0
        self.resends = 0
        self.aborted = 0

    # -- state and obligations ---------------------------------------------
    @property
    def outstanding(self) -> int:
        return int(self.state != IDLE)

    @property
    def req_addr(self) -> int:
        return self._req_addr

    def outputs(self, inputs: Inputs) -> Outputs:
        if not isinstance(inputs, Inputs):
            raise TypeError("entry model requires protocol Inputs")
        resp_valid = int(self.state == SEND_RESP)
        acquire_valid = int(self.state == REFILL_REQ and not inputs.wfi_req)
        low = self._resp_low
        return Outputs(
            req_ready=int(self.state == IDLE),
            resp_valid=resp_valid,
            resp_data=((self._resp_high & 0xFFFF) << 16) | (low & 0xFFFF),
            resp_corrupt=self.resp_corrupt,
            resp_denied=self.resp_denied,
            resp_need_resend=int(resp_valid
                                 and cross_page_boundary(self._req_addr)
                                 and not self.resp_corrupt
                                 and not is_rvc(low)),
            acquire_valid=acquire_valid,
            acquire_addr=aligned_bus_address(self._req_addr, self.resending),
            acquire_mem_page_nc=self._req_mem_page_nc,
            acquire_mem_back_mm=self._req_mem_back_mm,
            wfi_safe=int(self.state != REFILL_RESP),
        )

    def _refill(self, inputs: Inputs) -> None:
        self.resp_corrupt = inputs.grant_corrupt
        self.resp_denied = inputs.grant_denied
        window = fetch_window(self._req_addr, inputs.grant_data)
        need = refill_needs_resend(self._req_addr, inputs.grant_data,
                                   corrupt=inputs.grant_corrupt,
                                   resending=self.resending)
        if self.resending:
            # The second beat contributes only the upper 16-bit half; the low
            # half was captured from the previous beat.
            self._resp_high = inputs.grant_data & 0xFFFF
        else:
            self._resp_low = window & 0xFFFF
            self._resp_high = (window >> 16) & 0xFFFF
        self.resending = int(need)
        if need:
            self.resends += 1
            self.state = REFILL_REQ
        else:
            self.state = SEND_RESP

    def tick(self, inputs: Inputs) -> None:
        if not isinstance(inputs, Inputs):
            raise TypeError("entry model requires protocol Inputs")
        if inputs.reset:
            if self.state != IDLE:
                self.aborted += 1
            self.state = IDLE
            self._req_addr = 0
            self._req_mem_back_mm = 0
            self._req_mem_page_nc = 0
            self.resending = 0
            self._resp_low = 0
            self._resp_high = 0
            self.resp_corrupt = 0
            self.resp_denied = 0
            self.accepted = 0
            self.completed = 0
            self.resends = 0
            return
        before = self.outputs(inputs)
        if self.state == IDLE:
            if inputs.req_valid:
                self._req_addr = inputs.req_addr
                self._req_mem_back_mm = inputs.req_mem_back_mm
                self._req_mem_page_nc = inputs.req_mem_page_nc
                self.accepted += 1
                self.state = REFILL_REQ
        elif self.state == REFILL_REQ:
            if before.acquire_valid and inputs.acquire_ready:
                self.state = REFILL_RESP
        elif self.state == REFILL_RESP:
            if inputs.grant_valid:
                self._refill(inputs)
        elif self.state == SEND_RESP:
            # resp.ready is the pruned constant true in this closure.
            self.completed += 1
            self.state = IDLE
        else:  # pragma: no cover - unreachable by construction
            raise AssertionError(f"entry model entered unknown state {self.state!r}")

    # -- completion accounting ---------------------------------------------
    def audit(self) -> None:
        expected_outstanding = 0 if self.state == IDLE else 1
        if self.accepted - self.completed != expected_outstanding:
            raise AssertionError(
                f"entry model accounting: accepted={self.accepted} completed={self.completed} "
                f"state={self.state}")
        if self.resends > self.accepted:
            raise AssertionError("entry model counted more resends than requests")

    def snapshot(self) -> dict[str, object]:
        return {
            "state": self.state,
            "req_addr": self._req_addr,
            "resending": self.resending,
            "resp_data": ((self._resp_high & 0xFFFF) << 16) | (self._resp_low & 0xFFFF),
            "resp_corrupt": self.resp_corrupt,
            "resp_denied": self.resp_denied,
            "accepted": self.accepted,
            "completed": self.completed,
            "resends": self.resends,
            "aborted": self.aborted,
        }


def reset_snapshot(inputs: Inputs | None = None) -> Outputs:
    """Outputs that must hold while reset is asserted."""
    return Outputs(1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1)


def replace_input(inputs: Inputs, **changes) -> Inputs:
    """Typed helper used by tests that step one field of a cycle."""
    return replace(inputs, **changes)


#: Explicit aliases keep call sites unambiguous when several DUT models coexist.
EntryInputs = Inputs
EntryOutputs = Outputs
