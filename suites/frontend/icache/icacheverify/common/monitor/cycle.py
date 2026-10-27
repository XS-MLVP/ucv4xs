from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any
from typing import Generic
from typing import TypeVar

from toffee import Monitor
from toffee import RisingEdge
from toffee import SamplingMonitor
from toffee import Transfer
from toffee import on
from toffee.data import compile_sampler

from icacheverify.common.bundle.bindings import PortBinding


T = TypeVar("T")


class CycleMonitor(Monitor[T], Generic[T]):
    """Passive transaction sampler for non-ready/valid predictor outputs."""

    def __init__(
        self,
        binding: PortBinding,
        *,
        decoder: Callable[[Any], T] | None = None,
        capacity: int = 64,
    ) -> None:
        if capacity <= 0:
            raise ValueError("monitor capacity must be positive")
        self.binding = binding
        self.decoder = decoder
        self.capacity = capacity
        self._monitor: SamplingMonitor[T] | None = None
        self._execution = None
        self._subscription = None
        self._sampler = None
        self._sampled_bits = None

    def _capture(self, event):
        # TAGE's bounded state-observation scope changes the binding. Cache a
        # compiled sampler only for that exact data node, never across rebinds.
        if self._sampled_bits is not self.binding.bits:
            self._sampler = compile_sampler(self.binding.bits)
            self._sampled_bits = self.binding.bits
        sample = self._sampler()
        return sample if self.decoder is None else self.decoder(sample)

    def start(
        self,
        execution,
        *,
        observer: Callable[[Transfer[T]], None] | None = None,
    ):
        if self._subscription is not None or self._monitor is not None:
            raise RuntimeError("monitor is already started")
        if execution.reactor is None:
            raise RuntimeError("monitor requires an active Execution")
        if observer is None:
            self._monitor = SamplingMonitor(
                RisingEdge(self.binding.clock), capture=self._capture,
                capacity=self.capacity,
            ).start(execution)
        else:
            # Callback-only consumers use the framework subscription directly;
            # they do not allocate a second queue or background delivery task.
            async def deliver(observation):
                observer(observation)

            spec = on(
                RisingEdge(self.binding.clock), delivery="lossless",
                capacity=self.capacity, capture=self.sample_at,
            )(deliver)
            self._subscription = execution.subscribe(spec.bind())
        self._execution = execution
        return self

    async def recv(self):
        if self._monitor is None:
            raise RuntimeError("monitor recv requires start without an observer")
        return await self._monitor.recv()

    def sample_at(self, event) -> Transfer[T]:
        """Create an immutable snapshot at an event awaited by a driver."""

        return Transfer(event=event, value=self._capture(event))

    async def aclose(self) -> None:
        monitor, self._monitor = self._monitor, None
        if monitor is not None:
            await monitor.aclose()
        subscription = self._subscription
        execution = self._execution
        self._subscription = None
        self._execution = None
        self._sampler = None
        self._sampled_bits = None
        if subscription is None or execution is None or execution.reactor is None:
            return
        execution.reactor.cancel_subscription(subscription)
        if subscription.task is not None:
            try:
                await subscription.task
            except asyncio.CancelledError:
                pass
