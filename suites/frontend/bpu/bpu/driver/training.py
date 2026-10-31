"""suites.frontend.bpu.bpu.driver.training components."""

from __future__ import annotations
from contextlib import contextmanager
from typing import Any
from typing import Callable
from toffee import AsyncDriver
from toffee import ReadyValid
from toffee import Role
from toffee import drive_ready_valid
from toffee.data import iter_data_leaves


class BpuTrainingDriver(AsyncDriver[Any, Any]):
    """Queue integrated BPU feedback; each handle resolves at acceptance."""

    def __init__(
        self,
        interface: ReadyValid,
        *,
        encoder: Callable[[Any, Any], None],
    ) -> None:
        if interface.role is not Role.PRODUCER:
            raise ValueError("BPU training requires a producer port")
        self.interface = interface
        self.encoder = encoder
        self._admission = None
        self._admission_handles = None
        self._payload_leaves = tuple(
            signal for _, signal in iter_data_leaves(interface.bits, interface.name)
        )
        # One physical ready/valid port accepts at most one beat per cycle.
        # Queued submissions can nevertheless be accepted on adjacent cycles
        # without waiting for the earlier predictor update to retire.
        super().__init__(
            (interface.valid, *self._payload_leaves), name=interface.name
        )

    @contextmanager
    def admit_when(self, predicate: Callable[[Any], bool]):
        """Gate launches in the driver's drive slot, without wrapping requests.

        Enter only on an idle port; finish or cancel all submissions before
        leaving. Predictor-specific policy remains in the environment.
        """
        if not callable(predicate):
            raise TypeError('admission predicate must be callable')
        if self._admission is not None or self.has_outstanding:
            raise RuntimeError('admission requires an idle driver and an exclusive scope')
        self._admission = predicate
        handles = self._admission_handles = []
        try:
            yield self
            if any(not handle.done() for handle in handles):
                raise RuntimeError('admission scope has unfinished submissions')
        finally:
            # A body failure or an early normal exit must not let queued work
            # launch later without its policy. Accepted response ownership is
            # not revoked; cancellation only applies to unaccepted input.
            for handle in handles:
                if not handle.done() and handle.accepted_event is None:
                    handle.cancel()
            self._admission = None
            self._admission_handles = None

    def _track_admission(self, handle):
        if self._admission_handles is not None:
            self._admission_handles.append(handle)
        return handle

    def send(self, transaction: Any):
        return self._track_admission(super().send(transaction))

    def submit(self, transaction: Any):
        return self._track_admission(super().submit(transaction))

    async def _drive_one(self, transaction: Any):
        admission = self._admission
        return await drive_ready_valid(
            self.interface.clock,
            self.interface.valid,
            self.interface.ready,
            lambda: self.encoder(self.interface.bits, transaction),
            bits=self.interface.bits,
            admit=None if admission is None else lambda: admission(transaction),
        )
