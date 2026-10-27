"""Only public input/output pins enter this semantic adapter."""
import asyncio
from contextlib import suppress

from toffee import Bundle, DriveStable, RisingEdge, on

from bpuverify.uras.model.semantic import Action, Operation, RasEvents
from bpuverify.uras.transaction.types import UrasResult


def decode_events(sample):
    def operation(prefix):
        return Operation(Action(getattr(sample.inputs, f'{prefix}_action').as_int()),
                         getattr(sample.inputs, f'{prefix}_start_pc').as_int(),
                         getattr(sample.inputs, f'{prefix}_position').as_int())

    return RasEvents(
        main_top=sample.inputs.full_ret_addr.as_int(),
        accept=operation('spec') if sample.inputs.s1_fire.as_int() else None,
        correct_pending=operation('s2') if sample.inputs.s2_valid.as_int() else None,
        correct_retiring=operation('s3') if sample.inputs.s3_valid.as_int() else None,
        advance=bool(sample.inputs.s2_fire.as_int()),
        retire=bool(sample.inputs.s3_fire.as_int()),
        redirect=bool(sample.inputs.has_redirect.as_int()),
        reset=bool(sample.reset.as_int()),
        enabled=bool(sample.inputs.enable.as_int()))


class UrasSemanticMonitor:
    def __init__(self, dut, ports):
        self.clock = ports.stimulus.clock
        self.inputs = Bundle(reset=dut.reset, inputs=ports.stimulus.bits).compile_sampler()
        self.outputs = ports.result.bits.compile_sampler()
        self.launched = RasEvents()
        self.execution = None
        self.subscriptions = []

    def start(self, execution, checker):
        self.execution = execution

        def inputs(event):
            launched = decode_events(self.inputs())
            # RiseWrite XData reads pending launch values, not the values
            # consumed by this DUT clock. Conversion stays in the adapter.
            checker.capture_input(event, self.launched)
            self.launched = launched

        def outputs(event):
            sample = self.outputs()
            checker.capture_output(event, UrasResult(sample.usable.as_int(), sample.target.as_int()))

        async def delivered(_):
            pass

        for trigger, capture in ((DriveStable(self.clock), inputs), (RisingEdge(self.clock), outputs)):
            spec = on(trigger, delivery='lossless', capacity=64, capture=capture)(delivered)
            self.subscriptions.append(execution.subscribe(spec.bind()))
        return self

    async def aclose(self):
        for subscription in self.subscriptions:
            self.execution.reactor.cancel_subscription(subscription)
            if subscription.task is not None:
                with suppress(asyncio.CancelledError):
                    await subscription.task
        self.subscriptions.clear()
