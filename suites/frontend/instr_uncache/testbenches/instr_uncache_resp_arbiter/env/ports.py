"""Native binding for the one-input InstrUncache response arbiter."""

from __future__ import annotations

from toffee import Bundle

from suites.frontend.instr_uncache.testbenches.instr_uncache_resp_arbiter.model import Inputs
from suites.frontend.instr_uncache.testbenches.instr_uncache_resp_arbiter.model import Outputs


INPUTS = {
    "in_valid": ("io_in_0_valid", 1),
    "in_data": ("io_in_0_bits_data", 32),
    "in_corrupt": ("io_in_0_bits_corrupt", 1),
    "in_denied": ("io_in_0_bits_denied", 1),
    "in_need_resend": ("io_in_0_bits_needResend", 1),
}

OUTPUTS = {
    "out_valid": ("io_out_valid", 1),
    "out_data": ("io_out_bits_data", 32),
    "out_corrupt": ("io_out_bits_corrupt", 1),
    "out_denied": ("io_out_bits_denied", 1),
    "out_need_resend": ("io_out_bits_needResend", 1),
}

INTERFACE = {
    "top": "Arbiter1_InstrUncacheResp",
    "inputs": {name: (width, port) for name, (port, width) in INPUTS.items()},
    "outputs": {name: (width, port) for name, (port, width) in OUTPUTS.items()},
    "absent": {},
}


class RespArbiterPorts:
    def __init__(self, dut):
        def bind(name, width, *, output=False):
            signal = getattr(dut, name)
            if max(1, int(signal.mWidth)) != width:
                raise ValueError(f"{name}: expected native width {width}, got {signal.mWidth}")
            if ((output and not signal.IsOutIO())
                    or (not output and (not signal.IsInIO() or signal.IsOutIO()))):
                raise ValueError(f"{name}: wrong native port direction")
            return signal

        self.bits = Bundle(**{field: bind(name, width)
                              for field, (name, width) in INPUTS.items()})
        self._outputs = Bundle(**{field: bind(name, width, output=True)
                                  for field, (name, width) in OUTPUTS.items()})
        actual_inputs = {
            name for name, signal in vars(dut).items()
            if name != "dut" and callable(getattr(signal, "IsInIO", None))
            and signal.IsInIO() and not signal.IsOutIO()
        }
        expected_inputs = {name for name, _ in INPUTS.values()}
        if actual_inputs != expected_inputs:
            raise ValueError(f"Arbiter1_InstrUncacheResp input ownership mismatch: "
                             f"{actual_inputs ^ expected_inputs}")
        actual_outputs = {
            name for name, signal in vars(dut).items()
            if name != "dut" and callable(getattr(signal, "IsOutIO", None))
            and signal.IsOutIO()
        }
        expected_outputs = {name for name, _ in OUTPUTS.values()}
        if actual_outputs != expected_outputs:
            raise ValueError(f"Arbiter1_InstrUncacheResp output ownership mismatch: "
                             f"{actual_outputs ^ expected_outputs}")

    @staticmethod
    def encode(inputs: Inputs) -> dict[str, int]:
        if not isinstance(inputs, Inputs):
            raise TypeError("resp arbiter driver requires semantic Inputs")
        values = {
            "in_valid": inputs.in_valid,
            "in_data": inputs.in_data,
            "in_corrupt": inputs.in_corrupt,
            "in_denied": inputs.in_denied,
            "in_need_resend": inputs.in_need_resend,
        }
        if values.keys() != set(INPUTS):
            raise ValueError("resp arbiter encoder must drive every input once")
        return values

    def capture(self, event) -> Outputs:
        values = {field: int(value) for field, value in self._outputs.sample().items()}
        return Outputs(**values)
