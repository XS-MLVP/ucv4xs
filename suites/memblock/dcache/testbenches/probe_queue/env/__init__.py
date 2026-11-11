"""ProbeEnv environment for the probe_queue DUT.

Functional tests describe B-channel probe offers and MainPipe pressure with the
typed methods below.  The generated pin names, pre-edge ready sampling and the
LR/SC block encoding stay inside this environment.

Contracts encoded here:

* ``ProbeRequest`` rejects non-integer addresses, addresses outside the 48-bit
  physical range, unaligned lines, non-integer/unknown params and a non-bool
  ``need_data`` before any pin is touched.
* ``offer_probe`` keeps the previous offer until it is explicitly settled or
  cancelled; a second offer without cancelling fails.  The persistent LR/SC
  reservation and the ``update_resv`` pulse are *not* request payload and are
  not cleared by a new offer.
* ``reset`` clears the whole input surface (payload, reservation, pulse and
  MainPipe ready).
"""
from __future__ import annotations

from dataclasses import dataclass

from suites.memblock.dcache.testbenches.shared.env.execution import refresh
from suites.memblock.dcache.testbenches.shared.env.execution import set_reset
from suites.memblock.dcache.testbenches.shared.env.execution import step


PROBE_PARAMS = (0, 1, 2)  # TtoB, TtoN, TtoT
ADDRESS_BITS = 48
BLOCK_SIZE = 64


@dataclass(frozen=True)
class ProbeRequest:
    """One B-channel probe offer.  ``need_data`` is B.data[0]."""

    address: int
    param: int
    need_data: bool = False

    def __post_init__(self) -> None:
        if type(self.address) is not int:
            raise TypeError(f"probe address must be an int: {self.address!r}")
        if not 0 <= self.address < (1 << ADDRESS_BITS):
            raise ValueError(
                f"probe address must be {ADDRESS_BITS}-bit: {self.address:#x}")
        if self.address & (BLOCK_SIZE - 1):
            raise ValueError(
                f"probe address must be cache-line aligned: {self.address:#x}")
        if type(self.param) is not int or self.param not in PROBE_PARAMS:
            raise ValueError(f"probe param must be one of {PROBE_PARAMS}: {self.param!r}")
        if type(self.need_data) is not bool:
            raise TypeError(f"probe need_data must be bool: {self.need_data!r}")

    @property
    def data(self) -> int:
        return 1 if self.need_data else 0


@dataclass(frozen=True)
class ProbeAcceptance:
    """Result of a B-channel offer: pre-edge ready and the accepted edge."""

    request: ProbeRequest
    ready_before: int
    fired: bool
    cycles: int


@dataclass(frozen=True)
class PipeRequest:
    """Immutable snapshot of one MainPipe probe request."""

    param: int
    need_data: int
    addr: int
    id: int


