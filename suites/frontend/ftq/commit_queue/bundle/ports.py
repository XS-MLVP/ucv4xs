"""CommitQueue port binding over generated flat pins."""

from __future__ import annotations

from dataclasses import dataclass

from toffee import Bundle

from suites.frontend.ftq.ports import Pins
from suites.frontend.ftq.harness import Dut
from suites.frontend.ftq.commit_queue.transaction.types import Input, Snapshot, CallRet, WIDTH


def commit_lane(dut: Dut, lane: int) -> Pins:
    prefix = f"io_backendCommit_{lane}_"
    return Pins(dut, {
        "valid": prefix + "valid",
        "ras": prefix + "bits_rasAction",
        "ptr": prefix + "bits_ftqPtr_value",
    }, name=f"commit_queue.backend{lane}")


@dataclass(frozen=True)
class CommitQueuePorts:
    backend: tuple[Pins, ...]
    train: Pins
    inputs: dict
    bits: Bundle

    @classmethod
    def bind(cls, dut: Dut, width: int = 8) -> "CommitQueuePorts":
        if type(width) is not int or width != WIDTH:
            raise ValueError('DefaultConfig CommitQueue has exactly eight input lanes')
        backend = tuple(commit_lane(dut, lane) for lane in range(width))
        train = Pins(dut, {
            "valid": "io_bpuTrain_valid",
            "ras": "io_bpuTrain_bits_rasAction",
            "ptr": "io_bpuTrain_bits_ftqPtr_value",
        }, name="commit_queue.train")
        expected_inputs = {'reset': 1}
        for group in backend:
            expected_inputs.update((pin, dict(valid=1, ras=2, ptr=6)[logical])
                                   for logical, pin in group.names.items())
        expected_outputs = {pin: dict(valid=1, ras=2, ptr=6)[logical]
                            for logical, pin in train.names.items()}
        if set(dut.input_names()) != set(expected_inputs):
            raise ValueError('CommitQueue input schema/ownership mismatch: '
                             + repr(set(dut.input_names()) ^ set(expected_inputs)))
        if dut.output_names() != set(expected_outputs):
            raise ValueError('CommitQueue output schema mismatch')
        for output, fields in ((False, expected_inputs | {'clock': 1}), (True, expected_outputs)):
            for name, bits in fields.items():
                signal = getattr(dut.dut, name)
                if (max(1, int(signal.W())) != bits or bool(signal.IsOutIO()) != output
                        or (not output and not signal.IsInIO())):
                    raise ValueError(f'CommitQueue {name}: expected {bits}-bit '
                                     + ('output' if output else 'input'))
        inputs = {name: dut.input(name) for name in expected_inputs}
        return cls(backend, train, inputs, Bundle(**inputs))

    def encode(self, frame: Input):
        if type(frame) is not Input:
            raise ValueError('CommitQueue driver requires a validated Input')
        values = {'reset': int(frame.reset)}
        for group, row in zip(self.backend, frame.rows, strict=True):
            for name, value in dict(valid=int(row is not None),
                                    ras=0 if row is None else row.ras,
                                    ptr=0 if row is None else row.ptr).items():
                values[group.physical(name)] = value
        return values

    def capture(self, dut, head):
        rows = tuple(CallRet(group.u('ptr'), group.u('ras')) if group.b('valid') else None
                     for group in self.backend)
        return Snapshot(bool(dut.input('reset').U()), rows, head)
