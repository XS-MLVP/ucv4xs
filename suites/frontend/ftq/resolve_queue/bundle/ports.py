"""ResolveQueue port binding over generated flat pins."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from toffee import Bundle

from suites.frontend.ftq.ports import Pins
from suites.frontend.ftq.harness import Dut
from suites.frontend.ftq.resolve_queue.transaction.cycle import ResolveInput


LANE_FIELDS = {
    "index_flag": "bits_ftqIdx_flag",
    "index": "bits_ftqIdx_value",
    "offset": "bits_ftqOffset",
    "pc": "bits_pc_addr",
    "target": "bits_target_addr",
    "taken": "bits_taken",
    "mispredict": "bits_mispredict",
    "branch_type": "bits_attribute_branchType",
    "ras_action": "bits_attribute_rasAction",
}


def lane_pins(dut: Dut, prefix: str, *, name: str) -> Pins:
    names = {logical: prefix + field for logical, field in LANE_FIELDS.items()}
    names["valid"] = prefix + "valid"
    return Pins(dut, names, name=name)


def train_output_pins(dut: Dut) -> Pins:
    names = {
        "valid": "io_bpuTrain_valid",
        "ready": "io_bpuTrain_ready",
        "index_flag": "io_bpuTrain_bits_ftqIdx_flag",
        "index": "io_bpuTrain_bits_ftqIdx_value",
        "start_pc": "io_bpuTrain_bits_startPc_addr",
    }
    for slot in range(8):
        base = f"io_bpuTrain_bits_branches_{slot}_"
        for field in ("valid", "bits_target_addr", "bits_taken",
                      "bits_cfiPosition", "bits_attribute_branchType",
                      "bits_attribute_rasAction", "bits_mispredict"):
            names[f"slot{slot}.{field}"] = base + field
    return Pins(dut, names, name="resolve_queue.train")


@dataclass(frozen=True)
class ResolveQueuePorts:
    backend: tuple[Pins, Pins, Pins]
    ifu: Pins
    train: Pins
    redirect: Pins
    enqueue: Pins
    inputs: dict
    bits: Bundle

    @classmethod
    def bind(cls, dut: Dut) -> "ResolveQueuePorts":
        backend = tuple(
            lane_pins(dut, f"io_backendResolve_{lane}_", name=f"resolve_queue.backend{lane}")
            for lane in range(3)
        )
        ifu = lane_pins(dut, "io_ifuResolve_", name="resolve_queue.ifu")
        train = train_output_pins(dut)
        redirect = Pins(dut, {
            "valid": "io_backendRedirect",
            "flag": "io_backendRedirectPtr_flag",
            "value": "io_backendRedirectPtr_value",
        }, name="resolve_queue.redirect")
        enqueue = Pins(dut, {
            "valid": "io_bpuEnqueue",
            "value": "io_bpuEnqueuePtr_value",
        }, name="resolve_queue.enqueue")
        widths = dict(index_flag=1, index=6, offset=5, pc=49, target=49,
                      taken=1, mispredict=1, branch_type=2, ras_action=2, valid=1)
        input_widths = {'reset': 1, 'io_bpuTrain_ready': 1}
        for group in (*backend, ifu):
            input_widths.update((pin, widths[logical]) for logical, pin in group.names.items())
        input_widths.update((pin, dict(valid=1, flag=1, value=6)[key]) for key, pin in redirect.names.items())
        input_widths.update((pin, dict(valid=1, value=6)[key]) for key, pin in enqueue.names.items())
        output_widths = {train.physical(key): bits for key, bits in dict(valid=1, index_flag=1, index=6, start_pc=49).items()}
        for slot in range(8):
            for key, bits in dict(valid=1, bits_target_addr=49, bits_taken=1, bits_cfiPosition=5,
                                  bits_attribute_branchType=2, bits_attribute_rasAction=2, bits_mispredict=1).items():
                output_widths[train.physical(f'slot{slot}.{key}')] = bits
        if set(dut.input_names()) != set(input_widths) or dut.output_names() != set(output_widths):
            raise ValueError('ResolveQueue full input/output schema mismatch')
        for output, fields in ((False, input_widths | {'clock': 1}), (True, output_widths)):
            for name, bits in fields.items():
                signal = getattr(dut.dut, name)
                if (max(1, int(signal.W())) != bits or bool(signal.IsOutIO()) != output
                        or (not output and not signal.IsInIO())):
                    raise ValueError(f'ResolveQueue {name}: expected {bits}-bit ' + ('output' if output else 'input'))
        inputs = {name: dut.input(name) for name in input_widths}
        return cls(backend, ifu, train, redirect, enqueue, inputs, Bundle(**inputs))

    def encode(self, frame):
        from suites.frontend.ftq.resolve_queue.driver.encoding import encode
        if type(frame) is not ResolveInput:
            raise ValueError('ResolveQueue driver requires a validated ResolveInput')
        values = dict.fromkeys(self.inputs, 0)
        values['reset'], values['io_bpuTrain_ready'] = int(frame.reset), int(frame.ready)
        for group, report in zip((*self.backend, self.ifu), frame.reports, strict=True):
            if report is not None:
                values.update((group.physical(key), value) for key, value in encode(report).items())
        if frame.redirect is not None:
            flag, pointer = frame.redirect
            values.update((self.redirect.physical(key), value) for key, value in dict(valid=1, flag=flag, value=pointer).items())
        if frame.enqueue is not None:
            values[self.enqueue.physical('valid')] = 1
            values[self.enqueue.physical('value')] = frame.enqueue
        return values
