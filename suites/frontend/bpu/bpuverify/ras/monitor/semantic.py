"""Public RAS event decoding only; expected call frames live in the model."""
import asyncio
from contextlib import suppress

from toffee import Bundle, DriveStable, RisingEdge, on

from bpuverify.ras.bundle.values import _plain
from bpuverify.ras.model.semantic import Events, Recovery, Retirement, instruction_return
from bpuverify.ras.monitor.observation import committed_state


def pointer_value(pointer):
    return pointer.flag.as_int() * 16 + pointer.value.as_int()


def decode_events(row):
    operation, address, recovery, retirement = None, None, None, None
    if row.speculative.valid.as_int():
        bits = row.speculative.bits
        operation = bits.action.as_int()
        if operation & 2:
            address = instruction_return(bits.start_pc.as_int(), bits.position.as_int())
    if row.redirect.valid.as_int():
        bits = row.redirect.bits
        action = bits.action.as_int()
        # Guard/sign extension is semantic address arithmetic, not an actual
        # output or RTL timingTop observation used as a golden address.
        pc = bits.cfi_pc.as_int() * 2
        if pc >= 1 << 49:
            pc -= 1 << 50
        recovery = Recovery(bits.meta.ssp.as_int(), pointer_value(bits.meta.tosw),
            bits.meta.sctr.as_int(), action, (pc + 2) % (1 << 51) if action & 2 else None)
    if row.commit.valid.as_int():
        bits = row.commit.bits
        retirement = Retirement(bits.meta.ssp.as_int(), pointer_value(bits.meta.tosw), bits.action.as_int())
    return Events(operation, address, recovery, retirement,
                  bool(row.enabled.as_int()), bool(row.reset.as_int()))


class RasSemanticMonitor:
    def __init__(self, dut, ports):
        self.clock = dut.clock
        self.inputs = Bundle(reset=dut.reset, enabled=ports.speculative.bits.enable,
            speculative=Bundle(valid=ports.speculative.valid, bits=ports.speculative.bits),
            redirect=Bundle(valid=ports.redirect.valid, bits=ports.redirect.bits),
            commit=Bundle(valid=ports.commit.valid, bits=ports.commit.bits)).compile_sampler()
        self.outputs = Bundle(public=ports.state.bits, retained=committed_state(dut)).compile_sampler()
        self.launched = Events(enabled=False)
        self.subscriptions = []
        self.execution = None

    def start(self, execution, checker):
        self.execution = execution

        def inputs(event):
            launched = decode_events(self.inputs())
            checker.capture_input(event, self.launched)
            self.launched = launched

        def outputs(event):
            row = self.outputs()
            checker.capture_output(event, _plain(row.public), retained=_plain(row.retained))

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