class ProbeEnv:
    def __init__(self, dut, coverage=None):
        self.dut = dut
        self.coverage = coverage
        self.probe = {
            "ready": dut.io_mem_probe_ready,
            "valid": dut.io_mem_probe_valid,
            "param": dut.io_mem_probe_bits_param,
            "address": dut.io_mem_probe_bits_address,
            "data": dut.io_mem_probe_bits_data,
        }
        self.pipe = {
            "valid": dut.io_pipe_req_valid,
            "ready": dut.io_pipe_req_ready,
            "param": dut.io_pipe_req_bits_probe_param,
            "need_data": dut.io_pipe_req_bits_probe_need_data,
            "vaddr": dut.io_pipe_req_bits_vaddr,
            "addr": dut.io_pipe_req_bits_addr,
            "id": dut.io_pipe_req_bits_id,
        }
        self.lrsc = {
            "valid": dut.io_lrsc_locked_block_valid,
            "bits": dut.io_lrsc_locked_block_bits,
        }
        self.update_resv = dut.io_update_resv_set
        self._pending: ProbeRequest | None = None

    @staticmethod
    def value(signal) -> int:
        return int(signal.value)

    def reset(self) -> None:
        """Zero the whole input surface: payload, reservation and pulse."""
        for name in ("valid", "param", "address", "data"):
            self.probe[name].Set(0)
        self.lrsc["valid"].Set(0)
        self.lrsc["bits"].Set(0)
        self.update_resv.Set(0)
        self.pipe["ready"].Set(1)
        self._pending = None
        set_reset(self, 1)
        step(self, 3)
        set_reset(self, 0)
        step(self, 2)

    def _clear_probe_payload(self) -> None:
        """Clear only the request payload; reservation and ready persist."""
        self.probe["valid"].Set(0)

    # ------------------------------------------------------------- admission
    def can_accept_probe(self) -> bool:
        """Pre-edge view of the B-channel ready output."""
        refresh(self)
        return bool(self.value(self.probe["ready"]))

    def offer_probe(self, request: ProbeRequest) -> ProbeRequest:
        """Present one probe without advancing the clock.

        The offer stays asserted until ``settle_probe`` observes acceptance or
        ``cancel_probe_offer`` withdraws it.  Overwriting an unsettled offer is
        rejected instead of silently dropping the previous transaction.
        """
        if type(request) is not ProbeRequest:
            raise TypeError(f"offer_probe requires ProbeRequest: {request!r}")
        if self._pending is not None:
            raise AssertionError(
                "an earlier probe offer is still unsettled; settle or cancel it first")
        self._clear_probe_payload()
        self.probe["valid"].Set(1)
        self.probe["param"].Set(request.param)
        self.probe["address"].Set(request.address)
        self.probe["data"].Set(request.data)
        self._pending = request
        return request

    def cancel_probe_offer(self) -> None:
        """Explicitly withdraw the current offer without consuming it."""
        if self._pending is None:
            raise AssertionError("cancel_probe_offer called without an offer")
        self.probe["valid"].Set(0)
        self._pending = None

    def settle_probe(self, limit: int = 8) -> ProbeAcceptance:
        """Hold the pending offer until B ready, record the pre-edge ready."""
        if type(limit) is not int or limit < 1:
            raise ValueError(f"settle limit must be a positive int: {limit!r}")
        if self._pending is None:
            raise AssertionError("settle_probe called without an offered request")
        request = self._pending
        cycles = 0
        ready_before = 0
        for _ in range(limit):
            refresh(self)
            ready_before = self.value(self.probe["ready"])
            if ready_before:
                step(self)
                cycles += 1
                self.probe["valid"].Set(0)
                self._pending = None
                return ProbeAcceptance(request, ready_before, True, cycles)
            # Backpressure: keep valid and the whole payload untouched.
            step(self)
            cycles += 1
        self.probe["valid"].Set(0)
        self._pending = None
        return ProbeAcceptance(request, ready_before, False, cycles)

    def transmit_probe(self, request: ProbeRequest,
                       limit: int = 8) -> ProbeAcceptance:
        """Offer and settle one probe; readiness is sampled before each edge.

        The call budget is validated before the offer writes the B payload, so
        an invalid limit cannot leave an unsettled request behind.
        """
        if type(limit) is not int or limit < 1:
            raise ValueError(f"probe limit must be a positive int: {limit!r}")
        self.offer_probe(request)
        return self.settle_probe(limit)

    # ---------------------------------------------------------- backpressure
    def hold_mainpipe_ready(self, ready: bool = True) -> None:
        """Drive the MainPipe request-ready input (probe consumer backpressure)."""
        if type(ready) is not bool:
            raise TypeError(f"MainPipe ready must be bool: {ready!r}")
        self.pipe["ready"].Set(1 if ready else 0)

    def _peek_pipe(self) -> PipeRequest | None:
        if not self.value(self.pipe["valid"]):
            return None
        return PipeRequest(
            param=self.value(self.pipe["param"]),
            need_data=self.value(self.pipe["need_data"]),
            addr=self.value(self.pipe["addr"]),
            id=self.value(self.pipe["id"]),
        )

    def watch_pipe(self, limit: int = 6) -> PipeRequest | None:
        """Wait for the next MainPipe probe request snapshot (no Step once valid)."""
        if type(limit) is not int or limit < 1:
            raise ValueError(f"watch limit must be a positive int: {limit!r}")
        for _ in range(limit):
            snapshot = self._peek_pipe()
            if snapshot is not None:
                return snapshot
            step(self)
        return None

    def observe_pipe_window(self, cycles: int = 3) -> tuple[PipeRequest | None, ...]:
        """Sample the offered MainPipe request once per edge for ``cycles``.

        The samples are taken before each edge; the last sample is not followed
        by another clock.  With ``io_pipe_req_ready`` held low this records how
        long the same request stays offered without accepting it.
        """
        if type(cycles) is not int or cycles < 1:
            raise ValueError(f"window must be a positive int: {cycles!r}")
        samples = []
        for index in range(cycles):
            samples.append(self._peek_pipe())
            if index + 1 < cycles:
                step(self)
        return tuple(samples)

    # ------------------------------------------------------------------ LRSC
    def lock_lrsc_block(self, address: int) -> None:
        """Set the reservation block that prevents probes to the same line."""
        if type(address) is not int:
            raise TypeError(f"LR/SC block address must be an int: {address!r}")
        if not 0 <= address < (1 << ADDRESS_BITS):
            raise ValueError(
                f"LR/SC block address must be {ADDRESS_BITS}-bit: {address:#x}")
        self.lrsc["valid"].Set(1)
        self.lrsc["bits"].Set(address)

    def unlock_lrsc_block(self) -> None:
        self.lrsc["valid"].Set(0)

    def pulse_update_resv(self, cycles: int = 1) -> None:
        """Pulse ``io_update_resv_set`` for the documented next-cycle block."""
        if type(cycles) is not int or cycles < 1:
            raise ValueError(f"reservation pulse must be a positive int: {cycles!r}")
        self.update_resv.Set(1)
        try:
            step(self, cycles)
        finally:
            self.update_resv.Set(0)
